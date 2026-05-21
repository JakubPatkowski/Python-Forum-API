"""Logika biznesowa załączników — walidacja, zapis na dysku + DB, autoryzacja usuwania."""
from __future__ import annotations

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.permissions import has_role
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.post import Post
from app.models.user import User, UserRole
from app.services.storage_service import StorageService


def _validate_mime(content_type: str | None) -> str:
    """Sprawdza czy MIME-type jest na białej liście."""
    if not content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brak content-type w przesłanym pliku",
        )
    if content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Niedozwolony typ pliku: {content_type}",
        )
    return content_type


def attach_to_post(
    db: Session,
    storage: StorageService,
    post_id: int,
    upload: UploadFile,
    current_user: User,
) -> Attachment:
    """Załącza plik do posta. Uprawnienia: autor posta lub MODERATOR+/ADMIN."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post nie istnieje")
    if post.author_id != current_user.id and not has_role(current_user, UserRole.MODERATOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brak uprawnień do tego posta")

    return _save_attachment(
        db=db,
        storage=storage,
        upload=upload,
        uploader_id=current_user.id,
        post_id=post.id,
        comment_id=None,
    )


def attach_to_comment(
    db: Session,
    storage: StorageService,
    comment_id: int,
    upload: UploadFile,
    current_user: User,
) -> Attachment:
    """Załącza plik do komentarza. Uprawnienia: autor lub MODERATOR+/ADMIN."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Komentarz nie istnieje")
    if comment.author_id != current_user.id and not has_role(current_user, UserRole.MODERATOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brak uprawnień do tego komentarza")

    return _save_attachment(
        db=db,
        storage=storage,
        upload=upload,
        uploader_id=current_user.id,
        post_id=None,
        comment_id=comment.id,
    )


def delete_attachment(
    db: Session,
    storage: StorageService,
    attachment_id: int,
    current_user: User,
) -> None:
    """Usuwa załącznik (plik + rekord). Uprawnienia: uploader lub MODERATOR+/ADMIN."""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Załącznik nie istnieje")
    if attachment.uploader_id != current_user.id and not has_role(current_user, UserRole.MODERATOR):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brak uprawnień")

    storage.delete(attachment.stored_filename)
    db.delete(attachment)
    db.commit()


def _save_attachment(
    *,
    db: Session,
    storage: StorageService,
    upload: UploadFile,
    uploader_id: int,
    post_id: int | None,
    comment_id: int | None,
) -> Attachment:
    """Wspólna ścieżka zapisu — walidacja, zapis na dysku, zapis do DB."""
    content_type = _validate_mime(upload.content_type)
    original = upload.filename or "unknown"
    if len(original) > 255:
        original = original[-255:]

    stored = storage.generate_stored_filename(original)
    size = storage.save_upload(upload, stored)

    attachment = Attachment(
        original_filename=original,
        stored_filename=stored,
        content_type=content_type,
        size_bytes=size,
        uploader_id=uploader_id,
        post_id=post_id,
        comment_id=comment_id,
    )
    db.add(attachment)
    try:
        db.commit()
    except Exception:
        # Rollback DB i sprzątanie pliku
        db.rollback()
        storage.delete(stored)
        raise
    db.refresh(attachment)
    return attachment
