#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema to a JSON file — no database required.

Used by the `API Documentation` GitHub Actions workflow to render static Redoc
docs and publish them to GitHub Pages. Can also be run locally:

    uv run python scripts/export_openapi.py              # -> openapi.json
    uv run python scripts/export_openapi.py docs/api.json # custom path

Why the env setup below:
    * `create_app()` runs at import time (``app.main``). Its settings validator
      refuses to boot outside DEBUG with the default SECRET_KEY, so we set
      DEBUG=true for this throwaway, side-effect-free schema dump.
    * `create_app()` also does ``mkdir(UPLOAD_DIR)``; the production default is
      ``/app/uploads`` which is not writable on a CI runner, so we point it at a
      temp directory.
    * No DB connection is opened: ``app.openapi()`` only introspects the routes.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Configure a safe, dependency-free environment *before* importing the app.
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SECRET_KEY", "openapi-export-placeholder-not-a-secret")
os.environ.setdefault("UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "forum-openapi-uploads"))

# Make the backend package importable when run from the backend/ directory.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.main import app  # noqa: E402  (import after env setup is intentional)


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    schema = app.openapi()
    out_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False), encoding="utf-8")

    title = schema.get("info", {}).get("title", "API")
    version = schema.get("info", {}).get("version", "?")
    path_count = len(schema.get("paths", {}))
    print(f"Wrote {out_path} — {title} v{version} ({path_count} paths)")


if __name__ == "__main__":
    main()
