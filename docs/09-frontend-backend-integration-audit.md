# Frontend-Backend Integration Audit (v0.3.0)

Scope: review current frontend wiring vs backend API, identify missing connections, and note risks. This file is analysis-only; no code changes performed.

## What is already wired (high-level)
- Auth flow with refresh cookie and access token in memory (client + context).
- Core content: posts list/detail, comments tree, create/update/delete posts and comments.
- Files: upload via proxied POST /files, attach to posts/comments, show attachments, set avatar.

## Gaps and missing wiring

### Files module
- Presigned upload flow is implemented on backend but not used on frontend. Frontend always uses proxied upload via POST /files, and there is no UI to trigger /files/uploads + /complete flow. See backend endpoints at [backend/app/modules/files/presentation/routers/files.py](backend/app/modules/files/presentation/routers/files.py#L96-L133) and frontend uploader at [frontend/src/components/files/FileUploader.jsx](frontend/src/components/files/FileUploader.jsx#L23-L43).
- No UI or hooks for "My files" gallery (/files/mine) or for deleting an uploaded file (/files/{id}). Backend supports both in [backend/app/modules/files/presentation/routers/files.py](backend/app/modules/files/presentation/routers/files.py#L169-L248), but frontend hooks only cover upload/attach/avatar and do not expose list or delete [frontend/src/hooks/useFiles.js](frontend/src/hooks/useFiles.js#L1-L53).
- Category image upload is not wired. Backend supports POST /categories/{id}/image [backend/app/modules/files/presentation/routers/files.py](backend/app/modules/files/presentation/routers/files.py#L384-L414), while the frontend only reads the image for display [frontend/src/components/CategoryGlyph.jsx](frontend/src/components/CategoryGlyph.jsx#L1-L23) and has no hook/UI for setting it [frontend/src/hooks/useFiles.js](frontend/src/hooks/useFiles.js#L1-L53).
- Attachment URLs are used directly from list responses, with no refresh on expiry. The UI uses the presigned URLs as-is in the gallery [frontend/src/components/files/Attachments.jsx](frontend/src/components/files/Attachments.jsx#L1-L45), but does not call GET /files/{id} to refresh expired URLs.
- Orphan uploads are likely. Removing an item in the uploader only removes it from local state and does not call delete on the backend [frontend/src/components/files/FileUploader.jsx](frontend/src/components/files/FileUploader.jsx#L56-L61).

### Content editing gaps
- Comment edit flow only edits text and does not allow adding or removing attachments for existing comments. The edit UI is text-only [frontend/src/components/comments/CommentNode.jsx](frontend/src/components/comments/CommentNode.jsx#L56-L76), while attachments are only added on create [frontend/src/components/comments/CommentForm.jsx](frontend/src/components/comments/CommentForm.jsx#L16-L55).
- Post edit flow allows adding new attachments, but there is no UI to view or remove existing attachments inside the edit modal. The edit modal includes a new uploader only [frontend/src/components/compose/NewPostModal.jsx](frontend/src/components/compose/NewPostModal.jsx#L52-L118), while existing attachments are only shown on the post detail page [frontend/src/pages/PostPage.jsx](frontend/src/pages/PostPage.jsx#L55-L71).
- Category delete exists on backend but there is no UI action for it (only category selection). See backend delete endpoint [backend/app/modules/content/presentation/routers/categories.py](backend/app/modules/content/presentation/routers/categories.py#L40-L64) and category UI [frontend/src/pages/HomePage.jsx](frontend/src/pages/HomePage.jsx#L98-L132).

### Tag management
- Backend allows tag creation (moderator-only), but frontend only lists tags and offers no creation UI. Backend: [backend/app/modules/content/presentation/routers/tags.py](backend/app/modules/content/presentation/routers/tags.py#L33-L65). Frontend: [frontend/src/components/Panels.jsx](frontend/src/components/Panels.jsx#L1-L41).

### Admin endpoints
- Admin endpoints for users (roles, permissions, status) are available in the API but are not wired to any UI. (No direct frontend references found in current code.)

## Risks / potential issues
- Session expiration handler does not clear cached queries. On refresh failure, state is set to anonymous but query cache is not cleared (only logout clears it). This can leave private data in memory after an auth failure. See [frontend/src/auth/AuthContext.jsx](frontend/src/auth/AuthContext.jsx#L45-L58).
- File upload error feedback is generic. Upload errors are mapped to a static message, and backend error details (e.g., 415 unsupported type or max size) are not surfaced. See [frontend/src/components/files/FileUploader.jsx](frontend/src/components/files/FileUploader.jsx#L44-L98).

## Summary
- Core auth + posts/comments integration is solid.
- Files integration is partial: proxied upload + attach + read works, but presigned flow, file gallery, delete, and category image upload are missing.
- Editing flows are missing attachment management (add/remove for existing items).
- Admin and tag/category management features are not surfaced in the UI.

## Suggested next steps (implementation order)
1. Add presigned upload flow with fallback to proxied upload for local dev.
2. Add "My files" gallery with delete (cleanup orphan uploads).
3. Add category image upload UI (requires category.manage permission).
4. Extend edit flows to manage attachments (post and comment).
5. Add admin panel for roles/permissions/status (optional, depending on scope).
