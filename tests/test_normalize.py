"""Tests for skill_level.parser._normalize."""

from __future__ import annotations

import pytest

from skill_level.parser._normalize import (
    extract_unit_code,
    job_type_from_group,
    level_from_suffix,
    normalize,
)


class TestNormalize:
    def test_nfkc_fullwidth_alphanum(self) -> None:
        assert normalize("０６Ｃ０２２Ｌ１１") == "06C022L11"

    def test_ideographic_space_becomes_regular_space(self) -> None:
        # NFKC converts U+3000 (ideographic space) to a regular space.
        assert normalize("段取り　工程") == "段取り 工程"

    def test_strips_regular_whitespace(self) -> None:
        assert normalize("  hello  ") == "hello"

    def test_empty_string(self) -> None:
        assert normalize("") == ""

    def test_mixed_content(self) -> None:
        result = normalize("　０６Ｃ０２２Ｌ１１　")
        assert result == "06C022L11"


class TestExtractUnitCode:
    def test_fullwidth(self) -> None:
        assert extract_unit_code("０６Ｃ０２２Ｌ１１") == "06C022L11"

    def test_ascii_already_normalized(self) -> None:
        assert extract_unit_code("06C022L11") == "06C022L11"

    def test_embedded_in_text(self) -> None:
        assert extract_unit_code("unit ０６Ｃ０２２Ｌ１１ end") == "06C022L11"

    def test_lowercase_type_letter(self) -> None:
        assert extract_unit_code("06s001L11") == "06s001L11"

    def test_returns_none_for_non_code(self) -> None:
        assert extract_unit_code("様式２") is None

    def test_returns_none_for_empty(self) -> None:
        assert extract_unit_code("") is None

    def test_returns_none_for_legend_sheet(self) -> None:
        assert extract_unit_code("凡例") is None


class TestLevelFromSuffix:
    @pytest.mark.parametrize(
        "code,expected",
        [
            ("06C022L11", "L1"),
            ("06C022L22", "L2"),
            ("06C022L33", "L3"),
            ("06C022L44", "L4"),
            ("06S001L34", "L3-L4"),
            ("06S001L12", "L1-L2"),
        ],
    )
    def test_same_and_span(self, code: str, expected: str) -> None:
        assert level_from_suffix(code) == expected

    def test_no_match_returns_empty(self) -> None:
        assert level_from_suffix("invalid") == ""


class TestJobTypeFromGroup:
    @pytest.mark.parametrize(
        "group,expected",
        [
            ("06_01_施工管理", "施工管理"),
            ("06_02_現場管理", "現場管理"),
            ("06_00_施工技能", "施工技能"),
            ("06_03_建設営業", "建設営業"),
            ("06_04_建設生産", "建設生産"),
            ("06_00_共通能力ユニット", ""),
            ("06_99_職務概要書", ""),
        ],
    )
    def test_keyword_detection(self, group: str, expected: str) -> None:
        assert job_type_from_group(group) == expected
