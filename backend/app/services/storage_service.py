"""Logika zapisu/odczytu/usuwania plików na dysku.

Encje DB (Attachment) trzymają tylko metadane. Tu pilnujemy I/O.
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status

from app.config import settings


class StorageService:
    """Wrapper nad dyskiem — umieszczanie i usuwanie plików w UPLOAD_DIR."""

    def __init__(self, upload_dir: str | None = None) -> None:
        self._dir = Path(upload_dir or settings.UPLOAD_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def upload_dir(self) -> Path:
        return self._dir

    def _path_for(self, stored_filename: str) -> Path:
        # Zabezpieczenie przed path traversal — bierzemy tylko basename
        safe = os.path.basename(stored_filename)
        return self._dir / safe

    @staticmethod
    def generate_stored_filename(original_filename: str) -> str:
        """Zwraca unikalną nazwę: <uuid>.<extension> (extension z pliku originalnego)."""
        ext = Path(original_filename).suffix.lower()
        # Limit długości extension
        if len(ext) > 10:
            ext = ""
        return f"{uuid.uuid4().hex}{ext}"

    def save_upload(self, upload: UploadFile, stored_filename: str) -> int:
        """Zapisuje strumień z UploadFile na dysk. Zwraca rozmiar w bajtach.

        Pilnuje limitu rozmiaru — jeżeli przekroczy MAX_UPLOAD_SIZE_BYTES, kasuje plik
        i rzuca 413.
        """
        target = self._path_for(stored_filename)
        max_size = settings.MAX_UPLOAD_SIZE_BYTES
        size = 0
        chunk_size = 1024 * 1024  # 1 MB

        try:
            with target.open("wb") as out:
                while True:
                    chunk = upload.file.read(chunk_size)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_size:
                        out.close()
                        target.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Plik przekracza limit {max_size} bajtów",
                        )
                    out.write(chunk)
        finally:
            upload.file.close()
        return size

    def open_for_read(self, stored_filename: str) -> BinaryIO:
        """Zwraca otwarty strumień bajtów do streamowania w response."""
        path = self._path_for(stored_filename)
        if not path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plik nie istnieje na dysku")
        return path.open("rb")

    def delete(self, stored_filename: str) -> None:
        """Usuwa plik. Brak pliku nie jest błędem (idempotentnie)."""
        self._path_for(stored_filename).unlink(missing_ok=True)

    def clear_directory(self) -> None:
        """Czyści cały katalog uploadów — używane w testach."""
        if self._dir.is_dir():
            shutil.rmtree(self._dir)
        self._dir.mkdir(parents=True, exist_ok=True)


# Globalna instancja — wstrzykiwana przez Depends
storage_service = StorageService()


def get_storage_service() -> StorageService:
    return storage_service
