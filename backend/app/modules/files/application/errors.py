"""Application-level errors for the files module.

All subclass :class:`DomainError`, so the global exception handler turns them
into the standard ``{error:{code,message,field}}`` envelope with the right
HTTP status.
"""

from __future__ import annotations

from app.shared.domain.errors import DomainError


class FileNotFound(DomainError):
    """No file with the given public id."""

    code = "FILE_NOT_FOUND"
    http_status = 404

    def __init__(self, file_id: str) -> None:
        super().__init__(f"File {file_id} not found")


class FileNotReady(DomainError):
    """The file exists but its upload has not been finalised yet."""

    code = "FILE_NOT_READY"
    http_status = 409

    def __init__(self, file_id: str) -> None:
        super().__init__(f"File {file_id} is not ready", field="status")


class UnsupportedFileType(DomainError):
    """The declared or sniffed MIME type is not allowed."""

    code = "UNSUPPORTED_MEDIA_TYPE"
    http_status = 415

    def __init__(self, content_type: str) -> None:
        super().__init__(f"File type not allowed: {content_type}", field="content_type")


class FileTooLarge(DomainError):
    """The file exceeds the configured maximum size."""

    code = "PAYLOAD_TOO_LARGE"
    http_status = 413

    def __init__(self, *, size: int, limit: int) -> None:
        super().__init__(
            f"File is {size} bytes; the limit is {limit} bytes", field="size_bytes"
        )


class UploadNotConfirmed(DomainError):
    """``complete`` was called but the object is missing from storage."""

    code = "UPLOAD_NOT_CONFIRMED"
    http_status = 409

    def __init__(self, file_id: str) -> None:
        super().__init__(
            f"No uploaded object found for file {file_id}; PUT the bytes first",
            field="upload",
        )


class OwnerNotFound(DomainError):
    """The post/comment/user/category to attach the file to does not exist."""

    code = "OWNER_NOT_FOUND"
    http_status = 404

    def __init__(self, owner_type: str, owner_id: str) -> None:
        super().__init__(f"{owner_type} {owner_id} not found", field="owner_id")
