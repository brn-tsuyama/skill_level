"""
UnitParser — converts one _Sheet into a SkillSheet domain object.

Each ability-unit XLS/XLSX file contains multiple worksheets; UnitParser handles
exactly one worksheet.  It returns None when the sheet is not a valid unit sheet
(e.g. legend sheets, summary sheets, or sheets whose name contains no unit code).
"""

from __future__ import annotations

import re

from skill_level.models import SkillCriterion, SkillSheet
from skill_level.parser._models import _cell_str, _Sheet
from skill_level.parser._normalize import (
    extract_unit_code,
    job_type_from_group,
    level_from_suffix,
)

_CRITERIA_HEADER = "職務遂行のための基準"
_KNOWLEDGE_HEADER = "必要な知識"
_LEGEND_RE = re.compile(r"[●■○]印[：:]")
_MARKER_CHARS = frozenset("●■○")


class UnitParser:
    """Parses a single ability-unit worksheet into a SkillSheet."""

    def parse(
        self,
        sheet: _Sheet,
        industry_id: int,
        group_name: str,
        source_file: str,
        unit_map: dict[str, tuple[str, str]],
    ) -> SkillSheet | None:
        unit_code = extract_unit_code(sheet.name)
        if unit_code is None:
            return None

        excel_type = "B" if sheet.ncols <= 7 else "A"

        header_row_idx, criteria_col = self._find_criteria_header(sheet)
        if header_row_idx < 0 or criteria_col < 0:
            return None

        unit_name, unit_summary = self._extract_unit_meta(sheet, header_row_idx)

        knowledge_row_idx = self._find_row_with(
            sheet, _KNOWLEDGE_HEADER, header_row_idx + 1
        )
        data_end = knowledge_row_idx if knowledge_row_idx >= 0 else sheet.nrows

        criteria = self._extract_criteria(
            sheet, header_row_idx + 1, data_end, criteria_col
        )
        knowledge = self._extract_knowledge(sheet, knowledge_row_idx)
        level, job_type = self._resolve_level_job_type(unit_code, group_name, unit_map)

        return SkillSheet(
            industry_id=industry_id,
            source_file=source_file,
            group_name=group_name,
            unit_code=unit_code,
            unit_name=unit_name,
            unit_summary=unit_summary,
            excel_type=excel_type,
            level=level,
            job_type=job_type,
            criteria=criteria,
            knowledge=knowledge,
        )

    # ------------------------------------------------------------------
    # Header / metadata extraction
    # ------------------------------------------------------------------

    def _find_criteria_header(self, sheet: _Sheet) -> tuple[int, int]:
        for r in range(sheet.nrows):
            for c, v in enumerate(sheet.row_values(r)):
                if _CRITERIA_HEADER in _cell_str(v):
                    return r, c
        return -1, -1

    def _find_row_with(self, sheet: _Sheet, text: str, start: int) -> int:
        for r in range(start, sheet.nrows):
            if text in _cell_str(sheet.cell_value(r, 0)):
                return r
        return -1

    def _extract_unit_meta(
        self, sheet: _Sheet, header_row_idx: int
    ) -> tuple[str, str]:
        unit_name = ""
        unit_summary = ""
        for r in range(header_row_idx):
            row = sheet.row_values(r)
            for c, v in enumerate(row):
                cell = _cell_str(v)
                if not cell:
                    continue
                if "能力ユニット名" in cell:
                    for vc in range(c + 1, len(row)):
                        val = _cell_str(row[vc])
                        if val:
                            unit_name = val
                            break
                if cell.startswith("概") and not unit_summary:
                    for vc in range(c + 1, len(row)):
                        val = _cell_str(row[vc])
                        if val:
                            unit_summary = val
                            break
        return unit_name, unit_summary

    # ------------------------------------------------------------------
    # Criteria / knowledge extraction
    # ------------------------------------------------------------------

    def _extract_criteria(
        self, sheet: _Sheet, start: int, end: int, criteria_col: int
    ) -> list[SkillCriterion]:
        criteria: list[SkillCriterion] = []
        current_category: str | None = None

        for r in range(start, end):
            row = sheet.row_values(r)
            cat_val = _cell_str(row[0]) if row else ""
            if cat_val:
                current_category = cat_val

            if criteria_col >= len(row):
                continue
            text = _cell_str(row[criteria_col])
            if not text or _LEGEND_RE.search(text):
                continue

            marker: str | None = text[0] if text[0] in _MARKER_CHARS else None
            criteria.append(
                SkillCriterion(
                    category=current_category,
                    criterion_text=text,
                    criterion_type=marker,
                )
            )

        return criteria

    def _extract_knowledge(self, sheet: _Sheet, knowledge_row_idx: int) -> str:
        if knowledge_row_idx < 0:
            return ""
        parts: list[str] = []
        for r in range(knowledge_row_idx + 1, sheet.nrows):
            for v in sheet.row_values(r):
                text = _cell_str(v)
                if text:
                    parts.append(text)
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Level / job-type resolution
    # ------------------------------------------------------------------

    def _resolve_level_job_type(
        self,
        unit_code: str,
        group_name: str,
        unit_map: dict[str, tuple[str, str]],
    ) -> tuple[str, str]:
        level_fallback = level_from_suffix(unit_code)
        group_job_type = job_type_from_group(group_name)
        if unit_code in unit_map:
            level, job_type = unit_map[unit_code]
            return level, job_type or group_job_type
        return level_fallback, group_job_type
