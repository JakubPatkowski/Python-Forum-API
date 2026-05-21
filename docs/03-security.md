# 03 — Bezpieczeństwo: JWT, RBAC + ACL, walidacja, headers

## 1. Hashowanie haseł — Argon2id

**Biblioteka:** `argon2-cffi`.

```python
# app/shared/infrastructure/auth/argon2_hasher.py
from argon2 import PasswordHasher, exceptions
from argon2.profiles import RFC_9106_LOW_MEMORY

class Argon2Hasher:
    """Implements IPasswordHasher using Argon2id."""

    def __init__(self) -> None:
        # RFC 9106 LOW MEMORY profile: time=3, memory=64MiB, parallelism=4
        # Wystarczy dla aplikacji studenckiej; produkcyjnie ~256 MiB.
        self._ph = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)

    def hash(self, plain: str) -> str:
        return self._ph.hash(plain)

    def verify(self, hashed: str, plain: str) -> bool:
        try:
            return self._ph.verify(hashed, plain)
        except exceptions.VerifyMismatchError:
            return False

    def needs_rehash(self, hashed: str) -> bool:
        return self._ph.check_needs_rehash(hashed)
```

**Sól:** argon2 generuje sól automatycznie (per-hash, 16 bajtów, w wynikowym stringu).
Nie trzeba kolumny `salt` w DB. Format: `$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>`.

**Polityka haseł:**
- minimum 8 znaków, dowolne (wg NIST SP 800-63B — żadnych "musi być cyfra i znak specjalny",
  to obniża entropię),
- blacklist top-100 najczęstszych haseł (`zxcvbn` lub własna lista).

---

## 2. JWT — access + refresh

### 2.1 Format tokenów

**Access token** (krótki, stateless):
```json
{
  "sub": "01HXXX...",        // user.public_id (UUID)
  "username": "jakub",
  "permissions": ["post.create", "comment.delete.own", ...],
  "iat": 1715801234,
  "exp": 1715802134,         // +15 min
  "type": "access",
  "jti": "01HYYY..."
}
```

**Refresh token** (długi, whitelist w DB):
```json
{
  "sub": "01HXXX...",
  "iat": 1715801234,
  "exp": 1717010834,         // +14 dni
  "type": "refresh",
  "jti": "01HZZZ..."          // == refresh_tokens.public_id
}
```

`jti` wnętrze refresh tokenu = `public_id` w tabeli `refresh_tokens`. W tabeli trzymamy też
`token_hash = sha256(raw_jwt)` żeby przy refreshu zweryfikować, że to ten sam token
(ochrona przed użyciem tylko `jti`).

### 2.2 Endpointy

```
POST /api/v1/auth/register          → 201, ApiResponse[UserResponse]
POST /api/v1/auth/login             → 200, { access, refresh, expires_in }
POST /api/v1/auth/refresh           → 200, { access, refresh, expires_in } (rotacja)
POST /api/v1/auth/logout            → 204 (revoke aktualny refresh)
POST /api/v1/auth/logout-all        → 204 (revoke wszystkie refresh tokens usera)
```

### 2.3 Token rotation + reuse detection

Workflow:

1. Login → wystawiamy `access1` + `refresh1`. Zapisujemy `refresh1` w DB z `status='active'`.
2. Klient po ~14 min wysyła `POST /refresh` z `refresh1`.
3. Backend:
   - dekoduje `refresh1`, sprawdza podpis i `exp`,
   - znajduje rekord po `jti`, sprawdza `status='active'` i `token_hash == sha256(refresh1)`,
   - **TWORZY `refresh2`**, ustawia `refresh1.status='rotated'`, `replaced_by=refresh2.id`,
   - zwraca `access2` + `refresh2`.
4. Klient zapomina `refresh1`, używa `refresh2`.

**Reuse detection:** jeśli ktoś po kroku 3 ponownie użyje `refresh1`:
- `status='rotated'` (już nie `active`) → atak,
- backend ustawia `status='revoked'` na **całym łańcuchu** (`replaced_by` rekursywnie) i emituje
  event `RefreshTokenReuseDetected(user_id)` → wylogowanie wszystkich sesji.

Implementacja w `RefreshSessionUseCase`:

```python
async def execute(self, refresh_jwt: str) -> Result[TokenPair, AuthError]:
    payload = self._tokens.decode_refresh(refresh_jwt)
    if not payload:
        return Err(InvalidRefreshToken())

    async with self.uow as uow:
        stored = await uow.refresh_tokens.get_by_public_id(payload.jti)
        if not stored:
            return Err(InvalidRefreshToken())

        if stored.status == TokenStatus.ROTATED:
            # reuse — atak. Revoke wszystko.
            await uow.refresh_tokens.revoke_chain(stored.id)
            await uow.commit()
            await self.bus.publish(RefreshTokenReuseDetected(stored.user_id))
            return Err(TokenReuseDetected())

        if stored.status != TokenStatus.ACTIVE or stored.is_expired:
            return Err(InvalidRefreshToken())

        if stored.token_hash != sha256_hex(refresh_jwt):
            return Err(InvalidRefreshToken())

        user = await uow.users.get(stored.user_id)
        if not user or not user.is_active:
            return Err(UserInactive())

        new_pair = self._tokens.issue_pair(user)
        stored.rotate_to(new_pair.refresh_record)
        await uow.refresh_tokens.add(new_pair.refresh_record)
        await uow.commit()
        return Ok(new_pair)
```

### 2.4 Cleanup expired tokens

Cron / scheduled task co 24h: `DELETE FROM refresh_tokens WHERE expires_at < now() AND status != 'active'`.
(Active się nie usuwa — może być w użyciu.) W k8s — `CronJob`.

### 2.5 Storage tokenów po stronie frontendu

- `access` → memory (np. axios interceptor + react context). **Nie** localStorage (XSS).
- `refresh` → `httpOnly Secure SameSite=Lax cookie` (nieosiągalne dla JS).

Backend logout = `Set-Cookie: refresh_token=; Max-Age=0` + revoke w DB.

---

## 3. RBAC + ACL

### 3.1 Model

- **Permission** (`Permission`) — atomowy element kontroli dostępu, np. `"post.delete.any"`.
- **Role** — bundle uprawnień. Predefined: `user`, `moderator`, `admin`. Custom: można dodawać.
- **User → Role** (M:N) — zwykle 1 rola, ale możliwe wiele.
- **User → Permission** (M:N, z flagą `granted=true|false`) — override per-user:
  - `granted=true`: dodaje uprawnienie **ponad** to co daje rola,
  - `granted=false`: cofa uprawnienie **pomimo** roli.

Efektywne uprawnienia liczy widok `v_user_effective_permissions` (patrz `docs/02-database-schema.md`).

### 3.2 Permission codes — konwencja

Format: `<resource>.<action>[.<scope>]`.

Examples:
- `post.read` (publiczne czytanie, nie używamy w sumie — endpoint publiczny)
- `post.create`
- `post.update.own`, `post.update.any`
- `post.delete.own`, `post.delete.any`
- `comment.update.own`, `comment.update.any`
- `file.delete.own`, `file.delete.any`
- `user.manage`, `role.manage`, `audit.read`

`.own` = autor zasobu, `.any` = dowolny zasób (moderator+).

### 3.3 Sprawdzanie uprawnień w endpointach

```python
# app/shared/presentation/deps.py
from fastapi import Depends, HTTPException, status
from typing import Annotated, Callable

def requires(*permission_codes: str) -> Callable:
    """Builder dependency: OR check.

    requires('post.delete.own', 'post.delete.any')  -> any of these
    """
    async def check(
        user: Annotated["User", Depends(get_current_user)],
    ) -> "User":
        if not any(code in user.permissions for code in permission_codes):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")
        return user
    return check
```

Użycie:

```python
@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: PostPublicId,
    user: Annotated[User, Depends(requires("post.delete.own", "post.delete.any"))],
    uc:   Annotated[DeletePostUseCase, Depends(get_delete_post_uc)],
) -> None:
    result = await uc.execute(DeletePostCommand(post_id, requester=user))
    present_or_raise(result)
```

**Sprawdzenie ownership** (`.own` vs `.any`) odbywa się **w use case**, nie w dependency.
Dependency tylko sprawdza, że ma jakiekolwiek uprawnienie z listy. Use case decyduje:

```python
class DeletePostUseCase:
    async def execute(self, cmd: DeletePostCommand) -> Result[None, DomainError]:
        async with self.uow as uow:
            post = await uow.posts.get_by_public_id(cmd.post_id)
            if not post:
                return Err(NotFoundError("post", cmd.post_id))

            if post.author_id != cmd.requester.id and "post.delete.any" not in cmd.requester.permissions:
                return Err(PermissionDeniedError("post.delete.any required for someone else's post"))

            post.mark_deleted()
            await uow.commit()
            for ev in post.pull_events():
                await self.bus.publish(ev)
            return Ok(None)
```

### 3.4 Skąd `user.permissions` w request scope?

Z JWT (access token zawiera listę uprawnień przy wystawieniu). Plus / minus:

- ✅ Stateless — żadnego DB lookup na każdy request.
- ❌ Token "stary" 15 minut po zmianie uprawnień. Akceptowalne dla MVP.

Jeśli potrzebujemy natychmiastowego revoke uprawnień — invalidate access tokens przez krótki TTL
+ blocklist `jti` w Redis (przyszłość). MVP: czekamy do refreshu, max 15 min.

---

## 4. Walidacja danych wejściowych

### 4.1 Walidacja DTO — Pydantic v2

```python
from pydantic import BaseModel, EmailStr, field_validator, Field

class RegisterUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_not_in_common(cls, v: str) -> str:
        if v.lower() in COMMON_PASSWORDS:
            raise ValueError("password is too common")
        return v

    def to_command(self) -> RegisterUserCommand: ...
```

### 4.2 Walidacja plików

**Backend:**

```python
# app/modules/files/application/use_cases/upload_file.py
ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "video/mp4", "video/webm",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/zip",
    "text/plain",
}
MAX_BYTES = 10 * 1024 * 1024

async def execute(self, cmd: UploadFileCommand) -> Result[FileResponse, DomainError]:
    # 1) MIME sniffing zamiast wierzenia w Content-Type z headera
    import magic
    head = await cmd.stream.read(2048)
    sniffed = magic.from_buffer(head, mime=True)
    if sniffed not in ALLOWED_TYPES:
        return Err(UnsupportedMediaType(sniffed))

    # 2) Sprawdzenie rozmiaru (streaming, bez ładowania całości do RAM)
    sha = hashlib.sha256()
    sha.update(head)
    size = len(head)
    storage_key = f"{uuid4()}{extension_for(sniffed)}"

    async with self.storage.open_write(storage_key) as sink:
        await sink.write(head)
        while chunk := await cmd.stream.read(65536):
            size += len(chunk)
            if size > MAX_BYTES:
                await self.storage.delete(storage_key)
                return Err(FileTooLarge(size))
            sha.update(chunk)
            await sink.write(chunk)
    # ...
```

**Frontend:** dodatkowo walidacja `accept="..."` i `file.size < MAX` przed uploadem,
ale to UX — backend musi i tak walidować.

---

## 5. Security headers — middleware

```python
# app/shared/presentation/middleware/security_headers.py
class SecurityHeadersMiddleware:
    HEADERS = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        # CSP osobno bo bywa skomplikowane — patrz niżej
    }
    async def __call__(self, request, call_next):
        resp = await call_next(request)
        for k, v in self.HEADERS.items():
            resp.headers.setdefault(k, v)
        return resp
```

**CSP** (Content-Security-Policy): nie wystawiamy z FastAPI — frontend nginx
ustawia w `nginx.conf`:

```nginx
add_header Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; connect-src 'self' ws: wss:; style-src 'self' 'unsafe-inline'" always;
```

---

## 6. CORS

W `app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,    # np. ["http://forum.local"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
```

W minikube z Ingress NGINX cały ruch ma jeden origin — CORS staje się prosty.

---

## 7. Rate limiting

`slowapi` (wrapper na `limits` library, Redis backend opcjonalny).

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login")
@limiter.limit("5/minute")
async def login(...): ...

@router.post("/register")
@limiter.limit("3/hour")
async def register(...): ...

@router.post("/refresh")
@limiter.limit("60/minute")
async def refresh(...): ...
```

Bez Redis = in-memory limiter, per-instance. W skali wielu replik — false negatives. Akceptowalne dla MVP.
Docelowo Redis backend.

---

## 8. Audit logging

Wszystkie eventy domeny → consumer `audit` zapisuje do `audit_log`. Plus, w endpointach
loggujemy każdy request (method, path, user_id, status, latency) jako structured log.

```python
# app/shared/presentation/middleware/request_logging.py
async def __call__(self, request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info("http_request",
        method=request.method, path=request.url.path,
        status=response.status_code, elapsed_ms=elapsed_ms)
    return response
```

---

## 9. Sekrety

**Wszystkie sekrety przez `Secret` w k8s**, nie w ConfigMap. `pydantic-settings` czyta z env.

```yaml
# k8s/backend/secret.yaml — NIE commitować z prawdziwymi wartościami
apiVersion: v1
kind: Secret
metadata:
  name: backend-secrets
  namespace: forum-wedkarskie
type: Opaque
stringData:
  SECRET_KEY: "<random 64 bytes hex>"
  POSTGRES_PASSWORD: "..."
  RABBITMQ_PASSWORD: "..."
```

W deployment:

```yaml
envFrom:
  - configMapRef: { name: backend-config }
  - secretRef:    { name: backend-secrets }
```

Generowanie sekretu: `openssl rand -hex 64`.

W repo: `k8s/backend/secret.example.yaml` z placeholderami. Prawdziwy plik w `.gitignore`.

---

## 10. Checklist OWASP Top 10 (skrócone)

| OWASP                       | Środek zaradczy                                                              |
|-----------------------------|------------------------------------------------------------------------------|
| A01 Broken Access Control   | RBAC + ACL, sprawdzenie ownership w use case, `requires()` w deps           |
| A02 Cryptographic Failures  | Argon2id, JWT podpisany silnym kluczem, HTTPS w produkcji                   |
| A03 Injection               | ORM (parametrized queries), Pydantic walidacja, brak `eval`/`exec`          |
| A04 Insecure Design         | Threat model: refresh token reuse, file upload abuse, brute-force login     |
| A05 Security Misconfig      | Security headers middleware, secret rotation, CORS zacieśniony              |
| A06 Vulnerable Components   | `pip-audit` w CI, Dependabot                                                |
| A07 Identification & Auth   | Rate limit na `/login`, lockout po 10 failed (opcjonalnie), Argon2          |
| A08 Software Integrity      | Obrazy z konkretnymi tagami (nie `:latest` w prod), `imagePullPolicy`       |
| A09 Logging & Monitoring    | structlog JSON, audit_log, Prometheus alerty (failed login spike, 5xx)     |
| A10 SSRF                    | Brak user-controlled URL fetchów. Jeśli embed obrazków zewn. — proxy + lista|
