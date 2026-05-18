"""
DuckDB schema and CRUD operations.

Phase-1 tables (industries, ability_units, raw_rows) are kept for reference.
Phase-2 tables (skill_sheets, skill_criteria, required_knowledge) hold the
normalised, queryable skill data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from skill_level.models import Industry, SkillCriterion, SkillSheet

DB_PATH = Path("data/db/skill_level.duckdb")


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    # --- sequences -----------------------------------------------------------
    for seq in (
        "seq_industry_id",
        "seq_sheet_id",
        "seq_criteria_id",
        "seq_knowledge_id",
    ):
        conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1")

    # --- industries ----------------------------------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS industries (
            id            INTEGER DEFAULT nextval('seq_industry_id') PRIMARY KEY,
            name          VARCHAR NOT NULL UNIQUE,
            category      VARCHAR NOT NULL,
            zip_url       VARCHAR,
            downloaded_at TIMESTAMPTZ,
            processed_at  TIMESTAMPTZ
        )
    """)

    # --- Phase-2: one row per worksheet (= one unit code) --------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skill_sheets (
            id           INTEGER DEFAULT nextval('seq_sheet_id') PRIMARY KEY,
            industry_id  INTEGER NOT NULL REFERENCES industries(id),
            source_file  VARCHAR NOT NULL,
            group_name   VARCHAR NOT NULL,
            unit_code    VARCHAR NOT NULL,
            unit_name    VARCHAR NOT NULL,
            unit_summary VARCHAR,
            excel_type   VARCHAR NOT NULL,
            level        VARCHAR NOT NULL,
            job_type     VARCHAR
        )
    """)

    # --- Phase-2: criteria rows ----------------------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skill_criteria (
            id             INTEGER DEFAULT nextval('seq_criteria_id') PRIMARY KEY,
            sheet_id       INTEGER NOT NULL REFERENCES skill_sheets(id),
            category       VARCHAR,
            criterion_text VARCHAR NOT NULL,
            criterion_type VARCHAR
        )
    """)

    # --- Phase-2: required-knowledge sections --------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS required_knowledge (
            id       INTEGER DEFAULT nextval('seq_knowledge_id') PRIMARY KEY,
            sheet_id INTEGER NOT NULL REFERENCES skill_sheets(id),
            content  VARCHAR NOT NULL
        )
    """)


# ---------------------------------------------------------------------------
# Upsert / insert helpers
# ---------------------------------------------------------------------------


def upsert_industry(conn: duckdb.DuckDBPyConnection, industry: Industry) -> int:
    """Insert or ignore (by name) and return the id."""
    existing = conn.execute(
        "SELECT id FROM industries WHERE name = ?", [industry.name]
    ).fetchone()
    if existing:
        return int(existing[0])

    row = conn.execute(
        """
        INSERT INTO industries (name, category, zip_url, downloaded_at)
        VALUES (?, ?, ?, ?)
        RETURNING id
        """,
        [industry.name, industry.category, industry.zip_url, datetime.now(UTC)],
    ).fetchone()
    return int(row[0]) if row else -1


def insert_skill_sheet(conn: duckdb.DuckDBPyConnection, sheet: SkillSheet) -> int:
    """Insert one skill sheet and return its id."""
    row = conn.execute(
        """
        INSERT INTO skill_sheets
            (industry_id, source_file, group_name, unit_code, unit_name,
             unit_summary, excel_type, level, job_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        [
            sheet.industry_id,
            sheet.source_file,
            sheet.group_name,
            sheet.unit_code,
            sheet.unit_name,
            sheet.unit_summary or None,
            sheet.excel_type,
            sheet.level,
            sheet.job_type or None,
        ],
    ).fetchone()
    return int(row[0]) if row else -1


def insert_skill_criteria(
    conn: duckdb.DuckDBPyConnection,
    sheet_id: int,
    criteria: list[SkillCriterion],
) -> None:
    if not criteria:
        return
    conn.executemany(
        """
        INSERT INTO skill_criteria (sheet_id, category, criterion_text, criterion_type)
        VALUES (?, ?, ?, ?)
        """,
        [[sheet_id, c.category, c.criterion_text, c.criterion_type] for c in criteria],
    )


def insert_required_knowledge(
    conn: duckdb.DuckDBPyConnection, sheet_id: int, content: str
) -> None:
    if not content.strip():
        return
    conn.execute(
        "INSERT INTO required_knowledge (sheet_id, content) VALUES (?, ?)",
        [sheet_id, content],
    )


def mark_processed(conn: duckdb.DuckDBPyConnection, industry_id: int) -> None:
    conn.execute(
        "UPDATE industries SET processed_at = ? WHERE id = ?",
        [datetime.now(UTC), industry_id],
    )
