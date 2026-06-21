"""Unit tests for the shared Result type (Ok / Err)."""

from __future__ import annotations

from app.shared.application.result import Err, Ok, Result
from app.shared.domain.errors import NotFoundError


class TestOk:
    def test_carries_value(self) -> None:
        ok = Ok(42)
        assert ok.value == 42

    def test_predicates(self) -> None:
        ok = Ok("x")
        assert ok.is_ok() is True
        assert ok.is_err() is False

    def test_is_frozen(self) -> None:
        import dataclasses

        ok = Ok(1)
        try:
            ok.value = 2  # type: ignore[misc]
        except dataclasses.FrozenInstanceError:
            pass
        else:  # pragma: no cover - guard
            raise AssertionError("Ok should be immutable")


class TestErr:
    def test_carries_error(self) -> None:
        err = Err(NotFoundError("missing"))
        assert isinstance(err.error, NotFoundError)

    def test_predicates(self) -> None:
        err = Err(NotFoundError("missing"))
        assert err.is_ok() is False
        assert err.is_err() is True


def test_pattern_matching() -> None:
    def classify(r: Result[int, str]) -> str:
        match r:
            case Ok(value):
                return f"ok:{value}"
            case Err(error):
                return f"err:{error}"

    assert classify(Ok(5)) == "ok:5"
    assert classify(Err("boom")) == "err:boom"
