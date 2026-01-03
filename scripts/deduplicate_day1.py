#!/usr/bin/env python3
"""
Removes duplicate products from the Day 1 dataset using
product_url as the unique identifier.
"""

import pandas as pd
from pathlib import Path

# Resolve project root
BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_CSV = BASE_DIR / "data" / "qudo_skincare_day1.csv"
OUTPUT_CSV = BASE_DIR / "data" / "qudo_skincare_day1_deduped.csv"


def main():
    """
    Reads Day 1 CSV, removes duplicates, and writes a clean file.
    """
    df = pd.read_csv(INPUT_CSV)

    before = len(df)
    df = df.drop_duplicates(subset=["product_url"], keep="first")
    after = len(df)

    df.to_csv(OUTPUT_CSV, index=False)

    print(f"Rows before deduplication: {before}")
    print(f"Rows after deduplication:  {after}")
    print(f"Saved cleaned file to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
