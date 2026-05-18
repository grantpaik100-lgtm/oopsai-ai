from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from services.db import get_connection


def make_cache_key(*parts: Any) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached_json(task_type: str, cache_key: str) -> Any | None:
    try:
        with get_connection() as connection:
            _ensure_cache_table(connection)
            row = connection.execute(
                """
                SELECT output_json
                FROM ai_cache
                WHERE task_type = ? AND cache_key = ?
                """,
                (task_type, cache_key),
            ).fetchone()
    except (FileNotFoundError, RuntimeError, sqlite3.Error):
        return None

    if row is None:
        return None

    try:
        return json.loads(row["output_json"])
    except (TypeError, json.JSONDecodeError):
        return None


def set_cached_json(
    task_type: str,
    cache_key: str,
    model: str | None,
    input_json: Any,
    output_json: Any,
) -> None:
    try:
        with get_connection() as connection:
            _ensure_cache_table(connection)
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                INSERT INTO ai_cache (
                    cache_key,
                    task_type,
                    model,
                    input_json,
                    output_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_type, cache_key) DO UPDATE SET
                    model = excluded.model,
                    input_json = excluded.input_json,
                    output_json = excluded.output_json,
                    updated_at = excluded.updated_at
                """,
                (
                    cache_key,
                    task_type,
                    model,
                    json.dumps(input_json, ensure_ascii=False, sort_keys=True, default=str),
                    json.dumps(output_json, ensure_ascii=False, sort_keys=True, default=str),
                    now,
                    now,
                ),
            )
            connection.commit()
    except (FileNotFoundError, RuntimeError, sqlite3.Error):
        return


def _ensure_cache_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT NOT NULL,
            task_type TEXT NOT NULL,
            model TEXT,
            input_json TEXT NOT NULL,
            output_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(task_type, cache_key)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_cache_task_key
        ON ai_cache(task_type, cache_key)
        """
    )
