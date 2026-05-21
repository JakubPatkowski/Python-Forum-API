"""Funkcje pomocnicze do bezpieczeństwa: hasła + JWT."""
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Zwraca hash bcrypt podanego hasła."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Weryfikuje hasło wobec hasha."""
    return _pwd_context.verify(plain, hashed)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Tworzy podpisany token JWT z claim `sub` i datą wygaśnięcia."""
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "iat": now, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Dekoduje token JWT, rzuca JWTError gdy niepoprawny / wygasły."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# Re-export, żeby moduły wyżej mogły łapać wyjątek bez importu jose
JWTDecodeError = JWTError
