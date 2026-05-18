"""
Public API for the skill-level parser package.

Callers import from skill_level.parser the same way as before:

    from skill_level import parser
    sheets = parser.parse_industry_dir(industry_dir, industry_id)
    overview = parser.scout(industry_dir)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from skill_level.parser._industry import IndustryParser

if TYPE_CHECKING:
    from pathlib import Path

    from skill_level.models import SkillSheet

_default_parser = IndustryParser()


def parse_industry_dir(industry_dir: Path, industry_id: int) -> list[SkillSheet]:
    return _default_parser.parse(industry_dir, industry_id)


def scout(industry_dir: Path) -> str:
    return _default_parser.scout(industry_dir)
