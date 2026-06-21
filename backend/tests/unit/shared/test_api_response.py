"""Unit tests for the public response envelopes."""

from __future__ import annotations

from app.shared.presentation.api_response import (
    ApiResponse,
    ErrorDetail,
    ErrorResponse,
    PaginatedResponse,
)


class TestApiResponse:
    def test_wraps_data(self) -> None:
        resp = ApiResponse[dict[str, int]](data={"count": 3})
        dumped = resp.model_dump()
        assert dumped["data"] == {"count": 3}
        assert dumped["meta"] is None


class TestErrorResponse:
    def test_envelope_shape(self) -> None:
        resp = ErrorResponse(
            error=ErrorDetail(code="NOT_FOUND", message="gone", field="id"),
            request_id="req-1",
        )
        dumped = resp.model_dump()
        assert dumped["error"]["code"] == "NOT_FOUND"
        assert dumped["error"]["field"] == "id"
        assert dumped["request_id"] == "req-1"

    def test_field_is_optional(self) -> None:
        detail = ErrorDetail(code="X", message="m")
        assert detail.field is None


class TestPaginatedResponse:
    def test_defaults(self) -> None:
        page = PaginatedResponse[int](items=[1, 2, 3])
        assert page.next_cursor is None
        assert page.total is None

    def test_with_cursor(self) -> None:
        page = PaginatedResponse[int](items=[1], next_cursor="abc", total=10)
        assert page.next_cursor == "abc"
        assert page.total == 10
