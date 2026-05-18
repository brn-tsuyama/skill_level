"""
Unified in-memory sheet representation shared by all parser components.
Both xlrd (.xls) and openpyxl (.xlsx) reduce their worksheets to _Sheet before
any parsing logic runs, so the rest of the package is format-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class _Sheet:
    """Rows-based sheet that works for both xlrd (.xls) and openpyxl (.xlsx)."""

    name: str
    rows: list[list[Any]]

    @property
    def nrows(self) -> int:
        return len(self.rows)

    @property
    def ncols(self) -> int:
        return max((len(r) for r in self.rows), default=0)

    def row_values(self, r: int) -> list[Any]:
        return self.rows[r] if r < len(self.rows) else []

    def cell_value(self, r: int, c: int) -> Any:
        row = self.row_values(r)
        return row[c] if c < len(row) else ""


def _cell_str(v: Any) -> str:
    """Convert any cell value to a stripped string (None → empty string)."""
    return "" if v is None else str(v).strip()
