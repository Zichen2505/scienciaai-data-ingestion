from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from sciencia_ingestion.bootstrap_ssl import inject_truststore
from sciencia_ingestion.config.settings import load_settings
from sciencia_ingestion.logging.logger import setup_logger
from sciencia_ingestion.rate_limit.limiter import RateLimiter
from sciencia_ingestion.retry.retry import RetryPolicy, call_with_retries
from sciencia_ingestion.sources.google_play.client import fetch_app, fetch_reviews_page
from sciencia_ingestion.sources.google_play.normalize import normalize_app, normalize_review
from sciencia_ingestion.storage.sqlite_store import (
    app_exists,
    commit,
    connect_sqlite,
    ensure_schema,
    link_app_run,
    link_review_run,
    record_failure,
    record_raw_sample,
    review_exists,
    rollback_run,
    upsert_app,
    upsert_review,
    upsert_run,
)

def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def classify_status(e: Exception) -> int | None:
    # best effort: requests-style exception may carry .response.status_code
    resp = getattr(e, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None)
        if isinstance(code, int):
            return code
    msg = str(e)
    for code in (429, 403, 404, 500, 502, 503):
        if str(code) in msg:
            return code
    return None

def is_retryable(e: Exception) -> bool:
    code = classify_status(e)
    if code in (429, 403, 500, 502, 503):
        return True
    # network-ish errors
    msg = str(e).lower()
    if "timeout" in msg or "temporar" in msg or "connection" in msg:
        return True
    return False

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--country", default="us")
    ap.add_argument("--min-interval", type=float, default=0.6)
    ap.add_argument("--pages-raw-sample", type=int, default=2, help="store only first N pages raw to D: for auditing")
    args = ap.parse_args()

    if args.limit < 1 or args.limit > 200:
        raise SystemExit("For sample stage, --limit must be between 1 and 200.")

    inject_truststore()
    s = load_settings()

    run_id = uuid.uuid4().hex[:12]
    logger = setup_logger(s.logs_dir, run_id)
    logger.info(f"run_id={run_id}")
    logger.info(f"db_path={s.db_path}")

    # checkpoint location (D:)
    ckpt = s.checkpoints_dir / f"{args.app_id}_sample.json"
    ck = {}
    if ckpt.exists():
        ck = json.loads(ckpt.read_text(encoding="utf-8"))

    continuation = ck.get("continuation_token")
    fetched_total = int(ck.get("fetched_total") or 0)
    page = int(ck.get("page") or 0)

    con = connect_sqlite(s.db_path)
    ensure_schema(con)
    upsert_run(con, run_id, "google_play", "running", params_json=json.dumps(vars(args)))

    policy = RetryPolicy(max_attempts=5, base_delay=1.2, max_delay=25.0)

    try:
        # 1) app detail
        app_detail = call_with_retries(lambda: fetch_app(args.app_id, args.lang, args.country), policy, is_retryable)
        is_new_app = 0 if app_exists(con, args.app_id) else 1
        upsert_app(con, normalize_app(args.app_id, app_detail))

        app_sample_path = s.raw_dir / f"app_{args.app_id}_{run_id}.json"
        write_json(app_sample_path, app_detail)
        record_raw_sample(con, f"app:{run_id}", run_id, "google_play", args.app_id, "app_detail", str(app_sample_path))
        link_app_run(con, run_id, args.app_id, is_new_app, str(app_sample_path))

        limiter = RateLimiter(args.min_interval)

        # 2) reviews pages
        while fetched_total < args.limit:
            need = min(100, args.limit - fetched_total)
            limiter.wait()

            items, token = call_with_retries(
                lambda: fetch_reviews_page(args.app_id, args.lang, args.country, need, continuation),
                policy,
                is_retryable,
            )

            page += 1
            logger.info(f"page={page} fetched_page={len(items)} before_total={fetched_total}")

            # raw sample store only first N pages
            if page <= args.pages_raw_sample:
                pth = s.raw_dir / f"reviews_page{page}_{args.app_id}_{run_id}.json"
                write_json(pth, items)
                record_raw_sample(con, f"reviews_page{page}:{run_id}", run_id, "google_play", args.app_id, "reviews_page", str(pth))

            # write reviews (idempotent) + run link for rollback safety
            for it in items:
                nr = normalize_review(args.app_id, args.lang, args.country, it)
                is_new = 0 if review_exists(con, nr["review_id"]) else 1
                upsert_review(con, nr)
                link_review_run(con, run_id, nr["review_id"], is_new)
            commit(con)

            fetched_total += len(items)
            continuation = token

            ckpt.parent.mkdir(parents=True, exist_ok=True)
            ckpt.write_text(json.dumps({
                "app_id": args.app_id,
                "lang": args.lang,
                "country": args.country,
                "target_limit": args.limit,
                "fetched_total": fetched_total,
                "page": page,
                "continuation_token": continuation,
            }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

            logger.info(f"after_total={fetched_total} checkpoint={ckpt}")

            if not items or continuation is None:
                break

        upsert_run(con, run_id, "google_play", "success")
        logger.info(f"done fetched_total={fetched_total}")
        return 0

    except Exception as e:
        code = classify_status(e)
        msg = f"{type(e).__name__}: {e}"
        logger.error(msg)

        record_failure(con, run_id, "google_play", args.app_id, "ingest", code, type(e).__name__, str(e))
        append_jsonl(s.failure_queue, {
            "run_id": run_id,
            "source": "google_play",
            "app_id": args.app_id,
            "stage": "ingest",
            "status_code": code,
            "error_type": type(e).__name__,
            "message": str(e),
        })
        upsert_run(con, run_id, "google_play", "failed", error=msg)

        # Note: we do NOT auto-rollback on failure; rollback is an explicit operator action.
        logger.info("failure recorded. If needed, run scripts/rollback_run.py with this run_id.")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
