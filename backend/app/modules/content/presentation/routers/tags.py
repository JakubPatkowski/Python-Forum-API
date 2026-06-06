"""HTTP endpoints for the tag resource: ``/api/v1/tags``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.container import get_create_tag_uc, get_list_tags_uc
from app.modules.content.application.use_cases import (
    CreateTagUseCase,
    ListTagsUseCase,
)
from app.modules.content.presentation.dto import (
    CreateTagRequest,
    TagResponse,
)
from app.modules.identity.presentation.deps import CurrentUserData, requires
from app.shared.application.result import Err
from app.shared.domain.errors import DomainError

router = APIRouter()


def _raise_if_error(result: object) -> None:
    if isinstance(result, Err):
        if isinstance(result.error, DomainError):
            raise result.error
        raise HTTPException(status_code=500, detail=str(result.error))


@router.get(
    "",
    response_model=list[TagResponse],
    summary="List all tags",
)
async def list_tags(
    uc: Annotated[ListTagsUseCase, Depends(get_list_tags_uc)],
) -> list[TagResponse]:
    result = await uc.execute()
    _raise_if_error(result)
    return [
        TagResponse(id=t.public_id, name=t.name, slug=t.slug)
        for t in result.value  # type: ignore[union-attr]
    ]


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tag (moderator+)",
)
async def create_tag(
    body: CreateTagRequest,
    _user: CurrentUserData = Depends(requires("tag.manage")),
    uc: CreateTagUseCase = Depends(get_create_tag_uc),
) -> TagResponse:
    result = await uc.execute(body.to_command())
    _raise_if_error(result)
    summary = result.value  # type: ignore[union-attr]
    return TagResponse(id=summary.public_id, name=summary.name, slug=summary.slug)
