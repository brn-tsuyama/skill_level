"""DuckDB schema and CRUD for MLIT 能力評価基準 tables."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

    from skill_level.mlit.models import MlitIndustry, MlitLevelCriterion


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    for seq in ("seq_mlit_industry_id", "seq_mlit_criteria_id"):
        conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mlit_industries (
            id              INTEGER DEFAULT nextval('seq_mlit_industry_id') PRIMARY KEY,
            name            VARCHAR NOT NULL UNIQUE,
            pdf_url         VARCHAR NOT NULL,
            ccus_codes      VARCHAR,
            evaluation_body VARCHAR,
            title           VARCHAR,
            downloaded_at   TIMESTAMPTZ,
            processed_at    TIMESTAMPTZ
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mlit_level_criteria (
            id             INTEGER DEFAULT nextval('seq_mlit_criteria_id') PRIMARY KEY,
            industry_id    INTEGER NOT NULL REFERENCES mlit_industries(id),
            level          VARCHAR NOT NULL,
            criterion_type VARCHAR,
            criterion_text VARCHAR NOT NULL
        )
    """)


def upsert_industry(conn: duckdb.DuckDBPyConnection, industry: MlitIndustry) -> int:
    """Insert or update industry row; return its id."""
    existing = conn.execute(
        "SELECT id FROM mlit_industries WHERE name = ?", [industry.name]
    ).fetchone()

    if existing:
        conn.execute(
            """
            UPDATE mlit_industries
            SET pdf_url = ?, ccus_codes = ?, evaluation_body = ?, title = ?
            WHERE id = ?
            """,
            [
                industry.pdf_url,
                industry.ccus_codes,
                industry.evaluation_body,
                industry.title,
                existing[0],
            ],
        )
        return int(existing[0])

    row = conn.execute(
        """
        INSERT INTO mlit_industries
            (name, pdf_url, ccus_codes, evaluation_body, title, downloaded_at)
        VALUES (?, ?, ?, ?, ?, ?)
        RETURNING id
        """,
        [
            industry.name,
            industry.pdf_url,
            industry.ccus_codes,
            industry.evaluation_body,
            industry.title,
            datetime.now(UTC),
        ],
    ).fetchone()
    return int(row[0]) if row else -1


def insert_criteria(
    conn: duckdb.DuckDBPyConnection,
    criteria: list[MlitLevelCriterion],
) -> None:
    if not criteria:
        return
    conn.executemany(
        """
        INSERT INTO mlit_level_criteria
            (industry_id, level, criterion_type, criterion_text)
        VALUES (?, ?, ?, ?)
        """,
        [
            [c.industry_id, c.level, c.criterion_type, c.criterion_text]
            for c in criteria
        ],
    )


def delete_criteria_for_industry(
    conn: duckdb.DuckDBPyConnection, industry_id: int
) -> None:
    conn.execute("DELETE FROM mlit_level_criteria WHERE industry_id = ?", [industry_id])


def mark_processed(conn: duckdb.DuckDBPyConnection, industry_id: int) -> None:
    conn.execute(
        "UPDATE mlit_industries SET processed_at = ? WHERE id = ?",
        [datetime.now(UTC), industry_id],
    )
