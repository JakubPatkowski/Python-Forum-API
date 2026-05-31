"""Object storage + content-processing adapters for the files module."""

from app.modules.files.infrastructure.storage.image_processing import (
    PillowFileProcessor,
)
from app.modules.files.infrastructure.storage.minio_storage import MinioFileStorage

__all__ = ["MinioFileStorage", "PillowFileProcessor"]
