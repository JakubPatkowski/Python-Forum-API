"""HTTP endpoints for the generic files module (mounted at ``/api/v1``).

Two upload paths:
* Presigned (efficient): ``POST /files/uploads`` -> client PUTs to MinIO ->
  ``POST /files/uploads/{id}/complete``.
* Proxied (simple fallback): ``POST /files`` (multipart) streams through here.

Plus attachment sugar for posts/comments, avatars and category images, and a
disposition-aware ``/content`` redirect that sends the browser straight to
MinIO (bandwidth offload).

Reading attached files is public (mirrors public posts); upload/attach/delete
require authentication.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.container import (
    get_attach_files_uc,
    get_complete_upload_uc,
    get_delete_file_uc,
    get_direct_upload_uc,
    get_get_avatar_uc,
    get_get_category_image_uc,
    get_get_file_uc,
    get_get_post_icon_uc,
    get_list_my_files_uc,
    get_list_owner_files_uc,
    get_request_upload_uc,
    get_set_avatar_uc,
    get_set_category_image_uc,
    get_set_post_icon_uc,
)
from app.modules.files.application.commands import (
    AttachFilesCommand,
    CompleteUploadCommand,
    DeleteFileCommand,
    DirectUploadCommand,
    ListMyFilesQuery,
    ListOwnerFilesQuery,
    RequestUploadCommand,
    SetAvatarCommand,
    SetCategoryImageCommand,
    SetPostIconCommand,
)
from app.modules.files.application.use_cases import (
    AttachFilesUseCase,
    CompleteUploadUseCase,
    DeleteFileUseCase,
    DirectUploadUseCase,
    GetAvatarUseCase,
    GetCategoryImageUseCase,
    GetFileUseCase,
    GetPostIconUseCase,
    ListMyFilesUseCase,
    ListOwnerFilesUseCase,
    RequestUploadUseCase,
    SetAvatarUseCase,
    SetCategoryImageUseCase,
    SetPostIconUseCase,
)
from app.modules.files.domain.value_objects import FileOwnerType
from app.modules.files.presentation.deps import OptionalCurrentUser
from app.modules.files.presentation.dto import (
    AttachFilesRequest,
    FileResponse,
    RequestUploadRequest,
    UploadTicketResponse,
)
from app.modules.identity.presentation.deps import CurrentUser, requires
from app.shared.application.result import Err
from app.shared.domain.errors import DomainError
from app.shared.presentation.deps import DbSession

router = APIRouter()


def _raise_if_error(result: Any) -> None:
    if isinstance(result, Err):
        if isinstance(result.error, DomainError):
            raise result.error
        raise HTTPException(status_code=500, detail=str(result.error))


async def _read_upload(upload: UploadFile) -> tuple[str, str, bytes]:
    """Return ``(filename, content_type, data)`` from a multipart upload."""
    if not upload.filename:
        raise HTTPException(status_code=400, detail="Missing file name")
    data = await upload.read()
    content_type = upload.content_type or "application/octet-stream"
    return upload.filename, content_type, data


# --------------------------------------------------------------------------- #
# Generic upload — presigned (2-step)                                         #
# --------------------------------------------------------------------------- #


@router.post(
    "/files/uploads",
    response_model=UploadTicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a presigned upload (returns a PUT URL to MinIO)",
)
async def request_upload(
    body: RequestUploadRequest,
    user: Annotated[CurrentUser, Depends(requires("file.upload"))],
    uc: Annotated[RequestUploadUseCase, Depends(get_request_upload_uc)],
) -> UploadTicketResponse:
    result = await uc.execute(
        RequestUploadCommand(
            uploader_public_id=user.public_id,
            original_name=body.original_name,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
    )
    _raise_if_error(result)
    return UploadTicketResponse.from_ticket(result.value)  # type: ignore[union-attr]


@router.post(
    "/files/uploads/{file_id}/complete",
    response_model=FileResponse,
    summary="Finalise a presigned upload (validate bytes + thumbnails)",
)
async def complete_upload(
    file_id: UUID,
    user: CurrentUser,
    uc: Annotated[CompleteUploadUseCase, Depends(get_complete_upload_uc)],
) -> FileResponse:
    result = await uc.execute(
        CompleteUploadCommand(file_public_id=file_id, actor_public_id=user.public_id)
    )
    _raise_if_error(result)
    return FileResponse.from_view(result.value)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# Generic upload — proxied (multipart, one request)                          #
# --------------------------------------------------------------------------- #


@router.post(
    "/files",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file through the backend (proxied fallback)",
)
async def upload_direct(
    user: Annotated[CurrentUser, Depends(requires("file.upload"))],
    uc: Annotated[DirectUploadUseCase, Depends(get_direct_upload_uc)],
    file: UploadFile = File(...),
) -> FileResponse:
    name, content_type, data = await _read_upload(file)
    result = await uc.execute(
        DirectUploadCommand(
            uploader_public_id=user.public_id,
            original_name=name,
            content_type=content_type,
            data=data,
        )
    )
    _raise_if_error(result)
    return FileResponse.from_view(result.value)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# Read / delete                                                               #
# --------------------------------------------------------------------------- #


@router.get(
    "/files/mine",
    response_model=list[FileResponse],
    summary="List my uploaded files (lightweight reuse gallery)",
)
async def list_my_files(
    user: CurrentUser,
    uc: Annotated[ListMyFilesUseCase, Depends(get_list_my_files_uc)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[FileResponse]:
    result = await uc.execute(
        ListMyFilesQuery(
            uploader_public_id=user.public_id, limit=limit, offset=offset
        )
    )
    _raise_if_error(result)
    return [FileResponse.from_view(v) for v in result.value]  # type: ignore[union-attr]


@router.get(
    "/files/{file_id}",
    response_model=FileResponse,
    summary="Fetch a file's metadata + fresh presigned URLs",
)
async def get_file(
    file_id: UUID,
    user: OptionalCurrentUser,
    uc: Annotated[GetFileUseCase, Depends(get_get_file_uc)],
) -> FileResponse:
    actor = user.public_id if user else None
    result = await uc.execute(file_id, actor_public_id=actor)
    _raise_if_error(result)
    return FileResponse.from_view(result.value)  # type: ignore[union-attr]


@router.get(
    "/files/{file_id}/content",
    summary="Redirect to the file bytes in MinIO (presigned, offloads backend)",
)
async def get_file_content(
    file_id: UUID,
    user: OptionalCurrentUser,
    uc: Annotated[GetFileUseCase, Depends(get_get_file_uc)],
    download: bool = Query(default=False),
    variant: str | None = Query(default=None, max_length=32),
) -> RedirectResponse:
    actor = user.public_id if user else None
    result = await uc.execute(file_id, actor_public_id=actor)
    _raise_if_error(result)
    view = result.value  # type: ignore[union-attr]
    if variant is not None and variant in view.variants:
        target = view.variants[variant].url
    elif download:
        target = view.download_url
    else:
        target = view.url
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.delete(
    "/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a file (uploader or file.delete.any)",
)
async def delete_file(
    file_id: UUID,
    user: CurrentUser,
    uc: Annotated[DeleteFileUseCase, Depends(get_delete_file_uc)],
) -> None:
    if not user.has_any("file.delete.own", "file.delete.any", "file.upload"):
        raise HTTPException(status_code=403, detail="Permission denied")
    result = await uc.execute(
        DeleteFileCommand(
            file_public_id=file_id,
            actor_public_id=user.public_id,
            actor_can_delete_any=user.has("file.delete.any"),
        )
    )
    _raise_if_error(result)


# --------------------------------------------------------------------------- #
# Attachment sugar — posts & comments                                        #
# --------------------------------------------------------------------------- #


@router.post(
    "/posts/{post_id}/files",
    response_model=list[FileResponse],
    summary="Attach uploaded files to a post (author or moderator)",
)
async def attach_to_post(
    post_id: UUID,
    body: AttachFilesRequest,
    user: CurrentUser,
    uc: Annotated[AttachFilesUseCase, Depends(get_attach_files_uc)],
) -> list[FileResponse]:
    result = await uc.execute(
        AttachFilesCommand(
            actor_public_id=user.public_id,
            owner_type=FileOwnerType.POST,
            owner_public_id=post_id,
            file_ids=tuple(body.file_ids),
            actor_can_moderate=user.has("post.update.any"),
        )
    )
    _raise_if_error(result)
    return [FileResponse.from_view(v) for v in result.value]  # type: ignore[union-attr]


@router.get(
    "/posts/{post_id}/files",
    response_model=list[FileResponse],
    summary="List a post's attachments (public)",
)
async def list_post_files(
    post_id: UUID,
    uc: Annotated[ListOwnerFilesUseCase, Depends(get_list_owner_files_uc)],
) -> list[FileResponse]:
    result = await uc.execute(
        ListOwnerFilesQuery(owner_type=FileOwnerType.POST, owner_public_id=post_id)
    )
    _raise_if_error(result)
    return [FileResponse.from_view(v) for v in result.value]  # type: ignore[union-attr]


@router.post(
    "/comments/{comment_id}/files",
    response_model=list[FileResponse],
    summary="Attach uploaded files to a comment (author or moderator)",
)
async def attach_to_comment(
    comment_id: UUID,
    body: AttachFilesRequest,
    user: CurrentUser,
    uc: Annotated[AttachFilesUseCase, Depends(get_attach_files_uc)],
) -> list[FileResponse]:
    result = await uc.execute(
        AttachFilesCommand(
            actor_public_id=user.public_id,
            owner_type=FileOwnerType.COMMENT,
            owner_public_id=comment_id,
            file_ids=tuple(body.file_ids),
            actor_can_moderate=user.has("comment.update.any"),
        )
    )
    _raise_if_error(result)
    return [FileResponse.from_view(v) for v in result.value]  # type: ignore[union-attr]


@router.get(
    "/comments/{comment_id}/files",
    response_model=list[FileResponse],
    summary="List a comment's attachments (public)",
)
async def list_comment_files(
    comment_id: UUID,
    uc: Annotated[ListOwnerFilesUseCase, Depends(get_list_owner_files_uc)],
) -> list[FileResponse]:
    result = await uc.execute(
        ListOwnerFilesQuery(
            owner_type=FileOwnerType.COMMENT, owner_public_id=comment_id
        )
    )
    _raise_if_error(result)
    return [FileResponse.from_view(v) for v in result.value]  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# Avatars                                                                     #
# --------------------------------------------------------------------------- #


@router.post(
    "/users/me/avatar",
    response_model=FileResponse,
    summary="Upload and set the caller's avatar (image only)",
)
async def set_my_avatar(
    user: CurrentUser,
    uc: Annotated[SetAvatarUseCase, Depends(get_set_avatar_uc)],
    file: UploadFile = File(...),
) -> FileResponse:
    name, content_type, data = await _read_upload(file)
    result = await uc.execute(
        SetAvatarCommand(
            user_public_id=user.public_id,
            original_name=name,
            content_type=content_type,
            data=data,
        )
    )
    _raise_if_error(result)
    return FileResponse.from_view(result.value)  # type: ignore[union-attr]


@router.get(
    "/users/{user_id}/avatar",
    summary="Redirect to a user's avatar image (404 if none)",
)
async def get_user_avatar(
    user_id: UUID,
    uc: Annotated[GetAvatarUseCase, Depends(get_get_avatar_uc)],
    variant: str | None = Query(default=None, max_length=32),
) -> RedirectResponse:
    result = await uc.execute(user_id)
    _raise_if_error(result)
    view = result.value  # type: ignore[union-attr]
    if view is None:
        raise HTTPException(status_code=404, detail="No avatar set")
    target = (
        view.variants[variant].url
        if variant is not None and variant in view.variants
        else view.url
    )
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


# --------------------------------------------------------------------------- #
# Category images                                                             #
# --------------------------------------------------------------------------- #


@router.post(
    "/categories/{category_id}/image",
    response_model=FileResponse,
    summary="Set a category image (owner or category.manage)",
)
async def set_category_image(
    category_id: UUID,
    db: DbSession,
    user: Annotated[CurrentUser, Depends(requires("category.create"))],
    uc: Annotated[SetCategoryImageUseCase, Depends(get_set_category_image_uc)],
    file: UploadFile = File(...),
) -> FileResponse:
    # Ownership: właściciel kategorii LUB moderator (category.manage).
    owner_row = db.execute(
        text(
            "SELECT u.public_id FROM categories c "
            "LEFT JOIN users u ON u.id = c.owner_id "
            "WHERE c.public_id = :cid"
        ),
        {"cid": str(category_id)},
    ).first()
    if owner_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    is_owner = owner_row[0] is not None and str(owner_row[0]) == str(user.public_id)
    if not is_owner and not user.has("category.manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the category owner or a moderator can set its image",
        )
    name, content_type, data = await _read_upload(file)
    result = await uc.execute(
        SetCategoryImageCommand(
            actor_public_id=user.public_id,
            category_public_id=category_id,
            original_name=name,
            content_type=content_type,
            data=data,
        )
    )
    _raise_if_error(result)
    return FileResponse.from_view(result.value)  # type: ignore[union-attr]


@router.get(
    "/categories/{category_id}/image",
    summary="Redirect to a category's image (404 if none)",
)
async def get_category_image(
    category_id: UUID,
    uc: Annotated[GetCategoryImageUseCase, Depends(get_get_category_image_uc)],
    variant: str | None = Query(default=None, max_length=32),
) -> RedirectResponse:
    result = await uc.execute(category_id)
    _raise_if_error(result)
    view = result.value  # type: ignore[union-attr]
    if view is None:
        raise HTTPException(status_code=404, detail="No category image set")
    target = (
        view.variants[variant].url
        if variant is not None and variant in view.variants
        else view.url
    )
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


# --------------------------------------------------------------------------- #
# Post (thread) icons — ikona wątku (owner_type=post_icon)                    #
# --------------------------------------------------------------------------- #


@router.post(
    "/posts/{post_id}/icon",
    response_model=FileResponse,
    summary="Set a post (thread) icon (author or post.update.any)",
)
async def set_post_icon(
    post_id: UUID,
    db: DbSession,
    user: CurrentUser,
    uc: Annotated[SetPostIconUseCase, Depends(get_set_post_icon_uc)],
    file: UploadFile = File(...),
) -> FileResponse:
    # Autoryzacja: autor wątku LUB moderator (post.update.any).
    author_row = db.execute(
        text(
            "SELECT u.public_id FROM posts p "
            "LEFT JOIN users u ON u.id = p.author_id "
            "WHERE p.public_id = :pid"
        ),
        {"pid": str(post_id)},
    ).first()
    if author_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    is_author = author_row[0] is not None and str(author_row[0]) == str(user.public_id)
    if not is_author and not user.has("post.update.any"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the thread author or a moderator can set its icon",
        )
    name, content_type, data = await _read_upload(file)
    result = await uc.execute(
        SetPostIconCommand(
            actor_public_id=user.public_id,
            post_public_id=post_id,
            original_name=name,
            content_type=content_type,
            data=data,
        )
    )
    _raise_if_error(result)
    return FileResponse.from_view(result.value)  # type: ignore[union-attr]


@router.get(
    "/posts/{post_id}/icon",
    summary="Redirect to a post's icon image (404 if none)",
)
async def get_post_icon(
    post_id: UUID,
    uc: Annotated[GetPostIconUseCase, Depends(get_get_post_icon_uc)],
    variant: str | None = Query(default=None, max_length=32),
) -> RedirectResponse:
    result = await uc.execute(post_id)
    _raise_if_error(result)
    view = result.value  # type: ignore[union-attr]
    if view is None:
        raise HTTPException(status_code=404, detail="No post icon set")
    target = (
        view.variants[variant].url
        if variant is not None and variant in view.variants
        else view.url
    )
    return RedirectResponse(url=target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
