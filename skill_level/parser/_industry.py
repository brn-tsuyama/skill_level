"""
IndustryParser — orchestrates the full parse of one extracted industry directory.

Responsibility: walk the directory tree, dispatch loading to SheetLoader,
delegate 様式 parsing to StyleParser and sheet parsing to UnitParser.
It holds no parsing logic itself (Dependency Inversion, Single Responsibility).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from skill_level.parser._loaders import get_loader
from skill_level.parser._normalize import extract_unit_code, normalize
from skill_level.parser._style import StyleParser
from skill_level.parser._unit import UnitParser

if TYPE_CHECKING:
    from pathlib import Path

    from skill_level.models import SkillSheet
    from skill_level.parser._loaders import SheetLoader
    from skill_level.parser._models import _Sheet

_SKIP_DIRS: frozenset[str] = frozenset({"職務概要書"})
_SKIP_FILE_PATTERNS: tuple[str, ...] = ("様式", "レベル区分", "template", "Template")
_STYLE_PATTERNS: tuple[str, ...] = ("様式",)
_XL_EXTS: tuple[str, ...] = (".xls", ".xlsx")


class IndustryParser:
    """
    Parses an entire extracted industry directory into SkillSheet objects.

    Dependencies are injected so they can be replaced in tests or extended for
    new file formats without modifying this class (Open/Closed Principle).
    """

    def __init__(
        self,
        style_parser: StyleParser | None = None,
        unit_parser: UnitParser | None = None,
    ) -> None:
        self._style = style_parser or StyleParser()
        self._unit = unit_parser or UnitParser()

    def parse(self, industry_dir: Path, industry_id: int) -> list[SkillSheet]:
        """
        Walk `industry_dir`, build unit-code map from 様式 file, then parse
        every ability-unit XLS/XLSX file.  Returns all SkillSheet objects found.
        """
        unit_map = self._build_unit_map(industry_dir)
        sheets: list[SkillSheet] = []

        for group_dir in sorted(industry_dir.iterdir()):
            if not group_dir.is_dir():
                continue
            group_name = group_dir.name
            if any(pat in group_name for pat in _SKIP_DIRS):
                continue

            for xl_path in sorted(
                p for ext in _XL_EXTS for p in group_dir.glob(f"*{ext}")
            ):
                if any(pat in xl_path.name for pat in _SKIP_FILE_PATTERNS):
                    continue
                source_file = str(xl_path.relative_to(industry_dir))
                for raw_sheet in self._load(xl_path):
                    result = self._unit.parse(
                        raw_sheet, industry_id, group_name, source_file, unit_map
                    )
                    if result is not None:
                        sheets.append(result)

        return sheets

    def scout(self, industry_dir: Path) -> str:
        """Return a human-readable overview of the directory and file structure."""
        lines: list[str] = []
        unit_map = self._build_unit_map(industry_dir)
        lines.append(f"Unit map entries: {len(unit_map)}")

        for group_dir in sorted(industry_dir.iterdir()):
            lines.append(f"\n{'=' * 60}")
            if group_dir.is_dir():
                lines.append(f"DIR: {group_dir.name}/")
                for xl_path in sorted(
                    p for ext in _XL_EXTS for p in group_dir.glob(f"*{ext}")
                ):
                    lines.append(f"  FILE: {xl_path.name}")
                    if not any(pat in xl_path.name for pat in _SKIP_FILE_PATTERNS):
                        for sh in self._load(xl_path):
                            code = extract_unit_code(sh.name) or normalize(sh.name)
                            info = unit_map.get(code, ("?", "?"))
                            lines.append(f"    sheet {sh.name!r:20s}  → {info}")
            else:
                lines.append(f"FILE: {group_dir.name}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_unit_map(self, industry_dir: Path) -> dict[str, tuple[str, str]]:
        for ext in _XL_EXTS:
            for p in industry_dir.glob(f"*{ext}"):
                if any(pat in p.name for pat in _STYLE_PATTERNS):
                    return self._style.build_unit_map(self._load(p))
        return {}

    def _load(self, path: Path) -> list[_Sheet]:
        loader: SheetLoader | None = get_loader(path)
        if loader is None:
            return []
        return loader.load(path)
