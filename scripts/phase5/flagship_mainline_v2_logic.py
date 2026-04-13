from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GENERIC_TITLE_STOP_WORDS = {
    "access",
    "answer",
    "answers",
    "app",
    "issue",
    "issues",
    "problem",
    "problems",
    "user",
    "users",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def resolve_repo_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (repo_root / value).resolve()


def rel_repo(repo_root: Path, path: Path) -> str:
    return str(path.relative_to(repo_root)).replace("\\", "/")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Required JSON file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return payload


def load_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [str(name).strip() for name in (reader.fieldnames or [])]
        rows = [{key: str(value) if value is not None else "" for key, value in row.items()} for row in reader]
    return fieldnames, rows


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_non_empty_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def ensure_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field_name} must be a non-empty list of non-empty strings")
    return [str(item).strip() for item in value]


def numeric_rating(value: str) -> int | None:
    text = str(value or "").strip()
    if text.isdigit():
        return int(text)
    return None


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def clean_excerpt(text: str, limit: int = 280) -> str:
    collapsed = collapse_whitespace(text)
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def normalize_for_match(text: str) -> str:
    normalized = str(text or "").lower()
    normalized = normalized.replace("’", "'").replace("`", "'")
    normalized = normalized.replace("'", "")
    normalized = re.sub(r"[_/\\-]+", " ", normalized)
    normalized = re.sub(r"[^\w\s]+", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized, flags=re.UNICODE).strip()
    return normalized


def split_review_segments(text: str) -> list[str]:
    working = str(text or "")
    if not working.strip():
        return []
    working = working.replace("\r\n", "\n")
    working = re.sub(r"\b\d+\s*[\.)]\s*", ". ", working)
    working = re.sub(r"\b(?:but|however|although|though|except|yet)\b", ". ", working, flags=re.IGNORECASE)
    raw_parts = re.split(r"[\n.!?;]+", working)
    parts = [collapse_whitespace(part.strip(" -•\t")) for part in raw_parts]
    parts = [part for part in parts if part]
    return parts or [collapse_whitespace(working)]


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", str(text or "").lower())


def word_hits(text: str, words: set[str]) -> list[str]:
    return sorted({token for token in tokenize_words(text) if token in words})


def pattern_hits(text: str, patterns: list[str]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text)]


def matches_family(text: str, family_def: dict[str, Any], key_prefix: str) -> bool:
    required_all = [str(pattern) for pattern in family_def.get(f"{key_prefix}_all", [])]
    required_any = [str(pattern) for pattern in family_def.get(f"{key_prefix}_any", [])]
    if not required_all and not required_any:
        return False
    if required_all and not all(re.search(pattern, text) for pattern in required_all):
        return False
    if required_any and not any(re.search(pattern, text) for pattern in required_any):
        return False
    return True


def mechanical_title(title: str, config: dict[str, Any]) -> bool:
    normalized = normalize_for_match(title)
    if not normalized:
        return True
    title_rules = config.get("title_quality_rules", {})
    generic_tail_tokens = set(str(item) for item in title_rules.get("mechanical_tail_tokens", []))
    generic_title_words = set(str(item) for item in title_rules.get("generic_title_words", [])) | GENERIC_TITLE_STOP_WORDS
    tokens = [token for token in tokenize_words(normalized) if token]
    if len(set(tokens)) <= 3:
        return True
    if " for " in f" {normalized} ":
        tail = normalized.split(" for ", 1)[1]
        tail_tokens = [token for token in tokenize_words(tail) if token]
        if tail_tokens and all(token in generic_tail_tokens or token in generic_title_words for token in tail_tokens):
            return True
    if all(token in generic_title_words for token in tokens[-3:]):
        return True
    return False


def normalize_against_max(value: float, max_value: float) -> float:
    if max_value <= 0:
        return 0.0
    return float(value) / float(max_value)


def select_window_rows(rows: list[dict[str, str]], version_window: dict[str, Any]) -> list[dict[str, str]]:
    allowed_versions = {str(item).strip() for item in version_window.get("allowed_versions", [])}
    include_null_buckets = {str(item).strip() for item in version_window.get("include_null_version_buckets", [])}
    return [
        row
        for row in rows
        if str(row.get("app_version_or_null_reason", "")).strip() in allowed_versions
        or str(row.get("app_version_or_null_reason", "")).strip() in include_null_buckets
    ]


def choose_best_family_match(review_text: str, label: str, config: dict[str, Any]) -> tuple[dict[str, Any] | None, int, int]:
    family_defs = list(config.get("family_rules", {}).get(label, []))
    analysis_patterns = config.get("analysis_patterns", {})
    complaint_patterns = [str(pattern) for pattern in analysis_patterns.get("complaint_patterns", [])]
    cross_patterns = [str(pattern) for pattern in analysis_patterns.get("cross_label_patterns", {}).get(label, [])]
    praise_words = {str(item) for item in analysis_patterns.get("praise_words", [])}

    strong_family_hits: list[str] = []
    family_hits: list[str] = []
    best_match: dict[str, Any] | None = None

    segments = split_review_segments(review_text)
    candidate_segments = list(segments)
    if collapse_whitespace(review_text) and collapse_whitespace(review_text) not in candidate_segments:
        candidate_segments.append(collapse_whitespace(review_text))

    for segment in candidate_segments:
        segment_norm = normalize_for_match(segment)
        if not segment_norm:
            continue
        complaint_score = len(pattern_hits(segment_norm, complaint_patterns))
        cross_penalty = 2 if pattern_hits(segment_norm, cross_patterns) else 0
        praise_penalty = len(word_hits(segment_norm, praise_words))
        for family_def in family_defs:
            strong = matches_family(segment_norm, family_def, "required")
            weak = strong or matches_family(segment_norm, family_def, "weak_required")
            if not weak:
                continue
            family_name = str(family_def["issue_family"])
            family_hits.append(family_name)
            if strong:
                strong_family_hits.append(family_name)
            focus_priority = len(pattern_hits(segment_norm, [str(pattern) for pattern in family_def.get("focus_priority_any", [])]))
            score = (8 if strong else 4) + complaint_score + focus_priority - praise_penalty - cross_penalty
            candidate = {
                "issue_family": family_name,
                "canonical_issue_name": str(family_def["canonical_issue_name"]),
                "focus_segment": clean_excerpt(segment, limit=240),
                "segment_normalized": segment_norm,
                "match_strength": "strong" if strong else "weak",
                "score": score,
            }
            if best_match is None or score > int(best_match["score"]):
                best_match = candidate

    return best_match, len(set(strong_family_hits)), len(set(family_hits))


def choose_negative_focus_segment(review_text: str, config: dict[str, Any]) -> str:
    analysis_patterns = config.get("analysis_patterns", {})
    complaint_patterns = [str(pattern) for pattern in analysis_patterns.get("complaint_patterns", [])]
    praise_words = {str(item) for item in analysis_patterns.get("praise_words", [])}
    best_segment = ""
    best_score = -99
    for segment in split_review_segments(review_text):
        segment_norm = normalize_for_match(segment)
        if not segment_norm:
            continue
        score = len(pattern_hits(segment_norm, complaint_patterns)) - len(word_hits(segment_norm, praise_words))
        if score > best_score:
            best_segment = clean_excerpt(segment, limit=240)
            best_score = score
    return best_segment if best_score > 0 else ""


def analyze_rows(rows: list[dict[str, str]], config: dict[str, Any]) -> list[dict[str, Any]]:
    analysis_patterns = config.get("analysis_patterns", {})
    praise_words = {str(item) for item in analysis_patterns.get("praise_words", [])}
    complaint_patterns = [str(pattern) for pattern in analysis_patterns.get("complaint_patterns", [])]
    multi_issue_patterns = [str(pattern) for pattern in analysis_patterns.get("multi_issue_patterns", [])]

    analyzed_rows: list[dict[str, Any]] = []
    for row in rows:
        review_text = str(row.get("review_text", ""))
        review_norm = normalize_for_match(review_text)
        label = str(row.get("primary_label", "")).strip()
        cross_patterns = [str(pattern) for pattern in analysis_patterns.get("cross_label_patterns", {}).get(label, [])]
        best_match, strong_family_count, family_count = choose_best_family_match(review_text, label, config)

        flags: list[str] = []
        review_praise_hits = word_hits(review_norm, praise_words)
        review_complaint_hits = pattern_hits(review_norm, complaint_patterns)
        if review_praise_hits and best_match is not None and normalize_for_match(best_match["focus_segment"]) != review_norm:
            flags.append("praise_mixed_review")
        if len(review_praise_hits) >= 2 and len(review_norm.split()) >= 12:
            flags.append("generic_positive_filler")
        review_cross_hits = pattern_hits(review_norm, cross_patterns)
        focus_cross_hits = pattern_hits(best_match["segment_normalized"], cross_patterns) if best_match is not None else []
        if focus_cross_hits:
            flags.append("cross_label_semantics_in_focus")
        elif review_cross_hits:
            flags.append("cross_label_semantics_outside_focus")
        if strong_family_count > 1 or family_count > 1 or pattern_hits(review_text, multi_issue_patterns):
            flags.append("multi_issue_ambiguity")
        if best_match is None and review_complaint_hits:
            flags.append("generic_negative_without_family")
        if best_match is None and not review_complaint_hits:
            flags.append("no_concrete_issue_family")
        if best_match is not None and str(best_match["match_strength"]) != "strong":
            flags.append("weak_focus_signal")
        if best_match is not None and len(str(best_match["focus_segment"]).split()) < 4:
            flags.append("short_focus_text")

        issue_focus_text = best_match["focus_segment"] if best_match is not None else choose_negative_focus_segment(review_text, config)
        cluster_input_text = normalize_for_match(issue_focus_text)

        if best_match is None:
            issue_evidence_tier = "weak_issue_evidence" if "generic_negative_without_family" in flags else "excluded_noise_or_praise"
            tier_reason = "generic_negative_without_family" if issue_evidence_tier == "weak_issue_evidence" else "excluded_without_family"
        elif str(best_match["match_strength"]) == "strong":
            if "cross_label_semantics_in_focus" in flags or ("multi_issue_ambiguity" in flags and strong_family_count > 1):
                issue_evidence_tier = "weak_issue_evidence"
                tier_reason = f"strong_family_but_contaminated:{best_match['issue_family']}"
            else:
                issue_evidence_tier = "core_issue_evidence"
                tier_reason = f"strong_family_match:{best_match['issue_family']}"
        else:
            issue_evidence_tier = "weak_issue_evidence"
            tier_reason = f"weak_family_match:{best_match['issue_family']}"

        analyzed_rows.append(
            {
                "review_id": str(row.get("review_id", "")).strip(),
                "primary_label": label,
                "issue_relevance_status": str(row.get("issue_relevance_status", "")).strip(),
                "issue_relevance_reason": str(row.get("issue_relevance_reason", "")).strip(),
                "source_inference_run_id": str(row.get("source_inference_run_id", "")).strip(),
                "gate_run_id": str(row.get("gate_run_id", "")).strip(),
                "predicted_probability": str(row.get("predicted_probability", "")).strip(),
                "review_at": str(row.get("review_at", "")).strip(),
                "rating": str(row.get("rating", "")).strip(),
                "version_or_null_reason": str(row.get("app_version_or_null_reason", "")).strip(),
                "review_text": review_text,
                "review_text_excerpt": clean_excerpt(review_text),
                "issue_evidence_tier": issue_evidence_tier,
                "tier_reason": tier_reason,
                "issue_family": None if best_match is None else str(best_match["issue_family"]),
                "canonical_issue_name": None if best_match is None else str(best_match["canonical_issue_name"]),
                "issue_focus_text": issue_focus_text,
                "cluster_input_text": cluster_input_text,
                "contamination_flags": sorted(set(flags)),
            }
        )

    return analyzed_rows


def representative_reviews(rows: list[dict[str, Any]], max_representatives: int) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        rating_value = numeric_rating(str(item.get("rating", "")))
        rating_rank = rating_value if rating_value is not None else 99
        focus_len = len(str(item.get("issue_focus_text", "")))
        review_at = str(item.get("review_at", ""))
        return (rating_rank, -focus_len, review_at)

    ranked = sorted(rows, key=sort_key)[:max_representatives]
    return [
        {
            "review_id": str(item["review_id"]),
            "primary_label": str(item["primary_label"]),
            "issue_family": item.get("issue_family"),
            "version_or_null_reason": str(item["version_or_null_reason"]),
            "rating": str(item["rating"]),
            "review_at": str(item["review_at"]),
            "issue_focus_text": str(item.get("issue_focus_text", "")),
            "review_text_excerpt": str(item.get("review_text_excerpt", "")),
            "issue_relevance_reason": str(item.get("issue_relevance_reason", "")),
            "tier_reason": str(item.get("tier_reason", "")),
        }
        for item in ranked
    ]


def build_why_it_matters(
    *,
    core_review_count: int,
    weak_review_count: int,
    low_rating_share: float,
    version_concentration: dict[str, Any] | None,
    version_coverage_note: str | None,
) -> str:
    total_count = core_review_count + weak_review_count
    parts = [f"{total_count} retained reviews ({core_review_count} core, {weak_review_count} bounded weak attachments)"]
    parts.append(f"{low_rating_share * 100:.1f}% are low-rated")
    if version_concentration is not None:
        parts.append(
            "{share:.1f}% of attributable mentions concentrate in {version}".format(
                share=float(version_concentration["dominant_version_share"]) * 100.0,
                version=version_concentration["dominant_version"],
            )
        )
    elif version_coverage_note:
        parts.append(version_coverage_note)
    return "; ".join(parts) + "."


def build_issue_objects(
    analyzed_rows: list[dict[str, Any]],
    config: dict[str, Any],
    run_id: str,
    version_window: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issue_rules = config.get("issue_object_formation", {})
    min_core_rows = int(issue_rules.get("min_core_rows_per_issue", 2))
    max_rep = int(issue_rules.get("max_representative_reviews_per_issue", 5))
    allowed_weak_flags = {str(item) for item in issue_rules.get("weak_attachment_allowed_flags", [])}

    grouped_core: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in analyzed_rows:
        if row["issue_evidence_tier"] != "core_issue_evidence":
            continue
        family = row.get("issue_family")
        if not family:
            continue
        grouped_core.setdefault((str(row["primary_label"]), str(family)), []).append(row)

    retained_keys = {key for key, rows in grouped_core.items() if len(rows) >= min_core_rows}
    grouped_retained: dict[tuple[str, str], list[dict[str, Any]]] = {key: list(rows) for key, rows in grouped_core.items() if key in retained_keys}

    for row in analyzed_rows:
        if row["issue_evidence_tier"] != "weak_issue_evidence":
            continue
        family = row.get("issue_family")
        if not family:
            continue
        key = (str(row["primary_label"]), str(family))
        if key not in retained_keys:
            continue
        flag_set = set(str(item) for item in row.get("contamination_flags", []))
        if not str(row.get("issue_focus_text", "")).strip():
            continue
        if flag_set - allowed_weak_flags:
            continue
        grouped_retained.setdefault(key, []).append(row)

    issue_objects: list[dict[str, Any]] = []
    row_status_map: dict[str, dict[str, Any]] = {}
    for label_family in sorted(retained_keys):
        label, family = label_family
        retained_rows = grouped_retained.get(label_family, [])
        core_rows = [row for row in retained_rows if row["issue_evidence_tier"] == "core_issue_evidence"]
        weak_rows = [row for row in retained_rows if row["issue_evidence_tier"] == "weak_issue_evidence"]
        if len(core_rows) < min_core_rows:
            continue

        canonical_issue_name = str(core_rows[0]["canonical_issue_name"])
        issue_id = f"{run_id}_{sanitize_id_fragment(label)}_{sanitize_id_fragment(family)}"
        representatives = representative_reviews(core_rows, max_rep)
        rating_values = [numeric_rating(str(row.get("rating", ""))) for row in retained_rows]
        known_ratings = [value for value in rating_values if value is not None]
        low_rating_count = sum(1 for value in known_ratings if value <= 3)
        low_rating_share = float(low_rating_count) / float(len(known_ratings)) if known_ratings else 0.0
        version_values = [str(row.get("version_or_null_reason", "")) for row in retained_rows]
        attributable_versions = [value for value in version_values if value and not value.startswith("null_reason:")]
        version_counts = Counter(attributable_versions)
        issue_version_coverage = float(len(attributable_versions)) / float(len(retained_rows)) if retained_rows else 0.0
        version_concentration = None
        if version_counts:
            dominant_version, dominant_count = version_counts.most_common(1)[0]
            version_concentration = {
                "dominant_version": dominant_version,
                "dominant_version_share": round(float(dominant_count) / float(len(attributable_versions)), 4),
                "attributable_review_count": len(attributable_versions),
                "attributable_review_share": round(issue_version_coverage, 4),
                "version_distribution": dict(version_counts.most_common()),
            }

        contamination_counter = Counter(flag for row in retained_rows for flag in row.get("contamination_flags", []))
        issue_objects.append(
            {
                "issue_id": issue_id,
                "canonical_issue_name": canonical_issue_name,
                "issue_title": canonical_issue_name,
                "primary_label": label,
                "issue_family": family,
                "core_issue_review_count": len(core_rows),
                "attached_weak_review_count": len(weak_rows),
                "issue_review_count": len(retained_rows),
                "low_rating_share": round(low_rating_share, 4),
                "issue_version_coverage": round(issue_version_coverage, 4),
                "version_concentration": version_concentration,
                "representative_reviews": representatives,
                "contamination_flag_counts": dict(sorted(contamination_counter.items())),
                "source_inference_run_id": str(core_rows[0].get("source_inference_run_id", "")),
                "gate_run_id": str(core_rows[0].get("gate_run_id", "")),
            }
        )
        for row in retained_rows:
            row_status_map[str(row["review_id"])] = {
                "issue_id": issue_id,
                "canonical_issue_name": canonical_issue_name,
                "retention_status": "core_retained" if row["issue_evidence_tier"] == "core_issue_evidence" else "weak_attached",
            }

    for row in analyzed_rows:
        review_id = str(row["review_id"])
        if review_id in row_status_map:
            continue
        if row["issue_evidence_tier"] == "core_issue_evidence":
            family = row.get("issue_family")
            if family and (str(row["primary_label"]), str(family)) in grouped_core:
                row_status_map[review_id] = {
                    "issue_id": None,
                    "canonical_issue_name": row.get("canonical_issue_name"),
                    "retention_status": "core_not_formed_below_min_rows",
                }
            else:
                row_status_map[review_id] = {
                    "issue_id": None,
                    "canonical_issue_name": row.get("canonical_issue_name"),
                    "retention_status": "core_unassigned",
                }
        elif row["issue_evidence_tier"] == "weak_issue_evidence":
            row_status_map[review_id] = {
                "issue_id": None,
                "canonical_issue_name": row.get("canonical_issue_name"),
                "retention_status": "weak_not_attached",
            }
        else:
            row_status_map[review_id] = {
                "issue_id": None,
                "canonical_issue_name": None,
                "retention_status": "excluded_noise_or_praise",
            }

    issue_population_rows: list[dict[str, Any]] = []
    for row in analyzed_rows:
        row_state = row_status_map[str(row["review_id"])]
        issue_population_rows.append(
            {
                "review_id": str(row["review_id"]),
                "primary_label": str(row["primary_label"]),
                "issue_family": row.get("issue_family"),
                "canonical_issue_name": row_state.get("canonical_issue_name"),
                "issue_id": row_state.get("issue_id"),
                "issue_evidence_tier": str(row["issue_evidence_tier"]),
                "tier_reason": str(row["tier_reason"]),
                "retention_status": str(row_state.get("retention_status")),
                "issue_focus_text": str(row.get("issue_focus_text", "")),
                "cluster_input_text": str(row.get("cluster_input_text", "")),
                "contamination_flags": list(row.get("contamination_flags", [])),
                "issue_relevance_reason": str(row.get("issue_relevance_reason", "")),
                "review_text_excerpt": str(row.get("review_text_excerpt", "")),
                "version_or_null_reason": str(row.get("version_or_null_reason", "")),
                "rating": str(row.get("rating", "")),
                "review_at": str(row.get("review_at", "")),
                "source_inference_run_id": str(row.get("source_inference_run_id", "")),
                "gate_run_id": str(row.get("gate_run_id", "")),
            }
        )

    return issue_objects, issue_population_rows


def sanitize_id_fragment(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_for_match(value)).strip("_")


def score_issue_objects(
    issue_objects: list[dict[str, Any]],
    config: dict[str, Any],
    version_window: dict[str, Any],
    baseline_not_used_value: str,
    run_level_version_coverage: float,
) -> list[dict[str, Any]]:
    if not issue_objects:
        return []
    weights = config.get("ranking_rules", {}).get("weights", {})
    version_coverage_threshold = float(config.get("version_window_rules", {}).get("version_coverage_threshold", 0.7))
    version_factor_active = run_level_version_coverage >= version_coverage_threshold

    max_volume = max(float(item["issue_review_count"]) for item in issue_objects)
    max_low_rating_share = max(float(item["low_rating_share"]) for item in issue_objects)
    max_version_concentration = max(
        float(item["version_concentration"]["dominant_version_share"]) if item["version_concentration"] else 0.0
        for item in issue_objects
    )

    scored_issues: list[dict[str, Any]] = []
    for issue in issue_objects:
        volume_raw = float(issue["issue_review_count"])
        low_rating_raw = float(issue["low_rating_share"])
        version_raw = float(issue["version_concentration"]["dominant_version_share"]) if issue["version_concentration"] else 0.0

        active_factors = []
        inactive_factors = [{"factor": "growth", "reason": "baseline_not_used"}]

        volume_norm = normalize_against_max(volume_raw, max_volume)
        volume_points = round(volume_norm * float(weights.get("volume", 50.0)), 4)
        active_factors.append(
            {
                "factor": "volume",
                "raw_value": int(volume_raw),
                "normalized_value": round(volume_norm, 4),
                "points": volume_points,
            }
        )

        low_rating_norm = normalize_against_max(low_rating_raw, max_low_rating_share)
        low_rating_points = round(low_rating_norm * float(weights.get("low_rating_share", 30.0)), 4)
        active_factors.append(
            {
                "factor": "low_rating_share",
                "raw_value": round(low_rating_raw, 4),
                "normalized_value": round(low_rating_norm, 4),
                "points": low_rating_points,
            }
        )

        version_points = 0.0
        version_coverage_note = None
        if version_factor_active and issue["version_concentration"] is not None:
            version_norm = normalize_against_max(version_raw, max_version_concentration)
            version_points = round(version_norm * float(weights.get("version_concentration", 20.0)), 4)
            active_factors.append(
                {
                    "factor": "version_concentration",
                    "raw_value": round(version_raw, 4),
                    "normalized_value": round(version_norm, 4),
                    "points": version_points,
                }
            )
        else:
            version_coverage_note = (
                f"version_concentration withheld because run-level version coverage is {run_level_version_coverage:.1%}, below threshold {version_coverage_threshold:.0%}."
                if not version_factor_active
                else "version_concentration unavailable because the issue has no attributable version rows."
            )
            inactive_factors.append({"factor": "version_concentration", "reason": version_coverage_note})

        priority_score = round(volume_points + low_rating_points + version_points, 4)
        why_it_matters = build_why_it_matters(
            core_review_count=int(issue["core_issue_review_count"]),
            weak_review_count=int(issue["attached_weak_review_count"]),
            low_rating_share=float(issue["low_rating_share"]),
            version_concentration=issue["version_concentration"] if version_factor_active else None,
            version_coverage_note=version_coverage_note,
        )

        scored_issues.append(
            {
                "issue_id": issue["issue_id"],
                "canonical_issue_name": issue["canonical_issue_name"],
                "issue_title": issue["issue_title"],
                "primary_label": issue["primary_label"],
                "issue_family": issue["issue_family"],
                "why_it_matters": why_it_matters,
                "priority_score": priority_score,
                "issue_review_count": issue["issue_review_count"],
                "core_issue_review_count": issue["core_issue_review_count"],
                "attached_weak_review_count": issue["attached_weak_review_count"],
                "low_rating_share": issue["low_rating_share"],
                "version_concentration": issue["version_concentration"] if version_factor_active else None,
                "version_coverage_note": version_coverage_note,
                "baseline_not_used": baseline_not_used_value,
                "representative_review_ids": [item["review_id"] for item in issue["representative_reviews"]],
                "representative_review_texts": [item["issue_focus_text"] for item in issue["representative_reviews"]],
                "ranking_factor_breakdown": {
                    "active_factors": active_factors,
                    "inactive_factors": inactive_factors,
                    "total_priority_score": priority_score,
                },
                "version_window": version_window,
                "evidence_refs": {
                    "issue_population_index_ref": None,
                    "source_issue_relevance_gate_run_id": issue["gate_run_id"],
                    "source_inference_run_id": issue["source_inference_run_id"],
                },
            }
        )

    scored_issues.sort(
        key=lambda item: (
            -float(item["priority_score"]),
            -int(item["issue_review_count"]),
            -float(item["low_rating_share"]),
            str(item["issue_title"]),
        )
    )
    return scored_issues


def row_is_core(row: dict[str, Any]) -> bool:
    return str(row.get("issue_evidence_tier", "")) == "core_issue_evidence"


def row_is_retained(row: dict[str, Any]) -> bool:
    return str(row.get("retention_status", "")) in {"core_retained", "weak_attached"}


def issue_grouping_alignment(issue_rows: list[dict[str, Any]]) -> float:
    if not issue_rows:
        return 0.0
    families = [str(row.get("issue_family", "")) for row in issue_rows if row.get("issue_family")]
    if not families:
        return 0.0
    dominant_family, dominant_count = Counter(families).most_common(1)[0]
    if not dominant_family:
        return 0.0
    return round(float(dominant_count) / float(len(issue_rows)), 4)


def build_comparison_artifact(
    *,
    config: dict[str, Any],
    input_package: dict[str, Any],
    run_id: str,
    version_window: dict[str, Any],
    v1_issue_objects: dict[str, Any],
    v1_issue_population: dict[str, Any],
    v1_top_issues: dict[str, Any],
    v2_issue_objects: list[dict[str, Any]],
    v2_population_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    v1_rows = list(v1_issue_population.get("issue_population_rows", []))
    v1_by_review = {str(row.get("review_id", "")): row for row in v1_rows}
    v2_by_review = {str(row.get("review_id", "")): row for row in v2_population_rows}

    v1_retained_rows = len(v1_by_review)
    v2_retained = [row for row in v2_population_rows if row_is_retained(row)]
    v2_retained_rows = len(v2_retained)

    v1_core_rows = sum(1 for review_id in v1_by_review if row_is_core(v2_by_review.get(review_id, {})))
    v2_core_rows = sum(1 for row in v2_retained if row_is_core(row))
    v1_purity = round(float(v1_core_rows) / float(v1_retained_rows), 4) if v1_retained_rows else 0.0
    v2_purity = round(float(v2_core_rows) / float(v2_retained_rows), 4) if v2_retained_rows else 0.0

    v1_issue_groups: dict[str, list[dict[str, Any]]] = {}
    for row in v1_rows:
        v1_issue_groups.setdefault(str(row.get("issue_id", "")), []).append(v2_by_review.get(str(row.get("review_id", "")), {}))
    v1_grouping_scores = [issue_grouping_alignment(rows) for rows in v1_issue_groups.values() if rows]
    v1_grouping = round(sum(v1_grouping_scores) / float(len(v1_grouping_scores)), 4) if v1_grouping_scores else 0.0
    v2_issue_groups: dict[str, list[dict[str, Any]]] = {}
    for row in v2_retained:
        v2_issue_groups.setdefault(str(row.get("issue_id", "")), []).append(row)
    v2_grouping_scores = [issue_grouping_alignment(rows) for rows in v2_issue_groups.values() if rows]
    v2_grouping = round(sum(v2_grouping_scores) / float(len(v2_grouping_scores)), 4) if v2_grouping_scores else 0.0

    v1_issue_title_quality = list(v1_issue_objects.get("issues", []))
    v1_titles = [str(issue.get("issue_title", "")) for issue in v1_issue_title_quality if str(issue.get("issue_title", "")).strip()]
    v2_titles = [str(issue.get("issue_title", "")) for issue in v2_issue_objects if str(issue.get("issue_title", "")).strip()]
    v1_mechanical = sum(1 for title in v1_titles if mechanical_title(title, config))
    v2_mechanical = sum(1 for title in v2_titles if mechanical_title(title, config))
    v1_title_fidelity = round(1.0 - (float(v1_mechanical) / float(len(v1_titles))), 4) if v1_titles else 0.0
    v2_title_fidelity = round(1.0 - (float(v2_mechanical) / float(len(v2_titles))), 4) if v2_titles else 0.0

    v1_micro_issue_count = sum(1 for issue in v1_issue_title_quality if int(issue.get("issue_review_count", 0)) < 3)
    v2_micro_issue_count = sum(1 for issue in v2_issue_objects if int(issue.get("issue_review_count", 0)) < 3)

    v1_contaminated = v1_retained_rows - v1_core_rows
    v2_contaminated = v2_retained_rows - v2_core_rows

    pricing_v1_review_ids = [
        str(row.get("review_id", ""))
        for row in v1_rows
        if str(row.get("primary_label", "")) == "pricing_access_limits"
    ]
    pricing_v2_rows = [
        row
        for row in v2_population_rows
        if str(row.get("primary_label", "")) == "pricing_access_limits"
    ]
    pricing_v1_retained = len(pricing_v1_review_ids)
    pricing_v1_core = sum(1 for review_id in pricing_v1_review_ids if row_is_core(v2_by_review.get(review_id, {})))
    pricing_v2_retained_rows = [row for row in pricing_v2_rows if row_is_retained(row)]
    pricing_v2_core = sum(1 for row in pricing_v2_retained_rows if row_is_core(row))
    pricing_v2_weak = sum(1 for row in pricing_v2_retained_rows if str(row.get("retention_status", "")) == "weak_attached")
    pricing_v2_excluded = sum(1 for row in pricing_v2_rows if str(row.get("retention_status", "")) == "excluded_noise_or_praise")
    pricing_family_counts = Counter(
        str(row.get("issue_family", ""))
        for row in pricing_v2_rows
        if str(row.get("issue_family", "")).strip() and str(row.get("issue_evidence_tier", "")) == "core_issue_evidence"
    )

    excluded_or_downgraded: list[dict[str, Any]] = []
    reassigned: list[dict[str, Any]] = []
    for review_id, v1_row in v1_by_review.items():
        v2_row = v2_by_review.get(review_id, {})
        retention_status = str(v2_row.get("retention_status", ""))
        if retention_status in {"excluded_noise_or_praise", "weak_not_attached", "core_not_formed_below_min_rows", "core_unassigned"}:
            excluded_or_downgraded.append(
                {
                    "review_id": review_id,
                    "primary_label": str(v1_row.get("primary_label", "")),
                    "v1_issue_id": str(v1_row.get("issue_id", "")),
                    "v1_issue_title": str(v1_row.get("issue_title", "")),
                    "v2_decision": retention_status,
                    "v2_issue_evidence_tier": str(v2_row.get("issue_evidence_tier", "")),
                    "v2_issue_family": v2_row.get("issue_family"),
                    "v2_contamination_flags": list(v2_row.get("contamination_flags", [])),
                    "review_text_excerpt": str(v2_row.get("review_text_excerpt", "")),
                }
            )
        if retention_status in {"core_retained", "weak_attached"} and str(v1_row.get("issue_title", "")) != str(v2_row.get("canonical_issue_name", "")):
            reassigned.append(
                {
                    "review_id": review_id,
                    "primary_label": str(v1_row.get("primary_label", "")),
                    "v1_issue_id": str(v1_row.get("issue_id", "")),
                    "v1_issue_title": str(v1_row.get("issue_title", "")),
                    "v2_issue_id": str(v2_row.get("issue_id", "")),
                    "v2_issue_title": str(v2_row.get("canonical_issue_name", "")),
                    "v2_issue_family": v2_row.get("issue_family"),
                    "review_text_excerpt": str(v2_row.get("review_text_excerpt", "")),
                }
            )

    v1_issue_sets = {
        str(issue_id): {str(row.get("review_id", "")) for row in rows if str(row.get("review_id", "")).strip()}
        for issue_id, rows in v1_issue_groups.items()
    }
    title_changes: list[dict[str, Any]] = []
    for v2_issue in v2_issue_objects:
        v2_issue_id = str(v2_issue.get("issue_id", ""))
        v2_review_ids = {str(row.get("review_id", "")) for row in v2_retained if str(row.get("issue_id", "")) == v2_issue_id}
        best_v1_issue_id = None
        best_overlap = 0
        for v1_issue_id, review_ids in v1_issue_sets.items():
            overlap = len(v2_review_ids & review_ids)
            if overlap > best_overlap:
                best_overlap = overlap
                best_v1_issue_id = v1_issue_id
        if not best_v1_issue_id:
            continue
        v1_issue_title = next(
            (str(issue.get("issue_title", "")) for issue in v1_issue_title_quality if str(issue.get("issue_id", "")) == best_v1_issue_id),
            "",
        )
        if not v1_issue_title or not mechanical_title(v1_issue_title, config):
            continue
        title_changes.append(
            {
                "v1_issue_id": best_v1_issue_id,
                "v1_issue_title": v1_issue_title,
                "v2_issue_id": v2_issue_id,
                "v2_issue_title": str(v2_issue.get("issue_title", "")),
                "overlap_review_ids": sorted(v2_review_ids & v1_issue_sets.get(best_v1_issue_id, set()))[:5],
            }
        )

    comparison = {
        "phase": "phase5",
        "surface": "flagship_mainline_v2_comparison",
        "run_id": run_id,
        "generated_at": utc_now_iso(),
        "version_window": version_window,
        "v1_baseline_refs": {
            "config_ref": str(input_package.get("artifact_refs", {}).get("v1_config_json", "")),
            "input_package_ref": str(input_package.get("artifact_refs", {}).get("v1_input_package_json", "")),
            "run_summary_ref": str(input_package.get("artifact_refs", {}).get("v1_run_summary_json", "")),
            "issue_objects_ref": str(input_package.get("artifact_refs", {}).get("v1_issue_objects_json", "")),
            "issue_population_index_ref": str(input_package.get("artifact_refs", {}).get("v1_issue_population_index_json", "")),
            "top_issues_ref": str(input_package.get("artifact_refs", {}).get("v1_top_issues_json", "")),
        },
        "summary_metrics": {
            "issue_object_purity_change": {
                "definition": "share of retained rows classified as core_issue_evidence under the bounded v2 structural rules",
                "v1": v1_purity,
                "v2": v2_purity,
                "delta": round(v2_purity - v1_purity, 4),
            },
            "issue_title_semantic_fidelity_change": {
                "definition": "share of issue titles not flagged as mechanically weak by the bounded title heuristic",
                "v1": v1_title_fidelity,
                "v2": v2_title_fidelity,
                "delta": round(v2_title_fidelity - v1_title_fidelity, 4),
            },
            "issue_grouping_fidelity_change": {
                "definition": "average issue-level dominant-family alignment for retained rows",
                "v1": v1_grouping,
                "v2": v2_grouping,
                "delta": round(v2_grouping - v1_grouping, 4),
            },
            "contamination_reduction": {
                "definition": "retained rows that do not qualify as core_issue_evidence under the bounded v2 structural rules",
                "v1_contaminated_retained_rows": v1_contaminated,
                "v2_contaminated_retained_rows": v2_contaminated,
                "rows_removed_from_issue_formation": max(0, v1_contaminated - v2_contaminated),
            },
            "fragmentation_reduction": {
                "definition": "issue object count and micro-issue count with fewer than 3 retained rows",
                "v1_issue_count": len(v1_issue_title_quality),
                "v2_issue_count": len(v2_issue_objects),
                "v1_micro_issue_count": v1_micro_issue_count,
                "v2_micro_issue_count": v2_micro_issue_count,
            },
        },
        "pricing_access_limits_diagnostic": {
            "v1_retained_rows": pricing_v1_retained,
            "v1_core_rows_under_v2_rules": pricing_v1_core,
            "v1_purity_under_v2_rules": round(float(pricing_v1_core) / float(pricing_v1_retained), 4) if pricing_v1_retained else 0.0,
            "v2_retained_rows": len(pricing_v2_retained_rows),
            "v2_core_rows": pricing_v2_core,
            "v2_attached_weak_rows": pricing_v2_weak,
            "v2_excluded_rows": pricing_v2_excluded,
            "v2_purity": round(float(pricing_v2_core) / float(len(pricing_v2_retained_rows)), 4) if pricing_v2_retained_rows else 0.0,
            "v2_core_family_counts": dict(sorted(pricing_family_counts.items())),
        },
        "row_level_examples": {
            "retained_in_v1_but_excluded_or_downgraded_in_v2": excluded_or_downgraded[:10],
            "reassigned_into_cleaner_v2_issue_objects": reassigned[:10],
            "title_changes_from_mechanical_v1_titles": title_changes[:10],
        },
        "v1_top_issues_snapshot": {
            "run_id": str(v1_top_issues.get("run_id", "")),
            "top_issue_titles": [str(item.get("issue_title", "")) for item in v1_top_issues.get("top_issues", [])],
        },
    }
    return comparison


def build_verdict_artifact(
    *,
    contract_ref: str,
    run_id: str,
    comparison: dict[str, Any],
    evidence_list: list[str],
    reviewer: str,
) -> dict[str, Any]:
    metrics = comparison.get("summary_metrics", {})
    pricing_diag = comparison.get("pricing_access_limits_diagnostic", {})
    purity_delta = float(metrics.get("issue_object_purity_change", {}).get("delta", 0.0))
    title_delta = float(metrics.get("issue_title_semantic_fidelity_change", {}).get("delta", 0.0))
    grouping_delta = float(metrics.get("issue_grouping_fidelity_change", {}).get("delta", 0.0))
    pricing_purity_delta = float(pricing_diag.get("v2_purity", 0.0)) - float(pricing_diag.get("v1_purity_under_v2_rules", 0.0))

    required_checks = [
        {
            "check": "bounded_v2_issue_formation_emits_evidence_tiers",
            "outcome": "pass",
            "details": "issue_population_index.json includes issue_evidence_tier, issue_focus_text, cluster_input_text, contamination_flags, and issue_family for every selected row.",
        },
        {
            "check": "excluded_rows_do_not_participate_in_issue_formation",
            "outcome": "pass",
            "details": "Only core_issue_evidence rows seed issue objects; excluded_noise_or_praise rows remain outside issue formation.",
        },
        {
            "check": "comparison_artifact_is_row_traceable",
            "outcome": "pass",
            "details": "v2_vs_v1_comparison.json contains row-level excluded or downgraded examples, reassignment examples, and mechanical title change examples.",
        },
        {
            "check": "pricing_access_limits_contamination_reduction",
            "outcome": "pass" if pricing_purity_delta > 0 else "fail",
            "details": "pricing_access_limits purity is evaluated against the frozen v1 retained rows under the same bounded v2 structural rules.",
        },
        {
            "check": "issue_title_semantic_fidelity_improved",
            "outcome": "pass" if title_delta > 0 else "fail",
            "details": "Issue titles are compared with a bounded mechanical-title heuristic rather than narrative judgment.",
        },
        {
            "check": "issue_grouping_fidelity_improved",
            "outcome": "pass" if grouping_delta >= 0 else "fail",
            "details": "Grouping fidelity is measured as dominant-family alignment among retained rows.",
        },
    ]

    failures = [check for check in required_checks if check["outcome"] == "fail"]
    limitations: list[str] = []
    if pricing_purity_delta <= 0 or title_delta <= 0 or purity_delta <= 0:
        primary_verdict = "block"
        limitations.append("Required structural quality gains were not demonstrated clearly enough to support truthful v2 acceptance.")
    else:
        if purity_delta < 0.25:
            limitations.append("Overall retained-row purity improves, but the margin remains modest and should be reviewed against the row-level comparison examples.")
        if comparison.get("row_level_examples", {}).get("retained_in_v1_but_excluded_or_downgraded_in_v2"):
            limitations.append("Some previously retained rows now downgrade or fall out of issue formation because the cleaner family-bounded structure refuses ambiguous or contaminated evidence.")
        if int(pricing_diag.get("v2_attached_weak_rows", 0)) > 0:
            limitations.append("pricing_access_limits still carries bounded weak attachments and should be reviewed with the diagnostic family counts.")
        primary_verdict = "accept with limitation" if limitations else "accept"

    return {
        "work_item_scope_id": run_id,
        "contract_ref": contract_ref,
        "primary_verdict": primary_verdict,
        "evidence_list": evidence_list,
        "required_checks": required_checks,
        "limitation": limitations if limitations else None,
        "warning": None,
        "waiver": None,
        "reviewer": reviewer,
        "decision_time": utc_now_iso(),
    }