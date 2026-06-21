"""Use-case tests for the identity module using in-memory fakes.

These run the application layer end-to-end with the *real* Argon2 hasher and
PyJWT token service (so signing, verification and refresh-rotation reuse
detection are genuinely exercised), but with in-memory fake repositories
instead of Postgres. Fast and deterministic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.identity.application.commands import (
    AssignRoleCommand,
    DenyPermissionCommand,
    GrantPermissionCommand,
    LoginCommand,
    RefreshSessionCommand,
    RegisterUserCommand,
    RevokeRoleCommand,
    SetUserStatusCommand,
)
from app.modules.identity.application.errors import (
    EmailAlreadyTaken,
    InvalidCredentials,
    InvalidRefreshToken,
    RefreshTokenReuseDetected,
    RoleNotFound,
    UsernameAlreadyTaken,
    UserNotFound,
)
from app.modules.identity.application.errors import (
    UserBlocked as UserBlockedError,
)
from app.modules.identity.application.use_cases import (
    AssignRoleUseCase,
    DenyPermissionUseCase,
    GrantPermissionUseCase,
    LoginUseCase,
    RefreshSessionUseCase,
    RegisterUserUseCase,
    RevokeRoleUseCase,
    SetUserStatusUseCase,
)
from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.refresh_token import (
    RefreshToken,
    RefreshTokenId,
    TokenStatus,
)
from app.modules.identity.domain.role import Role, RoleId
from app.modules.identity.domain.user import User, UserId, UserStatus
from app.modules.identity.domain.value_objects import Email, Username
from app.modules.identity.infrastructure.auth import Argon2Hasher, PyJWTTokenService
from app.shared.application.result import Err, Ok
from app.shared.domain.errors import ValidationError

# --------------------------------------------------------------------------- #
# Fakes                                                                       #
# --------------------------------------------------------------------------- #


class FakeBus:
    def __init__(self) -> None:
        self.published: list[object] = []

    async def publish(self, event: object) -> None:
        self.published.append(event)

    def types(self) -> list[str]:
        return [type(e).__name__ for e in self.published]


class FakeUserRepo:
    def __init__(self) -> None:
        self.store: dict[UUID, User] = {}

    async def get(self, id_: UserId) -> User | None:
        return self.store.get(id_.value)

    async def add(self, user: User) -> None:
        self.store[user.id.value] = user

    async def save(self, user: User) -> None:
        self.store[user.id.value] = user

    async def get_by_username(self, username: Username) -> User | None:
        return next((u for u in self.store.values() if u.username == username), None)

    async def get_by_email(self, email: Email) -> User | None:
        return next((u for u in self.store.values() if u.email == email), None)

    async def get_by_username_or_email(self, value: str) -> User | None:
        return next(
            (
                u
                for u in self.store.values()
                if str(u.username) == value or str(u.email) == value.lower()
            ),
            None,
        )


class FakeRoleRepo:
    def __init__(self) -> None:
        self.store: dict[str, Role] = {}

    async def get_by_name(self, name: str) -> Role | None:
        return self.store.get(name)

    async def list_all(self) -> list[Role]:
        return list(self.store.values())


class FakeRefreshTokenRepo:
    def __init__(self) -> None:
        self.store: dict[UUID, RefreshToken] = {}

    async def get(self, id_: RefreshTokenId) -> RefreshToken | None:
        return self.store.get(id_.value)

    async def add(self, token: RefreshToken) -> None:
        self.store[token.id.value] = token

    async def save(self, token: RefreshToken) -> None:
        self.store[token.id.value] = token

    async def get_by_public_id(self, public_id: UUID) -> RefreshToken | None:
        return self.store.get(public_id)

    async def revoke_chain_from(self, token_id: RefreshTokenId) -> None:
        tok = self.store.get(token_id.value)
        if tok is not None:
            tok.revoke()

    async def revoke_all_for_user(self, user_id: UserId) -> None:
        for tok in self.store.values():
            if tok.user_id == user_id:
                tok.revoke()


class FakeIdentityUoW:
    def __init__(self) -> None:
        self.users = FakeUserRepo()
        self.roles = FakeRoleRepo()
        self.refresh_tokens = FakeRefreshTokenRepo()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> FakeIdentityUoW:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


@pytest.fixture
def hasher() -> Argon2Hasher:
    return Argon2Hasher()


@pytest.fixture
def tokens() -> PyJWTTokenService:
    return PyJWTTokenService()


@pytest.fixture
def bus() -> FakeBus:
    return FakeBus()


def _user_role() -> Role:
    return Role(
        id=RoleId.new(),
        name="user",
        permissions={Permission("post.create"), Permission("comment.create")},
    )


def _mod_role() -> Role:
    return Role(
        id=RoleId.new(),
        name="moderator",
        permissions={Permission("post.delete.any")},
    )


@pytest.fixture
def uow() -> FakeIdentityUoW:
    u = FakeIdentityUoW()
    u.roles.store["user"] = _user_role()
    u.roles.store["moderator"] = _mod_role()
    return u


def _seed_user(
    uow: FakeIdentityUoW,
    hasher: Argon2Hasher,
    *,
    username: str = "angler",
    email: str = "angler@example.com",
    password: str = "Sup3rStrongP@ss",
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    user = User.register(
        username=Username(username),
        email=Email(email),
        password_hash=hasher.hash(password),
        default_role=uow.roles.store["user"],
    )
    user.pull_events()
    if status != UserStatus.ACTIVE:
        user.block()  # exercise the real transition instead of poking private state
        user.pull_events()
    uow.users.store[user.id.value] = user
    return user


# --------------------------------------------------------------------------- #
# Register                                                                    #
# --------------------------------------------------------------------------- #


class TestRegister:
    async def test_success(self, uow: FakeIdentityUoW, hasher: Argon2Hasher, bus: FakeBus) -> None:
        res = await RegisterUserUseCase(uow, hasher, bus).execute(
            RegisterUserCommand(
                username="newangler", email="new@example.com", password="Sup3rStrongP@ss"
            )
        )
        assert isinstance(res, Ok)
        assert res.value.username == "newangler"
        assert "user" in res.value.roles
        assert "UserRegistered" in bus.types()

    async def test_duplicate_username(
        self, uow: FakeIdentityUoW, hasher: Argon2Hasher, bus: FakeBus
    ) -> None:
        _seed_user(uow, hasher, username="taken", email="a@example.com")
        res = await RegisterUserUseCase(uow, hasher, bus).execute(
            RegisterUserCommand(username="taken", email="b@example.com", password="Sup3rStrongP@ss")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, UsernameAlreadyTaken)

    async def test_duplicate_email(
        self, uow: FakeIdentityUoW, hasher: Argon2Hasher, bus: FakeBus
    ) -> None:
        _seed_user(uow, hasher, username="one", email="dup@example.com")
        res = await RegisterUserUseCase(uow, hasher, bus).execute(
            RegisterUserCommand(username="two", email="dup@example.com", password="Sup3rStrongP@ss")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, EmailAlreadyTaken)

    async def test_missing_default_role(self, hasher: Argon2Hasher, bus: FakeBus) -> None:
        empty = FakeIdentityUoW()  # no roles seeded
        res = await RegisterUserUseCase(empty, hasher, bus).execute(
            RegisterUserCommand(
                username="validname", email="x@example.com", password="Sup3rStrongP@ss"
            )
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, RoleNotFound)

    async def test_weak_password_rejected(
        self, uow: FakeIdentityUoW, hasher: Argon2Hasher, bus: FakeBus
    ) -> None:
        with pytest.raises(ValidationError):
            await RegisterUserUseCase(uow, hasher, bus).execute(
                RegisterUserCommand(username="weak", email="weak@example.com", password="123")
            )


# --------------------------------------------------------------------------- #
# Login                                                                       #
# --------------------------------------------------------------------------- #


class TestLogin:
    async def test_success_returns_token_pair(
        self,
        uow: FakeIdentityUoW,
        hasher: Argon2Hasher,
        tokens: PyJWTTokenService,
        bus: FakeBus,
    ) -> None:
        _seed_user(uow, hasher, username="angler", password="Sup3rStrongP@ss")
        res = await LoginUseCase(uow, hasher, tokens, bus).execute(
            LoginCommand(username_or_email="angler", password="Sup3rStrongP@ss")
        )
        assert isinstance(res, Ok)
        assert res.value.access_token
        assert res.value.refresh_token
        # the refresh token record was persisted
        assert len(uow.refresh_tokens.store) == 1

    async def test_wrong_password(
        self,
        uow: FakeIdentityUoW,
        hasher: Argon2Hasher,
        tokens: PyJWTTokenService,
        bus: FakeBus,
    ) -> None:
        _seed_user(uow, hasher, username="angler", password="Sup3rStrongP@ss")
        res = await LoginUseCase(uow, hasher, tokens, bus).execute(
            LoginCommand(username_or_email="angler", password="wrongpass")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, InvalidCredentials)

    async def test_unknown_user(
        self,
        uow: FakeIdentityUoW,
        hasher: Argon2Hasher,
        tokens: PyJWTTokenService,
        bus: FakeBus,
    ) -> None:
        res = await LoginUseCase(uow, hasher, tokens, bus).execute(
            LoginCommand(username_or_email="ghost", password="whatever")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, InvalidCredentials)

    async def test_blocked_user(
        self,
        uow: FakeIdentityUoW,
        hasher: Argon2Hasher,
        tokens: PyJWTTokenService,
        bus: FakeBus,
    ) -> None:
        _seed_user(
            uow, hasher, username="blocked", password="Sup3rStrongP@ss", status=UserStatus.BLOCKED
        )
        res = await LoginUseCase(uow, hasher, tokens, bus).execute(
            LoginCommand(username_or_email="blocked", password="Sup3rStrongP@ss")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, UserBlockedError)


# --------------------------------------------------------------------------- #
# Refresh-token rotation + reuse detection                                    #
# --------------------------------------------------------------------------- #


class TestRefresh:
    async def _login(
        self,
        uow: FakeIdentityUoW,
        hasher: Argon2Hasher,
        tokens: PyJWTTokenService,
        bus: FakeBus,
    ) -> str:
        _seed_user(uow, hasher, username="angler", password="Sup3rStrongP@ss")
        res = await LoginUseCase(uow, hasher, tokens, bus).execute(
            LoginCommand(username_or_email="angler", password="Sup3rStrongP@ss")
        )
        assert isinstance(res, Ok)
        return res.value.refresh_token

    async def test_rotation_issues_new_pair(
        self,
        uow: FakeIdentityUoW,
        hasher: Argon2Hasher,
        tokens: PyJWTTokenService,
        bus: FakeBus,
    ) -> None:
        r1 = await self._login(uow, hasher, tokens, bus)
        res = await RefreshSessionUseCase(uow, tokens, bus).execute(
            RefreshSessionCommand(refresh_token=r1)
        )
        assert isinstance(res, Ok)
        assert res.value.refresh_token != r1
        assert "RefreshTokenRotated" in bus.types()

    async def test_garbage_token_rejected(
        self, uow: FakeIdentityUoW, tokens: PyJWTTokenService, bus: FakeBus
    ) -> None:
        res = await RefreshSessionUseCase(uow, tokens, bus).execute(
            RefreshSessionCommand(refresh_token="not.a.jwt")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, InvalidRefreshToken)

    async def test_reuse_detection(
        self,
        uow: FakeIdentityUoW,
        hasher: Argon2Hasher,
        tokens: PyJWTTokenService,
        bus: FakeBus,
    ) -> None:
        r1 = await self._login(uow, hasher, tokens, bus)
        first = await RefreshSessionUseCase(uow, tokens, bus).execute(
            RefreshSessionCommand(refresh_token=r1)
        )
        assert isinstance(first, Ok)
        # Re-presenting the already-rotated R1 is treated as theft.
        replay = await RefreshSessionUseCase(uow, tokens, bus).execute(
            RefreshSessionCommand(refresh_token=r1)
        )
        assert isinstance(replay, Err)
        assert isinstance(replay.error, RefreshTokenReuseDetected)
        assert "RefreshTokenReuseDetected" in bus.types()
        # the whole chain should now be revoked
        assert all(t.status == TokenStatus.REVOKED for t in uow.refresh_tokens.store.values())


# --------------------------------------------------------------------------- #
# Admin: roles, permissions, status                                           #
# --------------------------------------------------------------------------- #


class TestAdmin:
    async def test_assign_and_revoke_role(
        self, uow: FakeIdentityUoW, hasher: Argon2Hasher, bus: FakeBus
    ) -> None:
        user = _seed_user(uow, hasher)
        res = await AssignRoleUseCase(uow, bus).execute(
            AssignRoleCommand(target_user_public_id=user.id.value, role_name="moderator")
        )
        assert isinstance(res, Ok)
        assert any(r.name == "moderator" for r in uow.users.store[user.id.value].roles)

        revoke = await RevokeRoleUseCase(uow, bus).execute(
            RevokeRoleCommand(target_user_public_id=user.id.value, role_name="moderator")
        )
        assert isinstance(revoke, Ok)
        assert not any(r.name == "moderator" for r in uow.users.store[user.id.value].roles)

    async def test_assign_role_unknown_user(self, uow: FakeIdentityUoW, bus: FakeBus) -> None:
        res = await AssignRoleUseCase(uow, bus).execute(
            AssignRoleCommand(target_user_public_id=uuid4(), role_name="moderator")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, UserNotFound)

    async def test_assign_unknown_role(
        self, uow: FakeIdentityUoW, hasher: Argon2Hasher, bus: FakeBus
    ) -> None:
        user = _seed_user(uow, hasher)
        res = await AssignRoleUseCase(uow, bus).execute(
            AssignRoleCommand(target_user_public_id=user.id.value, role_name="wizard")
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, RoleNotFound)

    async def test_grant_then_deny_permission(
        self, uow: FakeIdentityUoW, hasher: Argon2Hasher, bus: FakeBus
    ) -> None:
        user = _seed_user(uow, hasher)
        grant = await GrantPermissionUseCase(uow, bus).execute(
            GrantPermissionCommand(
                target_user_public_id=user.id.value, permission_code="user.manage"
            )
        )
        assert isinstance(grant, Ok)
        assert uow.users.store[user.id.value].has_permission("user.manage")

        deny = await DenyPermissionUseCase(uow, bus).execute(
            DenyPermissionCommand(
                target_user_public_id=user.id.value, permission_code="post.create"
            )
        )
        assert isinstance(deny, Ok)
        # post.create came from the 'user' role but is now explicitly denied
        assert not uow.users.store[user.id.value].has_permission("post.create")

    async def test_block_revokes_sessions(
        self,
        uow: FakeIdentityUoW,
        hasher: Argon2Hasher,
        bus: FakeBus,
    ) -> None:
        user = _seed_user(uow, hasher)
        # give the user an active refresh token
        token = RefreshToken(
            id=RefreshTokenId.new(),
            user_id=user.id,
            token_hash="hash",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
        uow.refresh_tokens.store[token.id.value] = token

        res = await SetUserStatusUseCase(uow, bus).execute(
            SetUserStatusCommand(target_user_public_id=user.id.value, blocked=True)
        )
        assert isinstance(res, Ok)
        assert uow.users.store[user.id.value].status == UserStatus.BLOCKED
        assert token.status == TokenStatus.REVOKED

    async def test_unblock(self, uow: FakeIdentityUoW, hasher: Argon2Hasher, bus: FakeBus) -> None:
        user = _seed_user(uow, hasher, status=UserStatus.BLOCKED)
        res = await SetUserStatusUseCase(uow, bus).execute(
            SetUserStatusCommand(target_user_public_id=user.id.value, blocked=False)
        )
        assert isinstance(res, Ok)
        assert uow.users.store[user.id.value].status == UserStatus.ACTIVE

    async def test_status_unknown_user(self, uow: FakeIdentityUoW, bus: FakeBus) -> None:
        res = await SetUserStatusUseCase(uow, bus).execute(
            SetUserStatusCommand(target_user_public_id=uuid4(), blocked=True)
        )
        assert isinstance(res, Err)
        assert isinstance(res.error, UserNotFound)
