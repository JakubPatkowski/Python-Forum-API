"""HTTP-level (e2e) tests driving the real FastAPI app via ``TestClient``.

No database is involved: the DI container's use-case providers are overridden
with use cases wired to in-memory fakes, and ``get_current_user`` is overridden
to inject a caller with a chosen permission set. This exercises the full
presentation layer — routing, request/response DTOs, status codes, the error
envelope from the global exception handler and the auth dependencies — which
unit tests on the use cases alone cannot reach.
"""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import container
from app.main import create_app
from app.modules.content.application.use_cases import (
    CreatePostUseCase,
    GetPostUseCase,
    ListPostsUseCase,
)
from app.modules.identity.application.use_cases import (
    LoginUseCase,
    RegisterUserUseCase,
)
from app.modules.identity.domain.permission import Permission
from app.modules.identity.domain.role import Role, RoleId
from app.modules.identity.domain.user import User
from app.modules.identity.domain.value_objects import Email, Username
from app.modules.identity.infrastructure.auth import Argon2Hasher, PyJWTTokenService
from app.modules.identity.presentation.deps import CurrentUserData, get_current_user

# Reuse the in-memory fakes defined by the use-case unit tests.
from tests.unit.content.test_use_cases import FakeBus, FakeContentUoW
from tests.unit.identity.test_application_use_cases import FakeIdentityUoW

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


class _Harness:
    def __init__(self) -> None:
        self.app = create_app()
        self.content_uow = FakeContentUoW()
        self.identity_uow = FakeIdentityUoW()
        self.identity_uow.roles.store["user"] = Role(
            id=RoleId.new(),
            name="user",
            permissions={Permission("post.create"), Permission("post.read")},
        )
        self.hasher = Argon2Hasher()
        self.tokens = PyJWTTokenService()
        self.bus = FakeBus()

        ov = self.app.dependency_overrides
        ov[container.get_list_posts_uc] = lambda: ListPostsUseCase(self.content_uow)
        ov[container.get_get_post_uc] = lambda: GetPostUseCase(self.content_uow)
        ov[container.get_create_post_uc] = lambda: CreatePostUseCase(self.content_uow, self.bus)
        ov[container.get_register_user_uc] = lambda: RegisterUserUseCase(
            self.identity_uow, self.hasher, self.bus
        )
        ov[container.get_login_uc] = lambda: LoginUseCase(
            self.identity_uow, self.hasher, self.tokens, self.bus
        )

    def login_as(self, *permissions: str) -> None:
        """Force ``get_current_user`` to return a caller with these permissions."""
        user = CurrentUserData(
            public_id=uuid4(), username="tester", permissions=frozenset(permissions)
        )
        self.app.dependency_overrides[get_current_user] = lambda: user

    def seed_user(
        self, *, username: str = "angler", email: str = "a@example.com", password: str = "pw"
    ) -> User:
        user = User.register(
            username=Username(username),
            email=Email(email),
            password_hash=self.hasher.hash(password),
            default_role=self.identity_uow.roles.store["user"],
        )
        user.pull_events()
        self.identity_uow.users.store[user.id.value] = user
        return user


@pytest.fixture
def harness() -> _Harness:
    return _Harness()


@pytest.fixture
def client(harness: _Harness) -> Iterator[TestClient]:
    # Instantiate WITHOUT the context manager so the app lifespan (which tries
    # to reach MinIO) does not run — these tests need no object storage.
    yield TestClient(harness.app)


# --------------------------------------------------------------------------- #
# Auth endpoints                                                               #
# --------------------------------------------------------------------------- #


class TestAuthEndpoints:
    def test_register_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "newangler",
                "email": "new@example.com",
                "password": "Sup3rStrongP@ss",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["username"] == "newangler"

    def test_register_validation_error_envelope(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": "ok", "email": "not-an-email", "password": "short"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"
        assert "message" in body["error"]

    def test_register_duplicate_returns_409_envelope(
        self, harness: _Harness, client: TestClient
    ) -> None:
        harness.seed_user(username="taken", email="taken@example.com")
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "taken",
                "email": "other@example.com",
                "password": "Sup3rStrongP@ss",
            },
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "USERNAME_TAKEN"

    def test_login_then_returns_token(self, harness: _Harness, client: TestClient) -> None:
        harness.seed_user(username="loginuser", email="l@example.com", password="Sup3rStrongP@ss")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "loginuser", "password": "Sup3rStrongP@ss"},
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_login_bad_password_returns_401(self, harness: _Harness, client: TestClient) -> None:
        harness.seed_user(username="loginuser", email="l@example.com", password="Sup3rStrongP@ss")
        resp = client.post(
            "/api/v1/auth/login",
            json={"username_or_email": "loginuser", "password": "nope"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


# --------------------------------------------------------------------------- #
# Posts endpoints                                                              #
# --------------------------------------------------------------------------- #


class TestPostsEndpoints:
    def test_list_posts_public_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/posts")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    def test_get_missing_post_404_envelope(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/posts/{uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "POST_NOT_FOUND"

    def test_create_post_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/v1/posts", json={"title": "No auth post", "content": "body"})
        assert resp.status_code == 401

    def test_create_post_forbidden_without_permission(
        self, harness: _Harness, client: TestClient
    ) -> None:
        harness.login_as("post.read")  # missing post.create
        resp = client.post(
            "/api/v1/posts",
            json={"title": "Forbidden post", "content": "body"},
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 403

    def test_create_post_success(self, harness: _Harness, client: TestClient) -> None:
        harness.login_as("post.create")
        resp = client.post(
            "/api/v1/posts",
            json={"title": "My first post", "content": "Tight lines!"},
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "My first post"

    def test_create_post_invalid_body_422(self, harness: _Harness, client: TestClient) -> None:
        harness.login_as("post.create")
        resp = client.post(
            "/api/v1/posts",
            json={"title": "x", "content": ""},  # title too short, content empty
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
