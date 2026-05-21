"""Unit of Work port.

A Unit of Work owns a transaction and exposes repositories as attributes.
Each module's UoW implementation declares its own repositories (e.g.
`SqlAlchemyIdentityUoW.users`, `SqlAlchemyContentUoW.posts`).
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self


class IUnitOfWork(Protocol):
    """Async context manager that commits/rolls back a transaction."""

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
