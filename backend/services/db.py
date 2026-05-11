import os
import sqlite3
from pathlib import Path


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./accident.db")


def get_database_path() -> Path:
    database_url = get_database_url()
    backend_dir = Path(__file__).resolve().parents[1]

    if database_url.startswith("sqlite:///"):
        raw_path = database_url.removeprefix("sqlite:///")
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return (backend_dir / path).resolve()

    return (backend_dir / "accident.db").resolve()


def database_is_configured() -> bool:
    return bool(get_database_url())


def get_connection() -> sqlite3.Connection:
    database_path = get_database_path()
    if not database_path.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {database_path}. "
            "Run `uv run python scripts/init_db.py` from the backend directory."
        )

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def connect() -> None:
    # TODO: Preserve the existing placeholder until a wider DB lifecycle is added.
    return None
