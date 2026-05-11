import os


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./accident.db")


def database_is_configured() -> bool:
    return bool(get_database_url())


def connect() -> None:
    # TODO: Add SQLite connection handling in the database implementation step.
    return None
