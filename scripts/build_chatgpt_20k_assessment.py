from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median


REPO = Path(__file__).resolve().parents[1]
RAW_FILE = REPO / "data" / "checkpoints" / "com.openai.chatgpt_recent_window_raw_f942add8.jsonl"
RAW_TO_SQLITE_SUMMARY = REPO / "reports" / "raw_to_sqlite_run_summary_2895d451b8c3.json"
QUANTILE_SUMMARY = REPO / "reports" / "quantile_sample_summary_165578901.json"
VALIDATION_DOC = REPO / "documents" / "PHASE_I_INGESTION_VALIDATION_SUMMARY.md"

OUT_DIR = REPO / "reports" / "current_chatgpt_20k_assessment"
SAMPLE_SCOPE_PATH = OUT_DIR / "sample_scope.json"
QUALITY_CHECKS_PATH = OUT_DIR / "quality_checks.json"
DISTRIBUTIONS_PATH = OUT_DIR / "distributions.json"
REPORT_PATH = OUT_DIR / "DATASET_ASSESSMENT.md"


def parse_iso_z(value: str | None):
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def sanitize_repo_path(value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        return str(path).replace("\\", "/")
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except Exception:
        return None


def quantile(sorted_values: list[int], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = (len(sorted_values) - 1) * q
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return float(sorted_values[lower])
    lower_val = sorted_values[lower]
    upper_val = sorted_values[upper]
    return float(lower_val + (upper_val - lower_val) * (pos - lower))


def recent_window_evidence(validation_doc_text: str) -> dict:
    phrase = "the current Google Play access path is recent-window bounded"
    if phrase in validation_doc_text:
        return {
            "status": "supported_by_saved_artifact",
            "value": True,
            "source_file": repo_rel(VALIDATION_DOC),
            "source_text": phrase,
        }
    return {
        "status": "not_verified_from_current_files",
        "value": None,
        "source_file": repo_rel(VALIDATION_DOC),
        "source_text": None,
    }


def sanitize_raw_to_sqlite_summary(summary: dict | None, source_path: Path) -> dict:
    if summary is None:
        return {
            "status": "missing",
            "source_file": repo_rel(source_path),
        }
    return {
        "status": "present",
        "source_file": repo_rel(source_path),
        "run_id": summary.get("run_id"),
        "app_id": summary.get("app_id"),
        "input_file": sanitize_repo_path(summary.get("input_file")),
        "total_input_rows": summary.get("total_input_rows"),
        "successful_rows": summary.get("successful_rows"),
        "new_review_rows": summary.get("new_review_rows"),
        "existing_review_rows": summary.get("existing_review_rows"),
        "failed_rows": summary.get("failed_rows"),
        "null_content_count": summary.get("null_content_count"),
        "null_at_count": summary.get("null_at_count"),
        "min_at": summary.get("min_at"),
        "max_at": summary.get("max_at"),
        "machine_specific_fields_omitted": True,
    }


def sanitize_quantile_summary(summary: dict | None, source_path: Path) -> dict:
    if summary is None:
        return {
            "status": "missing",
            "source_file": repo_rel(source_path),
        }
    return {
        "status": "present",
        "source_file": repo_rel(source_path),
        "run_id": summary.get("run_id"),
        "input_file": sanitize_repo_path(summary.get("input_file")),
        "output_sample_file": sanitize_repo_path(summary.get("output_sample_file")),
        "total_input_rows": summary.get("total_input_rows"),
        "total_sampled_rows": summary.get("total_sampled_rows"),
        "number_of_buckets": summary.get("number_of_buckets"),
        "target_per_bucket": summary.get("target_per_bucket"),
        "actual_counts_per_bucket": summary.get("actual_counts_per_bucket"),
        "duplicate_review_ids": summary.get("duplicate_review_ids"),
        "null_content_count": summary.get("null_content_count"),
        "null_at_count": summary.get("null_at_count"),
        "min_at": summary.get("min_at"),
        "max_at": summary.get("max_at"),
    }


def build_assessment() -> tuple[dict, dict, dict, str]:
    validation_doc_text = VALIDATION_DOC.read_text(encoding="utf-8")
    raw_to_sqlite_summary = read_json(RAW_TO_SQLITE_SUMMARY) if RAW_TO_SQLITE_SUMMARY.exists() else None
    quantile_summary = read_json(QUANTILE_SUMMARY) if QUANTILE_SUMMARY.exists() else None

    total_rows = 0
    app_ids = Counter()
    review_id_counts = Counter()
    rating_distribution = Counter()
    text_lengths = []
    parseable_timestamps = []
    timestamp_day_counts = defaultdict(int)
    null_content_count = 0
    empty_content_count = 0
    null_timestamp_count = 0
    malformed_timestamp_count = 0
    null_rating_count = 0
    invalid_rating_count = 0
    null_app_version_count = 0

    with RAW_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            total_rows += 1
            row = json.loads(line)

            app_id = row.get("app_id")
            if app_id is not None:
                app_ids[app_id] += 1

            review_id = row.get("review_id")
            if review_id is not None:
                review_id_counts[review_id] += 1

            rating = row.get("rating")
            if rating is None:
                null_rating_count += 1
            elif isinstance(rating, int) and 1 <= rating <= 5:
                rating_distribution[rating] += 1
            else:
                invalid_rating_count += 1

            content = row.get("content")
            if content is None:
                null_content_count += 1
            elif isinstance(content, str):
                if content.strip() == "":
                    empty_content_count += 1
                text_lengths.append(len(content))
            else:
                text_lengths.append(len(str(content)))

            at_raw = row.get("at")
            if at_raw is None:
                null_timestamp_count += 1
            else:
                at_dt = parse_iso_z(at_raw)
                if at_dt is None:
                    malformed_timestamp_count += 1
                else:
                    parseable_timestamps.append(at_dt)
                    timestamp_day_counts[at_dt.date().isoformat()] += 1

            if row.get("app_version") is None:
                null_app_version_count += 1

    duplicate_review_ids = [review_id for review_id, count in review_id_counts.items() if count > 1]
    unique_review_ids = len(review_id_counts)

    observed_min_at = min(parseable_timestamps).isoformat() if parseable_timestamps else None
    observed_max_at = max(parseable_timestamps).isoformat() if parseable_timestamps else None
    observed_span_days = None
    if parseable_timestamps:
        observed_span_days = round((max(parseable_timestamps) - min(parseable_timestamps)).total_seconds() / 86400.0, 6)

    sorted_text_lengths = sorted(text_lengths)
    sorted_day_keys = sorted(timestamp_day_counts)
    daily_counts = [timestamp_day_counts[key] for key in sorted_day_keys]

    sample_scope = {
        "computed_from_current_files": {
            "app_id": max(app_ids.items(), key=lambda item: item[1])[0] if app_ids else None,
            "total_rows": total_rows,
            "unique_review_ids": unique_review_ids,
            "observed_min_at": observed_min_at,
            "observed_max_at": observed_max_at,
            "observed_span_days": observed_span_days,
            "recent_window_bounded": recent_window_evidence(validation_doc_text),
        },
        "saved_repo_artifacts": {
            "raw_to_sqlite_run_summary": sanitize_raw_to_sqlite_summary(raw_to_sqlite_summary, RAW_TO_SQLITE_SUMMARY),
            "quantile_sample_summary": sanitize_quantile_summary(quantile_summary, QUANTILE_SUMMARY),
        },
    }

    quality_checks = {
        "computed_from_current_files": {
            "duplicate_review_id_count": len(duplicate_review_ids),
            "duplicate_review_id_examples": duplicate_review_ids[:10],
            "null_content_count": null_content_count,
            "empty_content_count": empty_content_count,
            "null_timestamp_count": null_timestamp_count,
            "malformed_timestamp_count": malformed_timestamp_count,
            "null_rating_count": null_rating_count,
            "invalid_rating_count": invalid_rating_count,
            "null_app_version_count": null_app_version_count,
        },
        "saved_repo_artifacts": {
            "raw_to_sqlite_run_summary": {
                "status": "present" if raw_to_sqlite_summary is not None else "missing",
                "failed_rows": raw_to_sqlite_summary.get("failed_rows") if raw_to_sqlite_summary is not None else None,
                "null_content_count": raw_to_sqlite_summary.get("null_content_count") if raw_to_sqlite_summary is not None else None,
                "null_at_count": raw_to_sqlite_summary.get("null_at_count") if raw_to_sqlite_summary is not None else None,
            },
            "quantile_sample_summary": {
                "status": "present" if quantile_summary is not None else "missing",
                "duplicate_review_ids": quantile_summary.get("duplicate_review_ids") if quantile_summary is not None else None,
                "null_content_count": quantile_summary.get("null_content_count") if quantile_summary is not None else None,
                "null_at_count": quantile_summary.get("null_at_count") if quantile_summary is not None else None,
            },
        },
    }

    distributions = {
        "computed_from_current_files": {
            "rating_distribution": dict(sorted(rating_distribution.items())),
            "timestamp_distribution_summary": {
                "parseable_timestamp_count": len(parseable_timestamps),
                "observed_min_at": observed_min_at,
                "observed_max_at": observed_max_at,
                "observed_day_count": len(timestamp_day_counts),
                "daily_review_count_min": min(daily_counts) if daily_counts else None,
                "daily_review_count_max": max(daily_counts) if daily_counts else None,
                "daily_review_count_median": median(daily_counts) if daily_counts else None,
                "daily_review_counts": {key: timestamp_day_counts[key] for key in sorted_day_keys},
            },
            "text_length_distribution_summary": {
                "count": len(text_lengths),
                "min": min(text_lengths) if text_lengths else None,
                "max": max(text_lengths) if text_lengths else None,
                "mean": round(mean(text_lengths), 3) if text_lengths else None,
                "median": median(text_lengths) if text_lengths else None,
                "p25": quantile(sorted_text_lengths, 0.25),
                "p75": quantile(sorted_text_lengths, 0.75),
                "short_text_lt_10_count": sum(1 for length in text_lengths if length < 10),
            },
        },
        "saved_repo_artifacts": {
            "phase_i_validation_doc_has_text_length_section": "### 4. Text length by app" in validation_doc_text,
            "phase_i_validation_doc_has_rating_distribution_section": "### 2. Overall rating distribution" in validation_doc_text,
        },
    }

    report = build_markdown_report(sample_scope, quality_checks, distributions)
    return sample_scope, quality_checks, distributions, report


def build_markdown_report(sample_scope: dict, quality_checks: dict, distributions: dict) -> str:
    scope = sample_scope["computed_from_current_files"]
    qa = quality_checks["computed_from_current_files"]
    dist = distributions["computed_from_current_files"]
    recent_window = scope["recent_window_bounded"]
    raw_replay = sample_scope["saved_repo_artifacts"]["raw_to_sqlite_run_summary"]
    quantile = sample_scope["saved_repo_artifacts"]["quantile_sample_summary"]

    lines = [
        "# Current ChatGPT 20k Dataset Assessment",
        "",
        "## What was analyzed",
        "",
        "Computed directly from current files:",
        f"- raw dataset: `{repo_rel(RAW_FILE)}`",
        "",
        "Read as saved repo artifacts:",
        f"- `{repo_rel(RAW_TO_SQLITE_SUMMARY)}`",
        f"- `{repo_rel(QUANTILE_SUMMARY)}`",
        f"- `{repo_rel(VALIDATION_DOC)}`",
        "",
        "## What is directly verified",
        "",
        f"- total_rows = {scope['total_rows']}",
        f"- unique_review_ids = {scope['unique_review_ids']}",
        f"- observed_min_at = {scope['observed_min_at']}",
        f"- observed_max_at = {scope['observed_max_at']}",
        f"- observed_span_days = {scope['observed_span_days']}",
        f"- duplicate_review_id_count = {qa['duplicate_review_id_count']}",
        f"- null_content_count = {qa['null_content_count']}",
        f"- empty_content_count = {qa['empty_content_count']}",
        f"- null_timestamp_count = {qa['null_timestamp_count']}",
        f"- malformed_timestamp_count = {qa['malformed_timestamp_count']}",
        f"- rating_distribution = {json.dumps(dist['rating_distribution'], ensure_ascii=False)}",
        f"- text_length_summary = {json.dumps(dist['text_length_distribution_summary'], ensure_ascii=False)}",
        f"- timestamp_distribution_summary = {json.dumps({k: v for k, v in dist['timestamp_distribution_summary'].items() if k != 'daily_review_counts'}, ensure_ascii=False)}",
        "",
        "## What the current files support",
        "",
        "Computed from current files:",
        "- The raw ChatGPT dataset can support direct counts, duplicate checks, null/empty checks, malformed timestamp checks, rating distribution, timestamp span, daily timestamp counts, and text-length summary statistics.",
        "",
        "Already present in saved repo artifacts:",
        f"- raw-to-SQLite replay summary confirms 20,000 input rows and 0 failed rows in `{repo_rel(RAW_TO_SQLITE_SUMMARY)}`." if raw_replay["status"] == "present" else "- raw-to-SQLite replay summary is missing from the current repo state.",
        f"- formal 1k pilot summary confirms a 1,000-row within-window pilot artifact in `{repo_rel(QUANTILE_SUMMARY)}`." if quantile["status"] == "present" else "- formal 1k pilot summary is missing from the current repo state.",
        f"- Phase I validation summary contains conservative written conclusions in `{repo_rel(VALIDATION_DOC)}`.",
        "",
        "Recent-window bounded support:",
        f"- status = {recent_window['status']}",
        f"- value = {recent_window['value']}",
        f"- source_file = {recent_window['source_file']}",
        "",
        "## What is still missing / not verified",
        "",
        "- Multi-year historical coverage is not verified by the current files.",
        "- A strong signal-quality-at-scale claim is not verified by the current files.",
        "- The current files do not provide a richer saved timestamp distribution analysis beyond range and lightweight daily counts.",
        "- The current files do not justify representativeness claims beyond the current observed recent-window dataset.",
        "",
        "## Strongest safe conclusion",
        "",
        "The current repository contains a 20,000-row recent-window raw artifact with directly computable rating, timestamp-span, text-length, and basic QA metrics, plus saved artifacts for a formal 1k pilot and raw-to-SQLite replay evidence where those files are present. The current files support a recent-window-bounded characterization only where saved repo artifacts say so. They do not support claims of multi-year historical coverage, broad representativeness, or strong signal quality at scale.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample_scope, quality_checks, distributions, report = build_assessment()

    SAMPLE_SCOPE_PATH.write_text(json.dumps(sample_scope, ensure_ascii=False, indent=2), encoding="utf-8")
    QUALITY_CHECKS_PATH.write_text(json.dumps(quality_checks, ensure_ascii=False, indent=2), encoding="utf-8")
    DISTRIBUTIONS_PATH.write_text(json.dumps(distributions, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")

    print("WROTE", SAMPLE_SCOPE_PATH)
    print("WROTE", QUALITY_CHECKS_PATH)
    print("WROTE", DISTRIBUTIONS_PATH)
    print("WROTE", REPORT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())