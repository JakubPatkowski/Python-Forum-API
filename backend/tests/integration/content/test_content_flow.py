"""Content module integration tests against a real Postgres (testcontainers).

Drives the public HTTP API end-to-end so the SQLAlchemy repositories, mappers,
unit-of-work and ORM (all 0 %-covered by the unit suite) are genuinely
exercised against Postgres — including the two features that only have meaning
at the database level: **keyset pagination** of posts and the **materialized
path** ordering of the comment tree.

Marked ``integration`` so ``pytest -m "not integration"`` skips the container
start-up cost. Requires Docker (provided by CI).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("httpx")

from httpx import AsyncClient

# postgres_url / app / client pochodzą z tests/integration/conftest.py
# (jeden współdzielony kontener Postgresa na całą sesję).
pytestmark = pytest.mark.integration


async def _register_and_login(client: AsyncClient, *, username: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "Tro4dl3-hammer-pizza",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username_or_email": username, "password": "Tro4dl3-hammer-pizza"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def test_category_post_comment_round_trip(client: AsyncClient) -> None:
    token = await _register_and_login(client, username="hubert")
    auth = {"Authorization": f"Bearer {token}"}

    # --- create a category (any logged-in user may, per category.create) ----
    # Unikalna nazwa: migracja 0005 zasiewa domyślne kategorie (m.in. „Spinning"),
    # więc stała nazwa kolidowałaby (409 CATEGORY_EXISTS) na zmigrowanej bazie.
    category_name = f"Spinning {uuid4().hex[:8]}"
    resp = await client.post("/api/v1/categories", json={"name": category_name}, headers=auth)
    assert resp.status_code == 201, resp.text
    category_id = resp.json()["id"]

    # --- create a post in that category, with tags --------------------------
    resp = await client.post(
        "/api/v1/posts",
        json={
            "title": "Where to spin for perch",
            "content": "Looking for tips on **perch** spots.",
            "category_id": category_id,
            "tags": ["perch", "spinning"],
        },
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    post = resp.json()
    post_id = post["id"]
    # CategoryRefResponse osadzony w poście używa `public_id` (CategoryResponse
    # z endpointu kategorii zwraca to samo UUID jako `id`).
    assert post["category"]["public_id"] == category_id
    assert {t["name"] for t in post["tags"]} == {"perch", "spinning"}

    # --- read it back -------------------------------------------------------
    resp = await client.get(f"/api/v1/posts/{post_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Where to spin for perch"

    # --- build a nested comment tree (materialized path ordering) -----------
    resp = await client.post(
        "/api/v1/comments",
        json={"post_id": post_id, "content": "Top-level comment"},
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    root_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/comments",
        json={"post_id": post_id, "content": "A reply", "parent_id": root_id},
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["depth"] == 1

    # the tree endpoint returns DFS order by path with depth annotations
    resp = await client.get("/api/v1/comments", params={"post_id": post_id})
    assert resp.status_code == 200, resp.text
    tree = resp.json()["items"]
    assert len(tree) == 2
    assert tree[0]["depth"] == 0
    assert tree[1]["depth"] == 1


async def test_post_keyset_pagination(client: AsyncClient) -> None:
    token = await _register_and_login(client, username="pager")
    auth = {"Authorization": f"Bearer {token}"}

    for i in range(5):
        resp = await client.post(
            "/api/v1/posts",
            json={"title": f"Pagination post number {i}", "content": "body"},
            headers=auth,
        )
        assert resp.status_code == 201, resp.text

    # first page
    resp = await client.get("/api/v1/posts", params={"limit": 2})
    assert resp.status_code == 200, resp.text
    page1 = resp.json()
    assert len(page1["items"]) == 2
    cursor = page1["next_cursor"]
    assert cursor, "more posts exist, so a next_cursor must be returned"

    # second page via the cursor — must not repeat items from page 1
    resp = await client.get("/api/v1/posts", params={"limit": 2, "cursor": cursor})
    assert resp.status_code == 200, resp.text
    page2 = resp.json()
    ids1 = {p["id"] for p in page1["items"]}
    ids2 = {p["id"] for p in page2["items"]}
    assert ids1.isdisjoint(ids2)
    # ordering is created_at DESC — page 2 items are strictly older than page 1's
    assert all(p["created_at"] <= page1["items"][-1]["created_at"] for p in page2["items"])
