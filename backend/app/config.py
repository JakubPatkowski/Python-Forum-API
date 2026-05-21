from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfiguracja aplikacji ładowana z env / pliku .env."""

    # Baza danych — psycopg3 jest jedynym sterownikiem w runtime,
    # więc DSN musi zaczynać się od postgresql+psycopg://.
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/forum_wedkarskie"
    )

    # JWT
    SECRET_KEY: str = "zmien-ten-klucz-na-produkcji"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Aplikacja
    APP_NAME: str = "Forum Wędkarskie API"
    DEBUG: bool = False

    # CORS — w produkcji ogranicz do konkretnego origin frontu
    CORS_ALLOW_ORIGINS: list[str] = ["*"]

    # Komentarze
    MAX_COMMENT_DEPTH: int = 5

    # Uploady plików
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_MIME_TYPES: list[str] = [
        # Obrazy
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        # Wideo
        "video/mp4",
        "video/webm",
        # Dokumenty / pliki do pobrania
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
        "text/plain",
    ]

    # Panel administratora
    ADMIN_COOKIE_NAME: str = "admin_token"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
