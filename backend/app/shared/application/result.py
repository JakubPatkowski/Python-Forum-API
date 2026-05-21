"""Result type — explicit success/failure container for use cases.

Inspired by Rust's `Result`. Use cases return a `Result` so the presentation
layer can map success and failure to HTTP without exceptions for control flow.

    res = await use_case.execute(cmd)
    match res:
        case Ok(value): ...
        case Err(error): ...
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Ok[T]:
    """Successful result with a value."""

    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class Err[E]:
    """Failure result with an error."""

    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True


type Result[T, E] = Ok[T] | Err[E]
