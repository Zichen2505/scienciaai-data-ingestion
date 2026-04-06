from __future__ import annotations

import argparse
import json
import math
import pickle
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression


REPO = Path(__file__).resolve().parents[2]
DEFAULT_GOLD_PATH = REPO / "data" / "gold_eval" / "phase_ii_gold_eval_set_v1.csv"
DEFAULT_OUTPUT_DIR = REPO / "reports" / "phase_ii_slice4"
FROZEN_LABELS = (
    "performance_reliability",
    "account_access",
    "ui_navigation",
    "pricing_access_limits",
    "capability_answer_quality",
    "other",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_run_id() -> str:
    return f"slice4_baseline_{uuid.uuid4().hex[:12]}"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Train the frozen Phase II baseline model using Slice 3 modeling input and gold labels"
    )
    ap.add_argument(
        "--modeling-input",
        required=True,
        help="Path to the Slice 3 modeling-input CSV to use for training",
    )
    ap.add_argument(
        "--gold-labels",
        default=str(DEFAULT_GOLD_PATH),
        help=f"Path to frozen gold labels CSV (default {DEFAULT_GOLD_PATH})",
    )
    ap.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory for run artifacts (default {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "--test-fraction",
        type=float,
        default=0.2,
        help="Fraction of chronologically newest labeled rows reserved for test (default 0.2)",
    )
    ap.add_argument(
        "--run-id",
        help="Optional explicit run identifier. If omitted, a new deterministic-looking UUID-based id is created.",
    )
    return ap.parse_args()


def validate_test_fraction(test_fraction: float) -> None:
    if not 0.0 < test_fraction < 1.0:
        raise SystemExit("--test-fraction must be strictly between 0 and 1")


def load_inputs(modeling_input_path: Path, gold_labels_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not modeling_input_path.exists():
        raise SystemExit(f"Modeling input not found: {modeling_input_path}")
    if not gold_labels_path.exists():
        raise SystemExit(f"Gold labels not found: {gold_labels_path}")

    modeling_df = pd.read_csv(modeling_input_path)
    gold_df = pd.read_csv(gold_labels_path)
    return modeling_df, gold_df


def validate_taxonomy(gold_df: pd.DataFrame) -> list[str]:
    label_values = sorted(set(gold_df["label"].dropna().astype(str)))
    unexpected = sorted(set(label_values) - set(FROZEN_LABELS))
    missing = sorted(set(FROZEN_LABELS) - set(label_values))
    if unexpected:
        raise SystemExit(f"Gold labels include unexpected taxonomy values: {unexpected}")
    if missing:
        raise SystemExit(f"Gold labels are missing frozen taxonomy values: {missing}")
    return list(label_values)


def build_labeled_dataset(modeling_df: pd.DataFrame, gold_df: pd.DataFrame) -> pd.DataFrame:
    required_modeling_columns = {"review_id", "review_at", "prepared_text"}
    required_gold_columns = {"review_id", "label"}
    missing_modeling = sorted(required_modeling_columns - set(modeling_df.columns))
    missing_gold = sorted(required_gold_columns - set(gold_df.columns))
    if missing_modeling:
        raise SystemExit(f"Modeling input missing required columns: {missing_modeling}")
    if missing_gold:
        raise SystemExit(f"Gold labels missing required columns: {missing_gold}")

    gold_deduped = gold_df.drop_duplicates(subset=["review_id"], keep="first").copy()
    modeling_deduped = modeling_df.drop_duplicates(subset=["review_id"], keep="first").copy()

    labeled_df = gold_deduped.merge(modeling_deduped, on="review_id", how="inner", validate="one_to_one")
    missing_review_ids = sorted(set(gold_deduped["review_id"]) - set(labeled_df["review_id"]))
    if missing_review_ids:
        preview = missing_review_ids[:10]
        raise SystemExit(
            f"Modeling input does not cover all gold review_ids. Missing count={len(missing_review_ids)} preview={preview}"
        )

    labeled_df["prepared_text"] = labeled_df["prepared_text"].fillna("").astype(str)
    labeled_df["review_at"] = pd.to_datetime(labeled_df["review_at"], utc=True, errors="coerce")
    if labeled_df["review_at"].isna().any():
        bad_ids = labeled_df.loc[labeled_df["review_at"].isna(), "review_id"].tolist()[:10]
        raise SystemExit(f"Unable to parse review_at for some labeled rows. Review id preview: {bad_ids}")

    labeled_df = labeled_df.sort_values(["review_at", "review_id"], ascending=[True, True], kind="mergesort")
    labeled_df = labeled_df.reset_index(drop=True)
    return labeled_df


def split_chronologically(labeled_df: pd.DataFrame, test_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    total_rows = len(labeled_df)
    test_count = max(1, math.ceil(total_rows * test_fraction))
    train_count = total_rows - test_count
    if train_count < 1:
        raise SystemExit("Chronological split would leave no training rows")

    train_df = labeled_df.iloc[:train_count].copy()
    test_df = labeled_df.iloc[train_count:].copy()

    missing_train_labels = sorted(set(FROZEN_LABELS) - set(train_df["label"]))
    if missing_train_labels:
        raise SystemExit(
            "Chronological split left some frozen labels absent from train: "
            f"{missing_train_labels}. Adjust the upstream labeled asset or split policy before training."
        )
    return train_df, test_df, train_count


def count_labels(df: pd.DataFrame) -> dict[str, int]:
    counts = df["label"].value_counts().to_dict()
    return {label: int(counts.get(label, 0)) for label in FROZEN_LABELS}


def build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=1,
        norm="l2",
    )


def build_classifier() -> LogisticRegression:
    return LogisticRegression(
        solver="lbfgs",
        max_iter=1000,
    )


def save_pickle(path: Path, obj: object) -> None:
    with path.open("wb") as f:
        pickle.dump(obj, f)


def save_json(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def main() -> int:
    args = parse_args()
    validate_test_fraction(args.test_fraction)

    run_id = args.run_id or build_run_id()
    modeling_input_path = Path(args.modeling_input).resolve()
    gold_labels_path = Path(args.gold_labels).resolve()
    output_root = Path(args.output_dir).resolve()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    modeling_df, gold_df = load_inputs(modeling_input_path, gold_labels_path)
    validate_taxonomy(gold_df)
    labeled_df = build_labeled_dataset(modeling_df, gold_df)
    train_df, test_df, train_count = split_chronologically(labeled_df, args.test_fraction)

    vectorizer = build_vectorizer()
    classifier = build_classifier()

    x_train = vectorizer.fit_transform(train_df["prepared_text"])
    x_test = vectorizer.transform(test_df["prepared_text"])
    classifier.fit(x_train, train_df["label"])

    model_artifact_path = run_dir / "baseline_logistic_regression.pkl"
    vectorizer_artifact_path = run_dir / "baseline_tfidf_vectorizer.pkl"
    config_path = run_dir / "training_config.json"
    summary_path = run_dir / "training_summary.json"

    save_pickle(model_artifact_path, classifier)
    save_pickle(vectorizer_artifact_path, vectorizer)

    config = {
        "run_id": run_id,
        "created_at": utc_now_iso(),
        "task": "single-label pain-point classification",
        "representation": "tfidf",
        "model": "logistic_regression",
        "frozen_taxonomy": list(FROZEN_LABELS),
        "input_paths": {
            "modeling_input": str(modeling_input_path),
            "gold_labels": str(gold_labels_path),
        },
        "split": {
            "strategy": "chronological",
            "sort_order": ["review_at asc", "review_id asc"],
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "test_fraction": args.test_fraction,
            "train_end_index_exclusive": int(train_count),
        },
        "tfidf": {
            "lowercase": True,
            "strip_accents": "unicode",
            "ngram_range": [1, 2],
            "min_df": 1,
            "norm": "l2",
        },
        "logistic_regression": {
            "solver": "lbfgs",
            "max_iter": 1000,
        },
        "artifacts": {
            "model": str(model_artifact_path),
            "vectorizer": str(vectorizer_artifact_path),
            "summary": str(summary_path),
        },
    }
    save_json(config_path, config)

    summary = {
        "run_id": run_id,
        "completed_at": utc_now_iso(),
        "script_path": str(Path(__file__).resolve()),
        "data_source_paths": {
            "modeling_input": str(modeling_input_path),
            "gold_labels": str(gold_labels_path),
        },
        "label_set_used": list(FROZEN_LABELS),
        "model_statement": "Only TF-IDF features and one Logistic Regression classifier were used.",
        "split_logic": {
            "strategy": "chronological",
            "description": (
                "Join frozen gold labels to Slice 3 modeling input on review_id, sort by review_at ascending and "
                "review_id ascending, use the oldest rows for train, and reserve the chronologically newest rows "
                "for test."
            ),
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
            "train_start_review_at": train_df.iloc[0]["review_at"].isoformat().replace("+00:00", "Z"),
            "train_end_review_at": train_df.iloc[-1]["review_at"].isoformat().replace("+00:00", "Z"),
            "test_start_review_at": test_df.iloc[0]["review_at"].isoformat().replace("+00:00", "Z"),
            "test_end_review_at": test_df.iloc[-1]["review_at"].isoformat().replace("+00:00", "Z"),
            "train_end_review_id": str(train_df.iloc[-1]["review_id"]),
            "test_start_review_id": str(test_df.iloc[0]["review_id"]),
        },
        "counts": {
            "joined_labeled_rows": int(len(labeled_df)),
            "train_rows": int(len(train_df)),
            "test_rows": int(len(test_df)),
        },
        "class_counts_by_split": {
            "train": count_labels(train_df),
            "test": count_labels(test_df),
        },
        "vectorizer": {
            "vocabulary_size": int(len(vectorizer.vocabulary_)),
            "train_matrix_shape": [int(x_train.shape[0]), int(x_train.shape[1])],
            "test_matrix_shape": [int(x_test.shape[0]), int(x_test.shape[1])],
        },
        "artifacts": {
            "model": str(model_artifact_path),
            "vectorizer": str(vectorizer_artifact_path),
            "config": str(config_path),
            "summary": str(summary_path),
        },
    }
    save_json(summary_path, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())