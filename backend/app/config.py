from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Wartość-pułapka: jeśli SECRET_KEY ma tę wartość poza trybem DEBUG, aplikacja
# odmawia startu (patrz walidator poniżej). Chroni przed wypuszczeniem buildu
# z domyślnym, publicznie znanym kluczem JWT.
_INSECURE_SECRET_KEY = "zmien-ten-klucz-na-produkcji"


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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_SECURE: bool = False  # set True behind HTTPS

    # Aplikacja
    APP_NAME: str = "Forum Wędkarskie API"
    DEBUG: bool = False

    # CORS — jawne originy wymagane przy allow_credentials=True
    # (wildcard "*" + credentials jest odrzucany przez przeglądarki).
    CORS_ALLOW_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://forum.local",
    ]

    # Komentarze
    MAX_COMMENT_DEPTH: int = 5

    # Uploady plików — limity i whitelista typów (moduł files / faza 3).
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB (wideo bywa większe)
    ALLOWED_MIME_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/avif",
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "audio/mpeg",
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/zip",
        "application/json",
        "text/plain",
        "text/markdown",
        "text/csv",
    ]
    SNIFF_GENERIC_MIME_TYPES: list[str] = [
        "application/zip",
        "application/octet-stream",
        "text/plain",
    ]
    SNIFF_BLOCKED_MIME_TYPES: list[str] = [
        "text/html",
        "application/x-dosexec",
        "application/x-executable",
        "application/x-sharedlib",
        "application/x-mach-binary",
        "text/x-shellscript",
        "application/x-msdownload",
    ]

    # --- MinIO / S3 object storage (moduł files) ---------------------------
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_PUBLIC_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "forum-files"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"

    FILE_DOWNLOAD_URL_TTL_SECONDS: int = 3600
    FILE_UPLOAD_URL_TTL_SECONDS: int = 900

    IMAGE_THUMBNAIL_SIZES: dict[str, int] = {
        "thumb": 256,
        "medium": 1024,
    }

    FILE_ORPHAN_RETENTION_HOURS: int = 24

    @property
    def minio_public_endpoint(self) -> str:
        """Endpoint do presigned URL-i — fallback na wewnętrzny endpoint."""
        return self.MINIO_PUBLIC_ENDPOINT or self.MINIO_ENDPOINT

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @model_validator(mode="after")
    def _reject_insecure_secret_key(self) -> "Settings":
        """Fail-fast: nie pozwól wystartować poza DEBUG z domyślnym SECRET_KEY.

        W K8s klucz wstrzykuje Secret `backend-secrets`; lokalnie (DEBUG=True
        lub własny .env) słaby default jest tolerowany dla wygody developmentu.
        """
        if not self.DEBUG and self.SECRET_KEY == _INSECURE_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY ma domyslna, niebezpieczna wartosc. Ustaw losowy "
                "SECRET_KEY w env (w K8s: Secret 'backend-secrets'; lokalnie: "
                ".env lub DEBUG=True na czas developmentu)."
            )
        return self


settings = Settings()
