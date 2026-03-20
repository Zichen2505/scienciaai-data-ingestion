#!/usr/bin/env python3
"""
Collect a recent-window crawl and produce time-bucketed samples.

Saves:
- deduplicated raw crawl -> data/checkpoints/<app_id>_recent_window_raw.jsonl
- sampled output ->   data/checkpoints/<app_id>_recent_window_sampled.jsonl
"""
from pathlib import Path
import sys
import argparse
import json
import uuid
from datetime import datetime, timezone, timedelta
from statistics import median
from typing import Any
import random

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
        return datetime.strptime(str(s), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None

def write_jsonl(path: Path, obj: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def collect_recent_window(
    app_id: str,
    lang: str,
    country: str,
    target_days: int,
    per_page: int,
    max_pages: int,
    num_buckets: int,
    sample_per_bucket: int,
    seed: int,
):
    run_id = uuid.uuid4().hex[:8]
    raw_out = OUT_DIR / f"{app_id}_recent_window_raw_{run_id}.jsonl"
    sampled_out = OUT_DIR / f"{app_id}_recent_window_sampled_{run_id}.jsonl"

    continuation = None
    pages_fetched = 0
    total_fetched = 0
    seen = {}
    duplicate_count = 0
    at_values = []

    for page_idx in range(1, max_pages + 1):
        items, continuation = fetch_reviews_page(app_id, lang, country, per_page, continuation)
        pages_fetched += 1
        total_fetched += len(items)

        for it in items:
            nr = normalize_review(app_id, lang, country, it)
            rid = nr.get("review_id")
            if rid in seen:
                duplicate_count += 1
            else:
                seen[rid] = nr
                at = parse_iso_z(nr.get("at"))
                if at:
                    at_values.append(at)

        # compute observed span
        if at_values:
            cur_min = min(at_values)
            cur_max = max(at_values)
            span_days = (cur_max - cur_min).total_seconds() / 86400.0
        else:
            span_days = 0.0

        # stop when target reached
        if span_days >= target_days:
            break

        if not items or continuation is None:
            break

    # write deduplicated raw
    with raw_out.open("w", encoding="utf-8") as f:
        for nr in seen.values():
            f.write(json.dumps(nr, ensure_ascii=False, default=str) + "\n")

    overall_min = min(at_values).isoformat() if at_values else None
    overall_max = max(at_values).isoformat() if at_values else None
    observed_span_days = (max(at_values) - min(at_values)).total_seconds() / 86400.0 if at_values else 0.0

    # bucket by equal-width time intervals
    buckets = []
    sampled_total = 0
    if at_values:
        overall_min_dt = min(at_values)
        overall_max_dt = max(at_values)
        total_range = (overall_max_dt - overall_min_dt)
        # if zero range, make tiny range to avoid div zero
        if total_range.total_seconds() == 0:
            total_range = timedelta(seconds=1)
        bucket_width = total_range / num_buckets

        # assign items to buckets
        items_by_bucket = [[] for _ in range(num_buckets)]
        for nr in seen.values():
            at = parse_iso_z(nr.get("at"))
            if at is None:
                continue
            # compute bucket index
            idx = int(((at - overall_min_dt).total_seconds() / total_range.total_seconds()) * num_buckets)
            if idx < 0:
                idx = 0
            if idx >= num_buckets:
                idx = num_buckets - 1
            items_by_bucket[idx].append(nr)

        rng = random.Random(seed)
        # sample and write per-bucket
        with sampled_out.open("w", encoding="utf-8") as sf:
            for i in range(num_buckets):
                start = (overall_min_dt + bucket_width * i).isoformat()
                end = (overall_min_dt + bucket_width * (i + 1)).isoformat()
                avail = len(items_by_bucket[i])
                take = min(sample_per_bucket, avail)
                sampled = rng.sample(items_by_bucket[i], take) if avail >= take and take > 0 else list(items_by_bucket[i])
                for s in sampled:
                    sf.write(json.dumps(s, ensure_ascii=False, default=str) + "\n")
                sampled_total += len(sampled)
                buckets.append({
                    "bucket_index": i,
                    "start": start,
                    "end": end,
                    "available": avail,
                    "sampled": len(sampled),
                })
    else:
        # no timestamps: empty buckets
        for i in range(num_buckets):
            buckets.append({
                "bucket_index": i,
                "start": None,
                "end": None,
                "available": 0,
                "sampled": 0,
            })

    # print summary
    print("Recent-window crawl summary")
    print("---------------------------")
    print("app_id:", app_id)
    print("run_id:", run_id)
    print("pages_fetched:", pages_fetched)
    print("total_fetched_items:", total_fetched)
    print("unique_review_ids:", len(seen))
    print("duplicate_count:", duplicate_count)
    print("overall_min_at:", overall_min)
    print("overall_max_at:", overall_max)
    print("observed_span_days:", round(observed_span_days, 3))
    print("raw_output:", raw_out)
    print("sampled_output:", sampled_out)
    print("\nBuckets:")
    for b in buckets:
        print(f"  idx={b['bucket_index']:2d} start={b['start']} end={b['end']} available={b['available']:4d} sampled={b['sampled']:4d}")

    return {
        "raw_out": str(raw_out),
        "sampled_out": str(sampled_out),
        "pages_fetched": pages_fetched,
        "total_fetched": total_fetched,
        "unique": len(seen),
        "duplicates": duplicate_count,
        "overall_min": overall_min,
        "overall_max": overall_max,
        "observed_span_days": observed_span_days,
        "buckets": buckets,
    }

def main():
    ap = argparse.ArgumentParser(description="Collect recent-window crawl and sample per time bucket")
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--target-days", type=int, required=True)
    ap.add_argument("--per-page", type=int, default=40)
    ap.add_argument("--max-pages", type=int, default=500)
    ap.add_argument("--num-buckets", type=int, default=10)
    ap.add_argument("--sample-per-bucket", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--country", default="us")
    args = ap.parse_args()

    collect_recent_window(
        app_id=args.app_id,
        lang=args.lang,
        country=args.country,
        target_days=args.target_days,
        per_page=args.per_page,
        max_pages=args.max_pages,
        num_buckets=args.num_buckets,
        sample_per_bucket=args.sample_per_bucket,
        seed=args.seed,
    )

if __name__ == "__main__":
    main()