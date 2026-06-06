"""SqlAlchemy implementation of :class:`IUserRepository`.

The repository is responsible for loading the full aggregate (user row + roles
+ direct permission overrides) into a domain :class:`User`, and for diffing
mutations on commit.

This is a synchronous-driver repository wrapped in ``async def`` methods.
Sync SQLAlchemy is what the rest of the project uses today; revisit when we
migrate to ``AsyncSession`` (likely phase 6+).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.application.ports import IUserRepository
from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.role import Role, RoleId
from app.modules.identity.domain.user import User, UserId
from app.modules.identity.domain.value_objects import Email, Username
from app.modules.identity.infrastructure.mappers import (
    status_to_db,
    user_from_orm,
)
from app.modules.identity.infrastructure.orm import (
    PermissionOrm,
    RoleOrm,
    RolePermissionOrm,
    UserOrm,
    UserPermissionOrm,
    UserRoleOrm,
)


class SqlAlchemyUserRepository(IUserRepository):
    """Loads/saves :class:`User` aggregates via SQLAlchemy ORM."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- read --------------------------------------------------------------

    async def get(self, id_: UserId) -> User | None:
        row = self._session.scalar(
            select(UserOrm).where(UserOrm.public_id == id_.value)
        )
        return await self._hydrate(row) if row else None

    async def get_by_username(self, username: Username) -> User | None:
        row = self._session.scalar(
            select(UserOrm).where(UserOrm.username == username.value)
        )
        return await self._hydrate(row) if row else None

    async def get_by_email(self, email: Email) -> User | None:
        row = self._session.scalar(
            select(UserOrm).where(UserOrm.email == email.value)
        )
        return await self._hydrate(row) if row else None

    async def get_by_username_or_email(self, value: str) -> User | None:
        normalised = value.strip()
        row = self._session.scalar(
            select(UserOrm).where(
                (UserOrm.username == normalised)
                | (UserOrm.email == normalised.lower())
            )
        )
        return await self._hydrate(row) if row else None

    async def exists(self, id_: UserId) -> bool:
        return (
            self._session.scalar(
                select(UserOrm.id).where(UserOrm.public_id == id_.value)
            )
            is not None
        )

    # --- write -------------------------------------------------------------

    async def add(self, entity: User) -> None:
        """Insert a brand-new user, then sync roles/permissions."""
        row = self._session.scalar(
            select(UserOrm).where(UserOrm.public_id == entity.id.value)
        )
        if row is None:
            row = UserOrm(
                public_id=entity.id.value,
                username=entity.username.value,
                email=entity.email.value,
                # Phase-1 column
                password_hash=entity.password_hash,
                status=status_to_db(entity.status),
                avatar_file_id=entity.avatar_file_id,
                # Legacy mirror columns (still required NOT NULL by old schema).
                hashed_password=entity.password_hash,
                is_active=entity.is_active,
                role=_legacy_role(entity),
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            self._session.add(row)
            # Need an autoflush to obtain the integer id for the M:N tables.
            self._session.flush()
        else:
            self._copy_state(entity, row)
            self._session.flush()

        self._sync_roles(row.id, entity.roles)
        self._sync_overrides(row.id, entity)

    async def remove(self, entity: User) -> None:
        self._session.execute(
            UserOrm.__table__.delete().where(UserOrm.public_id == entity.id.value)
        )

    # --- helpers -----------------------------------------------------------

    async def _hydrate(self, row: UserOrm) -> User:
        if row.public_id is None:
            # Legacy row missing UUID — back-fill on read for forward-compat.
            row.public_id = uuid4()
            self._session.flush()

        roles = self._load_user_roles(row.id)
        granted, denied = self._load_user_overrides(row.id)
        return user_from_orm(
            row,
            roles=roles,
            granted_codes=granted,
            denied_codes=denied,
        )

    def _load_user_roles(self, user_id: int) -> list[Role]:
        role_rows = self._session.execute(
            select(RoleOrm)
            .join(UserRoleOrm, UserRoleOrm.role_id == RoleOrm.id)
            .where(UserRoleOrm.user_id == user_id)
        ).scalars().all()
        return [self._role_with_permissions(r) for r in role_rows]

    def _role_with_permissions(self, row: RoleOrm) -> Role:
        codes = self._session.scalars(
            select(PermissionOrm.code)
            .join(
                RolePermissionOrm,
                RolePermissionOrm.permission_id == PermissionOrm.id,
            )
            .where(RolePermissionOrm.role_id == row.id)
        ).all()
        return Role(
            id=RoleId(UUID(int=int(row.id))),
            name=row.name,
            description=row.description,
            permissions={Permission(c) for c in codes},
        )

    def _load_user_overrides(self, user_id: int) -> tuple[list[str], list[str]]:
        rows = self._session.execute(
            select(PermissionOrm.code, UserPermissionOrm.granted)
            .join(
                UserPermissionOrm,
                UserPermissionOrm.permission_id == PermissionOrm.id,
            )
            .where(UserPermissionOrm.user_id == user_id)
        ).all()
        granted = [code for code, granted in rows if granted]
        denied = [code for code, granted in rows if not granted]
        return granted, denied

    def _copy_state(self, entity: User, row: UserOrm) -> None:
        row.username = entity.username.value
        row.email = entity.email.value
        row.password_hash = entity.password_hash
        row.status = status_to_db(entity.status)
        row.avatar_file_id = entity.avatar_file_id
        # Legacy mirrors
        row.hashed_password = entity.password_hash
        row.is_active = entity.is_active
        row.role = _legacy_role(entity)

    def _sync_roles(self, user_id_int: int, roles) -> None:
        existing = {
            r.role_id
            for r in self._session.execute(
                select(UserRoleOrm).where(UserRoleOrm.user_id == user_id_int)
            )
            .scalars()
            .all()
        }
        desired = {int(r.id.value) for r in roles}
        for role_db_id in desired - existing:
            self._session.add(
                UserRoleOrm(user_id=user_id_int, role_id=role_db_id)
            )
        for role_db_id in existing - desired:
            self._session.execute(
                UserRoleOrm.__table__.delete().where(
                    (UserRoleOrm.user_id == user_id_int)
                    & (UserRoleOrm.role_id == role_db_id)
                )
            )

    def _sync_overrides(self, user_id_int: int, user: User) -> None:
        granted = {p.code for p in user.granted_permissions}
        denied = {p.code for p in user.denied_permissions}

        codes_to_ids = dict(
            self._session.execute(
                select(PermissionOrm.code, PermissionOrm.id).where(
                    PermissionOrm.code.in_(granted | denied)
                )
            ).all()
        )

        # Drop existing overrides and re-insert; small set, simple algorithm.
        self._session.execute(
            UserPermissionOrm.__table__.delete().where(
                UserPermissionOrm.user_id == user_id_int
            )
        )
        for code in granted | denied:
            pid = codes_to_ids.get(code)
            if pid is None:  # unknown permission code — skip silently
                continue
            self._session.add(
                UserPermissionOrm(
                    user_id=user_id_int,
                    permission_id=pid,
                    granted=(code in granted),
                )
            )


def _legacy_role(entity: User):
    """Map domain roles to the legacy ``users.role`` enum.

    Picks the highest role the user has (admin > moderator > user).
    """
    from app.models.user import UserRole as LegacyUserRole

    names = {r.name for r in entity.roles}
    if "admin" in names:
        return LegacyUserRole.ADMIN
    if "moderator" in names:
        return LegacyUserRole.MODERATOR
    return LegacyUserRole.USER
