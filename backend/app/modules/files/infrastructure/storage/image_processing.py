"""MIME sniffing (libmagic) + image thumbnailing (Pillow).

Implements :class:`IFileProcessor`. Thumbnails are downscale-only (never
upscaled), aspect ratio preserved, EXIF orientation corrected.
"""

from __future__ import annotations

from io import BytesIO

import magic
import structlog
from PIL import Image, ImageOps

from app.modules.files.application.ports import IFileProcessor, ProcessedVariant

logger = structlog.get_logger(__name__)

_DEFAULT_FORMAT = "PNG"
_DEFAULT_MIME = "image/png"
# Formats that cannot hold alpha — flatten RGBA/P to RGB before saving.
_NO_ALPHA = {"JPEG"}


class PillowFileProcessor(IFileProcessor):
    """Concrete content inspector backed by python-magic and Pillow."""

    def sniff_mime(self, data: bytes) -> str:
        return magic.from_buffer(data, mime=True)

    def probe_image(self, data: bytes) -> tuple[int, int] | None:
        try:
            with Image.open(BytesIO(data)) as img:
                return (img.width, img.height)
        except Exception:
            return None

    def make_image_variants(self, data: bytes, *, sizes: dict[str, int]) -> list[ProcessedVariant]:
        try:
            with Image.open(BytesIO(data)) as src:
                src = ImageOps.exif_transpose(src)
                fmt = (src.format or _DEFAULT_FORMAT).upper()
                mime = Image.MIME.get(fmt, _DEFAULT_MIME)
                longest = max(src.width, src.height)
                out: list[ProcessedVariant] = []
                for name, max_edge in sizes.items():
                    if longest <= max_edge:
                        continue  # never upscale
                    variant = self._render(src, fmt, mime, name, max_edge)
                    if variant is not None:
                        out.append(variant)
                return out
        except Exception:
            logger.warning("thumbnail_generation_failed", exc_info=True)
            return []

    def _render(
        self, src: Image.Image, fmt: str, mime: str, name: str, max_edge: int
    ) -> ProcessedVariant | None:
        try:
            img = src.copy()
            img.thumbnail((max_edge, max_edge))
            if fmt in _NO_ALPHA and img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format=fmt)
            return ProcessedVariant(
                name=name,
                data=buf.getvalue(),
                width=img.width,
                height=img.height,
                content_type=mime,
            )
        except Exception:
            logger.warning("thumbnail_variant_failed", variant=name, exc_info=True)
            return None
