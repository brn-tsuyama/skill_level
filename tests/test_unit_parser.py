"""Tests for skill_level.parser._unit.UnitParser."""

from __future__ import annotations

from typing import Any

from skill_level.parser._models import _Sheet
from skill_level.parser._unit import UnitParser

_EMPTY_MAP: dict[str, tuple[str, str]] = {}
_GROUP = "06_01_施工技能"


class TestParseUnitCode:
    def test_fullwidth_sheet_name(self, unit_sheet_a: _Sheet) -> None:
        parser = UnitParser()
        result = parser.parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.unit_code == "06C022L11"

    def test_no_unit_code_returns_none(self) -> None:
        sheet = _Sheet(name="凡例", rows=[])
        parser = UnitParser()
        assert parser.parse(sheet, 1, _GROUP, "f.xls", _EMPTY_MAP) is None

    def test_no_criteria_header_returns_none(self) -> None:
        sheet = _Sheet(name="06C022L11", rows=[["some", "content"]])
        parser = UnitParser()
        assert parser.parse(sheet, 1, _GROUP, "f.xls", _EMPTY_MAP) is None


class TestExcelType:
    def test_type_a_wide(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.excel_type == "A"

    def test_type_b_narrow(self, unit_sheet_b: _Sheet) -> None:
        result = UnitParser().parse(
            unit_sheet_b, 1, "06_01_施工管理", "f.xls", _EMPTY_MAP
        )
        assert result is not None
        assert result.excel_type == "B"


class TestUnitMeta:
    def test_unit_name(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.unit_name == "段取り"

    def test_unit_summary(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.unit_summary == "型枠工事の段取りを行う"


class TestCriteriaExtraction:
    def test_count(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert len(result.criteria) == 2

    def test_first_criterion_text(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.criteria[0].criterion_text == "●作業前点検を行う"

    def test_first_criterion_marker(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.criteria[0].criterion_type == "●"

    def test_second_criterion_marker(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.criteria[1].criterion_type == "○"

    def test_category_propagation(self, unit_sheet_a: _Sheet) -> None:
        """Both criteria share the same 能力細目 because the second row is merged."""
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.criteria[0].category == "切断"
        assert result.criteria[1].category == "切断"

    def test_legend_row_skipped(self) -> None:
        """Rows matching '●印：' are not counted as criteria."""
        rows: list[list[Any]] = [
            ["能力ユニット名", "テスト"] + [""] * 8,
            [""] * 4 + ["職務遂行のための基準"] + [""] * 5,
            ["", "", "", "", "●印：エントリーレベル", "", "", "", "", ""],
            ["作業", "", "", "", "●実際の作業ができる", "", "", "", "", ""],
            ["必要な知識"] + [""] * 9,
        ]
        sheet = _Sheet(name="06C001L11", rows=rows)
        result = UnitParser().parse(sheet, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert len(result.criteria) == 1


class TestKnowledgeExtraction:
    def test_knowledge_content(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert "型枠の種類と特性" in result.knowledge

    def test_no_knowledge_section(self) -> None:
        rows: list[list[Any]] = [
            ["能力ユニット名", "段取り"] + [""] * 8,
            [""] * 4 + ["職務遂行のための基準"] + [""] * 5,
            ["切断", "", "", "", "●点検を行う", "", "", "", "", ""],
        ]
        sheet = _Sheet(name="06C022L11", rows=rows)
        result = UnitParser().parse(sheet, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.knowledge == ""


class TestLevelJobTypeResolution:
    def test_fallback_from_suffix(self, unit_sheet_a: _Sheet) -> None:
        """unit_code 06C022L11 → L1 (from suffix), job_type from group."""
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.level == "L1"
        assert result.job_type == "施工技能"

    def test_level_from_unit_map(self, unit_sheet_a: _Sheet) -> None:
        unit_map = {"06C022L11": ("L2", "現場管理")}
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", unit_map)
        assert result is not None
        assert result.level == "L2"
        assert result.job_type == "現場管理"

    def test_job_type_fallback_when_map_empty(self, unit_sheet_a: _Sheet) -> None:
        """If unit_map has empty job_type, fall back to group-name inference."""
        unit_map = {"06C022L11": ("L1", "")}
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "f.xls", unit_map)
        assert result is not None
        assert result.job_type == "施工技能"


class TestIndustryId:
    def test_industry_id_stored(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 42, _GROUP, "f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.industry_id == 42

    def test_source_file_stored(self, unit_sheet_a: _Sheet) -> None:
        result = UnitParser().parse(unit_sheet_a, 1, _GROUP, "dir/f.xls", _EMPTY_MAP)
        assert result is not None
        assert result.source_file == "dir/f.xls"
