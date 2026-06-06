"""HTTP endpoints for the post resource: ``/api/v1/posts``.

Permission gates:

* ``POST /``     — ``post.create``
* ``PUT /{id}``  — author OR ``post.update.any`` (ownership decided in use case)
* ``DELETE /{id}`` — author OR ``post.delete.any``

Listing and reading posts are public (no auth required).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.container import (
    get_create_post_uc,
    get_delete_post_uc,
    get_get_post_uc,
    get_list_posts_uc,
    get_update_post_uc,
)
from app.modules.content.application.commands import ListPostsQuery
from app.modules.content.application.use_cases import (
    CreatePostUseCase,
    DeletePostUseCase,
    GetPostUseCase,
    ListPostsUseCase,
    UpdatePostUseCase,
)
from app.modules.content.presentation.dto import (
    CreatePostRequest,
    PostListResponse,
    PostResponse,
    UpdatePostRequest,
)
from app.modules.identity.presentation.deps import (
    CurrentUser,
    requires,
)
from app.shared.application.result import Err
from app.shared.domain.errors import DomainError

router = APIRouter()


def _raise_if_error(result: object) -> None:
    if isinstance(result, Err):
        if isinstance(result.error, DomainError):
            raise result.error
        raise HTTPException(status_code=500, detail=str(result.error))


# --------------------------------------------------------------------------- #
# Read endpoints — public                                                     #
# --------------------------------------------------------------------------- #


@router.get(
    "",
    response_model=PostListResponse,
    summary="List posts (keyset pagination)",
)
async def list_posts(
    uc: Annotated[ListPostsUseCase, Depends(get_list_posts_uc)],
    cursor: str | None = Query(default=None, max_length=1024),
    limit: int = Query(default=20, ge=1, le=100),
    category_id: UUID | None = Query(default=None),
    tag: str | None = Query(default=None, max_length=60),
    author_id: UUID | None = Query(default=None),
) -> PostListResponse:
    result = await uc.execute(
        ListPostsQuery(
            cursor=cursor,
            limit=limit,
            category_public_id=category_id,
            tag_slug=tag,
            author_public_id=author_id,
        )
    )
    _raise_if_error(result)
    return PostListResponse.from_page(result.value)  # type: ignore[union-attr]


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="Fetch a single post",
)
async def get_post(
    post_id: UUID,
    uc: Annotated[GetPostUseCase, Depends(get_get_post_uc)],
) -> PostResponse:
    result = await uc.execute(post_id)
    _raise_if_error(result)
    return PostResponse.from_summary(result.value)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# Write endpoints — auth required                                             #
# --------------------------------------------------------------------------- #


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a post",
)
async def create_post(
    body: CreatePostRequest,
    user: Annotated[CurrentUser, Depends(requires("post.create"))],
    uc: Annotated[CreatePostUseCase, Depends(get_create_post_uc)],
) -> PostResponse:
    result = await uc.execute(body.to_command(author_public_id=user.public_id))
    _raise_if_error(result)
    return PostResponse.from_summary(result.value)  # type: ignore[union-attr]


@router.put(
    "/{post_id}",
    response_model=PostResponse,
    summary="Update a post (author or moderator)",
)
async def update_post(
    post_id: UUID,
    body: UpdatePostRequest,
    user: CurrentUser,
    uc: Annotated[UpdatePostUseCase, Depends(get_update_post_uc)],
) -> PostResponse:
    if not user.has_any("post.update.own", "post.update.any"):
        raise HTTPException(status_code=403, detail="Permission denied")
    result = await uc.execute(
        body.to_command(
            post_public_id=post_id,
            actor_public_id=user.public_id,
            actor_can_moderate=user.has("post.update.any"),
        )
    )
    _raise_if_error(result)
    return PostResponse.from_summary(result.value)  # type: ignore[union-attr]


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a post (author or moderator)",
)
async def delete_post(
    post_id: UUID,
    user: CurrentUser,
    uc: Annotated[DeletePostUseCase, Depends(get_delete_post_uc)],
) -> Response:
    if not user.has_any("post.delete.own", "post.delete.any"):
        raise HTTPException(status_code=403, detail="Permission denied")
    from app.modules.content.application.commands import DeletePostCommand

    result = await uc.execute(
        DeletePostCommand(
            post_public_id=post_id,
            actor_public_id=user.public_id,
            actor_can_moderate=user.has("post.delete.any"),
        )
    )
    _raise_if_error(result)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
