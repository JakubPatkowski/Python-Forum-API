"""Use case abstraction.

A use case takes a typed command/query and returns a `Result`. Concrete
use cases implement this Protocol; tests can substitute fakes.
"""

from __future__ import annotations

from typing import Protocol


class UseCase[I, O](Protocol):
    """Single-method callable contract: `execute(input) -> output`."""

    async def execute(self, input_: I) -> O: ...
