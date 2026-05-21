"""Generic repository port.

Modules extend `IRepository[T, ID]` with their own query methods, e.g.::

    class IUserRepository(IRepository[User, UserId], Protocol):
        async def get_by_email(self, email: Email) -> User | None: ...
"""

from __future__ import annotations

from typing import Protocol


class IRepository[T, ID](Protocol):
    """Minimal repository contract: get / add / remove / exists.

    Variance is inferred automatically from method signatures by
    type checkers that support PEP 695 (mypy >= 1.13, pyright recent).
    """

    async def get(self, id_: ID) -> T | None: ...

    async def add(self, entity: T) -> None: ...

    async def remove(self, entity: T) -> None: ...

    async def exists(self, id_: ID) -> bool: ...
