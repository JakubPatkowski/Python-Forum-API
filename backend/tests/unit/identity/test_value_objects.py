"""Unit tests for identity value objects: Email, Username, RawPassword."""

from __future__ import annotations

import pytest

from app.modules.identity.domain.value_objects import (
    Email,
    RawPassword,
    Username,
)
from app.shared.domain.errors import ValidationError


class TestEmail:
    def test_accepts_valid_address_and_lowercases(self) -> None:
        e = Email("Jakub@Example.com")
        assert e.value == "jakub@example.com"
        assert str(e) == "jakub@example.com"

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "not-an-email",
            "missing@dot",
            "spaces are bad@example.com",
            "@example.com",
        ],
    )
    def test_rejects_invalid_address(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            Email(raw)

    def test_equality_by_value(self) -> None:
        assert Email("a@b.co") == Email("A@B.Co")


class TestUsername:
    def test_accepts_alnum_and_underscore(self) -> None:
        u = Username("user_42")
        assert u.value == "user_42"

    @pytest.mark.parametrize("raw", ["ab", "x" * 51, "no spaces", "kropka.", "ü"])
    def test_rejects_invalid(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            Username(raw)


class TestRawPassword:
    def test_minimum_length(self) -> None:
        with pytest.raises(ValidationError):
            RawPassword("short")

    def test_max_length(self) -> None:
        with pytest.raises(ValidationError):
            RawPassword("x" * 129)

    def test_rejects_common(self) -> None:
        with pytest.raises(ValidationError):
            RawPassword("password")

    def test_accepts_strong(self) -> None:
        p = RawPassword("Tro4dl3-hammer-pizza")
        assert p.value == "Tro4dl3-hammer-pizza"

    def test_str_does_not_leak_value(self) -> None:
        assert str(RawPassword("Tro4dl3-hammer-pizza")) == "***"
