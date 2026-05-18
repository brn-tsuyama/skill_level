"""Tests for skill_level.database (in-memory DuckDB)."""

from __future__ import annotations

import duckdb

from skill_level import database
from skill_level.models import Industry, SkillCriterion, SkillSheet


def _make_industry(name: str = "型枠工事業") -> Industry:
    return Industry(name=name, category="建設業関係", zip_url="http://example.com/a.zip")


def _make_sheet(industry_id: int, unit_code: str = "06C022L11") -> SkillSheet:
    return SkillSheet(
        industry_id=industry_id,
        source_file="test.xls",
        group_name="06_01_施工技能",
        unit_code=unit_code,
        unit_name="段取り",
        unit_summary="型枠工事の段取りを行う",
        excel_type="A",
        level="L1",
        job_type="施工技能",
    )


class TestInitSchema:
    def test_tables_exist(self, conn: duckdb.DuckDBPyConnection) -> None:
        tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
        assert "industries" in tables
        assert "skill_sheets" in tables
        assert "skill_criteria" in tables
        assert "required_knowledge" in tables

    def test_idempotent(self, conn: duckdb.DuckDBPyConnection) -> None:
        database.init_schema(conn)  # calling twice must not raise
        tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
        assert "industries" in tables


class TestUpsertIndustry:
    def test_insert_new(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        assert ind_id > 0

    def test_idempotent(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind = _make_industry()
        id1 = database.upsert_industry(conn, ind)
        id2 = database.upsert_industry(conn, ind)
        assert id1 == id2

    def test_different_names_get_different_ids(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        id1 = database.upsert_industry(conn, _make_industry("型枠工事業"))
        id2 = database.upsert_industry(conn, _make_industry("左官工事業"))
        assert id1 != id2


class TestInsertSkillSheet:
    def test_returns_positive_id(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        sheet_id = database.insert_skill_sheet(conn, _make_sheet(ind_id))
        assert sheet_id > 0

    def test_row_stored(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        database.insert_skill_sheet(conn, _make_sheet(ind_id))
        rows = conn.execute("SELECT unit_code FROM skill_sheets").fetchall()
        assert rows[0][0] == "06C022L11"

    def test_multiple_sheets_sequential_ids(
        self, conn: duckdb.DuckDBPyConnection
    ) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        id1 = database.insert_skill_sheet(conn, _make_sheet(ind_id, "06C022L11"))
        id2 = database.insert_skill_sheet(conn, _make_sheet(ind_id, "06C022L22"))
        assert id2 > id1


class TestInsertSkillCriteria:
    def test_inserts_criteria(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        sheet_id = database.insert_skill_sheet(conn, _make_sheet(ind_id))
        criteria = [
            SkillCriterion(category="切断", criterion_text="●点検を行う", criterion_type="●"),
            SkillCriterion(category="切断", criterion_text="○選定ができる", criterion_type="○"),
        ]
        database.insert_skill_criteria(conn, sheet_id, criteria)
        count = conn.execute("SELECT COUNT(*) FROM skill_criteria").fetchone()
        assert count is not None
        assert count[0] == 2

    def test_empty_criteria_noop(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        sheet_id = database.insert_skill_sheet(conn, _make_sheet(ind_id))
        database.insert_skill_criteria(conn, sheet_id, [])
        count = conn.execute("SELECT COUNT(*) FROM skill_criteria").fetchone()
        assert count is not None
        assert count[0] == 0


class TestInsertRequiredKnowledge:
    def test_inserts_content(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        sheet_id = database.insert_skill_sheet(conn, _make_sheet(ind_id))
        database.insert_required_knowledge(conn, sheet_id, "型枠の種類と特性")
        row = conn.execute("SELECT content FROM required_knowledge").fetchone()
        assert row is not None
        assert row[0] == "型枠の種類と特性"

    def test_blank_content_noop(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        sheet_id = database.insert_skill_sheet(conn, _make_sheet(ind_id))
        database.insert_required_knowledge(conn, sheet_id, "   ")
        count = conn.execute("SELECT COUNT(*) FROM required_knowledge").fetchone()
        assert count is not None
        assert count[0] == 0


class TestMarkProcessed:
    def test_sets_processed_at(self, conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = database.upsert_industry(conn, _make_industry())
        database.mark_processed(conn, ind_id)
        # Fetch a non-timestamp column to avoid pytz dependency in DuckDB's
        # TIMESTAMPTZ deserializer — just confirm the row was updated.
        row = conn.execute(
            "SELECT COUNT(*) FROM industries WHERE id = ? AND processed_at IS NOT NULL",
            [ind_id],
        ).fetchone()
        assert row is not None
        assert row[0] == 1
