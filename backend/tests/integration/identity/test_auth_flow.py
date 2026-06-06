"""End-to-end auth flow against a real Postgres via testcontainers.

The test exercises the full happy path *and* the refresh-token reuse detection:

    register -> login -> refresh -> refresh (again on rotated) -> all sessions revoked

Marked ``integration`` so unit-test runs (``pytest -m "not integration"``)
skip the container start-up cost.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("testcontainers.postgres")
pytest.importorskip("httpx")

from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def postgres_url() -> str:
    with PostgresContainer("postgres:16-alpine") as container:
        # Translate the JDBC-style URL to a psycopg one.
        raw = container.get_connection_url()
        # e.g. postgresql+psycopg2://test:test@localhost:5432/test
        url = raw.replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        yield url


@pytest.fixture(scope="module")
def app(postgres_url: str):
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(cfg, "head")

    # Late import so the env DATABASE_URL is in effect.
    from app.main import create_app

    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_full_auth_flow_with_reuse_detection(client: AsyncClient) -> None:
    # --- register ----------------------------------------------------------
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "jakub",
            "email": "jakub@example.com",
            "password": "Tro4dl3-hammer-pizza",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == "jakub"
    assert "user" in body["roles"]

    # --- login -------------------------------------------------------------
    resp = await client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "jakub",
            "password": "Tro4dl3-hammer-pizza",
        },
    )
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    access = tokens["access_token"]
    refresh1 = tokens["refresh_token"]

    # --- /users/me ---------------------------------------------------------
    resp = await client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 200, resp.text
    me = resp.json()
    assert me["username"] == "jakub"
    assert "post.create" in me["permissions"]

    # --- refresh -----------------------------------------------------------
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh1}
    )
    assert resp.status_code == 200, resp.text
    refresh2 = resp.json()["refresh_token"]
    assert refresh2 != refresh1

    # --- reuse of the old refresh => 401 + all sessions revoked -----------
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh1}
    )
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "REFRESH_TOKEN_REUSE"

    # The rotated successor token must also be unusable now.
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh2}
    )
    assert resp.status_code == 401, resp.text
