from datetime import datetime

from pydantic import BaseModel


class AttachmentOut(BaseModel):
    """Metadane pliku zwracane do klienta. Sam plik pobiera się przez GET /api/attachments/{id}."""

    id: int
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime
    uploader_id: int
    post_id: int | None
    comment_id: int | None

    model_config = {"from_attributes": True}
