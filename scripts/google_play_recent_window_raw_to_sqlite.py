from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from sciencia_ingestion.bootstrap_ssl import inject_truststore
from sciencia_ingestion.config.settings import load_settings
from sciencia_ingestion.logging.logger import setup_logger
from sciencia_ingestion.retry.retry import RetryPolicy, call_with_retries
from sciencia_ingestion.sources.google_play.client import fetch_app
from sciencia_ingestion.sources.google_play.normalize import normalize_app
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


def parse_iso_z(s: str | None):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None


def classify_status(e: Exception) -> int | None:
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
    msg = str(e).lower()
    if "timeout" in msg or "temporar" in msg or "connection" in msg:
        return True
    return False


def ensure_app_row(con, args, run_id: str, logger, raw_sample_dir: Path) -> None:
    existing = app_exists(con, args.app_id)

    if args.skip_app_fetch:
        upsert_app(con, {"app_id": args.app_id, "source": "google_play"})
        link_app_run(con, run_id, args.app_id, 0 if existing else 1, None)
        return

    policy = RetryPolicy(max_attempts=5, base_delay=1.2, max_delay=25.0)
    try:
        app_detail = call_with_retries(
            lambda: fetch_app(args.app_id, args.lang, args.country),
            policy,
            is_retryable,
        )
        upsert_app(con, normalize_app(args.app_id, app_detail))
        app_sample_path = raw_sample_dir / f"app_{args.app_id}_{run_id}.json"
        write_json(app_sample_path, app_detail)
        record_raw_sample(
            con,
            f"app:{run_id}",
            run_id,
            "google_play",
            args.app_id,
            "app_detail",
            str(app_sample_path),
        )
        link_app_run(con, run_id, args.app_id, 0 if existing else 1, str(app_sample_path))
    except Exception as e:
        logger.warning(f"app detail fetch failed; continuing with minimal app row: {type(e).__name__}: {e}")
        upsert_app(con, {"app_id": args.app_id, "source": "google_play"})
        link_app_run(con, run_id, args.app_id, 0 if existing else 1, None)


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay a recent-window raw JSONL artifact into SQLite")
    ap.add_argument("--raw-file", type=Path, required=True, help="Path to a normalized recent-window raw JSONL file")
    ap.add_argument("--app-id", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--country", default="us")
    ap.add_argument("--batch-size", type=int, default=500, help="Commit every N successful review rows")
    ap.add_argument("--skip-app-fetch", action="store_true", help="Do not fetch app detail; create/update a minimal app row instead")
    args = ap.parse_args()

    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")
    if not args.raw_file.exists():
        raise SystemExit(f"raw file not found: {args.raw_file}")

    inject_truststore()
    settings = load_settings()

    run_id = uuid.uuid4().hex[:12]
    logger = setup_logger(settings.logs_dir, run_id)
    logger.info(f"run_id={run_id}")
    logger.info(f"db_path={settings.db_path}")
    logger.info(f"raw_file={args.raw_file}")

    con = connect_sqlite(settings.db_path)
    ensure_schema(con)

    params = {
        "raw_file": str(args.raw_file),
        "app_id": args.app_id,
        "lang": args.lang,
        "country": args.country,
        "batch_size": args.batch_size,
        "skip_app_fetch": args.skip_app_fetch,
    }
    upsert_run(con, run_id, "google_play", "running", params_json=json.dumps(params))

    raw_input_sample_id = f"recent_window_raw:{run_id}"
    record_raw_sample(
        con,
        raw_input_sample_id,
        run_id,
        "google_play",
        args.app_id,
        "recent_window_raw",
        str(args.raw_file.resolve()),
    )

    try:
        ensure_app_row(con, args, run_id, logger, settings.raw_dir)

        total_input_rows = 0
        successful_rows = 0
        new_review_rows = 0
        existing_review_rows = 0
        failed_rows = 0
        null_content_count = 0
        null_at_count = 0
        min_at = None
        max_at = None
        pending_commit = 0

        with args.raw_file.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                total_input_rows += 1

                try:
                    row = json.loads(line)
                except Exception as e:
                    failed_rows += 1
                    message = f"line={line_number} parse error: {type(e).__name__}: {e}"
                    record_failure(con, run_id, "google_play", args.app_id, "raw_parse", None, type(e).__name__, message)
                    append_jsonl(settings.failure_queue, {
                        "run_id": run_id,
                        "source": "google_play",
                        "app_id": args.app_id,
                        "stage": "raw_parse",
                        "status_code": None,
                        "error_type": type(e).__name__,
                        "message": message,
                    })
                    continue

                try:
                    review_app_id = row.get("app_id")
                    review_id_value = row.get("review_id")
                    if not review_id_value:
                        raise ValueError("missing review_id")
                    if review_app_id and review_app_id != args.app_id:
                        raise ValueError(f"app_id mismatch: expected {args.app_id}, got {review_app_id}")

                    row["app_id"] = args.app_id
                    row.setdefault("source", "google_play")
                    row.setdefault("lang", args.lang)
                    row.setdefault("country", args.country)

                    content = row.get("content")
                    if content is None or (isinstance(content, str) and content.strip() == ""):
                        null_content_count += 1

                    at_value = row.get("at")
                    at_dt = parse_iso_z(at_value)
                    if at_dt is None:
                        null_at_count += 1
                    else:
                        min_at = at_dt if min_at is None or at_dt < min_at else min_at
                        max_at = at_dt if max_at is None or at_dt > max_at else max_at

                    is_new = 0 if review_exists(con, review_id_value) else 1
                    upsert_review(con, row)
                    link_review_run(con, run_id, review_id_value, is_new)

                    successful_rows += 1
                    if is_new:
                        new_review_rows += 1
                    else:
                        existing_review_rows += 1

                    pending_commit += 1
                    if pending_commit >= args.batch_size:
                        commit(con)
                        logger.info(
                            f"progress total_input_rows={total_input_rows} successful_rows={successful_rows} failed_rows={failed_rows}"
                        )
                        pending_commit = 0

                except Exception as e:
                    failed_rows += 1
                    code = classify_status(e)
                    message = f"line={line_number} validation/insert error: {type(e).__name__}: {e}"
                    record_failure(con, run_id, "google_play", args.app_id, "raw_replay", code, type(e).__name__, message)
                    append_jsonl(settings.failure_queue, {
                        "run_id": run_id,
                        "source": "google_play",
                        "app_id": args.app_id,
                        "stage": "raw_replay",
                        "status_code": code,
                        "error_type": type(e).__name__,
                        "message": message,
                    })

        if pending_commit:
            commit(con)

        summary = {
            "run_id": run_id,
            "app_id": args.app_id,
            "input_file": str(args.raw_file.resolve()),
            "db_path": str(settings.db_path),
            "total_input_rows": total_input_rows,
            "successful_rows": successful_rows,
            "new_review_rows": new_review_rows,
            "existing_review_rows": existing_review_rows,
            "failed_rows": failed_rows,
            "null_content_count": null_content_count,
            "null_at_count": null_at_count,
            "min_at": min_at.isoformat() if min_at else None,
            "max_at": max_at.isoformat() if max_at else None,
        }

        summary_path = REPO / "reports" / f"raw_to_sqlite_run_summary_{run_id}.json"
        write_json(summary_path, summary)
        summary["summary_file"] = str(summary_path)
        write_json(summary_path, summary)

        upsert_run(con, run_id, "google_play", "success")

        print("Recent-window raw to SQLite replay summary")
        print("-----------------------------------------")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        logger.info(f"summary_file={summary_path}")
        return 0

    except Exception as e:
        code = classify_status(e)
        message = f"{type(e).__name__}: {e}"
        logger.error(message)
        record_failure(con, run_id, "google_play", args.app_id, "run", code, type(e).__name__, str(e))
        append_jsonl(settings.failure_queue, {
            "run_id": run_id,
            "source": "google_play",
            "app_id": args.app_id,
            "stage": "run",
            "status_code": code,
            "error_type": type(e).__name__,
            "message": str(e),
        })
        upsert_run(con, run_id, "google_play", "failed", error=message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())