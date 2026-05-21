"""Endpointy do uploadu, pobierania i usuwania załączników."""
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.database import get_db
from app.models.attachment import Attachment
from app.models.user import User
from app.schemas.attachment import AttachmentOut
from app.services import attachment_service
from app.services.storage_service import StorageService, get_storage_service

router = APIRouter()


# POST /api/attachments/posts/{post_id}
@router.post(
    "/posts/{post_id}",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_attachment_to_post(
    post_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    file: UploadFile = File(...),
) -> Attachment:
    return attachment_service.attach_to_post(
        db=db, storage=storage, post_id=post_id, upload=file, current_user=current_user
    )


# POST /api/attachments/comments/{comment_id}
@router.post(
    "/comments/{comment_id}",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_attachment_to_comment(
    comment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
    file: UploadFile = File(...),
) -> Attachment:
    return attachment_service.attach_to_comment(
        db=db, storage=storage, comment_id=comment_id, upload=file, current_user=current_user
    )


# GET /api/attachments/{attachment_id}/info  — same metadane
@router.get("/{attachment_id}/info", response_model=AttachmentOut)
def get_attachment_info(
    attachment_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> Attachment:
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Załącznik nie istnieje")
    return attachment


# GET /api/attachments/{attachment_id}  — pobranie pliku
@router.get("/{attachment_id}")
def download_attachment(
    attachment_id: int,
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> StreamingResponse:
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Załącznik nie istnieje")

    stream = storage.open_for_read(attachment.stored_filename)
    # RFC 5987 — bezpieczne kodowanie nazw z polskimi znakami
    encoded_name = quote(attachment.original_filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
        "Content-Length": str(attachment.size_bytes),
    }
    return StreamingResponse(stream, media_type=attachment.content_type, headers=headers)


# DELETE /api/attachments/{attachment_id}
@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment_endpoint(
    attachment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageService, Depends(get_storage_service)],
) -> None:
    attachment_service.delete_attachment(
        db=db, storage=storage, attachment_id=attachment_id, current_user=current_user
    )
