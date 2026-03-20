#!/usr/bin/env python3
"""
Minimal pagination verification:
- fetch several pages using existing client
- normalize reviews
- print per-page: index, count, min_at, max_at, sample review_ids
"""
from pathlib import Path
import sys
import argparse
from datetime import datetime, timezone
from statistics import median

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sciencia_ingestion.sources.google_play.client import fetch_reviews_page
from sciencia_ingestion.sources.google_play.normalize import normalize_review

def parse_iso_z(s: str):
    if s is None:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--country", default="us")
    ap.add_argument("--pages", type=int, default=5, help="number of pages/batches to fetch")
    ap.add_argument("--per-page", type=int, default=40, help="count per page request")
    args = ap.parse_args()

    continuation = None
    page_summaries = []

    for i in range(1, args.pages + 1):
        items, continuation = fetch_reviews_page(args.app_id, args.lang, args.country, args.per_page, continuation)
        at_list = []
        ids = []
        for it in items:
            nr = normalize_review(args.app_id, args.lang, args.country, it)
            at = parse_iso_z(nr.get("at"))
            if at:
                at_list.append(at)
            ids.append(nr.get("review_id"))
        if at_list:
            min_at = min(at_list).isoformat()
            max_at = max(at_list).isoformat()
            med_ts = median([dt.timestamp() for dt in at_list])
            med_at = datetime.fromtimestamp(med_ts, tz=timezone.utc).isoformat()
        else:
            min_at = max_at = med_at = None
        page_summaries.append({
            "page": i,
            "count": len(items),
            "min_at": min_at,
            "max_at": max_at,
            "median_at": med_at,
            "sample_ids": ids[:3],
        })
        # stop early if no items or continuation is None
        if not items or continuation is None:
            break

    # print compact summary
    print("Pagination verification summary")
    print("------------------------------")
    for p in page_summaries:
        print(f"page={p['page']:2d} count={p['count']:3d} min_at={p['min_at']} max_at={p['max_at']} sample_ids={p['sample_ids']}")
    # quick trend check on max_at values
    max_times = [p["max_at"] for p in page_summaries if p["max_at"]]
    if len(max_times) >= 2:
        # check if max_at is non-increasing (older)
        non_increasing = all(max_times[i] >= max_times[i+1] for i in range(len(max_times)-1))
        if non_increasing:
            print("\nPreliminary: timestamps move older or stay same across pages (suggests pagination reaches older reviews).")
        else:
            print("\nPreliminary: timestamps do NOT consistently move older across pages (behavior may be recent-skewed or unstable).")
    else:
        print("\nPreliminary: not enough timestamp data to judge.")

if __name__ == "__main__":
    main()