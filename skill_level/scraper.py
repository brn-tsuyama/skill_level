"""
Rule-based scraper for https://www.mhlw.go.jp/stf/newpage_04653.html

Page structure (confirmed from raw HTML):
  Section 2 — ZIP download table:
    <table class="m-table">
      <thead><tr><th>あ</th><th>い</th>...</tr></thead>
      <tbody>
        <tr>
          <td>（建設業関係）<br/><a href="/content/.../xxxxx.zip">型枠工事業</a></td>
          <td>（製造業関係）<br/><a href="...">電気機械器具製造業</a></td>
          ...
        </tr>
      </tbody>
    </table>

Strategy (no LLM):
  Each ZIP <td> has the category label "（建設業関係）" as its visible text.
  → Find every <td> whose text contains "建設業関係"
  → Extract the <a href="*.zip"> inside it
  One pass, no fuzzy matching needed.
"""

import httpx
from bs4 import BeautifulSoup, Tag

from skill_level.models import Industry

BASE_URL = "https://www.mhlw.go.jp"
SOURCE_URL = f"{BASE_URL}/stf/newpage_04653.html"
CONSTRUCTION_LABEL = "建設業関係"


def fetch_construction_industries(html: str | None = None) -> list[Industry]:
    """
    Return Industries for 建設業関係.
    Pass `html` to skip HTTP (useful for tests / offline inspection).
    """
    if html is None:
        resp = httpx.get(SOURCE_URL, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "lxml")
    return _extract_from_zip_table(soup)


def _extract_from_zip_table(soup: BeautifulSoup) -> list[Industry]:
    """
    Scan every <td> in the ZIP download table.
    A cell belongs to 建設業関係 when its text contains "建設業関係".
    The <a href="*.zip"> inside is the industry ZIP link.
    """
    industries: list[Industry] = []

    for td in soup.find_all("td"):
        if not isinstance(td, Tag):
            continue
        if CONSTRUCTION_LABEL not in td.get_text():
            continue

        # This <td> is labelled 建設業関係 — find the ZIP link inside it
        for a in td.find_all("a"):
            if not isinstance(a, Tag):
                continue
            href = str(a.get("href", ""))
            if not href.lower().endswith(".zip"):
                continue
            name = a.get_text(strip=True)
            if not name:
                continue
            absolute = href if href.startswith("http") else f"{BASE_URL}{href}"
            industries.append(
                Industry(name=name, category=CONSTRUCTION_LABEL, zip_url=absolute)
            )

    return industries
