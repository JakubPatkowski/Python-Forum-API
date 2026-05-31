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
    # UPLOAD_DIR zostaje tylko dla zgodności (PVC montaż); od fazy 3 bajty
    # trzymamy w MinIO, nie na dysku.
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB (wideo bywa większe)
    ALLOWED_MIME_TYPES: list[str] = [
        # Obrazy (wyświetlane inline, generujemy miniatury)
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/avif",
        # Wideo (wyświetlane inline w <video>)
        "video/mp4",
        "video/webm",
        "video/quicktime",
        # Audio (odtwarzane inline w <audio>)
        "audio/mpeg",  # mp3
        "audio/ogg",
        "audio/wav",
        "audio/x-wav",
        # Dokumenty / pliki do pobrania
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
    # Typy, które sniffing (python-magic) zwraca dla kontenerów OOXML/zip i
    # plików tekstowych — akceptowane, gdy zadeklarowany typ jest na whiteliście.
    SNIFF_GENERIC_MIME_TYPES: list[str] = [
        "application/zip",
        "application/octet-stream",
        "text/plain",
    ]
    # Typy zawsze odrzucane po sniffingu (wykonywalne / skrypty / HTML z JS).
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
    # Endpoint widziany przez BACKEND (wewnątrz sieci docker/k8s).
    MINIO_ENDPOINT: str = "localhost:9000"
    # Endpoint wstawiany do presigned URL-i (musi być osiągalny z PRZEGLĄDARKI).
    # Pusty → użyj MINIO_ENDPOINT. W docker-compose: "localhost:9000".
    MINIO_PUBLIC_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "forum-files"
    MINIO_SECURE: bool = False  # True za TLS
    MINIO_REGION: str = "us-east-1"

    # Czas ważności presigned URL-i (sekundy).
    FILE_DOWNLOAD_URL_TTL_SECONDS: int = 3600  # 1 h — pobieranie/podgląd
    FILE_UPLOAD_URL_TTL_SECONDS: int = 900  # 15 min — okno na PUT do MinIO

    # Miniatury obrazów: nazwa wariantu → maks. krawędź (px). Oryginał zawsze
    # zostaje; warianty generowane przy finalizacji uploadu (tylko obrazy).
    IMAGE_THUMBNAIL_SIZES: dict[str, int] = {
        "thumb": 256,
        "medium": 1024,
    }

    # Retencja plików osieroconych (standalone, niepodpiętych) w godzinach.
    # Po tym czasie cleanup job usuwa wiersz DB + obiekty z MinIO.
    FILE_ORPHAN_RETENTION_HOURS: int = 24

    @property
    def minio_public_endpoint(self) -> str:
        """Endpoint do presigned URL-i — fallback na wewnętrzny endpoint."""
        return self.MINIO_PUBLIC_ENDPOINT or self.MINIO_ENDPOINT

    # Panel administratora
    ADMIN_COOKIE_NAME: str = "admin_token"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
