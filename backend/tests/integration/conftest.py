"""Współdzielone fixture'y dla testów integracyjnych (real Postgres).

Wszystkie testy integracyjne dzielą **jeden** kontener Postgresa na całą sesję
pytest. Powód: ``app.shared.infrastructure.db.engine`` (i tym samym
``SessionLocal``) jest tworzony jednorazowo przy pierwszym imporcie z
``settings.DATABASE_URL``. Gdyby każdy plik startował własny kontener
(scope="module"), drugi moduł dostałby świeży URL, ale silnik aplikacji nadal
wskazywałby na pierwszy (już zatrzymany) kontener → ``connection refused``.

Kolejność jest istotna: ustawiamy ``DATABASE_URL`` w env ZANIM cokolwiek
zaimportuje ``app.config`` / warstwę bazy, więc silnik wiąże się z właściwym
kontenerem. Migracje Alembica honorują ``sqlalchemy.url`` ustawiony tutaj na
configu (patrz ``alembic/env.py``).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest

pytest.importorskip("testcontainers.postgres")
pytest.importorskip("httpx")

from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """Jeden kontener Postgresa na całą sesję; eksponuje DSN dla psycopg3."""
    with PostgresContainer("postgres:16-alpine") as container:
        # testcontainers zwraca DSN psycopg2 — projekt używa psycopg3.
        url = container.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        yield url


@pytest.fixture(scope="session")
def app(postgres_url: str) -> Any:
    """Aplikacja FastAPI po migracji schematu do najnowszej rewizji."""
    from alembic.config import Config
    from sqlalchemy import create_engine

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(cfg, "head")

    # KLUCZOWE: globalny `engine`/`SessionLocal` w app.shared.infrastructure.db
    # powstają RAZ przy pierwszym imporcie z `settings.DATABASE_URL`. W zadaniu
    # integracyjnym ten import zdarza się już na etapie kolekcji (inny moduł
    # testowy importuje `app.*` na górze pliku) — ZANIM ten fixture ustawi
    # DATABASE_URL — więc silnik zostaje przypięty do domyślnego localhost:5432.
    # Przepinamy WSPÓŁDZIELONY sessionmaker na bazę kontenera: `.configure()`
    # mutuje ten sam obiekt, którego referencję trzymają `get_db` ORAZ use-case'y
    # z container.py, więc wszystkie ścieżki naraz celują w testową bazę.
    from app.shared.infrastructure import db as db_module

    test_engine = create_engine(postgres_url, pool_pre_ping=True, future=True)
    db_module.engine = test_engine
    db_module.SessionLocal.configure(bind=test_engine)

    # Późny import: dopiero teraz montujemy aplikację (silnik już przepięty).
    from app.main import create_app

    return create_app()


@pytest.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
