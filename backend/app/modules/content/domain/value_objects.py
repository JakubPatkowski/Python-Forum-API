"""Value Objects of the content module: Slug, MarkdownContent, ContentFormat.

Like the identity VOs, these are immutable, equality-by-value and validate
their invariants in ``__post_init__``. The presentation layer constructs them
at the request boundary; once created, they are guaranteed well-formed.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject

# Slug: lowercase ASCII letters, digits and hyphens. 1..120 chars.
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SLUG_REPLACE_RE = re.compile(r"[^a-z0-9]+")

# Transliteration for letters NFKD does not decompose to ASCII (notably Polish
# "ł"/"Ł", which have no canonical decomposition). Applied BEFORE NFKD, so this
# map only needs the no-decomposition letters; the rest (ó, ą, ę, ć, ń, ś, ź, ż)
# are handled by NFKD + stripping combining marks. Without this, "Łódź Łowienie"
# produced "odz-owienie".
_TRANSLITERATION = str.maketrans(
    {
        "ł": "l",
        "Ł": "L",
        "ß": "ss",
        "æ": "ae",
        "Æ": "AE",
        "ø": "o",
        "Ø": "O",
        "đ": "d",
        "Đ": "D",
    }
)


class ContentFormat(StrEnum):
    """Format of a post or comment's ``content`` field."""

    PLAIN = "plain"
    MARKDOWN = "markdown"


@dataclass(frozen=True, slots=True)
class Slug(ValueObject):
    """A URL-safe slug.

    Format: lowercase ``[a-z0-9-]+`` with no leading/trailing or doubled hyphens.
    Use :meth:`from_text` to generate one automatically from arbitrary input.
    """

    value: str

    def __post_init__(self) -> None:
        v = self.value.strip()
        if not v:
            raise ValidationError("Slug must not be empty", field="slug")
        if len(v) > 220:
            raise ValidationError("Slug must be at most 220 characters", field="slug")
        if not _SLUG_RE.match(v):
            raise ValidationError(
                "Slug may contain only lowercase letters, digits and hyphens",
                field="slug",
            )
        object.__setattr__(self, "value", v)

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_text(cls, text: str, *, max_length: int = 120) -> Slug:
        """Build a slug from arbitrary text.

        Transliterates letters with no NFKD decomposition (e.g. Polish "ł"),
        strips accents, lower-cases, collapses runs of non-alphanumerics into
        a single hyphen, trims leading/trailing hyphens, then truncates.
        """
        transliterated = text.translate(_TRANSLITERATION)
        normalised = unicodedata.normalize("NFKD", transliterated)
        ascii_only = "".join(
            ch for ch in normalised if not unicodedata.combining(ch)
        )
        lowered = ascii_only.lower()
        slug_body = _SLUG_REPLACE_RE.sub("-", lowered).strip("-")
        if not slug_body:
            raise ValidationError(
                f"Could not derive a slug from text: {text!r}", field="slug"
            )
        return cls(slug_body[:max_length].rstrip("-"))


@dataclass(frozen=True, slots=True)
class MarkdownContent(ValueObject):
    """Body text with an explicit format marker.

    The actual safe-render step (HTML sanitisation, link rewriting) is done in
    the presentation layer. The domain only guarantees the content is not
    empty and not absurdly large.
    """

    body: str
    format: ContentFormat = ContentFormat.MARKDOWN

    # 64 KiB cap — well above realistic forum posts, well below DoS territory.
    _MAX_BYTES: int = 64 * 1024

    def __post_init__(self) -> None:
        if not self.body or not self.body.strip():
            raise ValidationError("Content must not be empty", field="content")
        if len(self.body.encode("utf-8")) > self._MAX_BYTES:
            raise ValidationError(
                f"Content must be at most {self._MAX_BYTES // 1024} KiB",
                field="content",
            )

    def __str__(self) -> str:
        return self.body
