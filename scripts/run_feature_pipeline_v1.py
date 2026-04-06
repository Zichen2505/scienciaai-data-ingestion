from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from sciencia_ingestion.config.settings import load_settings


DEFAULT_LIMIT = 100


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def connect_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def build_prepared_text(content: object) -> str:
    if content is None:
        return ""
    text = str(content).strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)


def count_sentences(prepared_text: str) -> int:
    if not prepared_text:
        return 0
    parts = [part for part in re.split(r"[.!?]+", prepared_text) if part.strip()]
    return len(parts) if parts else 1


def try_compute_sentiment(prepared_text: str) -> tuple[float | None, str | None, str]:
    if not prepared_text:
        return None, None, "none"
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore

        analyzer = SentimentIntensityAnalyzer()
        compound = float(analyzer.polarity_scores(prepared_text)["compound"])
        if compound >= 0.05:
            label = "positive"
        elif compound <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        return compound, label, "vader"
    except Exception:
        return None, None, "none"


def ensure_required_tables(con: sqlite3.Connection) -> None:
    required = {"reviews", "feature_runs", "review_features"}
    rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    existing = {row[0] for row in rows}
    missing = sorted(required - existing)
    if missing:
        raise RuntimeError(f"Missing required tables: {missing}")


def insert_feature_run(
    con: sqlite3.Connection,
    feature_run_id: str,
    upstream_run_id: str | None,
    feature_version: str,
    text_prep_version: str,
    extractor_config_json: str,
) -> None:
    con.execute(
        """
        INSERT INTO feature_runs(
            feature_run_id, created_at, status, upstream_run_id,
            feature_version, text_prep_version, extractor_config_json, notes
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            feature_run_id,
            utc_now_iso(),
            "started",
            upstream_run_id,
            feature_version,
            text_prep_version,
            extractor_config_json,
            None,
        ),
    )


def update_feature_run_status(con: sqlite3.Connection, feature_run_id: str, status: str) -> None:
    con.execute(
        "UPDATE feature_runs SET status=? WHERE feature_run_id=?",
        (status, feature_run_id),
    )


def select_reviews(con: sqlite3.Connection, app_id: str | None, limit: int) -> list[sqlite3.Row]:
    sql = "SELECT review_id, content FROM reviews"
    params: list[object] = []
    if app_id:
        sql += " WHERE app_id=?"
        params.append(app_id)
    sql += " ORDER BY at DESC, review_id LIMIT ?"
    params.append(limit)
    return con.execute(sql, params).fetchall()


def insert_review_feature(
    con: sqlite3.Connection,
    feature_run_id: str,
    review_id: str,
    char_count: int,
    word_count: int,
    sentence_count: int,
    sentiment_compound: float | None,
    sentiment_label: str | None,
    aspect_count: int,
    quality_flag_short_text: int,
    quality_flag_empty_after_prep: int,
) -> None:
    con.execute(
        """
        INSERT INTO review_features(
            feature_run_id, review_id, char_count, word_count, sentence_count,
            sentiment_compound, sentiment_label, keyword_topk_json, aspect_count,
            quality_flag_short_text, quality_flag_empty_after_prep
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            feature_run_id,
            review_id,
            char_count,
            word_count,
            sentence_count,
            sentiment_compound,
            sentiment_label,
            None,
            aspect_count,
            quality_flag_short_text,
            quality_flag_empty_after_prep,
        ),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Run minimal feature pipeline v1 over canonical reviews")
    ap.add_argument("--app-id", help="Optional app_id filter")
    ap.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of reviews to process for this run (default {DEFAULT_LIMIT})",
    )
    ap.add_argument("--upstream-run-id", help="Optional linked ingestion run_id")
    ap.add_argument("--feature-version", default="feature_v1")
    ap.add_argument("--text-prep-version", default="prep_v1")
    ap.add_argument("--short-text-threshold", type=int, default=3)
    args = ap.parse_args()

    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.short_text_threshold < 0:
        raise SystemExit("--short-text-threshold must be >= 0")

    settings = load_settings()
    feature_run_id = uuid.uuid4().hex[:12]
    extractor_config = {
        "short_text_threshold": args.short_text_threshold,
        "sentiment_method": "vader_if_available_else_null",
        "keyword_method": None,
        "aspect_extraction_method": None,
        "selection_limit": args.limit,
        "app_id": args.app_id,
    }

    con = connect_db(settings.db_path)
    ensure_required_tables(con)

    run_inserted = False
    processed_count = 0
    sentiment_method_used = "none"

    try:
        insert_feature_run(
            con,
            feature_run_id,
            args.upstream_run_id,
            args.feature_version,
            args.text_prep_version,
            json.dumps(extractor_config, ensure_ascii=False, sort_keys=True),
        )
        run_inserted = True

        rows = select_reviews(con, args.app_id, args.limit)
        for row in rows:
            prepared_text = build_prepared_text(row["content"])
            char_count = len(prepared_text)
            if prepared_text:
                word_count = len(prepared_text.split())
                sentence_count = count_sentences(prepared_text)
                quality_flag_empty_after_prep = 0
                sentiment_compound, sentiment_label, sentiment_method = try_compute_sentiment(prepared_text)
                sentiment_method_used = sentiment_method if sentiment_method != "none" else sentiment_method_used
            else:
                word_count = 0
                sentence_count = 0
                quality_flag_empty_after_prep = 1
                sentiment_compound = None
                sentiment_label = None

            quality_flag_short_text = 1 if word_count < args.short_text_threshold else 0
            insert_review_feature(
                con,
                feature_run_id,
                row["review_id"],
                char_count,
                word_count,
                sentence_count,
                sentiment_compound,
                sentiment_label,
                0,
                quality_flag_short_text,
                quality_flag_empty_after_prep,
            )
            processed_count += 1

        if sentiment_method_used != extractor_config["sentiment_method"]:
            extractor_config["sentiment_method"] = sentiment_method_used
            con.execute(
                "UPDATE feature_runs SET extractor_config_json=? WHERE feature_run_id=?",
                (json.dumps(extractor_config, ensure_ascii=False, sort_keys=True), feature_run_id),
            )

        update_feature_run_status(con, feature_run_id, "completed")
        con.commit()

        print("Feature pipeline v1 summary")
        print("---------------------------")
        print(json.dumps({
            "feature_run_id": feature_run_id,
            "db_path": str(settings.db_path),
            "app_id": args.app_id,
            "limit": args.limit,
            "processed_reviews": processed_count,
            "sentiment_method": extractor_config["sentiment_method"],
            "status": "completed",
        }, ensure_ascii=False, indent=2))
        return 0

    except Exception:
        if run_inserted:
            try:
                update_feature_run_status(con, feature_run_id, "failed")
                con.commit()
            except Exception:
                pass
        raise
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())