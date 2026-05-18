"""Unit tests for skill_level.mlit.scraper (no HTTP)."""

from __future__ import annotations

import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from skill_level.mlit.models import MlitIndustry
from skill_level.mlit.scraper import _extract_pdf_links, fetch_mlit_industries

# ---------------------------------------------------------------------------
# Sample HTML fixtures
# ---------------------------------------------------------------------------

_THREE_INDUSTRIES_HTML = """<html><body>
<table>
  <tr>
    <td><a href="/totikensangyo/const/content/001387650.pdf">電気工事</a></td>
    <td><a href="/totikensangyo/const/content/001398459.pdf">橋梁</a></td>
    <td><a href="/totikensangyo/const/content/001968043.pdf">造園</a></td>
  </tr>
</table>
</body></html>"""

_MIXED_LINKS_HTML = """<html><body>
<table>
  <tr>
    <td><a href="/totikensangyo/const/content/001387650.pdf">電気工事</a></td>
  </tr>
</table>
<!-- non-<td> links must be ignored -->
<div><a href="/totikensangyo/const/content/099999999.pdf">お知らせ</a></div>
<h4><a href="/totikensangyo/const/content/088888888.pdf">ガイドライン</a></h4>
<p><a href="/totikensangyo/const/content/077777777.pdf">手引き</a></p>
<!-- non-PDF <a> inside <td> must be ignored -->
<table><tr><td><a href="/totikensangyo/const/content/000000001.docx">ワード</a></td></tr></table>
<!-- external domain must be ignored -->
<table><tr><td><a href="https://example.com/foo.pdf">外部</a></td></tr></table>
</body></html>"""

_DUPLICATE_HREF_HTML = """<html><body>
<table>
  <tr>
    <td><a href="/totikensangyo/const/content/001387650.pdf">電気工事</a></td>
    <td><a href="/totikensangyo/const/content/001387650.pdf">電気工事（再掲）</a></td>
  </tr>
</table>
</body></html>"""


def _soup(html: str) -> BeautifulSoup:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExtractPdfLinks:
    def test_extracts_industries_from_td(self) -> None:
        result = _extract_pdf_links(_soup(_THREE_INDUSTRIES_HTML))
        assert len(result) == 3

    def test_industry_names_correct(self) -> None:
        result = _extract_pdf_links(_soup(_THREE_INDUSTRIES_HTML))
        names = [i.name for i in result]
        assert "電気工事" in names
        assert "橋梁" in names
        assert "造園" in names

    def test_absolute_url_constructed(self) -> None:
        result = _extract_pdf_links(_soup(_THREE_INDUSTRIES_HTML))
        assert all(i.pdf_url.startswith("https://www.mlit.go.jp") for i in result)
        assert (
            result[0].pdf_url
            == "https://www.mlit.go.jp/totikensangyo/const/content/001387650.pdf"
        )

    def test_ignores_non_td_links(self) -> None:
        result = _extract_pdf_links(_soup(_MIXED_LINKS_HTML))
        names = [i.name for i in result]
        assert names == ["電気工事"]

    def test_ignores_non_pdf_td_links(self) -> None:
        result = _extract_pdf_links(_soup(_MIXED_LINKS_HTML))
        assert all(i.pdf_url.endswith(".pdf") for i in result)

    def test_deduplicates_same_href(self) -> None:
        result = _extract_pdf_links(_soup(_DUPLICATE_HREF_HTML))
        assert len(result) == 1
        assert result[0].name == "電気工事"

    def test_empty_page_returns_empty_list(self) -> None:
        result = _extract_pdf_links(_soup("<html><body></body></html>"))
        assert result == []

    def test_industry_has_no_metadata_yet(self) -> None:
        result = _extract_pdf_links(_soup(_THREE_INDUSTRIES_HTML))
        ind = result[0]
        assert ind.ccus_codes is None
        assert ind.evaluation_body is None
        assert ind.title is None
        assert ind.id is None


class TestFetchMlitIndustriesOffline:
    def test_uses_provided_html(self) -> None:
        result = fetch_mlit_industries(html=_THREE_INDUSTRIES_HTML)
        assert len(result) == 3

    def test_returns_mlit_industry_objects(self) -> None:
        result = fetch_mlit_industries(html=_THREE_INDUSTRIES_HTML)
        assert all(isinstance(i, MlitIndustry) for i in result)

    def test_empty_html_returns_empty_list(self) -> None:
        result = fetch_mlit_industries(html="<html><body></body></html>")
        assert result == []
