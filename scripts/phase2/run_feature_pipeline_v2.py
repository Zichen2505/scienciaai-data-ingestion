from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from sciencia_ingestion.config.settings import load_settings


DEFAULT_LIMIT = 200
DEFAULT_SHORT_TEXT_THRESHOLD = 3
DEFAULT_OUTPUT_DIR = REPO / "reports" / "phase_ii_slice3"


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
            "slice3_hardened_modeling_input_export",
        ),
    )


def update_feature_run_status(con: sqlite3.Connection, feature_run_id: str, status: str) -> None:
    con.execute("UPDATE feature_runs SET status=? WHERE feature_run_id=?", (status, feature_run_id))


def select_reviews(con: sqlite3.Connection, app_id: str | None, limit: int) -> list[sqlite3.Row]:
    sql = """
    SELECT review_id, app_id, at, lang, country, rating, content
    FROM reviews
    """
    params: list[object] = []
    if app_id:
        sql += " WHERE app_id=?"
        params.append(app_id)
    sql += " ORDER BY COALESCE(at, '') DESC, review_id ASC LIMIT ?"
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
            0,
            quality_flag_short_text,
            quality_flag_empty_after_prep,
        ),
    )


def sha256_for_rows(rows: list[dict[str, object]]) -> str:
    hasher = hashlib.sha256()
    for row in rows:
        hasher.update(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def write_modeling_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "feature_run_id",
        "review_id",
        "app_id",
        "review_at",
        "lang",
        "country",
        "rating",
        "prepared_text",
        "char_count",
        "word_count",
        "sentence_count",
        "quality_flag_short_text",
        "quality_flag_empty_after_prep",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_reviews_snapshot(con: sqlite3.Connection) -> dict[str, object]:
    row = con.execute(
        """
        SELECT
            COUNT(*) AS review_count,
            SUM(CASE WHEN content IS NULL THEN 1 ELSE 0 END) AS null_content_count,
            MAX(COALESCE(last_seen_at, '')) AS max_last_seen_at,
            MIN(COALESCE(first_seen_at, '')) AS min_first_seen_at
        FROM reviews
        """
    ).fetchone()
    return {
        "review_count": int(row["review_count"] or 0),
        "null_content_count": int(row["null_content_count"] or 0),
        "max_last_seen_at": row["max_last_seen_at"],
        "min_first_seen_at": row["min_first_seen_at"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Run hardened feature pipeline v2 and export deterministic modeling input artifacts"
    )
    ap.add_argument("--app-id", help="Optional app_id filter")
    ap.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of reviews to process for this run (default {DEFAULT_LIMIT})",
    )
    ap.add_argument("--upstream-run-id", help="Optional linked ingestion run_id")
    ap.add_argument("--feature-version", default="feature_v2")
    ap.add_argument("--text-prep-version", default="prep_v2")
    ap.add_argument("--short-text-threshold", type=int, default=DEFAULT_SHORT_TEXT_THRESHOLD)
    ap.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for exported artifacts (default {DEFAULT_OUTPUT_DIR})",
    )
    args = ap.parse_args()

    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.short_text_threshold < 0:
        raise SystemExit("--short-text-threshold must be >= 0")

    settings = load_settings()
    feature_run_id = uuid.uuid4().hex[:12]
    output_dir = Path(args.output_dir)

    extractor_config = {
        "short_text_threshold": args.short_text_threshold,
        "sentiment_method": "vader_if_available_else_null",
        "keyword_method": None,
        "aspect_extraction_method": None,
        "selection_order": "coalesce(at, '') desc, review_id asc",
        "selection_limit": args.limit,
        "app_id": args.app_id,
        "modeling_export_format": "csv_utf8",
        "modeling_export_schema": "phase_ii_tfidf_input_v1",
    }

    con = connect_db(settings.db_path)
    ensure_required_tables(con)

    reviews_before = build_reviews_snapshot(con)
    inserted_count = 0
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
        con.commit()

        selected = select_reviews(con, args.app_id, args.limit)
        modeling_rows: list[dict[str, object]] = []
        modeling_rows_for_hash: list[dict[str, object]] = []

        edge_cases = {
            "null_text": 0,
            "empty_after_prep": 0,
            "short_text": 0,
            "very_long_text": 0,
        }

        for row in selected:
            is_null_text = row["content"] is None
            prepared_text = build_prepared_text(row["content"])
            char_count = len(prepared_text)
            if prepared_text:
                word_count = len(prepared_text.split())
                sentence_count = count_sentences(prepared_text)
                quality_flag_empty_after_prep = 0
                sentiment_compound, sentiment_label, sentiment_method = try_compute_sentiment(prepared_text)
                if sentiment_method != "none":
                    sentiment_method_used = sentiment_method
            else:
                word_count = 0
                sentence_count = 0
                quality_flag_empty_after_prep = 1
                sentiment_compound = None
                sentiment_label = None

            quality_flag_short_text = 1 if word_count < args.short_text_threshold else 0
            if is_null_text:
                edge_cases["null_text"] += 1
            if quality_flag_empty_after_prep == 1:
                edge_cases["empty_after_prep"] += 1
            if quality_flag_short_text == 1:
                edge_cases["short_text"] += 1
            if char_count >= 2000:
                edge_cases["very_long_text"] += 1

            insert_review_feature(
                con,
                feature_run_id,
                row["review_id"],
                char_count,
                word_count,
                sentence_count,
                sentiment_compound,
                sentiment_label,
                quality_flag_short_text,
                quality_flag_empty_after_prep,
            )

            exported_row = {
                "feature_run_id": feature_run_id,
                "review_id": row["review_id"],
                "app_id": row["app_id"],
                "review_at": row["at"],
                "lang": row["lang"],
                "country": row["country"],
                "rating": row["rating"],
                "prepared_text": prepared_text,
                "char_count": char_count,
                "word_count": word_count,
                "sentence_count": sentence_count,
                "quality_flag_short_text": quality_flag_short_text,
                "quality_flag_empty_after_prep": quality_flag_empty_after_prep,
            }
            modeling_rows.append(exported_row)
            modeling_rows_for_hash.append(
                {
                    "review_id": row["review_id"],
                    "prepared_text": prepared_text,
                    "char_count": char_count,
                    "word_count": word_count,
                    "sentence_count": sentence_count,
                    "quality_flag_short_text": quality_flag_short_text,
                    "quality_flag_empty_after_prep": quality_flag_empty_after_prep,
                }
            )
            inserted_count += 1

        if sentiment_method_used != extractor_config["sentiment_method"]:
            extractor_config["sentiment_method"] = sentiment_method_used
            con.execute(
                "UPDATE feature_runs SET extractor_config_json=? WHERE feature_run_id=?",
                (json.dumps(extractor_config, ensure_ascii=False, sort_keys=True), feature_run_id),
            )

        timestamp_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        artifact_base = f"feature_pipeline_v2_{feature_run_id}_{timestamp_tag}"
        modeling_csv_path = output_dir / f"{artifact_base}_modeling_input.csv"
        summary_path = output_dir / f"{artifact_base}_run_summary.json"

        write_modeling_csv(modeling_csv_path, modeling_rows)

        reviews_after = build_reviews_snapshot(con)
        review_features_count = con.execute(
            "SELECT COUNT(*) FROM review_features WHERE feature_run_id=?", (feature_run_id,)
        ).fetchone()[0]

        run_summary = {
            "created_at": utc_now_iso(),
            "feature_run_id": feature_run_id,
            "db_path": str(settings.db_path),
            "input_scope": {
                "app_id": args.app_id,
                "limit": args.limit,
                "selection_order": extractor_config["selection_order"],
            },
            "output_artifacts": {
                "modeling_input_csv": str(modeling_csv_path),
                "run_summary_json": str(summary_path),
            },
            "row_counts": {
                "selected_reviews": len(selected),
                "inserted_review_features": inserted_count,
                "review_features_rows_for_run": int(review_features_count),
            },
            "exclusions_or_skips": {
                "skipped_rows": 0,
                "notes": "No row-level skips; empty/short text represented through quality flags.",
            },
            "edge_case_counts": edge_cases,
            "hashes": {
                "modeling_input_stable_sha256": sha256_for_rows(modeling_rows_for_hash),
                "export_row_payload_sha256": sha256_for_rows(modeling_rows),
            },
            "reviews_read_only_snapshot": {
                "before": reviews_before,
                "after": reviews_after,
                "unchanged": reviews_before == reviews_after,
            },
            "status": "completed",
        }

        summary_path.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")

        update_feature_run_status(con, feature_run_id, "completed")
        con.commit()

        print("Feature pipeline v2 summary")
        print("---------------------------")
        print(json.dumps(run_summary, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        con.rollback()
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
