"""Pydantic DTOs for the files endpoints."""

from app.modules.files.presentation.dto.file_dto import (
    AttachFilesRequest,
    FileResponse,
    RequestUploadRequest,
    UploadTicketResponse,
    VariantResponse,
)

__all__ = [
    "AttachFilesRequest",
    "FileResponse",
    "RequestUploadRequest",
    "UploadTicketResponse",
    "VariantResponse",
]
