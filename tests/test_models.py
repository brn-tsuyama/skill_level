"""Tests for skill_level.parser._models (_Sheet and _cell_str)."""

from __future__ import annotations

from skill_level.parser._models import _cell_str, _Sheet


class TestSheet:
    def test_nrows(self) -> None:
        s = _Sheet(name="x", rows=[[1, 2], [3, 4, 5]])
        assert s.nrows == 2

    def test_ncols(self) -> None:
        s = _Sheet(name="x", rows=[[1, 2], [3, 4, 5]])
        assert s.ncols == 3

    def test_ncols_empty(self) -> None:
        s = _Sheet(name="x", rows=[])
        assert s.ncols == 0

    def test_row_values_valid(self) -> None:
        s = _Sheet(name="x", rows=[[1, 2, 3]])
        assert s.row_values(0) == [1, 2, 3]

    def test_row_values_out_of_bounds(self) -> None:
        s = _Sheet(name="x", rows=[[1]])
        assert s.row_values(99) == []

    def test_cell_value_valid(self) -> None:
        s = _Sheet(name="x", rows=[["a", "b"]])
        assert s.cell_value(0, 1) == "b"

    def test_cell_value_row_oob(self) -> None:
        s = _Sheet(name="x", rows=[["a"]])
        assert s.cell_value(5, 0) == ""

    def test_cell_value_col_oob(self) -> None:
        s = _Sheet(name="x", rows=[["a"]])
        assert s.cell_value(0, 5) == ""


class TestCellStr:
    def test_none(self) -> None:
        assert _cell_str(None) == ""

    def test_strips_whitespace(self) -> None:
        assert _cell_str("  hello  ") == "hello"

    def test_numeric(self) -> None:
        assert _cell_str(42) == "42"

    def test_float(self) -> None:
        assert _cell_str(3.0) == "3.0"

    def test_empty_string(self) -> None:
        assert _cell_str("") == ""
