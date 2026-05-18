"""Tests for skill_level.parser._style.StyleParser."""

from __future__ import annotations

from skill_level.parser._models import _Sheet
from skill_level.parser._style import StyleParser


class TestBuildUnitMap:
    def test_basic_level_extraction(self, style2_sheet):  # type: ignore[no-untyped-def]
        parser = StyleParser()
        unit_map = parser.build_unit_map([style2_sheet])
        assert "06C022L11" in unit_map
        assert unit_map["06C022L11"] == ("L1", "施工技能")

    def test_all_four_levels(self, style2_sheet):  # type: ignore[no-untyped-def]
        parser = StyleParser()
        unit_map = parser.build_unit_map([style2_sheet])
        assert unit_map.get("06C022L11") == ("L1", "施工技能")
        assert unit_map.get("06C022L22") == ("L2", "施工技能")
        assert unit_map.get("06C022L33") == ("L3", "施工技能")
        assert unit_map.get("06C022L44") == ("L4", "施工技能")

    def test_plain_suffix_name(self, style2_sheet_no_parens):  # type: ignore[no-untyped-def]
        parser = StyleParser()
        unit_map = parser.build_unit_map([style2_sheet_no_parens])
        assert unit_map.get("06S001L11") == ("L1", "施工管理")
        assert unit_map.get("06S001L22") == ("L2", "施工管理")

    def test_revel_format(self, style2_sheet_revel):  # type: ignore[no-untyped-def]
        """防水工事業 variant: 'レベル１' instead of 'Ｌ１'."""
        parser = StyleParser()
        unit_map = parser.build_unit_map([style2_sheet_revel])
        assert unit_map.get("11C001L11") == ("L1", "施工技能")
        assert unit_map.get("11C001L22") == ("L2", "施工技能")

    def test_skips_non_style2_sheets(self, style2_sheet):  # type: ignore[no-untyped-def]
        style1 = _Sheet(name="様式１", rows=[])
        parser = StyleParser()
        unit_map = parser.build_unit_map([style1, style2_sheet])
        assert len(unit_map) == 4  # only from style2_sheet

    def test_empty_sheets_list(self) -> None:
        parser = StyleParser()
        assert parser.build_unit_map([]) == {}

    def test_multiple_style2_sheets_merged(
        self, style2_sheet, style2_sheet_no_parens  # type: ignore[no-untyped-def]
    ) -> None:
        parser = StyleParser()
        unit_map = parser.build_unit_map([style2_sheet, style2_sheet_no_parens])
        assert "06C022L11" in unit_map  # from style2_sheet
        assert "06S001L11" in unit_map  # from style2_sheet_no_parens


class TestExtractJobType:
    def test_parenthetical(self) -> None:
        parser = StyleParser()
        assert parser._extract_job_type("様式２（施工管理）") == "施工管理"

    def test_plain_suffix(self) -> None:
        parser = StyleParser()
        assert parser._extract_job_type("様式２施工管理") == "施工管理"

    def test_ascii_parens(self) -> None:
        parser = StyleParser()
        assert parser._extract_job_type("様式２(施工技能)") == "施工技能"

    def test_empty_suffix(self) -> None:
        parser = StyleParser()
        assert parser._extract_job_type("様式２") == ""
