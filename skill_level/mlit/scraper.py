"""
Scraper for https://www.mlit.go.jp/totikensangyo/const/totikensangyo_const_fr2_000040.html

The page lists 49 construction industries, each linked to a PDF.
PDF hrefs match the pattern:  /totikensangyo/const/content/XXXXXX.pdf
"""

from __future__ import annotations

import warnings

import httpx
from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

from skill_level.mlit.models import MlitIndustry

BASE_URL = "https://www.mlit.go.jp"
SOURCE_URL = f"{BASE_URL}/totikensangyo/const/totikensangyo_const_fr2_000040.html"
_PDF_PATH_PREFIX = "/totikensangyo/const/content/"


def fetch_mlit_industries(html: str | None = None) -> list[MlitIndustry]:
    """Return MlitIndustry list scraped from MLIT page.

    Pass `html` to skip HTTP (useful for tests).
    """
    if html is None:
        resp = httpx.get(SOURCE_URL, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        html = resp.text

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")
    return _extract_pdf_links(soup)


def _extract_pdf_links(soup: BeautifulSoup) -> list[MlitIndustry]:
    # 業種リンクは <td> 直下の <a> のみ（お知らせや手引き等は <div>/<p> 直下）
    seen: set[str] = set()
    industries: list[MlitIndustry] = []

    for a in soup.find_all("a"):
        if not isinstance(a, Tag):
            continue
        parent = a.parent
        if not isinstance(parent, Tag) or parent.name != "td":
            continue
        href = str(a.get("href", ""))
        if not href.startswith(_PDF_PATH_PREFIX) or not href.lower().endswith(".pdf"):
            continue

        name = a.get_text(strip=True)
        if not name or href in seen:
            continue

        seen.add(href)
        absolute = f"{BASE_URL}{href}"
        industries.append(MlitIndustry(name=name, pdf_url=absolute))

    return industries
