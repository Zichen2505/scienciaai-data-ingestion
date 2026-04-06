from __future__ import annotations

import argparse
import csv
import json
import pickle
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from train_baseline_model import FROZEN_LABELS, build_labeled_dataset, load_inputs, split_chronologically, validate_taxonomy


REPO = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE_DIR = REPO / "reports" / "phase_ii_slice4" / "slice4_baseline_20260406T013500Z"
DEFAULT_OUTPUT_DIR = REPO / "reports" / "phase_ii_slice5"
DEFAULT_REPRESENTATIVE_ERROR_LIMIT = 12


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_run_id(baseline_run_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"slice5_eval_{baseline_run_id}_{timestamp}"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Evaluate the frozen Phase II Slice 4 baseline model on its held-out chronological test split"
    )
    ap.add_argument(
        "--baseline-dir",
        default=str(DEFAULT_BASELINE_DIR),
        help=f"Path to the Slice 4 baseline artifact directory (default {DEFAULT_BASELINE_DIR})",
    )
    ap.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for Slice 5 evaluation artifacts (default {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "--run-id",
        help="Optional explicit Slice 5 run id. If omitted, one is derived from the baseline run id and UTC timestamp.",
    )
    ap.add_argument(
        "--representative-error-limit",
        type=int,
        default=DEFAULT_REPRESENTATIVE_ERROR_LIMIT,
        help=(
            "Maximum number of representative misclassified examples to surface in the summary artifacts "
            f"(default {DEFAULT_REPRESENTATIVE_ERROR_LIMIT})"
        ),
    )
    return ap.parse_args()


def load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise SystemExit(f"Required JSON artifact not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return payload


def load_pickle(path: Path) -> object:
    if not path.exists():
        raise SystemExit(f"Required pickle artifact not found: {path}")
    with path.open("rb") as f:
        return pickle.load(f)


def load_baseline_artifacts(baseline_dir: Path) -> tuple[dict[str, object], dict[str, object], object, object]:
    config_path = baseline_dir / "training_config.json"
    summary_path = baseline_dir / "training_summary.json"
    config = load_json(config_path)
    summary = load_json(summary_path)

    artifacts = config.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit(f"Training config missing artifacts object: {config_path}")

    model_path = Path(str(artifacts.get("model", ""))).resolve()
    vectorizer_path = Path(str(artifacts.get("vectorizer", ""))).resolve()
    model = load_pickle(model_path)
    vectorizer = load_pickle(vectorizer_path)
    return config, summary, model, vectorizer


def validate_frozen_baseline_config(config: dict[str, object]) -> None:
    if config.get("task") != "single-label pain-point classification":
        raise SystemExit("Baseline config task does not match the frozen Phase II contract")
    if config.get("representation") != "tfidf":
        raise SystemExit("Baseline config representation is not the frozen TF-IDF path")
    if config.get("model") != "logistic_regression":
        raise SystemExit("Baseline config model is not the frozen Logistic Regression baseline")

    taxonomy = config.get("frozen_taxonomy")
    if taxonomy != list(FROZEN_LABELS):
        raise SystemExit("Baseline config taxonomy does not match the frozen Phase II taxonomy")

    split = config.get("split")
    if not isinstance(split, dict):
        raise SystemExit("Baseline config missing split object")
    if split.get("strategy") != "chronological":
        raise SystemExit("Baseline config split strategy is not chronological")


def reconstruct_test_set(config: dict[str, object]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    input_paths = config.get("input_paths")
    split = config.get("split")
    if not isinstance(input_paths, dict):
        raise SystemExit("Baseline config missing input_paths object")
    if not isinstance(split, dict):
        raise SystemExit("Baseline config missing split object")

    modeling_input_path = Path(str(input_paths.get("modeling_input", ""))).resolve()
    gold_labels_path = Path(str(input_paths.get("gold_labels", ""))).resolve()

    test_fraction = split.get("test_fraction")
    if not isinstance(test_fraction, (int, float)):
        raise SystemExit("Baseline config missing numeric split.test_fraction")

    modeling_df, gold_df = load_inputs(modeling_input_path, gold_labels_path)
    validate_taxonomy(gold_df)
    labeled_df = build_labeled_dataset(modeling_df, gold_df)
    train_df, test_df, _ = split_chronologically(labeled_df, float(test_fraction))
    return labeled_df, train_df, test_df


def assert_reconstructed_split_matches_summary(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    training_summary: dict[str, object],
) -> None:
    split_logic = training_summary.get("split_logic")
    counts = training_summary.get("counts")
    class_counts_by_split = training_summary.get("class_counts_by_split")
    if not isinstance(split_logic, dict) or not isinstance(counts, dict) or not isinstance(class_counts_by_split, dict):
        raise SystemExit("Training summary is missing split metadata needed for Slice 5 verification")

    expected_train_rows = int(counts.get("train_rows", -1))
    expected_test_rows = int(counts.get("test_rows", -1))
    if len(train_df) != expected_train_rows or len(test_df) != expected_test_rows:
        raise SystemExit(
            "Reconstructed split row counts do not match the frozen Slice 4 summary: "
            f"train={len(train_df)} expected_train={expected_train_rows}, "
            f"test={len(test_df)} expected_test={expected_test_rows}"
        )

    expected_train_start = str(split_logic.get("train_start_review_at", ""))
    expected_train_end = str(split_logic.get("train_end_review_at", ""))
    expected_test_start = str(split_logic.get("test_start_review_at", ""))
    expected_test_end = str(split_logic.get("test_end_review_at", ""))
    expected_train_end_review_id = str(split_logic.get("train_end_review_id", ""))
    expected_test_start_review_id = str(split_logic.get("test_start_review_id", ""))

    actual_train_start = train_df.iloc[0]["review_at"].isoformat().replace("+00:00", "Z")
    actual_train_end = train_df.iloc[-1]["review_at"].isoformat().replace("+00:00", "Z")
    actual_test_start = test_df.iloc[0]["review_at"].isoformat().replace("+00:00", "Z")
    actual_test_end = test_df.iloc[-1]["review_at"].isoformat().replace("+00:00", "Z")
    actual_train_end_review_id = str(train_df.iloc[-1]["review_id"])
    actual_test_start_review_id = str(test_df.iloc[0]["review_id"])

    comparisons = {
        "train_start_review_at": (actual_train_start, expected_train_start),
        "train_end_review_at": (actual_train_end, expected_train_end),
        "test_start_review_at": (actual_test_start, expected_test_start),
        "test_end_review_at": (actual_test_end, expected_test_end),
        "train_end_review_id": (actual_train_end_review_id, expected_train_end_review_id),
        "test_start_review_id": (actual_test_start_review_id, expected_test_start_review_id),
    }
    mismatches = [f"{key}: actual={actual} expected={expected}" for key, (actual, expected) in comparisons.items() if actual != expected]
    if mismatches:
        raise SystemExit("Reconstructed split does not match the frozen Slice 4 boundary metadata: " + "; ".join(mismatches))

    expected_train_counts = class_counts_by_split.get("train")
    expected_test_counts = class_counts_by_split.get("test")
    if not isinstance(expected_train_counts, dict) or not isinstance(expected_test_counts, dict):
        raise SystemExit("Training summary missing class_counts_by_split metadata")

    actual_train_counts = count_labels(train_df["label"].tolist())
    actual_test_counts = count_labels(test_df["label"].tolist())
    if actual_train_counts != {label: int(expected_train_counts.get(label, -1)) for label in FROZEN_LABELS}:
        raise SystemExit("Reconstructed train label counts do not match the frozen Slice 4 summary")
    if actual_test_counts != {label: int(expected_test_counts.get(label, -1)) for label in FROZEN_LABELS}:
        raise SystemExit("Reconstructed test label counts do not match the frozen Slice 4 summary")


def count_labels(values: list[str]) -> dict[str, int]:
    counts = Counter(values)
    return {label: int(counts.get(label, 0)) for label in FROZEN_LABELS}


def build_predictions_dataframe(test_df: pd.DataFrame, vectorizer: object, model: object) -> pd.DataFrame:
    if not hasattr(vectorizer, "transform"):
        raise SystemExit("Loaded vectorizer artifact does not expose transform()")
    if not hasattr(model, "predict"):
        raise SystemExit("Loaded model artifact does not expose predict()")

    transformed = vectorizer.transform(test_df["prepared_text"])
    predicted_labels = model.predict(transformed)

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba(transformed)
        class_order = list(getattr(model, "classes_", []))
        max_probability = probabilities.max(axis=1)
    else:
        probabilities = None
        class_order = []
        max_probability = [None] * len(test_df)

    predicted_df = test_df.copy()
    predicted_df["gold_label"] = predicted_df["label"].astype(str)
    predicted_df["predicted_label"] = pd.Series(predicted_labels, index=predicted_df.index).astype(str)
    predicted_df["correct"] = predicted_df["gold_label"] == predicted_df["predicted_label"]
    predicted_df["predicted_probability"] = list(max_probability)

    for label in FROZEN_LABELS:
        if probabilities is not None and label in class_order:
            class_index = class_order.index(label)
            predicted_df[f"proba_{label}"] = probabilities[:, class_index]
        else:
            predicted_df[f"proba_{label}"] = None

    return predicted_df


def compute_metric_package(predicted_df: pd.DataFrame) -> dict[str, object]:
    y_true = predicted_df["gold_label"].tolist()
    y_pred = predicted_df["predicted_label"].tolist()

    accuracy = accuracy_score(y_true, y_pred)
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=list(FROZEN_LABELS),
        average="macro",
        zero_division=0,
    )
    weighted_precision, weighted_recall, weighted_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=list(FROZEN_LABELS),
        average="weighted",
        zero_division=0,
    )

    per_class_precision, per_class_recall, per_class_f1, per_class_support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=list(FROZEN_LABELS),
        average=None,
        zero_division=0,
    )

    per_class_metrics = {}
    for index, label in enumerate(FROZEN_LABELS):
        per_class_metrics[label] = {
            "precision": round(float(per_class_precision[index]), 4),
            "recall": round(float(per_class_recall[index]), 4),
            "f1": round(float(per_class_f1[index]), 4),
            "support": int(per_class_support[index]),
        }

    confusion = confusion_matrix(y_true, y_pred, labels=list(FROZEN_LABELS))
    confusion_rows = []
    for row_index, gold_label in enumerate(FROZEN_LABELS):
        row_payload = {"gold_label": gold_label}
        for column_index, predicted_label in enumerate(FROZEN_LABELS):
            row_payload[predicted_label] = int(confusion[row_index, column_index])
        confusion_rows.append(row_payload)

    return {
        "overall": {
            "accuracy": round(float(accuracy), 4),
            "macro_precision": round(float(macro_precision), 4),
            "macro_recall": round(float(macro_recall), 4),
            "macro_f1": round(float(macro_f1), 4),
            "weighted_precision": round(float(weighted_precision), 4),
            "weighted_recall": round(float(weighted_recall), 4),
            "weighted_f1": round(float(weighted_f1), 4),
        },
        "per_class": per_class_metrics,
        "confusion_matrix": {
            "labels": list(FROZEN_LABELS),
            "rows": confusion_rows,
        },
        "true_label_distribution": count_labels(y_true),
        "predicted_label_distribution": count_labels(y_pred),
    }


def summarize_confusions(predicted_df: pd.DataFrame) -> list[dict[str, object]]:
    incorrect_df = predicted_df.loc[~predicted_df["correct"]].copy()
    if incorrect_df.empty:
        return []

    pair_counts = (
        incorrect_df.groupby(["gold_label", "predicted_label"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["count", "gold_label", "predicted_label"], ascending=[False, True, True])
    )

    summary = []
    for row in pair_counts.itertuples(index=False):
        summary.append(
            {
                "gold_label": str(row.gold_label),
                "predicted_label": str(row.predicted_label),
                "count": int(row.count),
            }
        )
    return summary


def pick_representative_errors(predicted_df: pd.DataFrame, limit: int) -> list[dict[str, object]]:
    if limit < 1:
        return []

    incorrect_df = predicted_df.loc[~predicted_df["correct"]].copy()
    if incorrect_df.empty:
        return []

    pair_counts = Counter(zip(incorrect_df["gold_label"], incorrect_df["predicted_label"]))
    incorrect_df["confusion_pair_count"] = [pair_counts[(gold, pred)] for gold, pred in zip(incorrect_df["gold_label"], incorrect_df["predicted_label"])]
    incorrect_df = incorrect_df.sort_values(
        ["confusion_pair_count", "predicted_probability", "review_at", "review_id"],
        ascending=[False, False, True, True],
        na_position="last",
        kind="mergesort",
    )

    selected_rows = []
    seen_pair_counts: dict[tuple[str, str], int] = {}
    max_per_pair = 3

    for row in incorrect_df.itertuples(index=False):
        pair = (str(row.gold_label), str(row.predicted_label))
        if seen_pair_counts.get(pair, 0) >= max_per_pair:
            continue
        selected_rows.append(row)
        seen_pair_counts[pair] = seen_pair_counts.get(pair, 0) + 1
        if len(selected_rows) >= limit:
            break

    if len(selected_rows) < min(limit, len(incorrect_df)):
        selected_ids = {str(row.review_id) for row in selected_rows}
        for row in incorrect_df.itertuples(index=False):
            if str(row.review_id) in selected_ids:
                continue
            selected_rows.append(row)
            if len(selected_rows) >= limit:
                break

    representative_errors = []
    for row in selected_rows:
        representative_errors.append(
            {
                "review_id": str(row.review_id),
                "review_at": row.review_at.isoformat().replace("+00:00", "Z"),
                "gold_label": str(row.gold_label),
                "predicted_label": str(row.predicted_label),
                "predicted_probability": None if pd.isna(row.predicted_probability) else round(float(row.predicted_probability), 4),
                "prepared_text": str(row.prepared_text),
                "rating": None if pd.isna(row.rating) else int(row.rating),
            }
        )
    return representative_errors


def build_diagnosis(metric_package: dict[str, object], confusion_summary: list[dict[str, object]]) -> dict[str, object]:
    predicted_distribution = metric_package["predicted_label_distribution"]
    true_distribution = metric_package["true_label_distribution"]
    per_class = metric_package["per_class"]
    assert isinstance(predicted_distribution, dict)
    assert isinstance(true_distribution, dict)
    assert isinstance(per_class, dict)

    predicted_total = sum(int(value) for value in predicted_distribution.values())
    sorted_predicted = sorted(predicted_distribution.items(), key=lambda item: (-int(item[1]), item[0]))
    top_two_predicted_share = 0.0
    if predicted_total > 0:
        top_two_predicted_share = sum(int(count) for _, count in sorted_predicted[:2]) / predicted_total

    unused_predicted_labels = [label for label, count in predicted_distribution.items() if int(count) == 0]
    collapse_flag = top_two_predicted_share >= 0.7 or len(unused_predicted_labels) >= 3

    other_true = int(true_distribution.get("other", 0))
    other_pred = int(predicted_distribution.get("other", 0))
    overuses_other = other_pred >= max(3, other_true * 2)

    minority_labels = [label for label, support in true_distribution.items() if int(support) <= 3]
    minority_struggles = []
    for label in minority_labels:
        label_metrics = per_class.get(label)
        if not isinstance(label_metrics, dict):
            continue
        if float(label_metrics.get("recall", 0.0)) == 0.0 or float(label_metrics.get("f1", 0.0)) == 0.0:
            minority_struggles.append(label)

    weakest_labels = sorted(
        [
            {
                "label": label,
                "f1": float(metrics.get("f1", 0.0)),
                "recall": float(metrics.get("recall", 0.0)),
                "support": int(metrics.get("support", 0)),
            }
            for label, metrics in per_class.items()
            if isinstance(metrics, dict) and int(metrics.get("support", 0)) > 0
        ],
        key=lambda item: (item["f1"], item["recall"], item["label"]),
    )

    blocking_failure = False
    blocking_reasons = []
    overall = metric_package["overall"]
    assert isinstance(overall, dict)
    if float(overall.get("macro_f1", 0.0)) < 0.35:
        blocking_failure = True
        blocking_reasons.append("macro_f1_below_0_35")
    if collapse_flag:
        blocking_reasons.append("predicted_distribution_concentrated")
    if overuses_other:
        blocking_reasons.append("other_overused")
    if len(minority_struggles) >= 2:
        blocking_reasons.append("multiple_minority_labels_have_zero_recall_or_f1")

    recommendation = "pass_to_slice6" if not blocking_failure else "fail_hold_slice6"

    return {
        "collapse_into_few_classes": collapse_flag,
        "collapse_evidence": {
            "top_two_predicted_share": round(float(top_two_predicted_share), 4),
            "unused_predicted_labels": unused_predicted_labels,
        },
        "minority_label_struggles": minority_struggles,
        "overuses_other": overuses_other,
        "top_confusion_pairs": confusion_summary[:5],
        "weakest_labels": weakest_labels[:3],
        "recommendation": recommendation,
        "blocking_failure": blocking_failure,
        "blocking_reasons": blocking_reasons,
    }


def build_follow_up_ideas(diagnosis: dict[str, object]) -> list[str]:
    ideas = [
        "Audit the weakest confusion pairs against the Slice 1 labeling rules to separate label-boundary noise from genuine model blind spots.",
        "Expand the frozen gold asset in a later slice with more chronologically recent examples for the weakest labels, especially low-support classes.",
        "Inspect the highest-confidence wrong predictions to identify missing lexical cues or wording patterns that TF-IDF is not separating well.",
        "Before large batch inference, add a lightweight manual QA pass on predicted `other` cases and the dominant confusion pairs to estimate operational review cost.",
    ]
    if bool(diagnosis.get("overuses_other")):
        ideas[3] = "Before large batch inference, add a lightweight manual QA pass focused on predicted `other` cases because the baseline appears to overuse that residual label."
    return ideas[:4]


def write_predictions_csv(path: Path, predicted_df: pd.DataFrame) -> None:
    export_df = predicted_df.copy()
    export_df["review_at"] = export_df["review_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    export_columns = [
        "review_id",
        "review_at",
        "rating",
        "gold_label",
        "predicted_label",
        "correct",
        "predicted_probability",
        "prepared_text",
    ] + [f"proba_{label}" for label in FROZEN_LABELS]
    export_df.to_csv(path, columns=export_columns, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)


def write_misclassified_csv(path: Path, predicted_df: pd.DataFrame) -> None:
    misclassified_df = predicted_df.loc[~predicted_df["correct"]].copy()
    misclassified_df["review_at"] = misclassified_df["review_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    export_columns = [
        "review_id",
        "review_at",
        "rating",
        "gold_label",
        "predicted_label",
        "correct",
        "predicted_probability",
        "prepared_text",
    ] + [f"proba_{label}" for label in FROZEN_LABELS]
    misclassified_df.to_csv(path, columns=export_columns, index=False, encoding="utf-8", quoting=csv.QUOTE_MINIMAL)


def build_markdown_summary(
    baseline_run_id: str,
    metric_package: dict[str, object],
    diagnosis: dict[str, object],
    representative_errors: list[dict[str, object]],
    follow_up_ideas: list[str],
    test_row_count: int,
) -> str:
    overall = metric_package["overall"]
    per_class = metric_package["per_class"]
    assert isinstance(overall, dict)
    assert isinstance(per_class, dict)

    strongest_labels = sorted(
        [
            {
                "label": label,
                "f1": float(metrics.get("f1", 0.0)),
                "recall": float(metrics.get("recall", 0.0)),
                "support": int(metrics.get("support", 0)),
            }
            for label, metrics in per_class.items()
            if isinstance(metrics, dict) and int(metrics.get("support", 0)) > 0
        ],
        key=lambda item: (-item["f1"], -item["recall"], item["label"]),
    )
    weakest_labels = diagnosis.get("weakest_labels", [])
    top_confusions = diagnosis.get("top_confusion_pairs", [])
    recommendation = str(diagnosis.get("recommendation", "pass_to_slice6"))

    lines = [
        "# Slice 5 Offline Evaluation Summary",
        "",
        f"Baseline evaluated: `{baseline_run_id}`",
        f"Held-out test rows: `{test_row_count}`",
        "",
        "## Headline",
        "",
        (
            "The frozen Slice 4 baseline was evaluated on the reconstructed chronological held-out test split without changing "
            "task semantics, labels, representation, split policy, or model family."
        ),
        "",
        (
            f"Headline metrics: accuracy `{overall['accuracy']:.4f}`, macro F1 `{overall['macro_f1']:.4f}`, "
            f"weighted F1 `{overall['weighted_f1']:.4f}`."
        ),
        "",
        "## Label Performance",
        "",
    ]

    for item in strongest_labels[:2]:
        lines.append(
            f"- Stronger label: `{item['label']}` with F1 `{item['f1']:.4f}`, recall `{item['recall']:.4f}`, support `{item['support']}`."
        )
    for item in weakest_labels:
        if isinstance(item, dict):
            lines.append(
                f"- Weaker label: `{item['label']}` with F1 `{float(item['f1']):.4f}`, recall `{float(item['recall']):.4f}`, support `{int(item['support'])}`."
            )

    lines.extend(["", "## Main Confusions", ""])
    if top_confusions:
        for item in top_confusions:
            if isinstance(item, dict):
                lines.append(
                    f"- `{item['gold_label']}` was most often predicted as `{item['predicted_label']}` `{int(item['count'])}` time(s)."
                )
    else:
        lines.append("- No off-diagonal confusions were observed on the held-out set.")

    lines.extend(["", "## Diagnosis", ""])
    lines.append(
        f"- Predicted-class concentration flag: `{bool(diagnosis.get('collapse_into_few_classes'))}`."
    )
    lines.append(f"- Minority-label struggle flags: `{', '.join(diagnosis.get('minority_label_struggles', [])) or 'none'}`.")
    lines.append(f"- `other` overuse flag: `{bool(diagnosis.get('overuses_other'))}`.")
    lines.append(
        f"- Slice 6 recommendation: `{'pass' if recommendation == 'pass_to_slice6' else 'fail'}`."
    )

    lines.extend(["", "## Representative Errors", ""])
    if representative_errors:
        for item in representative_errors:
            lines.append(
                f"- `{item['review_id']}`: gold=`{item['gold_label']}`, predicted=`{item['predicted_label']}`, text="
                f"{item['prepared_text'][:220].strip()}"
            )
    else:
        lines.append("- No misclassified examples were available.")

    lines.extend(["", "## Follow-Up Ideas", ""])
    for idea in follow_up_ideas:
        lines.append(f"- {idea}")

    return "\n".join(lines) + "\n"


def save_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def main() -> int:
    args = parse_args()
    if args.representative_error_limit < 1:
        raise SystemExit("--representative-error-limit must be >= 1")

    baseline_dir = Path(args.baseline_dir).resolve()
    if not baseline_dir.exists():
        raise SystemExit(f"Baseline directory not found: {baseline_dir}")

    config, training_summary, model, vectorizer = load_baseline_artifacts(baseline_dir)
    validate_frozen_baseline_config(config)

    baseline_run_id = str(config.get("run_id", baseline_dir.name))
    run_id = args.run_id or default_run_id(baseline_run_id)
    run_dir = Path(args.output_dir).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    labeled_df, train_df, test_df = reconstruct_test_set(config)
    assert_reconstructed_split_matches_summary(train_df, test_df, training_summary)

    predicted_df = build_predictions_dataframe(test_df, vectorizer, model)
    metric_package = compute_metric_package(predicted_df)
    confusion_summary = summarize_confusions(predicted_df)
    representative_errors = pick_representative_errors(predicted_df, args.representative_error_limit)
    diagnosis = build_diagnosis(metric_package, confusion_summary)
    follow_up_ideas = build_follow_up_ideas(diagnosis)

    predictions_path = run_dir / "test_predictions.csv"
    misclassified_path = run_dir / "misclassified_reviews.csv"
    summary_path = run_dir / "evaluation_summary.json"
    note_path = run_dir / "evaluation_note.md"

    write_predictions_csv(predictions_path, predicted_df)
    write_misclassified_csv(misclassified_path, predicted_df)

    summary_payload = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "script_path": str(Path(__file__).resolve()),
        "baseline": {
            "baseline_dir": str(baseline_dir),
            "baseline_run_id": baseline_run_id,
            "training_config_path": str(baseline_dir / "training_config.json"),
            "training_summary_path": str(baseline_dir / "training_summary.json"),
        },
        "frozen_contract": {
            "task": "single-label pain-point classification",
            "representation": "tfidf",
            "model": "logistic_regression",
            "taxonomy": list(FROZEN_LABELS),
            "split_strategy": "chronological",
        },
        "input_sources": config["input_paths"],
        "reconstructed_split_verification": {
            "joined_labeled_rows": int(len(labeled_df)),
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "train_start_review_at": train_df.iloc[0]["review_at"].isoformat().replace("+00:00", "Z"),
            "train_end_review_at": train_df.iloc[-1]["review_at"].isoformat().replace("+00:00", "Z"),
            "test_start_review_at": test_df.iloc[0]["review_at"].isoformat().replace("+00:00", "Z"),
            "test_end_review_at": test_df.iloc[-1]["review_at"].isoformat().replace("+00:00", "Z"),
            "train_end_review_id": str(train_df.iloc[-1]["review_id"]),
            "test_start_review_id": str(test_df.iloc[0]["review_id"]),
        },
        "metrics": metric_package,
        "diagnosis": diagnosis,
        "top_confusion_pairs": confusion_summary,
        "representative_errors": representative_errors,
        "follow_up_ideas": follow_up_ideas,
        "artifacts": {
            "evaluation_summary": str(summary_path),
            "test_predictions": str(predictions_path),
            "misclassified_reviews": str(misclassified_path),
            "evaluation_note": str(note_path),
        },
    }
    save_json(summary_path, summary_payload)

    note_path.write_text(
        build_markdown_summary(
            baseline_run_id=baseline_run_id,
            metric_package=metric_package,
            diagnosis=diagnosis,
            representative_errors=representative_errors,
            follow_up_ideas=follow_up_ideas,
            test_row_count=len(test_df),
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary_payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())