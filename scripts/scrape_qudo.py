#!/usr/bin/env python3

"""
Scrapes product data from Qudo's website and saves it to a CSV file.
"""

from __future__ import annotations

import csv
import re
import time
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


# --------- Paths (path-safe) ----------
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_URLS = BASE_DIR / "data" / "product_urls.txt"
OUTPUT_CSV = BASE_DIR / "data" / "qudo_skincare_day1.csv"


# --------- HTTP settings ----------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}
REQUEST_TIMEOUT = 20
SLEEP_SECONDS = 1.5  # polite delay


def clean_text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def first_non_empty(*vals: Optional[str]) -> Optional[str]:
    for v in vals:
        if v and v.strip():
            return v.strip()
    return None


def find_value_in_text(page_text: str, label: str) -> Optional[str]:
    """
    Extract value like:
      'EAN: 8809...' or 'Country of Origin: South Korea'
    """
    # Match label: value until line break
    pattern = rf"{re.escape(label)}\s*:\s*(.+)"
    m = re.search(pattern, page_text, flags=re.IGNORECASE)
    if not m:
        return None
    # stop at newline-like separators
    value = m.group(1).split("\n")[0].strip()
    return clean_text(value)


def normalize_category(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    x = raw.replace("Wholesale", "").strip()
    # Simple normalizations
    x = re.sub(r"\s+", " ", x)
    # Singularize very lightly (optional)
    x = x.replace("Face Masks", "Face Mask")
    return x or None


def normalize_size(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    x = raw
    x = x.replace("(", "").replace(")", "")
    x = re.sub(r"\s+", " ", x).strip()
    # standardize spacing a little
    x = x.replace("ml", " ml").replace("g", " g")
    x = re.sub(r"\s+", " ", x).strip()
    # undo double spaces introduced
    x = x.replace("  ", " ")
    return x


def extract_main_image_url(soup: BeautifulSoup) -> Optional[str]:
    """
    Try common WooCommerce product image patterns.
    """
    selectors = [
        "figure.woocommerce-product-gallery__wrapper img",
        ".woocommerce-product-gallery__image img",
        "img.wp-post-image",
        "img.attachment-woocommerce_single",
        "img",  # final fallback
    ]
    for sel in selectors:
        img = soup.select_one(sel)
        if img and img.get("src"):
            return clean_text(img["src"])
    return None


def extract_ingredients_key_actives(soup: BeautifulSoup) -> Optional[str]:
    """
    If full INCI is not present, capture the 'Product contains' key actives list.
    Returns a semicolon-separated list if found.
    """
    # Approach 1: find a heading/strong label "Product contains" then capture following list items
    text = soup.get_text("\n", strip=True)

    if "Product contains" not in text:
        return None

    # Try to extract a block after "Product contains:" up to "Product effects:" or "Recommended for:" etc.
    block = None
    m = re.search(r"Product contains\s*:\s*(.+)", text, flags=re.IGNORECASE | re.DOTALL)
    if m:
        block = m.group(1)

        # Stop at likely next section headings
        stop_markers = [
            "\nProduct effects",
            "\nRecommended for",
            "\nHow to use",
            "\nCapacity",
            "\nExpiration date",
            "\nCountry of origin",
            "\nEAN",
            "\nSKU",
        ]
        for sm in stop_markers:
            idx = block.lower().find(sm.strip().lower())
            if idx != -1:
                block = block[:idx]
                break

    if not block:
        return None

    # Extract candidate ingredient/active names from lines (keep it conservative)
    lines = [ln.strip(" -•\t") for ln in block.split("\n") if ln.strip()]
    # Filter out descriptive sentences; keep shorter lines or lines that look like "X – description"
    actives = []
    for ln in lines:
        # keep the left side before dash if present
        left = ln.split("–")[0].split("-")[0].strip()
        # avoid long paragraphs
        if 2 <= len(left) <= 80:
            actives.append(left)

    actives = [a for a in actives if a and not a.lower().startswith("product")]

    if not actives:
        return None

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for a in actives:
        key = a.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(a)

    return "; ".join(uniq) if uniq else None


def parse_product_page(url: str) -> Dict[str, Optional[str]]:
    r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    page_text = soup.get_text("\n", strip=True)

    # Product name: usually h1
    h1 = soup.select_one("h1")
    title = clean_text(h1.get_text(strip=True) if h1 else None)

    # Brand / Category / Capacity / EAN / SKU / Country
    brand = find_value_in_text(page_text, "Brand")
    raw_category = find_value_in_text(page_text, "Category")
    category = normalize_category(raw_category)

    capacity = find_value_in_text(page_text, "Capacity")
    size_packaging = normalize_size(capacity)

    # Ingredients: try key actives (since some pages don’t have full INCI)
    ingredients = extract_ingredients_key_actives(soup)

    image_url = extract_main_image_url(soup)

    # Source flags
    brand_source = "explicit_text" if brand else "missing"
    size_source = "capacity_section" if size_packaging else "missing"

    notes = []
    if not brand:
        notes.append("Brand not explicitly stated on product page")
    if not size_packaging:
        notes.append("Size/packaging not explicitly stated on product page")
    if ingredients:
        notes.append("Ingredients captured as key actives (full INCI not confirmed)")
    else:
        notes.append("Ingredients not found on product page")

    return {
        "product_name": title,
        "brand": brand,
        "category": category,
        "ingredients": ingredients,
        "size_packaging": size_packaging,
        "image_url": image_url,
        "product_url": url,
        "brand_source": brand_source,
        "size_source": size_source,
        "notes": "; ".join(notes),
    }


def read_urls() -> list[str]:
    if not INPUT_URLS.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_URLS}")
    urls = []
    for line in INPUT_URLS.read_text(encoding="utf-8").splitlines():
        u = line.strip()
        if u and not u.startswith("#"):
            urls.append(u)
    # dedupe URL list while preserving order
    seen = set()
    uniq = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def main() -> None:
    urls = read_urls()
    if not urls:
        print("No URLs found in product_urls.txt")
        return

    rows = []
    for i, url in enumerate(urls, start=1):
        try:
            print(f"[{i}/{len(urls)}] Scraping: {url}")
            row = parse_product_page(url)
            rows.append(row)
        except Exception as e:
            print(f"  !! Failed: {url} | {e}")
        time.sleep(SLEEP_SECONDS)

    if not rows:
        print("No rows scraped. Exiting.")
        return

    df_new = pd.DataFrame(rows)

    # If output exists, append then dedupe by product_url
    if OUTPUT_CSV.exists():
        df_old = pd.read_csv(OUTPUT_CSV)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_all = df_new

    # Deduplicate by product_url (keep first occurrence)
    if "product_url" in df_all.columns:
        df_all = df_all.drop_duplicates(subset=["product_url"], keep="first")

    # Write CSV safely
    df_all.to_csv(
        OUTPUT_CSV,
        index=False,
        quoting=csv.QUOTE_MINIMAL,
        encoding="utf-8"
    )

    print(f"Saved: {OUTPUT_CSV}")
    print(f"Total unique products: {len(df_all)}")


if __name__ == "__main__":
    main()
