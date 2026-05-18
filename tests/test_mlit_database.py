"""
Unit tests for skill_level.mlit.database + integration tests for
the scraper → parser → database pipeline (all in-memory, no HTTP/PDF).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb

from skill_level.mlit import database as mlit_db
from skill_level.mlit.models import MlitIndustry, MlitLevelCriterion
from skill_level.mlit.parser import parse_pdf
from skill_level.mlit.scraper import fetch_mlit_industries

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_ROWS_DATA: list[list[str | None]] = [
    ["CCUS職種コード", None, "０９電工－０１電気工"],
    ["能力評価実施団体", None, "（一社）日本電設工業協会"],
    ["呼 称", None, "電気工事技能者"],
    ["レベル４", "就業日数", "１０年（2150日）"],
    [None, "保有資格", "◇登録電気工事基幹技能者〔00001〕"],
    [None, "職長経験", "職長としての就業日数が３年（645日）"],
    ["レベル３", "就業日数", "５年（1075日）"],
    [None, "保有資格", "◇第一種電気工事士免状取得者〔31018〕"],
    [None, "職長・班長経験", "職長または班長としての就業日数が１年（215日）"],
    ["レベル２", "就業日数", "３年（645日）"],
    [None, "保有資格", "◇第一種電気工事士試験合格者〔31073〕"],
    [
        "レベル１",
        None,
        "建設キャリアアップシステムに技能者登録され、レベル２から４までの判定を受けていない技能者",
    ],
]


def _make_industry(name: str = "電気工事") -> MlitIndustry:
    return MlitIndustry(
        name=name,
        pdf_url="https://www.mlit.go.jp/totikensangyo/const/content/001387650.pdf",
        ccus_codes="０９電工－０１電気工",
        evaluation_body="（一社）日本電設工業協会",
        title="電気工事技能者",
    )


def _make_criteria(industry_id: int) -> list[MlitLevelCriterion]:
    return [
        MlitLevelCriterion(industry_id, "L4", "就業日数", "１０年（2150日）"),
        MlitLevelCriterion(industry_id, "L4", "保有資格", "◇登録電気工事基幹技能者"),
        MlitLevelCriterion(industry_id, "L3", "就業日数", "５年（1075日）"),
        MlitLevelCriterion(industry_id, "L2", "就業日数", "３年（645日）"),
        MlitLevelCriterion(industry_id, "L1", None, "CCUS登録済み技能者"),
    ]


# ---------------------------------------------------------------------------
# Unit: init_schema
# ---------------------------------------------------------------------------


class TestInitSchema:
    def test_mlit_tables_created(self, mlit_conn: duckdb.DuckDBPyConnection) -> None:
        tables = {r[0] for r in mlit_conn.execute("SHOW TABLES").fetchall()}
        assert "mlit_industries" in tables
        assert "mlit_level_criteria" in tables

    def test_idempotent(self, mlit_conn: duckdb.DuckDBPyConnection) -> None:
        mlit_db.init_schema(mlit_conn)  # second call must not raise
        tables = {r[0] for r in mlit_conn.execute("SHOW TABLES").fetchall()}
        assert "mlit_industries" in tables


# ---------------------------------------------------------------------------
# Unit: upsert_industry
# ---------------------------------------------------------------------------


class TestUpsertIndustry:
    def test_insert_returns_positive_id(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        ind_id = mlit_db.upsert_industry(mlit_conn, _make_industry())
        assert ind_id > 0

    def test_idempotent_same_id(self, mlit_conn: duckdb.DuckDBPyConnection) -> None:
        ind = _make_industry()
        id1 = mlit_db.upsert_industry(mlit_conn, ind)
        id2 = mlit_db.upsert_industry(mlit_conn, ind)
        assert id1 == id2

    def test_update_overwrites_metadata(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        ind = _make_industry()
        ind_id = mlit_db.upsert_industry(mlit_conn, ind)

        updated = MlitIndustry(
            name=ind.name,
            pdf_url=ind.pdf_url,
            ccus_codes="新コード",
            evaluation_body="新団体",
            title="新呼称",
        )
        mlit_db.upsert_industry(mlit_conn, updated)

        row = mlit_conn.execute(
            "SELECT ccus_codes, evaluation_body, title FROM mlit_industries WHERE id = ?",
            [ind_id],
        ).fetchone()
        assert row is not None
        assert row[0] == "新コード"
        assert row[1] == "新団体"
        assert row[2] == "新呼称"

    def test_different_names_get_different_ids(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        id1 = mlit_db.upsert_industry(mlit_conn, _make_industry("電気工事"))
        id2 = mlit_db.upsert_industry(mlit_conn, _make_industry("橋梁"))
        assert id1 != id2

    def test_row_count_after_upsert(self, mlit_conn: duckdb.DuckDBPyConnection) -> None:
        mlit_db.upsert_industry(mlit_conn, _make_industry("電気工事"))
        mlit_db.upsert_industry(mlit_conn, _make_industry("電気工事"))  # same name
        mlit_db.upsert_industry(mlit_conn, _make_industry("橋梁"))
        count = mlit_conn.execute("SELECT COUNT(*) FROM mlit_industries").fetchone()
        assert count is not None
        assert count[0] == 2


# ---------------------------------------------------------------------------
# Unit: insert_criteria / delete_criteria_for_industry
# ---------------------------------------------------------------------------


class TestInsertCriteria:
    def test_inserts_all_rows(self, mlit_conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = mlit_db.upsert_industry(mlit_conn, _make_industry())
        criteria = _make_criteria(ind_id)
        mlit_db.insert_criteria(mlit_conn, criteria)
        count = mlit_conn.execute("SELECT COUNT(*) FROM mlit_level_criteria").fetchone()
        assert count is not None
        assert count[0] == len(criteria)

    def test_empty_list_noop(self, mlit_conn: duckdb.DuckDBPyConnection) -> None:
        mlit_db.insert_criteria(mlit_conn, [])
        count = mlit_conn.execute("SELECT COUNT(*) FROM mlit_level_criteria").fetchone()
        assert count is not None
        assert count[0] == 0

    def test_l1_criterion_type_is_null(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        ind_id = mlit_db.upsert_industry(mlit_conn, _make_industry())
        mlit_db.insert_criteria(mlit_conn, _make_criteria(ind_id))
        row = mlit_conn.execute(
            "SELECT criterion_type FROM mlit_level_criteria WHERE level = 'L1'"
        ).fetchone()
        assert row is not None
        assert row[0] is None

    def test_levels_stored_correctly(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        ind_id = mlit_db.upsert_industry(mlit_conn, _make_industry())
        mlit_db.insert_criteria(mlit_conn, _make_criteria(ind_id))
        levels = {
            r[0]
            for r in mlit_conn.execute(
                "SELECT DISTINCT level FROM mlit_level_criteria"
            ).fetchall()
        }
        assert levels == {"L1", "L2", "L3", "L4"}


class TestDeleteCriteriaForIndustry:
    def test_removes_only_target_industry(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        id1 = mlit_db.upsert_industry(mlit_conn, _make_industry("電気工事"))
        id2 = mlit_db.upsert_industry(mlit_conn, _make_industry("橋梁"))
        mlit_db.insert_criteria(mlit_conn, _make_criteria(id1))
        mlit_db.insert_criteria(mlit_conn, _make_criteria(id2))

        mlit_db.delete_criteria_for_industry(mlit_conn, id1)

        remaining = mlit_conn.execute(
            "SELECT industry_id FROM mlit_level_criteria"
        ).fetchall()
        assert all(r[0] == id2 for r in remaining)

    def test_delete_nonexistent_is_noop(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        mlit_db.delete_criteria_for_industry(mlit_conn, 9999)  # must not raise


# ---------------------------------------------------------------------------
# Unit: mark_processed
# ---------------------------------------------------------------------------


class TestMarkProcessed:
    def test_sets_processed_at(self, mlit_conn: duckdb.DuckDBPyConnection) -> None:
        ind_id = mlit_db.upsert_industry(mlit_conn, _make_industry())
        mlit_db.mark_processed(mlit_conn, ind_id)
        row = mlit_conn.execute(
            "SELECT COUNT(*) FROM mlit_industries WHERE id = ? AND processed_at IS NOT NULL",
            [ind_id],
        ).fetchone()
        assert row is not None
        assert row[0] == 1


# ---------------------------------------------------------------------------
# Integration: scraper → parser → database
# ---------------------------------------------------------------------------

_SCRAPER_HTML = """<html><body>
<table>
  <tr>
    <td><a href="/totikensangyo/const/content/001387650.pdf">電気工事</a></td>
    <td><a href="/totikensangyo/const/content/001398459.pdf">橋梁</a></td>
  </tr>
</table>
</body></html>"""


class TestScraperToDatabase:
    """Scrape HTML → upsert industries into DB."""

    def test_all_scraped_industries_stored(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        industries = fetch_mlit_industries(html=_SCRAPER_HTML)
        for ind in industries:
            mlit_db.upsert_industry(mlit_conn, ind)

        count = mlit_conn.execute("SELECT COUNT(*) FROM mlit_industries").fetchone()
        assert count is not None
        assert count[0] == 2

    def test_scraped_industry_names_in_db(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        industries = fetch_mlit_industries(html=_SCRAPER_HTML)
        for ind in industries:
            mlit_db.upsert_industry(mlit_conn, ind)

        names = {
            r[0]
            for r in mlit_conn.execute("SELECT name FROM mlit_industries").fetchall()
        }
        assert names == {"電気工事", "橋梁"}


class TestParserToDatabase:
    """Mock parse_pdf → insert criteria → query results."""

    def _mock_pdf(self) -> MagicMock:
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [_SAMPLE_ROWS_DATA]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        return mock_pdf

    def test_full_pipeline_stores_criteria(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        base_industry = _make_industry()
        ind_id = mlit_db.upsert_industry(mlit_conn, base_industry)

        with patch(
            "skill_level.mlit.parser.pdfplumber.open", return_value=self._mock_pdf()
        ):
            _, criteria = parse_pdf(Path("fake.pdf"), base_industry, ind_id)

        for c in criteria:
            c.industry_id = ind_id

        mlit_db.delete_criteria_for_industry(mlit_conn, ind_id)
        mlit_db.insert_criteria(mlit_conn, criteria)
        mlit_db.mark_processed(mlit_conn, ind_id)

        count = mlit_conn.execute(
            "SELECT COUNT(*) FROM mlit_level_criteria WHERE industry_id = ?",
            [ind_id],
        ).fetchone()
        assert count is not None
        assert count[0] == 9

    def test_idempotent_reprocess_no_duplicates(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        """Running the pipeline twice must not duplicate rows."""
        base_industry = _make_industry()
        ind_id = mlit_db.upsert_industry(mlit_conn, base_industry)

        for _ in range(2):
            with patch(
                "skill_level.mlit.parser.pdfplumber.open",
                return_value=self._mock_pdf(),
            ):
                _, criteria = parse_pdf(Path("fake.pdf"), base_industry, ind_id)

            for c in criteria:
                c.industry_id = ind_id

            mlit_db.delete_criteria_for_industry(mlit_conn, ind_id)
            mlit_db.insert_criteria(mlit_conn, criteria)

        count = mlit_conn.execute(
            "SELECT COUNT(*) FROM mlit_level_criteria WHERE industry_id = ?",
            [ind_id],
        ).fetchone()
        assert count is not None
        assert count[0] == 9  # not 18

    def test_level_distribution_correct(
        self, mlit_conn: duckdb.DuckDBPyConnection
    ) -> None:
        base_industry = _make_industry()
        ind_id = mlit_db.upsert_industry(mlit_conn, base_industry)

        with patch(
            "skill_level.mlit.parser.pdfplumber.open", return_value=self._mock_pdf()
        ):
            _, criteria = parse_pdf(Path("fake.pdf"), base_industry, ind_id)

        for c in criteria:
            c.industry_id = ind_id

        mlit_db.insert_criteria(mlit_conn, criteria)

        rows = mlit_conn.execute(
            "SELECT level, COUNT(*) FROM mlit_level_criteria GROUP BY level ORDER BY level"
        ).fetchall()
        level_counts = {r[0]: r[1] for r in rows}
        assert level_counts["L4"] == 3
        assert level_counts["L3"] == 3
        assert level_counts["L2"] == 2
        assert level_counts["L1"] == 1
