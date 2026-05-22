"""Value Objects of the identity module: Email, Username, RawPassword.

All three are immutable, equality-by-value and validate their invariants in
``__post_init__``. Domain code should construct them at the application
boundary; once a VO exists it is guaranteed to be well-formed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject

# RFC 5322 is not realistic to implement in a regex; use a pragmatic check
# that catches obvious typos. Heavy validation is delegated to ``pydantic.EmailStr``
# at the API boundary.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")

# Top common passwords excerpt — keep small, fine-grained list in
# ``application.permissions`` if it grows.
_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "password",
        "12345678",
        "qwerty12",
        "admin123",
        "password1",
        "letmein1",
        "iloveyou",
    }
)


@dataclass(frozen=True, slots=True)
class Email(ValueObject):
    """A syntactically valid e-mail address.

    The canonical form is lower-cased so DB lookups can be done case-insensitively
    without rewriting the input every time.
    """

    value: str

    def __post_init__(self) -> None:
        normalised = self.value.strip().lower()
        if not _EMAIL_RE.match(normalised):
            raise ValidationError(
                f"Invalid email address: {self.value!r}", field="email"
            )
        # Bypass frozen restriction to store the normalised value.
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Username(ValueObject):
    """A user-visible login name. 3–50 characters, ``[A-Za-z0-9_]`` only."""

    value: str

    def __post_init__(self) -> None:
        v = self.value.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValidationError(
                "Username must be between 3 and 50 characters", field="username"
            )
        if not _USERNAME_RE.match(v):
            raise ValidationError(
                "Username may contain only letters, digits and underscore",
                field="username",
            )
        object.__setattr__(self, "value", v)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RawPassword(ValueObject):
    """A plaintext password.

    Wrapping the raw string in a VO documents intent (this is the password,
    not just any string) and gives one place to centralise password policy:
    minimum length and a blocklist of very common passwords (NIST SP 800-63B).
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) < 8:
            raise ValidationError(
                "Password must be at least 8 characters", field="password"
            )
        if len(self.value) > 128:
            raise ValidationError(
                "Password must be at most 128 characters", field="password"
            )
        if self.value.lower() in _COMMON_PASSWORDS:
            raise ValidationError("Password is too common", field="password")

    def __str__(self) -> str:  # pragma: no cover - defensive, do not log
        return "***"
