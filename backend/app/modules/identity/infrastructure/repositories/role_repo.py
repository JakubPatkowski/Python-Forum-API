"""Repository for the read-side of roles (used by use cases at write time too)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.application.ports import IRoleRepository
from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.role import Role, RoleId
from app.modules.identity.infrastructure.orm import (
    PermissionOrm,
    RoleOrm,
    RolePermissionOrm,
)


class SqlAlchemyRoleRepository(IRoleRepository):
    """Read roles + their associated permission codes."""

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_by_name(self, name: str) -> Role | None:
        row = self._session.scalar(select(RoleOrm).where(RoleOrm.name == name))
        if row is None:
            return None
        return self._hydrate(row)

    async def list_all(self) -> list[Role]:
        rows = self._session.scalars(select(RoleOrm)).all()
        return [self._hydrate(r) for r in rows]

    # --- internal -----------------------------------------------------------

    def _hydrate(self, row: RoleOrm) -> Role:
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
