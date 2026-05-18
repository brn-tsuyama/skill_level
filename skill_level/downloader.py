"""ZIP downloader with retry and resume-by-existence."""

import time
from pathlib import Path

import httpx

RAW_DIR = Path("data/raw")
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0  # seconds, doubles on each attempt


def download_zip(name: str, url: str, dest_dir: Path = RAW_DIR) -> Path:
    """
    Download `url` into `dest_dir/<name>.zip`.
    Skips download if the file already exists (idempotent).
    Returns the path to the local file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(name)
    dest = dest_dir / f"{safe_name}.zip"

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

    # All retries exhausted
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
    """Strip characters that are problematic in filenames."""
    unsafe = r'/\:*?"<>|'
    return "".join(c for c in name if c not in unsafe)
