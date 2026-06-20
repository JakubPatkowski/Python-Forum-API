"""HTTP endpoints for the category resource: ``/api/v1/categories``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text

from app.container import (
    get_create_category_uc,
    get_delete_category_uc,
    get_list_categories_uc,
)
from app.modules.content.application.commands import DeleteCategoryCommand
from app.modules.content.application.use_cases import (
    CreateCategoryUseCase,
    DeleteCategoryUseCase,
    ListCategoriesUseCase,
)
from app.modules.content.presentation.dto import (
    CategoryResponse,
    CreateCategoryRequest,
)
from app.modules.identity.presentation.deps import CurrentUserData, requires
from app.shared.application.result import Err
from app.shared.domain.errors import DomainError
from app.shared.presentation.deps import DbSession

router = APIRouter()


def _raise_if_error(result: object) -> None:
    if isinstance(result, Err):
        if isinstance(result.error, DomainError):
            raise result.error
        raise HTTPException(status_code=500, detail=str(result.error))


@router.get(
    "",
    response_model=list[CategoryResponse],
    summary="List categories",
)
async def list_categories(
    db: DbSession,
    uc: Annotated[ListCategoriesUseCase, Depends(get_list_categories_uc)],
) -> list[CategoryResponse]:
    result = await uc.execute()
    _raise_if_error(result)
    # Fetch owners in a single query (category public_id -> owner public_id).
    owners = {
        str(row[0]): row[1]
        for row in db.execute(
            text(
                "SELECT c.public_id, u.public_id FROM categories c "
                "LEFT JOIN users u ON u.id = c.owner_id"
            )
        ).all()
    }
    return [
        CategoryResponse.from_summary(c, owner_id=owners.get(str(c.public_id)))
        for c in result.value  # type: ignore[union-attr]
    ]


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new category (any authenticated user)",
)
async def create_category(
    body: CreateCategoryRequest,
    db: DbSession,
    user: CurrentUserData = Depends(requires("category.create")),
    uc: CreateCategoryUseCase = Depends(get_create_category_uc),
) -> CategoryResponse:
    result = await uc.execute(body.to_command())
    _raise_if_error(result)
    summary = result.value  # type: ignore[union-attr]
    # Persist the category owner (creator). Done as a separate UPDATE so we
    # don't mix ownership into the Category domain aggregate.
    db.execute(
        text(
            "UPDATE categories SET owner_id = "
            "(SELECT id FROM users WHERE public_id = :uid) "
            "WHERE public_id = :cid"
        ),
        {"uid": str(user.public_id), "cid": str(summary.public_id)},
    )
    db.commit()
    return CategoryResponse.from_summary(summary, owner_id=user.public_id)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a category (moderator+)",
)
async def delete_category(
    category_id: UUID,
    _user: CurrentUserData = Depends(requires("category.manage")),
    uc: DeleteCategoryUseCase = Depends(get_delete_category_uc),
) -> Response:
    result = await uc.execute(DeleteCategoryCommand(category_public_id=category_id))
    _raise_if_error(result)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
