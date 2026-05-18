"""
PDF parser for MLIT 能力評価基準.

PDF table layout (1 page, 3 columns):
  col0          col1              col2
  ─────────────────────────────────────────
  CCUS職種コード  None              <codes>
  能力評価実施団体  None              <body>
  呼 称          None              <title>
  レベル４        就業日数           <days>
  None           保有資格           <quals>
  None           職長経験           <exp>      (optional)
  レベル３        就業日数           <days>
  ...
  レベル１        None              <free-text>
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pdfplumber

from skill_level.mlit.models import MlitIndustry, MlitLevelCriterion

if TYPE_CHECKING:
    from pathlib import Path

_LEVEL_RE = re.compile(r"レベル([１２３４])")
_DIGIT_MAP = {"１": "1", "２": "2", "３": "3", "４": "4"}

_HDR_CCUS = "CCUS職種コード"
_HDR_BODY = "能力評価実施団体"
_HDR_TITLE = "呼　称"
_HDR_TITLE_ALT = "呼 称"


def parse_pdf(
    pdf_path: Path,
    industry: MlitIndustry,
    industry_id: int,
) -> tuple[MlitIndustry, list[MlitLevelCriterion]]:
    """Parse one MLIT PDF and return updated industry + criteria rows."""
    with pdfplumber.open(pdf_path) as pdf:
        rows: list[list[str | None]] = []
        for page in pdf.pages:
            tables = page.extract_tables()
            for tbl in tables:
                rows.extend(tbl)

    updated = _parse_header(rows, industry)
    criteria = _parse_levels(rows, industry_id)
    return updated, criteria


def _parse_header(rows: list[list[str | None]], base: MlitIndustry) -> MlitIndustry:
    ccus: str | None = None
    body: str | None = None
    title: str | None = None

    for row in rows:
        if not row:
            continue
        key = _cell(row[0])
        val = _cell(row[-1]) if len(row) >= 3 else None
        if key == _HDR_CCUS:
            ccus = val
        elif key == _HDR_BODY:
            body = val
        elif key in (_HDR_TITLE, _HDR_TITLE_ALT):
            title = val

    return MlitIndustry(
        name=base.name,
        pdf_url=base.pdf_url,
        ccus_codes=ccus,
        evaluation_body=body,
        title=title,
    )


def _parse_levels(
    rows: list[list[str | None]], industry_id: int
) -> list[MlitLevelCriterion]:
    criteria: list[MlitLevelCriterion] = []
    current_level: str | None = None

    for row in rows:
        if not row:
            continue
        col0 = _cell(row[0])
        col1 = _cell(row[1]) if len(row) > 1 else None
        col2 = _cell(row[2]) if len(row) > 2 else None

        # Check if this row starts a new level
        if col0:
            m = _LEVEL_RE.search(col0)
            if m:
                current_level = f"L{_DIGIT_MAP[m.group(1)]}"

        if current_level is None:
            continue

        # L1: free-text in col2 (col1 is None)
        if current_level == "L1" and col1 is None and col2:
            criteria.append(
                MlitLevelCriterion(
                    industry_id=industry_id,
                    level="L1",
                    criterion_type=None,
                    criterion_text=col2,
                )
            )
            continue

        # L2-L4: criterion_type in col1, text in col2
        if col1 and col2:
            criteria.append(
                MlitLevelCriterion(
                    industry_id=industry_id,
                    level=current_level,
                    criterion_type=col1,
                    criterion_text=col2,
                )
            )

    return criteria


def _cell(val: str | None) -> str | None:
    """Strip whitespace; return None for empty."""
    if val is None:
        return None
    stripped = val.strip()
    return stripped or None
