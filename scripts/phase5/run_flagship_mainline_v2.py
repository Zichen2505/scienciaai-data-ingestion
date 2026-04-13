from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
DEFAULT_INTERPRETER = (REPO / ".venv" / "Scripts" / "python.exe").resolve()
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.phase5.flagship_mainline_v2_logic import (  # noqa: E402
    analyze_rows,
    build_comparison_artifact,
    build_issue_objects,
    build_verdict_artifact,
    ensure_non_empty_string,
    load_csv_rows,
    load_json,
    rel_repo,
    resolve_repo_path,
    save_json,
    save_text,
    score_issue_objects,
    select_window_rows,
    utc_now_iso,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute the separately versioned purity-first Phase V flagship mainline v2."
    )
    parser.add_argument(
        "--input-package",
        default="configs/phase5/flagship_mainline_input_package_v2.json",
        help="Path to the flagship mainline v2 input package JSON.",
    )
    parser.add_argument(
        "--preflight-result",
        help="Optional path to the passed preflight result JSON. Defaults to output_root/preflight_result.json.",
    )
    return parser.parse_args()


def ensure_default_python() -> None:
    current = Path(sys.executable).resolve()
    if current.as_posix().lower() != DEFAULT_INTERPRETER.as_posix().lower():
        raise SystemExit(
            "Governed flagship mainline v2 execution must use .\\.venv\\Scripts\\python.exe; "
            f"observed sys.executable={current}"
        )


def markdown_issue(issue: dict[str, object]) -> str:
    lines = [
        f"## #{issue['issue_rank']} {issue['issue_title']}",
        "",
        f"- issue_id: `{issue['issue_id']}`",
        f"- primary_label: `{issue['primary_label']}`",
        f"- issue_family: `{issue['issue_family']}`",
        f"- priority_score: `{issue['priority_score']}`",
        f"- issue_review_count: `{issue['issue_review_count']}`",
        f"- core_issue_review_count: `{issue['core_issue_review_count']}`",
        f"- attached_weak_review_count: `{issue['attached_weak_review_count']}`",
        f"- low_rating_share: `{issue['low_rating_share']}`",
        f"- why_it_matters: {issue['why_it_matters']}",
        f"- baseline_not_used: `{issue['baseline_not_used']}`",
    ]
    if issue["version_concentration"] is not None:
        concentration = issue["version_concentration"]
        lines.append(
            "- version_concentration: `{version}` at `{share}` dominant share with `{coverage}` attributable coverage".format(
                version=concentration["dominant_version"],
                share=concentration["dominant_version_share"],
                coverage=concentration["attributable_review_share"],
            )
        )
    else:
        lines.append(f"- version_coverage_note: {issue['version_coverage_note']}")
    lines.append(f"- representative_review_ids: `{', '.join(issue['representative_review_ids'])}`")
    lines.append("- representative_review_texts:")
    for text in issue["representative_review_texts"]:
        lines.append(f"  - {text}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ensure_default_python()
    args = parse_args()

    input_package_path = resolve_repo_path(REPO, args.input_package)
    input_package = load_json(input_package_path)
    config_path = resolve_repo_path(REPO, ensure_non_empty_string(input_package, "config_ref"))
    config = load_json(config_path)
    output_root = resolve_repo_path(REPO, ensure_non_empty_string(input_package.get("output_targets", {}), "output_root"))
    output_root.mkdir(parents=True, exist_ok=True)

    preflight_default = output_root / str(config.get("target_outputs", {}).get("preflight_result_json", "preflight_result.json"))
    preflight_result = load_json(Path(args.preflight_result).resolve() if args.preflight_result else preflight_default)
    if str(preflight_result.get("verdict", "")).lower() != "pass":
        raise SystemExit("Flagship mainline v2 execution requires a passed preflight result.")
    if str(preflight_result.get("input_package_ref", "")).replace("\\", "/") != rel_repo(REPO, input_package_path):
        raise SystemExit("Preflight result does not anchor to the selected flagship mainline v2 input package.")

    artifact_refs = input_package.get("artifact_refs", {})
    gate_summary = load_json(resolve_repo_path(REPO, str(artifact_refs["issue_relevance_gate_summary_json"])))
    gate_run_summary = load_json(resolve_repo_path(REPO, str(artifact_refs["issue_relevance_gate_run_summary_json"])))
    v1_run_summary = load_json(resolve_repo_path(REPO, str(artifact_refs["v1_run_summary_json"])))
    v1_issue_objects = load_json(resolve_repo_path(REPO, str(artifact_refs["v1_issue_objects_json"])))
    v1_issue_population = load_json(resolve_repo_path(REPO, str(artifact_refs["v1_issue_population_index_json"])))
    v1_top_issues = load_json(resolve_repo_path(REPO, str(artifact_refs["v1_top_issues_json"])))

    fieldnames, routing_rows = load_csv_rows(resolve_repo_path(REPO, str(artifact_refs["issue_relevance_gate_routing_csv"])))
    required_fields = list(config.get("input_surface", {}).get("required_routing_fields", []))
    missing_fields = [name for name in required_fields if name not in fieldnames]
    if missing_fields:
        raise SystemExit(f"Issue relevance gate routing CSV is missing required fields: {missing_fields}")

    required_status = str(config.get("input_surface", {}).get("required_issue_relevance_status", "issue_bearing"))
    status_rows = [row for row in routing_rows if str(row.get("issue_relevance_status", "")).strip() == required_status]
    version_window = input_package.get("source_review_scope", {}).get("version_window", {})
    selected_rows = select_window_rows(status_rows, version_window)
    if not selected_rows:
        raise SystemExit("Explicit version window selected zero eligible rows for flagship mainline v2 execution.")

    analyzed_rows = analyze_rows(selected_rows, config)
    issue_objects, issue_population_rows = build_issue_objects(
        analyzed_rows=analyzed_rows,
        config=config,
        run_id=ensure_non_empty_string(input_package.get("execution_scope", {}), "run_id"),
        version_window=version_window,
    )

    run_level_attributable_count = sum(
        1 for row in selected_rows if not str(row.get("app_version_or_null_reason", "")).startswith("null_reason:")
    )
    run_level_version_coverage = float(run_level_attributable_count) / float(len(selected_rows))
    baseline_not_used_value = str(
        input_package.get("previous_version_baseline", {}).get("baseline_not_used_reason", "previous_version_baseline_disabled_by_default")
    )
    scored_issues = score_issue_objects(
        issue_objects=issue_objects,
        config=config,
        version_window=version_window,
        baseline_not_used_value=baseline_not_used_value,
        run_level_version_coverage=run_level_version_coverage,
    )

    top_n = int(input_package.get("ranking_request", {}).get("top_n", config.get("ranking_rules", {}).get("top_n_default", 5)))
    top_issues = []
    for rank, issue in enumerate(scored_issues[:top_n], start=1):
        ranked_issue = dict(issue)
        ranked_issue["issue_rank"] = rank
        top_issues.append(ranked_issue)

    issue_objects_path = output_root / str(config.get("target_outputs", {}).get("issue_objects_json", "issue_objects.json"))
    issue_population_index_path = output_root / str(config.get("target_outputs", {}).get("issue_population_index_json", "issue_population_index.json"))
    top_issues_json_path = output_root / str(config.get("target_outputs", {}).get("top_issues_json", "top_issues.json"))
    top_issues_markdown_path = output_root / str(config.get("target_outputs", {}).get("top_issues_markdown", "top_issues.md"))
    run_summary_path = output_root / str(config.get("target_outputs", {}).get("run_summary_json", "run_summary.json"))
    comparison_path = output_root / str(config.get("target_outputs", {}).get("comparison_json", "v2_vs_v1_comparison.json"))
    verdict_path = output_root / str(config.get("target_outputs", {}).get("verdict_json", "release_gate_verdict.json"))

    for issue in top_issues:
        issue["evidence_refs"]["issue_population_index_ref"] = rel_repo(REPO, issue_population_index_path)

    issue_objects_payload = {
        "phase": "phase5",
        "surface": "flagship_mainline_v2",
        "run_id": ensure_non_empty_string(input_package.get("execution_scope", {}), "run_id"),
        "generated_at": utc_now_iso(),
        "version_window": version_window,
        "requested_top_n": top_n,
        "returned_issue_count": len(scored_issues),
        "run_level_version_coverage": round(run_level_version_coverage, 4),
        "issues": scored_issues,
    }
    save_json(issue_objects_path, issue_objects_payload)

    issue_population_payload = {
        "phase": "phase5",
        "surface": "flagship_mainline_v2",
        "run_id": ensure_non_empty_string(input_package.get("execution_scope", {}), "run_id"),
        "generated_at": utc_now_iso(),
        "version_window": version_window,
        "issue_population_rows": issue_population_rows,
    }
    save_json(issue_population_index_path, issue_population_payload)

    top_issues_payload = {
        "phase": "phase5",
        "surface": "flagship_mainline_v2",
        "run_id": ensure_non_empty_string(input_package.get("execution_scope", {}), "run_id"),
        "generated_at": utc_now_iso(),
        "version_window": version_window,
        "previous_version_baseline_enabled": False,
        "requested_top_n": top_n,
        "returned_issue_count": len(top_issues),
        "active_ranking_factors": ["volume", "low_rating_share"]
        + (["version_concentration"] if run_level_version_coverage >= float(config.get("version_window_rules", {}).get("version_coverage_threshold", 0.7)) else []),
        "inactive_ranking_factors": ["growth"]
        + ([] if run_level_version_coverage >= float(config.get("version_window_rules", {}).get("version_coverage_threshold", 0.7)) else ["version_concentration"]),
        "run_level_version_coverage": round(run_level_version_coverage, 4),
        "version_coverage_threshold": float(config.get("version_window_rules", {}).get("version_coverage_threshold", 0.7)),
        "top_issues": top_issues,
    }
    save_json(top_issues_json_path, top_issues_payload)

    markdown_parts = [
        "# Phase V Flagship Top Issues v2",
        "",
        f"- run_id: `{ensure_non_empty_string(input_package.get('execution_scope', {}), 'run_id')}`",
        f"- version_window: `{version_window.get('window_label', '')}`",
        f"- selected_issue_bearing_reviews: `{len(selected_rows)}`",
        f"- requested_top_n: `{top_n}`",
        f"- returned_issue_count: `{len(top_issues)}`",
        f"- run_level_version_coverage: `{round(run_level_version_coverage, 4)}`",
        f"- version_coverage_threshold: `{float(config.get('version_window_rules', {}).get('version_coverage_threshold', 0.7))}`",
        "- previous_version_baseline: `disabled_by_default`",
        "- comparison_against_frozen_v1: `enabled`",
        "",
    ]
    for issue in top_issues:
        markdown_parts.append(markdown_issue(issue))
    save_text(top_issues_markdown_path, "\n".join(markdown_parts).strip() + "\n")

    comparison_payload = build_comparison_artifact(
        config=config,
        input_package=input_package,
        run_id=ensure_non_empty_string(input_package.get("execution_scope", {}), "run_id"),
        version_window=version_window,
        v1_issue_objects=v1_issue_objects,
        v1_issue_population=v1_issue_population,
        v1_top_issues=v1_top_issues,
        v2_issue_objects=scored_issues,
        v2_population_rows=issue_population_rows,
    )
    save_json(comparison_path, comparison_payload)

    verdict_payload = build_verdict_artifact(
        contract_ref=str(input_package.get("contract_ref")),
        run_id=ensure_non_empty_string(input_package.get("execution_scope", {}), "run_id"),
        comparison=comparison_payload,
        evidence_list=[
            rel_repo(REPO, preflight_default),
            rel_repo(REPO, issue_objects_path),
            rel_repo(REPO, issue_population_index_path),
            rel_repo(REPO, top_issues_json_path),
            rel_repo(REPO, comparison_path),
        ],
        reviewer="GitHub Copilot execution agent",
    )
    save_json(verdict_path, verdict_payload)

    retention_counts = Counter(str(row.get("retention_status", "")) for row in issue_population_rows)
    tier_counts = Counter(str(row.get("issue_evidence_tier", "")) for row in issue_population_rows)
    run_summary = {
        "phase": "phase5",
        "surface": "flagship_mainline_v2",
        "run_id": ensure_non_empty_string(input_package.get("execution_scope", {}), "run_id"),
        "executed_at": utc_now_iso(),
        "contract_ref": str(input_package.get("contract_ref")),
        "v2_contract_direction_ref": str(input_package.get("v2_contract_direction_ref")),
        "input_package_ref": rel_repo(REPO, input_package_path),
        "config_ref": rel_repo(REPO, config_path),
        "external_approval": input_package.get("external_approval"),
        "source_identity": input_package.get("source_identity"),
        "version_window": version_window,
        "selected_issue_bearing_reviews": len(selected_rows),
        "run_level_version_coverage": round(run_level_version_coverage, 4),
        "version_coverage_threshold": float(config.get("version_window_rules", {}).get("version_coverage_threshold", 0.7)),
        "previous_version_baseline_enabled": False,
        "requested_top_n": top_n,
        "returned_top_issue_count": len(top_issues),
        "issue_count_total": len(scored_issues),
        "evidence_tier_counts": dict(sorted(tier_counts.items())),
        "retention_status_counts": dict(sorted(retention_counts.items())),
        "quality_summary": comparison_payload.get("summary_metrics"),
        "lineage": {
            "issue_relevance_gate_run_id": gate_summary.get("run_id"),
            "issue_relevance_rule_version": gate_summary.get("lineage", {}).get("issue_relevance_rule_version"),
            "baseline_model_version": gate_summary.get("lineage", {}).get("baseline_model_version"),
            "baseline_feature_version": gate_summary.get("lineage", {}).get("baseline_feature_version"),
            "taxonomy_version": gate_summary.get("lineage", {}).get("taxonomy_version"),
            "source_inference_run_id": gate_summary.get("lineage", {}).get("source_inference_run_id"),
            "v1_baseline_run_id": v1_run_summary.get("run_id"),
        },
        "artifact_manifest": {
            "preflight_result_json": rel_repo(REPO, preflight_default),
            "issue_objects_json": rel_repo(REPO, issue_objects_path),
            "issue_population_index_json": rel_repo(REPO, issue_population_index_path),
            "top_issues_json": rel_repo(REPO, top_issues_json_path),
            "top_issues_markdown": rel_repo(REPO, top_issues_markdown_path),
            "comparison_json": rel_repo(REPO, comparison_path),
            "verdict_json": rel_repo(REPO, verdict_path),
            "run_summary_json": rel_repo(REPO, run_summary_path),
        },
    }
    save_json(run_summary_path, run_summary)
    print(json.dumps(run_summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())