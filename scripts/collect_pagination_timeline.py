#!/usr/bin/env python3
"""
Collect a sequential pagination timeline for a Google Play app.

Saves normalized reviews to data/checkpoints/{app_id}_timeline_{run_id}.jsonl
and prints a per-page summary plus final totals.

Minimal, modular, and readable.
"""
from pathlib import Path
import sys
import argparse
import json
import uuid
from datetime import datetime, timezone
from statistics import median
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sciencia_ingestion.sources.google_play.client import fetch_reviews_page
from sciencia_ingestion.sources.google_play.normalize import normalize_review

OUT_DIR = PROJECT_ROOT / "data" / "checkpoints"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def parse_iso_z(s: Any):
    if s is None:
        return None
    if isinstance(s, datetime):
        return s.astimezone(timezone.utc).replace(microsecond=0)
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None

def write_jsonl(path: Path, obj: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def collect_timeline(app_id: str, lang: str, country: str, pages: int, per_page: int):
    run_id = uuid.uuid4().hex[:10]
    out_path = OUT_DIR / f"{app_id}_timeline_{run_id}.jsonl"

    continuation = None
    page_summaries = []
    total_fetched = 0
    seen_ids = set()
    duplicate_count = 0
    overall_mins = []
    overall_maxs = []

    for page_idx in range(1, pages + 1):
        items, continuation = fetch_reviews_page(app_id, lang, country, per_page, continuation)
        total_fetched += len(items)

        normalized = []
        at_list = []
        ids = []

        for it in items:
            nr = normalize_review(app_id, lang, country, it)
            write_jsonl(out_path, nr)
            rid = nr.get("review_id")
            ids.append(rid)
            if rid in seen_ids:
                duplicate_count += 1
            else:
                seen_ids.add(rid)
            at = parse_iso_z(nr.get("at"))
            if at:
                at_list.append(at)

        if at_list:
            min_at = min(at_list)
            max_at = max(at_list)
            med_ts = median([dt.timestamp() for dt in at_list])
            med_at = datetime.fromtimestamp(med_ts, tz=timezone.utc)
            overall_mins.append(min_at)
            overall_maxs.append(max_at)
            min_at_s = min_at.isoformat()
            max_at_s = max_at.isoformat()
            med_at_s = med_at.isoformat()
        else:
            min_at_s = max_at_s = med_at_s = None

        page_summaries.append({
            "page": page_idx,
            "count": len(items),
            "min_at": min_at_s,
            "max_at": max_at_s,
            "median_at": med_at_s,
            "sample_ids": ids[:3],
        })

        # stop if no items or continuation exhausted
        if not items or continuation is None:
            break

    # final overall min/max
    overall_min = min(overall_mins).isoformat() if overall_mins else None
    overall_max = max(overall_maxs).isoformat() if overall_maxs else None

    # print summaries
    print("Pagination timeline summary")
    print("--------------------------")
    for p in page_summaries:
        print(f"page={p['page']:2d} count={p['count']:3d} min_at={p['min_at']} max_at={p['max_at']} sample_ids={p['sample_ids']}")
    print("\nFinal totals")
    print("------------")
    print("output_file:", out_path)
    print("pages_fetched:", len(page_summaries))
    print("total_fetched_items:", total_fetched)
    print("unique_review_ids:", len(seen_ids))
    print("duplicate_count:", duplicate_count)
    print("overall_min_at:", overall_min)
    print("overall_max_at:", overall_max)

    return {
        "out_path": str(out_path),
        "pages_fetched": len(page_summaries),
        "total_fetched": total_fetched,
        "unique": len(seen_ids),
        "duplicates": duplicate_count,
        "overall_min": overall_min,
        "overall_max": overall_max,
    }

def main():
    ap = argparse.ArgumentParser(description="Collect pagination timeline for Google Play app")
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--country", default="us")
    ap.add_argument("--pages", type=int, default=50, help="max pages to fetch")
    ap.add_argument("--per-page", type=int, default=40, help="count per page")
    args = ap.parse_args()

    collect_timeline(args.app_id, args.lang, args.country, args.pages, args.per_page)

if __name__ == "__main__":
    main()