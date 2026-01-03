#!/usr/bin/env python3
"""
Day 2 Deduplication Script

"""

from pathlib import Path
import pandas as pd


# ----------------------------
# Paths (run-from-anywhere)
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_CSV = BASE_DIR / "data" / "qudo_skincare_day2_enriched.csv"
OUTPUT_CSV = BASE_DIR / "data" / "qudo_skincare_day2_enriched_final.csv"


def clean_sources(cell: str) -> str:
    """
    Deduplicate URLs within a pipe-separated cell.
    Preserves original order.
    """
    if pd.isna(cell) or not cell.strip():
        return ""

    urls = [u.strip() for u in cell.split("|") if u.strip()]
    unique_urls = list(dict.fromkeys(urls))  # order-preserving
    return " | ".join(unique_urls)


def main() -> None:
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)

    # ----------------------------
    # 1) Remove duplicate rows
    # ----------------------------
    dedupe_key = "product_url" if "product_url" in df.columns else "product_name"

    before_rows = len(df)
    df = df.drop_duplicates(subset=[dedupe_key])
    after_rows = len(df)

    print(f"Removed {before_rows - after_rows} duplicate rows")

    # ----------------------------
    # 2) Clean sources_top5 column
    # ----------------------------
    if "sources_top5" in df.columns:
        df["sources_top5"] = df["sources_top5"].apply(clean_sources)

    # ----------------------------
    # Save final output
    # ----------------------------
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Final Day 2 file saved: {OUTPUT_CSV}")
    print(f"Final row count: {len(df)}")


if __name__ == "__main__":
    main()
