"""
MLIT 建設技能者能力評価基準 パイプライン.

Usage:
  uv run python mlit_main.py            # 全49業種を処理
  uv run python mlit_main.py --scout    # 最初の1業種のみ確認
"""

from __future__ import annotations

import sys

from skill_level import database as base_db
from skill_level.mlit import database as mlit_db
from skill_level.mlit import downloader, scraper
from skill_level.mlit.parser import parse_pdf


def run_pipeline(scout_mode: bool = False) -> None:
    print("Connecting to database …")
    conn = base_db.connect()
    base_db.init_schema(conn)  # 既存テーブルも維持
    mlit_db.init_schema(conn)  # mlit_* テーブル追加

    print("Scraping MLIT industry list …")
    industries = scraper.fetch_mlit_industries()

    if not industries:
        print("[ERROR] No industries found — check scraper or page structure.")
        sys.exit(1)

    print(f"Found {len(industries)} industries")

    if scout_mode:
        industries = industries[:1]
        print(f"[Scout mode] Processing only: {industries[0].name}")

    for industry in industries:
        print(f"\n{'─' * 50}")
        print(f"Industry: {industry.name}")

        # --- Download PDF -------------------------------------------------------
        print(f"  Downloading {industry.pdf_url} …")
        pdf_path = downloader.download_pdf(industry.name, industry.pdf_url)
        print(f"  Saved: {pdf_path}")

        # --- Parse PDF ----------------------------------------------------------
        print("  Parsing PDF …")
        # 仮 industry_id で parse してから DB 登録後に差し替え
        updated_industry, criteria = parse_pdf(pdf_path, industry, industry_id=0)

        # --- DB: upsert industry (with parsed header data) ----------------------
        industry_id = mlit_db.upsert_industry(conn, updated_industry)

        # criterion の industry_id を確定値に差し替え
        for c in criteria:
            c.industry_id = industry_id

        # --- DB: insert criteria (冪等: 既存分を削除して再挿入) -----------------
        mlit_db.delete_criteria_for_industry(conn, industry_id)
        mlit_db.insert_criteria(conn, criteria)
        mlit_db.mark_processed(conn, industry_id)

        print(f"  Stored {len(criteria)} criteria rows (industry_id={industry_id})")

        if scout_mode:
            print("\n[Scout] Sample rows:")
            for c in criteria[:5]:
                print(f"  {c.level} / {c.criterion_type}: {c.criterion_text[:80]}")
            print("\nRun without --scout to process all industries.")
            conn.close()
            return

    conn.close()
    print(f"\nDone. DB: {base_db.DB_PATH}")
    print("Tables: mlit_industries, mlit_level_criteria")


def main() -> None:
    scout = "--scout" in sys.argv
    run_pipeline(scout_mode=scout)


if __name__ == "__main__":
    main()
