#!/usr/bin/env python3
"""
Day 2 – Enrich scraped skincare products using Google Custom Search JSON API.

"""

from __future__ import annotations

import csv
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv


# ----------------------------
# Paths (run-from-anywhere)
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_CSV = BASE_DIR / "data" / "qudo_skincare_day1.csv"
OUTPUT_CSV = BASE_DIR / "data" / "qudo_skincare_day2_enriched.csv"


# ----------------------------
# API config
# ----------------------------
API_ENDPOINT = "https://customsearch.googleapis.com/customsearch/v1"
SLEEP_SECONDS = 1.0
NUM_RESULTS = 5


@dataclass(frozen=True)
class ApiCallEvidence:
    """Stores auditable API call details without relying on a long URL string."""
    endpoint: str
    cx: str
    query: str
    num: int


def load_secrets() -> Tuple[str, str]:
    """Load API credentials from .env."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_CSE_API_KEY")
    cx = os.getenv("GOOGLE_CSE_CX")
    if not api_key or not cx:
        raise RuntimeError("Missing GOOGLE_CSE_API_KEY or GOOGLE_CSE_CX in .env")
    return api_key, cx


def build_queries(product_name: str, brand: Optional[str]) -> List[str]:
    """Generate a small set of queries (at least one) for each product."""
    product_name = (product_name or "").strip()
    brand = (brand or "").strip()

    queries: List[str] = []
    if brand:
        queries.append(f"{brand} {product_name} official product")
    queries.append(f"{product_name} ingredients")
    queries.append(f"{product_name} EAN")
    return queries


def google_cse_search(api_key: str, cx: str, query: str, num: int = NUM_RESULTS) -> Dict:
    """Make a single Google Custom Search API request."""
    params = {"key": api_key, "cx": cx, "q": query, "num": int(num)}
    r = requests.get(API_ENDPOINT, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def domain(url: str) -> str:
    """Extract domain-ish part for scoring (simple)."""
    try:
        return url.split("//", 1)[1].split("/", 1)[0].lower()
    except Exception:
        return ""


def choose_best_result(items: List[Dict], brand: Optional[str]) -> Tuple[str, str]:
    """
    Pick best result link + title using simple heuristics:
    - Prefer results whose domain contains brand tokens (if brand exists)
    - Otherwise fall back to top-ranked result
    """
    if not items:
        return "", ""

    brand_tokens = set((brand or "").lower().replace("&", " ").split())
    best = None
    best_score = -1

    for it in items:
        link = it.get("link", "") or ""
        title = it.get("title", "") or ""
        d = domain(link)

        score = 0
        if brand_tokens:
            score += sum(1 for t in brand_tokens if t and t in d) * 3
            score += sum(1 for t in brand_tokens if t and t in title.lower())

        # small boost for likely official pages
        if any(x in d for x in ["official", "shop", "store"]):
            score += 1

        if score > best_score:
            best_score = score
            best = (link, title)

    return best if best else (items[0].get("link", ""), items[0].get("title", ""))


def reliability_score(best_url: str, brand: Optional[str]) -> int:
    """Simple, defensible reliability scoring."""
    if not best_url:
        return 0

    d = domain(best_url)
    score = 50

    # Brand-domain match gives strong confidence
    if brand:
        tokens = [t for t in brand.lower().replace("&", " ").split() if len(t) >= 3]
        if any(t in d for t in tokens):
            score += 25

    # Qudo itself (source of truth for Day 1) is a credible reference
    if "qudobeauty.com" in d:
        score += 10

    # Penalize obvious low-signal sources (very light)
    if any(x in d for x in ["blogspot", "wordpress"]):
        score -= 10

    return max(0, min(score, 100))


def confidence_label(score: int) -> str:
    if score >= 80:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def main() -> None:
    api_key, cx = load_secrets()

    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_CSV}")

    df = pd.read_csv(INPUT_CSV)
    df_enrich = df.head(10).copy()  # requirement: at least 10 products

    # Add Day 2 columns (clean and auditable)
    new_cols = [
        "cse_query_used",
        "cse_endpoint",
        "cse_cx",
        "cse_num",
        "official_product_page",
        "official_product_title",
        "reliability_score",
        "match_confidence",
        "sources_top5",
        "api_error",
    ]
    for c in new_cols:
        df_enrich[c] = ""

    for idx, row in df_enrich.iterrows():
        product_name = str(row.get("product_name", "")).strip()
        brand = str(row.get("brand", "")).strip() or None
        queries = build_queries(product_name, brand)

        collected_sources: List[str] = []
        best_url = ""
        best_title = ""
        query_used = ""
        api_error = ""

        # Ensure at least ONE API call per product; we attempt up to 3 queries
        for q in queries:
            try:
                data = google_cse_search(api_key, cx, q, num=NUM_RESULTS)
                items = data.get("items") or []

                # collect sources
                for it in items:
                    link = (it.get("link") or "").strip()
                    if link:
                        collected_sources.append(link)

                # choose a best candidate once
                if not best_url and items:
                    best_url, best_title = choose_best_result(items, brand)
                    query_used = q  # record the query that produced the chosen result

            except requests.HTTPError as e:
                # Record per-product error but continue
                api_error = f"HTTPError: {e}"
            except Exception as e:
                api_error = f"Error: {e}"

            time.sleep(SLEEP_SECONDS)

        score = reliability_score(best_url, brand)
        conf = confidence_label(score)

        # Store structured API evidence (avoids CSV mixing issues)
        evidence = ApiCallEvidence(
            endpoint=API_ENDPOINT,
            cx=cx,
            query=query_used or queries[0],
            num=NUM_RESULTS,
        )

        # Deduplicate sources, keep top 5
        unique_sources = list(dict.fromkeys(collected_sources))[:5]

        df_enrich.at[idx, "cse_query_used"] = evidence.query
        df_enrich.at[idx, "cse_endpoint"] = evidence.endpoint
        df_enrich.at[idx, "cse_cx"] = evidence.cx
        df_enrich.at[idx, "cse_num"] = evidence.num
        df_enrich.at[idx, "official_product_page"] = best_url
        df_enrich.at[idx, "official_product_title"] = best_title
        df_enrich.at[idx, "reliability_score"] = score
        df_enrich.at[idx, "match_confidence"] = conf
        df_enrich.at[idx, "sources_top5"] = " | ".join(unique_sources)
        df_enrich.at[idx, "api_error"] = api_error

        print(f"[{idx}] {product_name} -> {best_url} ({conf}, {score})")

    # CSV-safe output
    df_enrich.to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8",
        quoting=csv.QUOTE_MINIMAL
    )
    print(f"\nSaved: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
