"""Export financial_facts to an Excel workbook. Diagnostic/utility (not pipeline).

USAGE (from the repo root):
    python tools/viewdatabase.py
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

# this utility lives in tools/; make the flat pipeline config in src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from fi import config

DATABASE_PATH = config.DATABASE_PATH
OUTPUT_PATH = config.BASE_DIR / "outputs" / "financials_database_export.xlsx"

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

connection = sqlite3.connect(DATABASE_PATH)

financial_facts = pd.read_sql_query(
    """
    SELECT
        ticker,
        cik,
        company_group,
        position,
        value,
        concept,
        form,
        fiscal_period_end_date
    FROM financial_facts
    ORDER BY
        ticker,
        fiscal_period_end_date DESC,
        form,
        position
    """,
    connection,
)

connection.close()

with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
    financial_facts.to_excel(
        writer,
        sheet_name="financial_facts",
        index=False,
    )

print(f"Excel export saved to: {OUTPUT_PATH}")
