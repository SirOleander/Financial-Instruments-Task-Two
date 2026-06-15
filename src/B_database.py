import sqlite3
from pathlib import Path
from typing import Any


DATABASE_PATH = Path("data/financials.db")


def _to_sqlite_value(value: Any) -> Any:
    """Normalize a value into something sqlite3 can bind.

    sqlite3 can only bind None, int, float, str, and bytes. The extraction
    client produces pandas/numpy values that are not directly bindable:
    - pandas missing markers (NaN, NaT, NA) must become SQL NULL,
    - numpy scalar types (numpy.int64, numpy.float64, ...) must become native
      Python scalars,
    - pandas Timestamp values must become strings.

    Types are detected by class name so this module stays free of a hard
    pandas/numpy import and remains a thin, transparent database layer.
    """
    if value is None:
        return None

    type_name = type(value).__name__

    # pandas missing-value markers -> SQL NULL
    if type_name in ("NaTType", "NAType"):
        return None

    # pandas Timestamp -> ISO string (dates are normally already strings;
    # this is a safety net for unexpected datetime-typed values).
    if type_name == "Timestamp":
        return value.isoformat()

    # numpy scalar -> native Python scalar (numpy.int64 is NOT a Python int)
    if hasattr(value, "item") and not isinstance(value, (str, bytes, bytearray)):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass

    # NaN (including numpy.nan after .item()) -> SQL NULL
    if isinstance(value, float) and value != value:
        return None

    return value


def get_connection() -> sqlite3.Connection:
    """Create a SQLite database connection."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection

def create_tables(drop_existing: bool = False) -> None:
    """
    Create database tables.

    Parameters
    ----------
    drop_existing:
        If True, rebuild the financial_facts table from scratch.
        Use True while developing. Use False once the pipeline is stable.
    """
    connection = get_connection()
    cursor = connection.cursor()

    if drop_existing:
        cursor.execute("DROP TABLE IF EXISTS financial_facts")

    cursor.execute("""
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
    """)

    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_financial_facts_unique
        ON financial_facts (
            ticker,
            accession_number,
            position,
            extraction_method
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_financial_facts_lookup
        ON financial_facts (
            ticker,
            fiscal_year,
            fiscal_period,
            position
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_financial_facts_statement
        ON financial_facts (
            ticker,
            statement_type,
            position
        )
    """)

    connection.commit()
    connection.close()


def insert_financial_facts(rows: list[dict[str, Any]]) -> None:
    """Insert standardized financial fact rows."""
    if not rows:
        return

    connection = get_connection()
    cursor = connection.cursor()

    cleaned_rows = []
    for row in rows:
        cleaned = dict(row)

        cleaned.setdefault("reporting_currency", cleaned.get("unit"))
        cleaned.setdefault("extraction_method", "sec_companyfacts")
        cleaned.setdefault("provider", "sec")

        # Required by the table. These defaults prevent SQLite binding errors
        # if a value is missing from the client output.
        cleaned.setdefault("label", None)
        cleaned.setdefault("fiscal_year", None)
        cleaned.setdefault("fiscal_period", None)

        # Normalize every value so pandas NA/NaT, numpy scalars, and timestamps
        # can be bound by sqlite3 without raising.
        cleaned = {key: _to_sqlite_value(value) for key, value in cleaned.items()}

        cleaned_rows.append(cleaned)

    cursor.executemany("""
        INSERT OR REPLACE INTO financial_facts (
            ticker,
            cik,
            company_name,
            sector,
            company_group,

            statement_type,
            position,

            value,
            unit,
            reporting_currency,

            taxonomy,
            concept,
            label,

            form,
            accession_number,
            primary_document,

            report_release_date,
            fiscal_period_end_date,
            fact_start_date,
            fact_end_date,
            duration_days,
            fiscal_year,
            fiscal_period,

            selection_status,
            extraction_method,
            provider
        )
        VALUES (
            :ticker,
            :cik,
            :company_name,
            :sector,
            :company_group,

            :statement_type,
            :position,

            :value,
            :unit,
            :reporting_currency,

            :taxonomy,
            :concept,
            :label,

            :form,
            :accession_number,
            :primary_document,

            :report_release_date,
            :fiscal_period_end_date,
            :fact_start_date,
            :fact_end_date,
            :duration_days,
            :fiscal_year,
            :fiscal_period,

            :selection_status,
            :extraction_method,
            :provider
        )
    """, cleaned_rows)

    connection.commit()
    connection.close()


def get_financial_facts(
    ticker: str | None = None,
    statement_type: str | None = None,
    position: str | None = None,
) -> list[dict[str, Any]]:
    """Read financial facts with optional filters."""
    connection = get_connection()
    cursor = connection.cursor()

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
        ORDER BY
            ticker,
            fiscal_period_end_date DESC,
            statement_type,
            position
    """

    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return rows


def get_available_periods(ticker: str) -> list[dict[str, Any]]:
    """Return available filings/periods for a ticker."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
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
    """, (ticker,))

    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return rows


def get_missing_items_summary() -> list[dict[str, Any]]:
    """Return rows where no value was selected."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            ticker,
            position,
            COUNT(*) AS missing_count
        FROM financial_facts
        WHERE value IS NULL
        GROUP BY ticker, position
        ORDER BY ticker, missing_count DESC
    """)

    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return rows