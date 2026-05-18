"""PDF downloader with retry and resume-by-existence."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

PDF_DIR = Path("data/mlit_pdfs")
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


def download_pdf(name: str, url: str, dest_dir: Path = PDF_DIR) -> Path:
    """Download `url` into `dest_dir/<name>.pdf`. Skips if already exists."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{_safe_filename(name)}.pdf"

    if dest.exists():
        return dest

    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            _stream_download(url, dest)
            return dest
        except httpx.HTTPError as exc:
            last_err = exc
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BASE_DELAY * (2**attempt))

    if dest.exists():
        dest.unlink()
    msg = f"Failed to download {url} after {_MAX_RETRIES} attempts"
    raise RuntimeError(msg) from last_err


def _stream_download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(".tmp")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes(chunk_size=65536):
                fh.write(chunk)
    tmp.rename(dest)


def _safe_filename(name: str) -> str:
    unsafe = r'/\:*?"<>|'
    return "".join(c for c in name if c not in unsafe)
