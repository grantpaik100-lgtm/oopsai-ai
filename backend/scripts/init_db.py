from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.db import get_database_path

TABLE_NAMES = ("incident_cases", "hazard_taxonomy", "prevention_taxonomy")
ID_COLUMNS = {
    "incident_cases": ("case_id", "CASE"),
    "hazard_taxonomy": ("hazard_id", "HZD"),
    "prevention_taxonomy": ("prevention_id", "PRV"),
}

PENDING_CASES_SQL = """
CREATE TABLE IF NOT EXISTS pending_cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id TEXT UNIQUE,
  raw_input TEXT,
  normalized TEXT,
  output_json TEXT,
  original_input_json TEXT,
  backend1_input TEXT,
  backend1_output TEXT,
  backend2_input TEXT,
  backend2_output TEXT,
  backend3_input TEXT,
  backend3_output TEXT,
  missing_info_questions TEXT,
  missing_info_answers TEXT,
  photo_metadata TEXT,
  step_status TEXT,
  error_log TEXT,
  final_report TEXT,
  조치결과 TEXT,
  조치일시 DATE,
  status TEXT DEFAULT 'pending',
  submitted_by TEXT,
  submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  reviewed_by TEXT,
  reviewed_at DATETIME
);
"""

PENDING_CASE_TEXT_COLUMNS = (
    "original_input_json",
    "backend1_input",
    "backend1_output",
    "backend2_input",
    "backend2_output",
    "backend3_input",
    "backend3_output",
    "missing_info_questions",
    "missing_info_answers",
    "photo_metadata",
    "step_status",
    "error_log",
    "final_report",
)


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_excel_path() -> Path:
    return get_project_root() / "data" / "아차사고_표준화_3시트_v2.xlsx"


def is_blank_column(series: pd.Series) -> bool:
    return series.isna().all() or series.astype(str).str.strip().eq("").all()


def clean_dataframe(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]

    columns_to_keep: list[str] = []
    indexes_to_keep: list[int] = []
    seen_columns: set[str] = set()
    for index, column in enumerate(cleaned.columns):
        if not column or column.lower().startswith("unnamed"):
            continue
        if column in seen_columns:
            continue
        if is_blank_column(cleaned.iloc[:, index]):
            continue
        columns_to_keep.append(column)
        indexes_to_keep.append(index)
        seen_columns.add(column)

    cleaned = cleaned.iloc[:, indexes_to_keep]
    cleaned.columns = columns_to_keep
    cleaned = cleaned.dropna(how="all")

    id_column, prefix = ID_COLUMNS[table_name]
    if id_column not in cleaned.columns:
        cleaned.insert(0, id_column, [f"{prefix}_{index:03d}" for index in range(1, len(cleaned) + 1)])

    if table_name == "incident_cases":
        now = datetime.now().isoformat(timespec="seconds")
        if "status" not in cleaned.columns:
            cleaned["status"] = "confirmed"
        if "created_at" not in cleaned.columns:
            cleaned["created_at"] = now

    return cleaned


def count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    cursor = connection.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    return int(cursor.fetchone()[0])


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    cursor = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def ensure_pending_case_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute('PRAGMA table_info("pending_cases")').fetchall()
    }
    for column in PENDING_CASE_TEXT_COLUMNS:
        if column not in existing_columns:
            connection.execute(f'ALTER TABLE pending_cases ADD COLUMN "{column}" TEXT')


def main() -> None:
    excel_path = get_excel_path()
    db_path = get_database_path()

    try:
        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")

        print(f"Reading Excel file: {excel_path}")
        excel_file = pd.ExcelFile(excel_path)
        sheet_names = excel_file.sheet_names
        print(f"Discovered sheets: {sheet_names}")

        if len(sheet_names) < 3:
            raise ValueError(f"Expected at least 3 sheets, found {len(sheet_names)}")

        if db_path.exists():
            db_path.unlink()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Creating SQLite DB: {db_path}")
        with sqlite3.connect(db_path) as connection:
            for index, table_name in enumerate(TABLE_NAMES):
                sheet_name = sheet_names[index]
                print(f"Loading sheet '{sheet_name}' into table '{table_name}'")
                raw_df = pd.read_excel(excel_file, sheet_name=sheet_name)
                cleaned_df = clean_dataframe(raw_df, table_name)
                cleaned_df.to_sql(table_name, connection, if_exists="replace", index=False)

            connection.execute(PENDING_CASES_SQL)
            ensure_pending_case_columns(connection)
            connection.commit()

            print("Row counts:")
            for table_name in TABLE_NAMES:
                print(f"- {table_name}: {count_rows(connection, table_name)}")
            print(f"- pending_cases exists: {table_exists(connection, 'pending_cases')}")

        print("DB initialization completed.")
    except Exception as exc:
        print(f"DB initialization failed: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
