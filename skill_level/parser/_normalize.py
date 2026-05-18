"""
String normalization and unit-code extraction utilities.

NFKC normalization converts full-width Japanese alphanumerics to ASCII,
so worksheet names like "０６Ｃ０２２Ｌ１１" become "06C022L11" and can
be matched by the unit-code regex.
"""

from __future__ import annotations

import re
import unicodedata

_UNIT_CODE_RE = re.compile(r"\d{2}[CScs]\d{3}L\d{2}", re.ASCII)

_JOB_TYPE_KEYWORDS: tuple[str, ...] = (
    "施工管理",
    "現場管理",
    "施工技能",
    "建設営業",
    "建設生産",
)


def normalize(raw: str) -> str:
    """NFKC-normalize and strip ideographic spaces."""
    return unicodedata.normalize("NFKC", raw).replace("　", "").strip()


def extract_unit_code(text: str) -> str | None:
    """Extract and return a normalized unit code from `text`, or None."""
    m = _UNIT_CODE_RE.search(normalize(text))
    return m.group() if m else None


def level_from_suffix(unit_code: str) -> str:
    """'06C022L11' → 'L1',  '06S001L34' → 'L3-L4'."""
    m = re.search(r"L(\d)(\d)$", unit_code)
    if not m:
        return ""
    a, b = m.group(1), m.group(2)
    return f"L{a}" if a == b else f"L{a}-L{b}"


def job_type_from_group(group_name: str) -> str:
    """Infer job_type from the group subdirectory name."""
    for keyword in _JOB_TYPE_KEYWORDS:
        if keyword in group_name:
            return keyword
    return ""
