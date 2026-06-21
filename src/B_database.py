from __future__ import annotations

import math
import sqlite3
from contextlib import closing
from typing import Any

import A_config

FINANCIAL_FACT_COLUMNS = (
    "ticker",
    "cik",
    "company_name",
    "sector",
    "company_group",
    "statement_type",
    "position",
    "value",
    "unit",
    "reporting_currency",
    "taxonomy",
    "concept",
    "label",
    "form",
    "accession_number",
    "primary_document",
    "report_release_date",
    "fiscal_period_end_date",
    "fact_start_date",
    "fact_end_date",
    "duration_days",
    "fiscal_year",
    "fiscal_period",
    "selection_status",
    "extraction_method",
    "provider",
)

DEFAULT_ROW_VALUES = {
    "label": None,
    "fiscal_year": None,
    "fiscal_period": None,
    "extraction_method": "sec_companyfacts",
    "provider": "sec",
}


def _to_sqlite_value(value: Any) -> Any:
    """Convert pandas/numpy scalar values to native sqlite3-bindable values."""
    if value is None:
        return None

    type_name = type(value).__name__
    if type_name in {"NaTType", "NAType"}:
        return None
    if type_name == "Timestamp":
        return value.isoformat()

    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            value = value.item()
        except (AttributeError, TypeError, ValueError):
            pass

    if isinstance(value, float) and math.isnan(value):
        return None

    return value


def get_connection() -> sqlite3.Connection:
    """Return a connection to the single project SQLite database."""
    A_config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(A_config.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables(drop_existing: bool = False) -> None:
    """Create the project database schema."""
    with closing(get_connection()) as connection:
        cursor = connection.cursor()

        if drop_existing:
            cursor.execute("DROP TABLE IF EXISTS financial_facts")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS financial_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                ticker TEXT NOT NULL,
                cik TEXT NOT NULL,
                company_name TEXT NOT NULL,
                sector TEXT NOT NULL,
                company_group TEXT NOT NULL,

                statement_type TEXT NOT NULL,
                position TEXT NOT NULL,

                value REAL,
                unit TEXT,
                reporting_currency TEXT,

                taxonomy TEXT,
                concept TEXT,
                label TEXT,

                form TEXT NOT NULL,
                accession_number TEXT NOT NULL,
                primary_document TEXT,

                report_release_date TEXT,
                fiscal_period_end_date TEXT,
                fact_start_date TEXT,
                fact_end_date TEXT,
                duration_days INTEGER,
                fiscal_year INTEGER,
                fiscal_period TEXT,

                selection_status TEXT,
                extraction_method TEXT NOT NULL DEFAULT 'sec_companyfacts',
                provider TEXT NOT NULL DEFAULT 'sec',

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_financial_facts_unique
            ON financial_facts (ticker, accession_number, position, extraction_method)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_financial_facts_lookup
            ON financial_facts (ticker, fiscal_year, fiscal_period, position)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_financial_facts_statement
            ON financial_facts (ticker, statement_type, position)
            """
        )
        connection.commit()


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = {**DEFAULT_ROW_VALUES, **row}
    cleaned.setdefault("reporting_currency", cleaned.get("unit"))
    return {column: _to_sqlite_value(cleaned.get(column)) for column in FINANCIAL_FACT_COLUMNS}


def insert_financial_facts(rows: list[dict[str, Any]]) -> None:
    """Insert or replace standardized financial fact rows."""
    if not rows:
        return

    columns_sql = ",\n                ".join(FINANCIAL_FACT_COLUMNS)
    placeholders_sql = ",\n                ".join(f":{column}" for column in FINANCIAL_FACT_COLUMNS)
    cleaned_rows = [_clean_row(row) for row in rows]

    with closing(get_connection()) as connection:
        connection.executemany(
            f"""
            INSERT OR REPLACE INTO financial_facts (
                {columns_sql}
            )
            VALUES (
                {placeholders_sql}
            )
            """,
            cleaned_rows,
        )
        connection.commit()


def get_financial_facts(
    ticker: str | None = None,
    statement_type: str | None = None,
    position: str | None = None,
) -> list[dict[str, Any]]:
    """Read financial facts with optional filters."""
    query = "SELECT * FROM financial_facts WHERE 1 = 1"
    params: list[Any] = []

    if ticker is not None:
        query += " AND ticker = ?"
        params.append(ticker)
    if statement_type is not None:
        query += " AND statement_type = ?"
        params.append(statement_type)
    if position is not None:
        query += " AND position = ?"
        params.append(position)

    query += """
        ORDER BY ticker, fiscal_period_end_date DESC, statement_type, position
    """

    with closing(get_connection()) as connection:
        rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_available_periods(ticker: str) -> list[dict[str, Any]]:
    """Return available filings and fiscal periods for a ticker."""
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT
                ticker,
                form,
                accession_number,
                report_release_date,
                fiscal_period_end_date,
                fiscal_year,
                fiscal_period
            FROM financial_facts
            WHERE ticker = ?
            ORDER BY fiscal_period_end_date DESC
            """,
            (ticker,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_missing_items_summary() -> list[dict[str, Any]]:
    """Return rows whose extraction status is missing."""
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT ticker, position, COUNT(*) AS missing_count
            FROM financial_facts
            WHERE selection_status = 'missing'
            GROUP BY ticker, position
            ORDER BY ticker, missing_count DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
