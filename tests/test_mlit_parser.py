"""Unit tests for skill_level.mlit.parser (no PDF files needed)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from skill_level.mlit.models import MlitIndustry
from skill_level.mlit.parser import _cell, _parse_header, _parse_levels, parse_pdf

# ---------------------------------------------------------------------------
# Fixtures — raw table rows extracted from a typical MLIT PDF
# ---------------------------------------------------------------------------

_SAMPLE_ROWS: list[list[str | None]] = [
    ["CCUS職種コード", None, "０９電工－０１電気工、１０ソーラーシステム取付工"],
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

_BASE_INDUSTRY = MlitIndustry(name="電気工事", pdf_url="https://example.com/test.pdf")


# ---------------------------------------------------------------------------
# _cell
# ---------------------------------------------------------------------------


class TestCell:
    def test_none_returns_none(self) -> None:
        assert _cell(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _cell("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert _cell("   ") is None

    def test_strips_surrounding_whitespace(self) -> None:
        assert _cell("  電気工事  ") == "電気工事"

    def test_normal_value_unchanged(self) -> None:
        assert _cell("就業日数") == "就業日数"


# ---------------------------------------------------------------------------
# _parse_header
# ---------------------------------------------------------------------------


class TestParseHeader:
    def test_extracts_ccus_codes(self) -> None:
        result = _parse_header(_SAMPLE_ROWS, _BASE_INDUSTRY)
        assert result.ccus_codes == "０９電工－０１電気工、１０ソーラーシステム取付工"

    def test_extracts_evaluation_body(self) -> None:
        result = _parse_header(_SAMPLE_ROWS, _BASE_INDUSTRY)
        assert result.evaluation_body == "（一社）日本電設工業協会"

    def test_extracts_title(self) -> None:
        result = _parse_header(_SAMPLE_ROWS, _BASE_INDUSTRY)
        assert result.title == "電気工事技能者"

    def test_preserves_name_and_url(self) -> None:
        result = _parse_header(_SAMPLE_ROWS, _BASE_INDUSTRY)
        assert result.name == "電気工事"
        assert result.pdf_url == "https://example.com/test.pdf"

    def test_missing_fields_are_none(self) -> None:
        sparse_rows: list[list[str | None]] = [
            ["CCUS職種コード", None, "コード値"],
        ]
        result = _parse_header(sparse_rows, _BASE_INDUSTRY)
        assert result.ccus_codes == "コード値"
        assert result.evaluation_body is None
        assert result.title is None

    def test_empty_rows_returns_base_with_nones(self) -> None:
        result = _parse_header([], _BASE_INDUSTRY)
        assert result.ccus_codes is None
        assert result.evaluation_body is None
        assert result.title is None

    def test_handles_alternate_title_spelling(self) -> None:
        # 呼　称 (full-width space) vs 呼 称 (half-width space)
        rows: list[list[str | None]] = [["呼　称", None, "専門技能者"]]
        result = _parse_header(rows, _BASE_INDUSTRY)
        assert result.title == "専門技能者"


# ---------------------------------------------------------------------------
# _parse_levels
# ---------------------------------------------------------------------------


class TestParseLevels:
    def test_returns_9_criteria_rows(self) -> None:
        # L4: 就業日数・保有資格・職長経験 (3)
        # L3: 就業日数・保有資格・職長・班長経験 (3)
        # L2: 就業日数・保有資格 (2)
        # L1: free-text (1)
        result = _parse_levels(_SAMPLE_ROWS, industry_id=1)
        assert len(result) == 9

    def test_all_levels_present(self) -> None:
        result = _parse_levels(_SAMPLE_ROWS, industry_id=1)
        levels = {c.level for c in result}
        assert levels == {"L1", "L2", "L3", "L4"}

    def test_l4_criteria(self) -> None:
        result = _parse_levels(_SAMPLE_ROWS, industry_id=1)
        l4 = [c for c in result if c.level == "L4"]
        assert len(l4) == 3
        types = {c.criterion_type for c in l4}
        assert types == {"就業日数", "保有資格", "職長経験"}

    def test_l3_criteria(self) -> None:
        result = _parse_levels(_SAMPLE_ROWS, industry_id=1)
        l3 = [c for c in result if c.level == "L3"]
        assert len(l3) == 3
        types = {c.criterion_type for c in l3}
        assert "職長・班長経験" in types

    def test_l2_criteria(self) -> None:
        result = _parse_levels(_SAMPLE_ROWS, industry_id=1)
        l2 = [c for c in result if c.level == "L2"]
        assert len(l2) == 2
        types = {c.criterion_type for c in l2}
        assert types == {"就業日数", "保有資格"}

    def test_l1_has_no_criterion_type(self) -> None:
        result = _parse_levels(_SAMPLE_ROWS, industry_id=1)
        l1 = [c for c in result if c.level == "L1"]
        assert len(l1) == 1
        assert l1[0].criterion_type is None

    def test_l1_text_correct(self) -> None:
        result = _parse_levels(_SAMPLE_ROWS, industry_id=1)
        l1 = next(c for c in result if c.level == "L1")
        assert "キャリアアップシステム" in l1.criterion_text

    def test_industry_id_set_on_all_criteria(self) -> None:
        result = _parse_levels(_SAMPLE_ROWS, industry_id=42)
        assert all(c.industry_id == 42 for c in result)

    def test_header_rows_before_first_level_ignored(self) -> None:
        # Rows above レベル４ must not produce criteria
        result = _parse_levels(_SAMPLE_ROWS, industry_id=1)
        # The 3 header rows (CCUS, 団体, 呼称) should not appear as criteria
        assert len(result) == 9

    def test_empty_rows_returns_empty(self) -> None:
        result = _parse_levels([], industry_id=1)
        assert result == []

    def test_rows_with_no_level_marker_returns_empty(self) -> None:
        rows: list[list[str | None]] = [
            ["CCUS職種コード", None, "コード"],
            ["能力評価実施団体", None, "団体名"],
        ]
        result = _parse_levels(rows, industry_id=1)
        assert result == []

    def test_level_without_criteria_produces_no_row(self) -> None:
        # A level marker row where col1 and col2 are both absent
        rows: list[list[str | None]] = [
            ["レベル２", None, None],
        ]
        result = _parse_levels(rows, industry_id=1)
        assert result == []


# ---------------------------------------------------------------------------
# parse_pdf (mock pdfplumber to avoid needing a real PDF file)
# ---------------------------------------------------------------------------


class TestParsePdf:
    def _make_mock_pdf(self) -> MagicMock:
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [_SAMPLE_ROWS]
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)
        return mock_pdf

    def test_returns_tuple_of_industry_and_criteria(self) -> None:
        mock_pdf = self._make_mock_pdf()
        with patch("skill_level.mlit.parser.pdfplumber.open", return_value=mock_pdf):
            industry, criteria = parse_pdf(Path("fake.pdf"), _BASE_INDUSTRY, 5)

        assert industry.name == "電気工事"
        assert len(criteria) == 9

    def test_header_fields_populated(self) -> None:
        mock_pdf = self._make_mock_pdf()
        with patch("skill_level.mlit.parser.pdfplumber.open", return_value=mock_pdf):
            industry, _ = parse_pdf(Path("fake.pdf"), _BASE_INDUSTRY, 5)

        assert industry.evaluation_body == "（一社）日本電設工業協会"
        assert industry.title == "電気工事技能者"

    def test_multi_page_pdf_rows_concatenated(self) -> None:
        # Two pages each with half the rows
        half = len(_SAMPLE_ROWS) // 2
        page1 = MagicMock()
        page1.extract_tables.return_value = [_SAMPLE_ROWS[:half]]
        page2 = MagicMock()
        page2.extract_tables.return_value = [_SAMPLE_ROWS[half:]]
        mock_pdf = MagicMock()
        mock_pdf.pages = [page1, page2]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("skill_level.mlit.parser.pdfplumber.open", return_value=mock_pdf):
            _, criteria = parse_pdf(Path("fake.pdf"), _BASE_INDUSTRY, 1)

        assert len(criteria) == 9

    def test_empty_pdf_returns_no_criteria(self) -> None:
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("skill_level.mlit.parser.pdfplumber.open", return_value=mock_pdf):
            industry, criteria = parse_pdf(Path("fake.pdf"), _BASE_INDUSTRY, 1)

        assert criteria == []
        assert industry.ccus_codes is None
