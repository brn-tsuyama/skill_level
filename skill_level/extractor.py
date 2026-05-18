"""
ZIP extractor that preserves the subdirectory structure inside the archive.

The ZIPs from MHLW have a single top-level directory (e.g. "06_型枠工事業/")
that is stripped on extraction so the contents land directly in the industry
directory.  Subsequent subdirectories (06_00_共通能力ユニット/, 06_01_施工管理/,
…) are kept intact because they encode the unit-group type used by the parser.

Extraction is idempotent: the destination directory is wiped and re-created on
every call, so running the pipeline twice never creates duplicate files.
"""

import shutil
import zipfile
from pathlib import Path

EXTRACTED_DIR = Path("data/extracted")


def extract_zip(
    zip_path: Path, industry_name: str, dest_dir: Path = EXTRACTED_DIR
) -> Path:
    """
    Extract `zip_path` into `dest_dir/<industry_name>/`, preserving
    subdirectory layout and stripping the single top-level ZIP prefix.
    Returns the industry directory path.
    """
    industry_dir = dest_dir / industry_name
    if industry_dir.exists():
        shutil.rmtree(industry_dir)
    industry_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        _extract_preserving_structure(zf, industry_dir)

    return industry_dir


def summarise(industry_dir: Path) -> dict[str, list[Path]]:
    """Return files grouped by extension."""
    groups: dict[str, list[Path]] = {}
    for p in sorted(industry_dir.rglob("*")):
        if p.is_file():
            ext = p.suffix.lower()
            groups.setdefault(ext, []).append(p)
    return groups


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fix_encoding(raw: str) -> str:
    """
    ZIP archives from Japanese tools often store filenames in cp932 (Shift-JIS
    superset) without setting the UTF-8 flag.  Try to recover the proper name.
    """
    try:
        return raw.encode("cp437").decode("cp932")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return raw


def _extract_preserving_structure(zf: zipfile.ZipFile, dest: Path) -> None:
    """
    Extract all files to `dest`, stripping the single common top-level prefix
    so that the first real subdirectory level lands directly in `dest`.
    """
    # Build (fixed_filename, ZipInfo) pairs with corrected encoding.
    entries: list[tuple[str, zipfile.ZipInfo]] = []
    for info in zf.infolist():
        fixed = info.filename
        if not (info.flag_bits & 0x800):  # UTF-8 flag not set
            fixed = _fix_encoding(info.filename)
        entries.append((fixed, info))

    # Determine the common top-level prefix (e.g. "06_型枠工事業/").
    prefix = _common_prefix([fixed for fixed, _ in entries])

    for fixed_name, info in entries:
        relative = fixed_name[len(prefix) :]
        if not relative or relative.endswith("/"):
            continue  # skip empty path or directory entries

        target = dest / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(info))


def _common_prefix(names: list[str]) -> str:
    """
    Return the longest common leading path component shared by all names,
    including the trailing slash.  Returns "" if no common prefix exists.
    """
    name_list = list(names)
    if not name_list:
        return ""
    # All paths that contain a "/" have a top-level dir component.
    tops = {n.split("/")[0] for n in name_list if "/" in n}
    if len(tops) == 1:
        return tops.pop() + "/"
    return ""
