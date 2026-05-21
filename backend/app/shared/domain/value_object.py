"""Base class marker for Value Objects.

Value Objects are immutable and have equality by value, not by identity.
Concrete value objects should be `@dataclass(frozen=True, slots=True)`
subclasses and put any invariants in `__post_init__`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValueObject:
    """Marker base for Value Objects. Inherit and add fields."""
