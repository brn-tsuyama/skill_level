"""Tests for skill_level.extractor."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from skill_level.extractor import (
    _common_prefix,
    _fix_encoding,
    extract_zip,
    summarise,
)


class TestCommonPrefix:
    def test_single_top_level_dir(self) -> None:
        names = ["06_型枠/a.xls", "06_型枠/subdir/b.xls"]
        assert _common_prefix(names) == "06_型枠/"

    def test_multiple_top_level_dirs(self) -> None:
        names = ["dir_a/file.xls", "dir_b/file.xls"]
        assert _common_prefix(names) == ""

    def test_empty_list(self) -> None:
        assert _common_prefix([]) == ""

    def test_flat_files(self) -> None:
        assert _common_prefix(["file.xls"]) == ""


class TestFixEncoding:
    def test_passthrough_for_valid_text(self) -> None:
        assert _fix_encoding("hello") == "hello"

    def test_recovers_cp932(self) -> None:
        raw = "型枠工事業".encode("cp932").decode("cp437")
        assert _fix_encoding(raw) == "型枠工事業"


class TestExtractZip:
    def test_strips_top_level_prefix(self, fixture_zip: Path, tmp_path: Any) -> None:
        dest = tmp_path / "out"
        result = extract_zip(fixture_zip, "06_型枠工事業", dest_dir=dest)
        assert result.name == "06_型枠工事業"
        assert (result / "06_00_共通" / "unit.xls").exists()
        assert (result / "06_01_施工技能" / "ability.xls").exists()

    def test_idempotent(self, fixture_zip: Path, tmp_path: Any) -> None:
        dest = tmp_path / "out"
        extract_zip(fixture_zip, "06_型枠工事業", dest_dir=dest)
        extract_zip(fixture_zip, "06_型枠工事業", dest_dir=dest)
        files = list((dest / "06_型枠工事業").rglob("*.xls"))
        assert len(files) == 2

    def test_returns_industry_dir(self, fixture_zip: Path, tmp_path: Any) -> None:
        dest = tmp_path / "out"
        result = extract_zip(fixture_zip, "06_型枠工事業", dest_dir=dest)
        assert result == dest / "06_型枠工事業"

    def test_directory_entries_skipped(self, tmp_path: Any) -> None:
        """Directory entries in ZIP (trailing /) must not create empty files."""
        zip_path = tmp_path / "dir_only.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.mkdir("prefix/")
            zf.mkdir("prefix/subdir/")
            zf.writestr("prefix/subdir/file.txt", "content")
        dest = tmp_path / "out"
        extract_zip(zip_path, "test", dest_dir=dest)
        result_dir = dest / "test"
        assert not (result_dir / "subdir").is_file()
        assert (result_dir / "subdir" / "file.txt").exists()


class TestSummarise:
    def test_groups_by_extension(self, fixture_zip: Path, tmp_path: Any) -> None:
        dest = tmp_path / "out"
        industry_dir = extract_zip(fixture_zip, "06_型枠工事業", dest_dir=dest)
        groups = summarise(industry_dir)
        assert ".xls" in groups
        assert len(groups[".xls"]) == 2
