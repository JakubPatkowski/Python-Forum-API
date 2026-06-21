"""End-to-end auth flow against a real Postgres via testcontainers.

The test exercises the full happy path *and* the refresh-token reuse detection:

    register -> login -> refresh -> refresh (again on rotated) -> all sessions revoked

Marked ``integration`` so unit-test runs (``pytest -m "not integration"``)
skip the container start-up cost.
"""

from __future__ import annotations

import pytest

pytest.importorskip("httpx")

from httpx import AsyncClient

# postgres_url / app / client pochodzą z tests/integration/conftest.py
# (jeden współdzielony kontener Postgresa na całą sesję).
pytestmark = pytest.mark.integration


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
    resp = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200, resp.text
    me = resp.json()
    assert me["username"] == "jakub"
    assert "post.create" in me["permissions"]

    # --- refresh -----------------------------------------------------------
    # The /auth/refresh endpoint prefers the httpOnly cookie (browser path) and
    # falls back to the JSON body for non-browser clients. ``AsyncClient`` keeps
    # a cookie jar, so login + each refresh would silently overwrite the cookie
    # with the freshly rotated token — masking the body token we want to test.
    # Clear the jar before every refresh so this models a pure API client that
    # only ever sends the explicit ``refresh_token`` in the body.
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
    assert resp.status_code == 200, resp.text
    refresh2 = resp.json()["refresh_token"]
    assert refresh2 != refresh1

    # --- reuse of the old refresh => 401 + all sessions revoked -----------
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
    assert resp.status_code == 401, resp.text
    assert resp.json()["error"]["code"] == "REFRESH_TOKEN_REUSE"

    # The rotated successor token must also be unusable now.
    client.cookies.clear()
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh2})
    assert resp.status_code == 401, resp.text
