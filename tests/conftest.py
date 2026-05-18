"""
Shared pytest fixtures.
"""

from __future__ import annotations

import zipfile
from typing import Any

import duckdb
import pytest

from skill_level import database
from skill_level.parser._models import _Sheet

# ---------------------------------------------------------------------------
# DuckDB in-memory connection
# ---------------------------------------------------------------------------


@pytest.fixture
def conn() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect(":memory:")
    database.init_schema(c)
    yield c  # type: ignore[misc]
    c.close()


# ---------------------------------------------------------------------------
# _Sheet factory helpers
# ---------------------------------------------------------------------------


def make_sheet(name: str, rows: list[list[Any]]) -> _Sheet:
    return _Sheet(name=name, rows=rows)


@pytest.fixture
def unit_sheet_a() -> _Sheet:
    """
    Minimal type-A (10-col) ability-unit sheet for unit code 06C022L11.
    Layout:
      row 0 — 能力ユニット名 | 段取り
      row 1 — 概要 | 型枠工事の段取りを行う
      row 2 — 職務遂行のための基準 (col 4)
      row 3 — criteria: category=切断, text=●作業前点検を行う
      row 4 — criteria: (same category), text=○工具の選定ができる
      row 5 — 必要な知識 (col 0)
      row 6 — knowledge content
    """
    rows: list[list[Any]] = [
        ["能力ユニット名", "段取り"] + [""] * 8,
        ["概要", "型枠工事の段取りを行う"] + [""] * 8,
        [""] * 4 + ["職務遂行のための基準"] + [""] * 5,
        ["切断", "", "", "", "●作業前点検を行う", "", "", "", "", ""],
        ["", "", "", "", "○工具の選定ができる", "", "", "", "", ""],
        ["必要な知識"] + [""] * 9,
        ["", "", "", "", "型枠の種類と特性", "", "", "", "", ""],
    ]
    return make_sheet("０６Ｃ０２２Ｌ１１", rows)


@pytest.fixture
def unit_sheet_b() -> _Sheet:
    """
    Minimal type-B (7-col) ability-unit sheet for unit code 06C001L22.
    """
    rows: list[list[Any]] = [
        ["能力ユニット名", "施工計画"] + [""] * 5,
        ["概要", "施工計画を作成する"] + [""] * 5,
        [""] * 3 + ["職務遂行のための基準"] + [""] * 3,
        ["計画", "", "", "■施工計画書を作成できる", "", "", ""],
        ["必要な知識"] + [""] * 6,
        ["", "", "", "建設材料の基礎知識", "", "", ""],
    ]
    return make_sheet("０６Ｃ００１Ｌ２２", rows)


@pytest.fixture
def style2_sheet() -> _Sheet:
    """
    Minimal 様式２（施工技能） sheet.
    Level header row: cols 2=Ｌ１, 3=Ｌ２, 4=Ｌ３, 5=Ｌ４
    Data row:         unit codes in each level column.
    """
    rows: list[list[Any]] = [
        [""] * 6,
        [""] * 6,
        [""] * 6,
        [""] * 6,
        # level header row
        ["", "", "Ｌ１", "Ｌ２", "Ｌ３", "Ｌ４"],
        # data row with unit codes
        [
            "",
            "段取り",
            "０６Ｃ０２２Ｌ１１",
            "０６Ｃ０２２Ｌ２２",
            "０６Ｃ０２２Ｌ３３",
            "０６Ｃ０２２Ｌ４４",
        ],
    ]
    return make_sheet("様式２（施工技能）", rows)


@pytest.fixture
def style2_sheet_no_parens() -> _Sheet:
    """
    様式２ sheet using the plain-suffix naming (電気通信工事業 variant).
    Sheet name: "様式２施工管理" (no parentheses).
    """
    rows: list[list[Any]] = [
        [""] * 4,
        [""] * 4,
        # level header row (ASCII L already)
        ["", "", "L1", "L2"],
        # data row
        ["", "管理業務", "06S001L11", "06S001L22"],
    ]
    return make_sheet("様式２施工管理", rows)


@pytest.fixture
def style2_sheet_revel() -> _Sheet:
    """
    様式２ sheet that uses 'レベル１' instead of 'Ｌ１' (防水工事業 variant).
    """
    rows: list[list[Any]] = [
        [""] * 4,
        [""] * 4,
        # level header row
        ["", "", "レベル１", "レベル２"],
        # data row
        ["", "防水作業", "11C001L11", "11C001L22"],
    ]
    return make_sheet("様式２（施工技能）", rows)


# ---------------------------------------------------------------------------
# Fixture ZIP (for extractor tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_zip(tmp_path: Any) -> Any:
    """
    Build a small ZIP with a single top-level directory and nested files.
    Layout in ZIP:
      06_型枠工事業/06_00_共通/unit.xls
      06_型枠工事業/06_01_施工技能/ability.xls
    """
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("06_型枠工事業/06_00_共通/unit.xls", b"fake xls")
        zf.writestr("06_型枠工事業/06_01_施工技能/ability.xls", b"fake xls")
    return zip_path
