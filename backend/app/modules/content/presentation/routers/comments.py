"""HTTP endpoints for the comment resource: ``/api/v1/comments``.

The flat DFS tree is exposed under ``GET /api/v1/posts/{post_id}/comments``
via :mod:`app.modules.content.presentation.routers.posts_comments`. Here
we expose the comment-level operations: create / read-by-id / edit / delete.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.container import (
    get_add_comment_uc,
    get_comment_tree_uc,
    get_delete_comment_uc,
    get_update_comment_uc,
)
from app.modules.content.application.commands import DeleteCommentCommand
from app.modules.content.application.use_cases import (
    AddCommentUseCase,
    DeleteCommentUseCase,
    GetCommentTreeUseCase,
    UpdateCommentUseCase,
)
from app.modules.content.presentation.dto import (
    AddCommentRequest,
    CommentResponse,
    CommentTreeResponse,
    UpdateCommentRequest,
)
from app.modules.identity.presentation.deps import (
    CurrentUser,
    requires,
)
from app.shared.application.result import Err
from app.shared.domain.errors import DomainError


router = APIRouter()


def _raise_if_error(result) -> None:
    if isinstance(result, Err):
        if isinstance(result.error, DomainError):
            raise result.error
        raise HTTPException(status_code=500, detail=str(result.error))


@router.get(
    "",
    response_model=CommentTreeResponse,
    summary="Comment tree for a post (DFS-ordered)",
)
async def get_tree(
    uc: Annotated[GetCommentTreeUseCase, Depends(get_comment_tree_uc)],
    post_id: Annotated[UUID, Query(description="UUID of the post to fetch comments for")],
) -> CommentTreeResponse:
    result = await uc.execute(post_id)
    _raise_if_error(result)
    return CommentTreeResponse.from_summaries(result.value)  # type: ignore[union-attr]


@router.post(
    "",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment (top-level or reply)",
)
async def add_comment(
    body: AddCommentRequest,
    user: Annotated[CurrentUser, Depends(requires("comment.create"))],
    uc: Annotated[AddCommentUseCase, Depends(get_add_comment_uc)],
) -> CommentResponse:
    result = await uc.execute(body.to_command(author_public_id=user.public_id))
    _raise_if_error(result)
    return CommentResponse.from_summary(result.value)  # type: ignore[union-attr]


@router.put(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Edit a comment (author or moderator)",
)
async def update_comment(
    comment_id: UUID,
    body: UpdateCommentRequest,
    user: CurrentUser,
    uc: Annotated[UpdateCommentUseCase, Depends(get_update_comment_uc)],
) -> CommentResponse:
    if not user.has_any("comment.update.own", "comment.update.any"):
        raise HTTPException(status_code=403, detail="Permission denied")
    result = await uc.execute(
        body.to_command(
            comment_public_id=comment_id,
            actor_public_id=user.public_id,
            actor_can_moderate=user.has("comment.update.any"),
        )
    )
    _raise_if_error(result)
    return CommentResponse.from_summary(result.value)  # type: ignore[union-attr]


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a comment (author or moderator)",
)
async def delete_comment(
    comment_id: UUID,
    user: CurrentUser,
    uc: Annotated[DeleteCommentUseCase, Depends(get_delete_comment_uc)],
) -> Response:
    if not user.has_any("comment.delete.own", "comment.delete.any"):
        raise HTTPException(status_code=403, detail="Permission denied")
    result = await uc.execute(
        DeleteCommentCommand(
            comment_public_id=comment_id,
            actor_public_id=user.public_id,
            actor_can_moderate=user.has("comment.delete.any"),
        )
    )
    _raise_if_error(result)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
