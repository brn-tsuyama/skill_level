"""
Entry point for the skill-level pipeline.

Usage:
  uv run python main.py             # full pipeline (all industries)
  uv run python main.py --scout     # download + extract first industry,
                                    # print directory/sheet layout, then stop
"""

from __future__ import annotations

import sys

from skill_level import database, downloader, extractor, parser, scraper


def run_pipeline(scout_mode: bool = False) -> None:
    print("Connecting to database …")
    conn = database.connect()
    database.init_schema(conn)

    print("Scraping industry list …")
    industries = scraper.fetch_construction_industries()

    if not industries:
        print("[ERROR] No industries found — check scraper or page structure.")
        sys.exit(1)

    print(f"Found {len(industries)} industries: {[i.name for i in industries]}")

    if scout_mode:
        industries = industries[:1]
        print(f"\n[Scout mode] Processing only: {industries[0].name}")

    for industry in industries:
        print(f"\n{'─' * 50}")
        print(f"Industry: {industry.name}")

        # --- Download -------------------------------------------------------
        print(f"  Downloading {industry.zip_url} …")
        zip_path = downloader.download_zip(industry.name, industry.zip_url)
        print(f"  Saved: {zip_path}")

        # --- DB: register industry ------------------------------------------
        industry_id = database.upsert_industry(conn, industry)

        # --- Extract --------------------------------------------------------
        print("  Extracting ZIP …")
        industry_dir = extractor.extract_zip(zip_path, industry.name)
        summary = extractor.summarise(industry_dir)
        for ext_name, files in summary.items():
            print(f"    {ext_name or '(no ext)'}: {len(files)} files")

        if scout_mode:
            print("\n[Scout] Directory and sheet structure:")
            print(parser.scout(industry_dir))
            print("\nRun without --scout to process all industries.")
            conn.close()
            return

        # --- Parse ----------------------------------------------------------
        print("  Parsing Excel files …")
        skill_sheets = parser.parse_industry_dir(industry_dir, industry_id)
        print(f"  Found {len(skill_sheets)} skill sheets")

        # --- DB: insert -----------------------------------------------------
        total_criteria = 0
        for sheet in skill_sheets:
            sheet_id = database.insert_skill_sheet(conn, sheet)
            database.insert_skill_criteria(conn, sheet_id, sheet.criteria)
            database.insert_required_knowledge(conn, sheet_id, sheet.knowledge)
            total_criteria += len(sheet.criteria)

        database.mark_processed(conn, industry_id)
        print(f"  Stored {total_criteria} criteria across {len(skill_sheets)} sheets")

    conn.close()
    print("\nDone. DB: data/db/skill_level.duckdb")


def main() -> None:
    scout = "--scout" in sys.argv
    run_pipeline(scout_mode=scout)


if __name__ == "__main__":
    main()
