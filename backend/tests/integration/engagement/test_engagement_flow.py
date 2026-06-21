"""Engagement (polubienia + statystyki) integracyjnie, na realnym Postgresie.

Moduł ``engagement`` to cienki router na surowym SQL (tabela ``reactions`` +
widok ``user_stats``), więc ma sens tylko przeciwko prawdziwej bazie. Test
przechodzi pełną ścieżkę: polub / odlub (idempotentnie), licznik i flagę
``liked``, polub komentarza, „wątek tygodnia" (featured) oraz statystyki usera
wraz z przypadkami 404.

Fixture'y ``client`` / ``app`` / ``postgres_url`` pochodzą z
``tests/integration/conftest.py`` (jeden współdzielony kontener na sesję).
Asercje są zawężone do własnej kategorii/wątku, więc współdzielona baza nie
czyni ich kruchymi.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("httpx")

from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def _register_and_login(client: AsyncClient, *, username: str) -> dict[str, str]:
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
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_like_unlike_and_stats_flow(client: AsyncClient) -> None:
    auth = await _register_and_login(client, username="anglerlikes")

    me = await client.get("/api/v1/users/me", headers=auth)
    assert me.status_code == 200, me.text
    user_id = me.json()["id"]

    # --- przygotuj kategorię + wątek + komentarz --------------------------
    cat = await client.post("/api/v1/categories", json={"name": "Feeder"}, headers=auth)
    assert cat.status_code == 201, cat.text
    category_id = cat.json()["id"]

    post = await client.post(
        "/api/v1/posts",
        json={"title": "Najlepszy feeder", "content": "treść", "category_id": category_id},
        headers=auth,
    )
    assert post.status_code == 201, post.text
    post_id = post.json()["id"]

    comment = await client.post(
        "/api/v1/comments",
        json={"post_id": post_id, "content": "świetny wątek"},
        headers=auth,
    )
    assert comment.status_code == 201, comment.text
    comment_id = comment.json()["id"]

    # --- polub wątek (idempotentnie) --------------------------------------
    resp = await client.post(f"/api/v1/posts/{post_id}/like", headers=auth)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"count": 1, "liked": True}

    # podwójny like nie dubluje
    resp = await client.post(f"/api/v1/posts/{post_id}/like", headers=auth)
    assert resp.json()["count"] == 1

    # GET z autoryzacją => liked True
    resp = await client.get(f"/api/v1/posts/{post_id}/likes", headers=auth)
    assert resp.json() == {"count": 1, "liked": True}

    # GET bez autoryzacji => liked False, licznik nadal 1
    resp = await client.get(f"/api/v1/posts/{post_id}/likes")
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"count": 1, "liked": False}

    # --- polub komentarz --------------------------------------------------
    resp = await client.post(f"/api/v1/comments/{comment_id}/like", headers=auth)
    assert resp.status_code == 200, resp.text
    assert resp.json()["count"] == 1
    resp = await client.get(f"/api/v1/comments/{comment_id}/likes", headers=auth)
    assert resp.json()["liked"] is True

    # --- featured (wątek tygodnia) w obrębie własnej kategorii ------------
    resp = await client.get("/api/v1/featured-post", params={"category_id": category_id})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["post_id"] == post_id
    assert body["likes"] == 1

    # --- statystyki usera -------------------------------------------------
    resp = await client.get(f"/api/v1/users/{user_id}/stats")
    assert resp.status_code == 200, resp.text
    stats = resp.json()
    assert stats["posts_count"] >= 1
    assert stats["comments_count"] >= 1
    assert stats["likes_received"] >= 1

    # --- odlub i sprawdź licznik -----------------------------------------
    resp = await client.delete(f"/api/v1/posts/{post_id}/like", headers=auth)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"count": 0, "liked": False}


async def test_like_missing_post_is_404(client: AsyncClient) -> None:
    auth = await _register_and_login(client, username="anglermiss")
    resp = await client.post(f"/api/v1/posts/{uuid4()}/like", headers=auth)
    assert resp.status_code == 404, resp.text


async def test_stats_for_unknown_user_is_404(client: AsyncClient) -> None:
    resp = await client.get(f"/api/v1/users/{uuid4()}/stats")
    assert resp.status_code == 404, resp.text


async def test_featured_post_empty_category_returns_null(client: AsyncClient) -> None:
    # Kategoria bez wątków => featured zwraca pustą odpowiedź (post_id=None).
    auth = await _register_and_login(client, username="anglerempty")
    cat = await client.post("/api/v1/categories", json={"name": "Pusta"}, headers=auth)
    assert cat.status_code == 201, cat.text
    category_id = cat.json()["id"]
    resp = await client.get("/api/v1/featured-post", params={"category_id": category_id})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"post_id": None, "likes": 0}
