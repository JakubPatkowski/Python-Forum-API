from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel value: if SECRET_KEY equals this outside DEBUG mode, the app refuses
# to start (see the validator below). Guards against shipping a build with the
# default, publicly known JWT key.
_INSECURE_SECRET_KEY = "change-this-key-in-production"


class Settings(BaseSettings):
    """Application configuration loaded from env / .env file."""

    # Database: psycopg3 is the only runtime driver, so the DSN must start
    # with postgresql+psycopg://.
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/forum_wedkarskie"

    # SQLAlchemy connection pool. Budget: replicas_max(HPA=3) * (size + overflow)
    # must fit within Postgres max_connections (default 100, minus headroom for
    # pgAdmin/migrations). 3 * (10+10) = 60 -> safe.
    # Previous defaults (5+10) were exhausted at ~150 VU (a 30 s timeout blocked
    # the event loop and broke /health/ready -- see docs/20).
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10
    # Short timeout = fast 5xx error instead of 30 s of hanging requests
    # (and readiness probes) when the pool is exhausted.
    DB_POOL_TIMEOUT_SECONDS: int = 5
    # Refresh connections every 30 min (prevents holding dead sockets).
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # JWT
    SECRET_KEY: str = "change-this-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_SECURE: bool = False  # set True behind HTTPS

    # Application
    APP_NAME: str = "Forum Wędkarskie API"
    DEBUG: bool = False

    # CORS -- explicit origins required when allow_credentials=True
    # (wildcard "*" + credentials is rejected by browsers).
    CORS_ALLOW_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://forum.local",
    ]

    # Comments
    MAX_COMMENT_DEPTH: int = 5

    # File uploads -- limits and a MIME type whitelist (files module / phase 3).
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB (video can be larger)
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

    # --- MinIO / S3 object storage (files module) -------------------------
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
        """Endpoint for presigned URLs -- falls back to the internal endpoint."""
        return self.MINIO_PUBLIC_ENDPOINT or self.MINIO_ENDPOINT

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @model_validator(mode="after")
    def _reject_insecure_secret_key(self) -> "Settings":
        """Fail-fast: refuse to start outside DEBUG with the default SECRET_KEY.

        In K8s the key is injected by the `backend-secrets` Secret; locally
        (DEBUG=True or a custom .env) the weak default is tolerated for
        development convenience.
        """
        if not self.DEBUG and self.SECRET_KEY == _INSECURE_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY has the default, insecure value. Set a random "
                "SECRET_KEY in env (in K8s: the 'backend-secrets' Secret; "
                "locally: .env or DEBUG=True during development)."
            )
        return self


settings = Settings()
