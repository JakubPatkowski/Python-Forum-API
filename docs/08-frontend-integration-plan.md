# 08 — Plan podlaczenia frontendu do API (V2: MinIO + presigned URLs)

Cel dokumentu: opisac docelowy flow integracji frontendu z nowym API files oraz
potencjalne problemy. Dokument jest niezalezny od konkretnej implementacji UI.

---

## 1. Bazowy kontrakt API

- Base URL: `/api/v1`
- Auth: access token w pamieci (context), refresh token w cookie httpOnly.
- CORS: `allow_credentials=true`, jawne originy (np. `http://localhost:5173`).
- Backend zwraca bledy w kopercie `{error:{code,message,field}}`.

---

## 2. Autoryzacja (front)

### 2.1 Logowanie
1. `POST /auth/login` -> access token w odpowiedzi, refresh cookie ustawiany
   przez backend.
2. Access token trzymaj tylko w pamieci (React context, nie localStorage).

### 2.2 Odswiezanie tokenu
- Przy 401 z API: `POST /auth/refresh` (cookie).
- Jesli refresh sie uda, ponow pierwotne zadanie.
- Jesli refresh sie nie uda: logout i czyszczenie stanu frontu.

### 2.3 Uwaga o CORS i cookies
- Dla cookie refresh konieczne jest `withCredentials: true` w axios/fetch.
- Origin musi byc wpisany w `CORS_ALLOW_ORIGINS` backendu.

---

## 3. Upload plikow (presigned, zalecany)

### 3.1 Flow presigned
1. `POST /files/uploads` z body:
   - `original_name`, `content_type`, `size_bytes`
2. Backend zwraca `upload_url` + `file_id`.
3. Front robi `PUT upload_url` z raw bytes (bez backendu).
4. `POST /files/uploads/{file_id}/complete`.
5. Backend zwraca `FileResponse` (z URL do podgladu i downloadu).

### 3.2 Podpinanie do obiektow
- Post: `POST /posts/{post_id}/files` z `file_ids[]`.
- Comment: `POST /comments/{comment_id}/files`.
- Avatar: `POST /users/me/avatar` (multipart, proxied).
- Category image: `POST /categories/{id}/image` (multipart, proxied).

### 3.3 Proxied fallback (opcjonalny)
- `POST /files` (multipart). Uzywac gdy klient nie ma dostepu do MinIO.

---

## 4. Renderowanie i pobieranie plikow

### 4.1 Metadane i URL-e
- `GET /files/{id}` zwraca `FileResponse`:
  - `url` (inline dla media)
  - `download_url` (wymusza download)
  - `variants` (miniatury)

### 4.2 Wyswietlanie
- `kind=image`: `<img src=url>` lub `variants.thumb` jako miniatura.
- `kind=video`: `<video controls src=url>`
- `kind=audio`: `<audio controls src=url>`
- `kind=document`: pokaz link do `download_url`.

### 4.3 Szybki redirect
- `GET /files/{id}/content?variant=thumb` zwraca 307 do MinIO.

---

## 5. Avatary i obrazki kategorii

- Avatar: `GET /users/{id}/avatar` -> 307 do MinIO (404 gdy brak).
- Category image: `GET /categories/{id}/image` -> 307 do MinIO.
- Dla miniatur: `?variant=thumb`.

---

## 6. Potencjalne problemy i jak je obejsc

1. **CORS dla MinIO**
   - Presigned URL jest bezposrednio na MinIO. MinIO musi pozwolic na origin
     frontu (CORS w MinIO, albo reverse proxy).
2. **Wygasanie URL**
   - `upload_url` i `download_url` maja TTL. Front powinien obslugiwac
     403/Expired i pobrac nowy `FileResponse`.
3. **Clock skew**
   - Rozjazd czasu klienta i serwera moze skracac czas waznosci URL.
4. **Content-Type mismatch**
   - Backend waliduje MIME po sniffingu. Zly typ -> 415.
5. **Duze pliki**
   - Sprawdz `MAX_UPLOAD_SIZE_BYTES` i pokaz jasny komunikat.
6. **Osirocone pliki**
   - Upload bez attach -> plik zostaje standalone. Cleanup robi CronJob.
   - Front moze dodac przycisk "usun" albo nie finalizowac uploadu.
7. **Redirect 307**
   - Przy pobieraniu uzywaj standardowego `fetch`/`<img>` (przegladarka
     obsluguje redirect). Dla `download_url` oczekuj pobrania pliku.

---

## 7. Minimalny plan prac frontend (MVP)

1. Auth flow (login, refresh, logout) + `withCredentials`.
2. Post list + post view + comment tree.
3. Presigned upload + attach do post/comment.
4. Renderowanie plikow w postach i komentarzach.
5. Avatar + category image.

---

## 8. Checklist integracji

- [ ] `baseURL` -> `/api/v1`
- [ ] `withCredentials: true`
- [ ] Refresh interceptor przy 401
- [ ] Upload presigned -> complete -> attach
- [ ] Render inline dla media, download dla dokumentow
- [ ] Avatar i category image dzialaja z redirectem
- [ ] Obsluga bledu `UNSUPPORTED_MEDIA_TYPE` (415)
