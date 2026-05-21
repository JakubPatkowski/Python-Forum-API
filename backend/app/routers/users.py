from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.permissions import require_admin
from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserOut, UserRoleUpdate, UserUpdate

router = APIRouter()


# GET /api/users/{user_id}
@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Annotated[Session, Depends(get_db)]) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")
    return user


# PUT /api/users/me
@router.put("/me", response_model=UserOut)
def update_me(
    update_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    data = update_data.model_dump(exclude_unset=True)
    if "username" in data and data["username"]:
        existing = db.query(User).filter(User.username == data["username"]).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Nazwa użytkownika jest już zajęta")
        current_user.username = data["username"]
    if "email" in data and data["email"]:
        existing = db.query(User).filter(User.email == data["email"]).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Email jest już zajęty")
        current_user.email = data["email"]

    db.commit()
    db.refresh(current_user)
    return current_user


# DELETE /api/users/me
@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    db.delete(current_user)
    db.commit()


# PATCH /api/users/{user_id}/role  (admin only)
@router.patch("/{user_id}/role", response_model=UserOut)
def change_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Admin zmienia rolę dowolnego użytkownika.

    Walidacja kolejności: 404 (nie istnieje) → 400 (próba odebrania sobie roli admina).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")
    if user.id == admin.id and payload.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=400,
            detail="Nie możesz odebrać samemu sobie roli administratora",
        )
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


# PATCH /api/users/{user_id}/active  (admin only — blokowanie konta)
@router.patch("/{user_id}/active", response_model=UserOut)
def set_user_active(
    user_id: int,
    is_active: bool,
    admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Użytkownik nie istnieje")
    if user.id == admin.id and not is_active:
        raise HTTPException(status_code=400, detail="Nie możesz zablokować własnego konta")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user
