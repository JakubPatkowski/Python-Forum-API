from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_moderator
from app.database import get_db
from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryOut

router = APIRouter()


# GET /api/categories
@router.get("/", response_model=list[CategoryOut])
def list_categories(db: Annotated[Session, Depends(get_db)]) -> list[Category]:
    return db.query(Category).order_by(Category.name).all()


# POST /api/categories  (moderator+ / admin)
@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    _user: Annotated[User, Depends(require_moderator)],
    db: Annotated[Session, Depends(get_db)],
) -> Category:
    if db.query(Category).filter(Category.name == data.name).first():
        raise HTTPException(status_code=400, detail="Kategoria o tej nazwie już istnieje")
    category = Category(name=data.name, description=data.description)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


# DELETE /api/categories/{category_id}  (moderator+ / admin)
@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    _user: Annotated[User, Depends(require_moderator)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategoria nie istnieje")
    db.delete(category)
    db.commit()
