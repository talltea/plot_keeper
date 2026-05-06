from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import Flask, current_app, g

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def init_app(app: Flask) -> None:
    app.teardown_appcontext(_close_connection)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = Path(current_app.config["DATABASE_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def _close_connection(_exc: BaseException | None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def schema_version() -> int:
    conn = get_db()
    if not _table_exists(conn, "meta"):
        return 0
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    return int(row[0]) if row else 0


def run_migrations() -> None:
    """Apply any unapplied migrations.

    Migrations are SQL files in `backend/migrations/` named `NNNN_<slug>.sql`.
    They are applied in numerical order, each in its own transaction, with
    the version recorded in `meta.schema_version`.
    """
    conn = get_db()
    current = schema_version()

    for path in _migration_files():
        version = _version_of(path)
        if version <= current:
            continue
        sql = path.read_text()
        try:
            conn.executescript(f"BEGIN;\n{sql}\nCOMMIT;")
        except sqlite3.Error:
            conn.execute("ROLLBACK")
            raise
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(version),),
        )
        conn.commit()
        current_app.logger.info("Applied migration %s", path.name)


def _migration_files() -> list[Path]:
    return sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))


def _version_of(path: Path) -> int:
    return int(path.name.split("_", 1)[0])


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None
