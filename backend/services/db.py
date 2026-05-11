import os
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


def connect() -> None:
    # TODO: Add SQLite connection handling in the database implementation step.
    return None
