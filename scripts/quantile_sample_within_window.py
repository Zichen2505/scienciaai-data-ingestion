#!/usr/bin/env python3
"""
Within-window quantile time sampling (smallest implementation).

Reads a recent-window raw jsonl, sorts by `at`, splits into quantile buckets,
samples from each bucket, writes sampled jsonl, writes a summary JSON report,
and prints the same summary to the terminal.

This preserves the original within-window quantile time sampling logic.
"""
from pathlib import Path
import sys
import argparse
import json
import random
from datetime import datetime, timezone
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "data" / "checkpoints"
REPORTS_DIR = PROJECT_ROOT / "reports"

def parse_iso_z(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None

def find_latest_raw(app_id: str):
    files = list(OUT_DIR.glob(f"{app_id}_recent_window_raw_*.jsonl"))
    return max(files, key=lambda p: p.stat().st_mtime) if files else None

def load_records_with_stats(path: Path):
    """
    Read jsonl, return list of (at_datetime, obj) for records with parseable at,
    plus a stats dict:
      total_input_rows, null_at_count, null_content_count
    """
    recs = []
    total = 0
    null_at = 0
    null_content = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                obj = json.loads(line)
            except Exception:
                # skip malformed lines but count them as input rows
                continue
            at_raw = obj.get("at")
            at = parse_iso_z(at_raw)
            if at is None:
                null_at += 1
            content = obj.get("content")
            if content is None or (isinstance(content, str) and content.strip() == ""):
                null_content += 1
            if at is not None:
                recs.append((at, obj))
    stats = {
        "total_input_rows": total,
        "null_at_count": null_at,
        "null_content_count": null_content,
    }
    return recs, stats

def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-file", type=Path, help="Path to recent_window_raw jsonl (optional)")
    ap.add_argument("--app-id", help="App id to auto-find latest raw file (used if --raw-file omitted)")
    ap.add_argument("--buckets", type=int, default=5, help="number of quantile buckets (default 5)")
    ap.add_argument("--sample-per-bucket", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if args.raw_file:
        raw_path = args.raw_file
    else:
        if not args.app_id:
            print("Either --raw-file or --app-id must be provided", file=sys.stderr)
            sys.exit(2)
        raw_path = find_latest_raw(args.app_id)
        if raw_path is None:
            print("No recent_window_raw file found for", args.app_id, file=sys.stderr)
            sys.exit(2)

    records, stats = load_records_with_stats(raw_path)
    if not records:
        print("No records with parsable timestamps in", raw_path)
        # still write a minimal summary file to reports for auditing
        run_id = random.Random(args.seed).getrandbits(32)
        summary_obj = {
            "run_id": str(run_id),
            "input_file": str(raw_path),
            "output_sample_file": None,
            "total_input_rows": stats.get("total_input_rows", 0),
            "total_sampled_rows": 0,
            "number_of_buckets": args.buckets,
            "target_per_bucket": args.sample_per_bucket,
            "actual_counts_per_bucket": [],
            "duplicate_review_ids": [],
            "null_content_count": stats.get("null_content_count", 0),
            "null_at_count": stats.get("null_at_count", 0),
            "min_at": None,
            "max_at": None,
        }
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        summary_path = REPORTS_DIR / f"quantile_sample_summary_{run_id}.json"
        write_json(summary_path, summary_obj)
        print(json.dumps(summary_obj, ensure_ascii=False, indent=2, default=str))
        sys.exit(0)

    # sort by timestamp ascending (oldest -> newest)
    records.sort(key=lambda x: x[0])
    n = len(records)
    k = args.buckets
    base = n // k

    rng = random.Random(args.seed)
    run_id = rng.getrandbits(32)
    sampled_path = OUT_DIR / f"{raw_path.stem}_sampled_quantiles_{run_id}.jsonl"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    sampled_objects = []
    actual_counts_per_bucket = []
    # perform sampling and write sampled jsonl
    with sampled_path.open("w", encoding="utf-8") as outf:
        start = 0
        for i in range(k):
            end = start + base + (1 if i < (n % k) else 0)
            bucket = records[start:end]
            avail = len(bucket)
            sampled = []
            if avail > 0:
                take = min(args.sample_per_bucket, avail)
                # sample returns dict objects (r[1])
                sampled = rng.sample([r[1] for r in bucket], take) if take < avail else [r[1] for r in bucket]
                for s in sampled:
                    outf.write(json.dumps(s, ensure_ascii=False, default=str) + "\n")
                # convert min/max from bucket edges
                min_ts = bucket[0][0].isoformat()
                max_ts = bucket[-1][0].isoformat()
            else:
                min_ts = max_ts = None
            sampled_objects.extend(sampled)
            actual_counts_per_bucket.append(len(sampled))
            start = end

    # compute duplicates in sampled objects by review id
    def extract_review_id(obj):
        return obj.get("review_id") or obj.get("id") or obj.get("reviewId") or None

    ids = [extract_review_id(o) for o in sampled_objects]
    id_counts = Counter(i for i in ids if i is not None)
    duplicate_ids = [rid for rid, cnt in id_counts.items() if cnt > 1]

    # min_at and max_at across parsed records (ISO strings)
    overall_min = records[0][0].isoformat() if records else None
    overall_max = records[-1][0].isoformat() if records else None

    total_sampled = len(sampled_objects)

    summary_obj = {
        "run_id": str(run_id),
        "input_file": str(raw_path),
        "output_sample_file": str(sampled_path),
        "total_input_rows": stats.get("total_input_rows", 0),
        "total_sampled_rows": total_sampled,
        "number_of_buckets": k,
        "target_per_bucket": args.sample_per_bucket,
        "actual_counts_per_bucket": actual_counts_per_bucket,
        "duplicate_review_ids": duplicate_ids,
        "null_content_count": stats.get("null_content_count", 0),
        "null_at_count": stats.get("null_at_count", 0),
        "min_at": overall_min,
        "max_at": overall_max,
    }

    summary_path = REPORTS_DIR / f"quantile_sample_summary_{run_id}.json"
    write_json(summary_path, summary_obj)

    # print compact human-friendly header and full JSON summary
    print(f"Within-window quantile time sampling (buckets={k})")
    print("raw_input:", raw_path)
    print("sampled_output:", sampled_path)
    print(json.dumps(summary_obj, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    raise SystemExit(main())