# Security

## Password hashing

Passwords are hashed with **Argon2id** (`argon2-cffi`), the current OWASP
recommendation. Hashes are stored in `users.password_hash`; the raw password
never leaves the request boundary and is wrapped in a `RawPassword` value object
whose `__str__` does not leak the value.

## Authentication — JWT with refresh rotation

Tokens are signed with **PyJWT** (HS256).

| Token | Lifetime | Transport |
|-------|----------|-----------|
| Access | 15 minutes | Returned in the response body; sent as `Authorization: Bearer` |
| Refresh | 14 days | `httpOnly` cookie (`refresh_token`); `Secure` behind HTTPS |

- **Rotation:** every refresh issues a new refresh token and revokes the old one.
- **Reuse detection:** the `refresh_tokens` whitelist tracks token status (`active` / `rotated` / `revoked`). Presenting an already-rotated token is treated as theft and the session chain is invalidated.
- **Logout everywhere:** revoking all of a user's refresh tokens ends every session.

On the frontend the access token lives **only in JS memory**; after a reload the
session is restored via `POST /auth/refresh` (using the cookie) followed by
`/users/me`. A 401 triggers a single-flight refresh-and-retry.

## Authorization — RBAC + ACL

Roles form a hierarchy `user < moderator < admin`, backed by the tables
`roles`, `permissions`, `role_permissions`, `user_roles`, and `user_permissions`.

Effective permissions are computed as:

```
effective = (∪ permissions of the user's roles) ∪ grants \ denies
```

where per-user grants and denies come from `user_permissions`. Permission codes
are domain strings such as `post.create`, `comment.delete.any`, `category.create`,
`user.manage`. Endpoints declare requirements declaratively
(`Depends(requires("post.create"))`); ownership checks (author vs `*.any`) live
in the use case, not the router.

Any logged-in user holds `category.create` (a product decision); deleting a
category still requires `category.manage` (moderator and above).

## Input validation & request hardening

- **Pydantic v2** DTOs validate every request body.
- Errors are normalized to a single envelope: `{error: {code, message, field}}`.
- **Upload limits** are enforced by `LimitUploadSizeMiddleware`: a missing `Content-Length` → 411, an invalid value → 400, an oversized payload → 413. MIME types are whitelisted and content is sniffed to block executables and HTML.

## Security headers

`SecurityHeadersMiddleware` adds to every response:

- `X-Frame-Options: DENY` (clickjacking)
- `X-Content-Type-Options: nosniff`
- `Strict-Transport-Security` (HSTS)
- `Referrer-Policy: no-referrer`
- `Content-Security-Policy: default-src 'self'` (relaxed only for `/docs`, `/redoc`, `/openapi.json`, `/metrics`, which need inline assets)

## CORS

Origins are listed explicitly (`localhost:3000`, `localhost:5173`, `forum.local`).
A wildcard `*` is never combined with `allow_credentials=True`, since browsers
reject that pairing.

## Secrets

`SECRET_KEY` and the MinIO / Postgres credentials are injected from Kubernetes
`Secret` objects, never `ConfigMap`s. Config refuses to start outside `DEBUG`
mode if `SECRET_KEY` is left at its insecure default. Only `*.example.yaml`
secret templates are committed; real secret files are gitignored.

See also: [Architecture](./01-architecture.md) · [Database](./02-database.md).
