"""
StyleParser — builds the unit-code → (level, job_type) map from 様式１・２ sheets.

Two 様式２ sheet-name variants are handled:
  "様式２（施工管理）"  →  job_type = "施工管理"   (parenthetical)
  "様式２施工管理"     →  job_type = "施工管理"   (plain suffix, 電気通信工事業)
"""

from __future__ import annotations

import re

from skill_level.parser._models import _cell_str, _Sheet
from skill_level.parser._normalize import _UNIT_CODE_RE, normalize

_LEVEL_CELL_RE = re.compile(r"(?:L|レベル)(\d)$")
_JOB_TYPE_SUB_ROW: frozenset[str] = frozenset({"施工技能", "現場管理", "施工管理"})


class StyleParser:
    """Parses 様式２ worksheets to produce a unit-code → (level, job_type) map."""

    def build_unit_map(self, sheets: list[_Sheet]) -> dict[str, tuple[str, str]]:
        """
        Filter `sheets` for 様式２ worksheets and accumulate all unit-code
        mappings into one dict.  Returns unit_code → (level, job_type).
        """
        unit_map: dict[str, tuple[str, str]] = {}
        for sheet in sheets:
            if not sheet.name.startswith("様式２"):
                continue
            job_type = self._extract_job_type(sheet.name)
            self._parse_sheet(sheet, job_type, unit_map)
        return unit_map

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_job_type(self, sheet_name: str) -> str:
        m = re.search(r"[（(](.+?)[）)]", sheet_name)
        return m.group(1) if m else sheet_name[len("様式２") :].strip()

    def _parse_sheet(
        self,
        sheet: _Sheet,
        default_job_type: str,
        unit_map: dict[str, tuple[str, str]],
    ) -> None:
        level_row_idx = self._find_level_header_row(sheet)
        if level_row_idx < 0:
            return

        level_row = [normalize(_cell_str(v)) for v in sheet.row_values(level_row_idx)]
        col_level = self._build_col_level_map(level_row)

        # Check for optional job-type sub-row immediately after the level row.
        col_job_type: dict[int, str] = {}
        next_idx = level_row_idx + 1
        if next_idx < sheet.nrows:
            next_row = [_cell_str(v) for v in sheet.row_values(next_idx)]
            col_job_type = {
                c: v for c, v in enumerate(next_row) if v in _JOB_TYPE_SUB_ROW
            }

        effective: dict[int, tuple[str, str]] = {
            c: (lv, col_job_type.get(c, default_job_type))
            for c, lv in col_level.items()
        }

        data_start = level_row_idx + (2 if col_job_type else 1)
        for r in range(data_start, sheet.nrows):
            row_vals = [normalize(_cell_str(v)) for v in sheet.row_values(r)]
            for c, v in enumerate(row_vals):
                m = _UNIT_CODE_RE.search(v)
                if m and c in effective:
                    unit_map[m.group()] = effective[c]

    def _find_level_header_row(self, sheet: _Sheet) -> int:
        """Return index of the row with ≥ 2 level-header cells, or -1."""
        for r in range(min(25, sheet.nrows)):
            normalized = [normalize(_cell_str(v)) for v in sheet.row_values(r)]
            level_count = sum(1 for v in normalized if _LEVEL_CELL_RE.fullmatch(v))
            if level_count >= 2:
                return r
        return -1

    def _build_col_level_map(self, level_row: list[str]) -> dict[int, str]:
        """
        Return {col: level} from a normalized level-header row, propagating the
        current level rightward until a new one is seen.
        """
        col_level: dict[int, str] = {}
        current = ""
        for c, v in enumerate(level_row):
            m = _LEVEL_CELL_RE.fullmatch(v)
            if m:
                current = f"L{m.group(1)}"
            if current:
                col_level[c] = current
        return col_level
