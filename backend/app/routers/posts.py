from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.permissions import has_role
from app.database import get_db
from app.models.post import Post
from app.models.user import User, UserRole
from app.schemas.post import PostCreate, PostOut, PostUpdate

router = APIRouter()


# GET /api/posts?category_id=&skip=&limit=
@router.get("/", response_model=list[PostOut])
def list_posts(
    db: Annotated[Session, Depends(get_db)],
    category_id: int | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[Post]:
    query = db.query(Post)
    if category_id is not None:
        query = query.filter(Post.category_id == category_id)
    return query.order_by(Post.created_at.desc()).offset(skip).limit(limit).all()


# GET /api/posts/{post_id}
@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Annotated[Session, Depends(get_db)]) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post nie istnieje")
    return post


# POST /api/posts
@router.post("/", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    data: PostCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Post:
    post = Post(**data.model_dump(), author_id=current_user.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


# PUT /api/posts/{post_id}
@router.put("/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    data: PostUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Post:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post nie istnieje")
    if post.author_id != current_user.id and not has_role(current_user, UserRole.MODERATOR):
        raise HTTPException(status_code=403, detail="Brak uprawnień")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    db.commit()
    db.refresh(post)
    return post


# DELETE /api/posts/{post_id}
@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post nie istnieje")
    if post.author_id != current_user.id and not has_role(current_user, UserRole.MODERATOR):
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    db.delete(post)
    db.commit()
