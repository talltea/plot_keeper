from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from . import db

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "plotkeeper.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(database_path: str | os.PathLike[str] | None = None) -> Flask:
    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        static_url_path="/",
    )
    app.config["DATABASE_PATH"] = str(Path(database_path) if database_path else DEFAULT_DB_PATH)

    db.init_app(app)
    with app.app_context():
        db.run_migrations()

    @app.get("/api/ping")
    def ping():
        return jsonify(
            ok=True,
            schema_version=db.schema_version(),
            now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    @app.get("/")
    def index():
        if not (STATIC_DIR / "index.html").exists():
            return (
                "<h1>Plot Keeper backend is up</h1>"
                "<p>Frontend not built. Run <code>cd frontend && npm run dev</code> "
                "and open the Vite URL, or <code>npm run build</code> to bundle into "
                "<code>backend/static</code>.</p>",
                200,
            )
        return send_from_directory(STATIC_DIR, "index.html")

    return app


app = create_app()
