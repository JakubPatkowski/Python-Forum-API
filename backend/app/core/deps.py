"""Wspólne FastAPI Dependencies."""
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import JWTDecodeError, decode_access_token
from app.database import get_db
from app.models.user import User

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _user_from_token(token: str, db: Session) -> User:
    """Dekoduje token i pobiera użytkownika z bazy. Rzuca 401 gdy cokolwiek nie gra."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nieprawidłowe dane uwierzytelniające",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if not isinstance(username, str):
            raise credentials_exc
    except JWTDecodeError:
        raise credentials_exc

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exc
    return user


def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Wymaga tokenu Bearer w nagłówku Authorization."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Brak tokenu uwierzytelniającego",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _user_from_token(token, db)


def get_current_user_optional(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User | None:
    """Zwraca usera jeśli podany prawidłowy token, w przeciwnym razie None."""
    if not token:
        return None
    try:
        return _user_from_token(token, db)
    except HTTPException:
        return None


def get_admin_from_cookie(
    db: Annotated[Session, Depends(get_db)],
    admin_token: Annotated[str | None, Cookie(alias=settings.ADMIN_COOKIE_NAME)] = None,
) -> User:
    """Dependency dla panelu admina — czyta JWT z cookie i wymaga roli ADMIN."""
    from app.models.user import UserRole  # late import — unika cykli

    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wymagane logowanie do panelu admina",
        )
    user = _user_from_token(admin_token, db)
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wymagana rola ADMIN",
        )
    return user
