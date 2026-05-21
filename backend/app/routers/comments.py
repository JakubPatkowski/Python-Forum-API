from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.permissions import has_role
from app.database import get_db
from app.models.comment import Comment
from app.models.user import User, UserRole
from app.schemas.comment import CommentCreate, CommentOut, CommentTreeOut, CommentUpdate
from app.services import comment_service

router = APIRouter()


# GET /api/comments?post_id=&tree=true
@router.get("/", response_model=list[CommentTreeOut] | list[CommentOut])
def list_comments(
    db: Annotated[Session, Depends(get_db)],
    post_id: int = Query(...),
    tree: bool = Query(default=True, description="Czy zwracać drzewo (z children) czy płaską listę"),
) -> list:
    if tree:
        return comment_service.list_comments_tree(db, post_id)
    flat = (
        db.query(Comment)
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return [CommentOut.model_validate(c) for c in flat]


# POST /api/comments
@router.post("/", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment(
    data: CommentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Comment:
    return comment_service.create_comment(db, data=data, author_id=current_user.id)


# PUT /api/comments/{comment_id}
@router.put("/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: int,
    data: CommentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Comment:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Komentarz nie istnieje")
    if comment.author_id != current_user.id and not has_role(current_user, UserRole.MODERATOR):
        raise HTTPException(status_code=403, detail="Brak uprawnień")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(comment, field, value)
    db.commit()
    db.refresh(comment)
    return comment


# DELETE /api/comments/{comment_id}
@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Komentarz nie istnieje")
    if comment.author_id != current_user.id and not has_role(current_user, UserRole.MODERATOR):
        raise HTTPException(status_code=403, detail="Brak uprawnień")
    db.delete(comment)
    db.commit()
