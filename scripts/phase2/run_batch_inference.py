from __future__ import annotations

import argparse
import csv
import json
import pickle
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from train_baseline_model import FROZEN_LABELS

REPO = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(REPO / "src"))

from sciencia_ingestion.config.settings import load_settings


DEFAULT_BASELINE_DIR = REPO / "reports" / "phase_ii_slice4" / "slice4_baseline_20260406T013500Z"
DEFAULT_GOLD_PATH = REPO / "data" / "gold_eval" / "phase_ii_gold_eval_set_v1.csv"
DEFAULT_OUTPUT_DIR = REPO / "artifacts" / "phase2" / "slice6"
DEFAULT_APP_ID = "com.openai.chatgpt"
DEFAULT_LIMIT = 5000


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now_tag() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_run_id(baseline_run_id: str) -> str:
    return f"slice6_inference_{baseline_run_id}_{utc_now_tag()}"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Run deterministic Slice 6 batch inference and write predictions to durable artifacts and SQLite"
    )
    ap.add_argument(
        "--baseline-dir",
        default=str(DEFAULT_BASELINE_DIR),
        help=f"Path to frozen Slice 4 baseline artifacts (default {DEFAULT_BASELINE_DIR})",
    )
    ap.add_argument(
        "--gold-labels",
        default=str(DEFAULT_GOLD_PATH),
        help=f"Path to frozen gold labels CSV used for exclusion (default {DEFAULT_GOLD_PATH})",
    )
    ap.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Root directory for Slice 6 artifacts (default {DEFAULT_OUTPUT_DIR})",
    )
    ap.add_argument(
        "--app-id",
        default=DEFAULT_APP_ID,
        help=f"App id scope for inference candidate selection (default {DEFAULT_APP_ID})",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "Maximum number of most-recent eligible reviews to score after excluding frozen gold review_ids "
            f"(default {DEFAULT_LIMIT})"
        ),
    )
    ap.add_argument(
        "--run-id",
        help="Optional explicit inference run identifier. If omitted, one is derived from baseline run id and UTC timestamp.",
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


def load_baseline_artifacts(baseline_dir: Path) -> tuple[dict[str, object], object, object, Path, Path]:
    config_path = baseline_dir / "training_config.json"
    config = load_json(config_path)

    if config.get("task") != "single-label pain-point classification":
        raise SystemExit("Baseline config task does not match the frozen Phase II contract")
    if config.get("representation") != "tfidf":
        raise SystemExit("Baseline config representation is not the frozen TF-IDF path")
    if config.get("model") != "logistic_regression":
        raise SystemExit("Baseline config model is not the frozen Logistic Regression baseline")
    if config.get("frozen_taxonomy") != list(FROZEN_LABELS):
        raise SystemExit("Baseline taxonomy does not match the frozen Phase II taxonomy")

    artifacts = config.get("artifacts")
    if not isinstance(artifacts, dict):
        raise SystemExit("Baseline config is missing artifacts object")

    model_path = Path(str(artifacts.get("model", ""))).resolve()
    vectorizer_path = Path(str(artifacts.get("vectorizer", ""))).resolve()
    model = load_pickle(model_path)
    vectorizer = load_pickle(vectorizer_path)

    if not hasattr(vectorizer, "transform"):
        raise SystemExit("Loaded vectorizer does not expose transform()")
    if not hasattr(model, "predict"):
        raise SystemExit("Loaded model does not expose predict()")

    return config, model, vectorizer, model_path, vectorizer_path


def load_gold_review_ids(gold_path: Path) -> list[str]:
    if not gold_path.exists():
        raise SystemExit(f"Gold labels CSV not found: {gold_path}")
    gold_df = pd.read_csv(gold_path)
    required = {"review_id", "label"}
    missing = sorted(required - set(gold_df.columns))
    if missing:
        raise SystemExit(f"Gold labels CSV missing required columns: {missing}")

    deduped = gold_df.dropna(subset=["review_id"]).copy()
    deduped["review_id"] = deduped["review_id"].astype(str)
    return sorted(set(deduped["review_id"].tolist()))


def build_prepared_text(content: object) -> str:
    if content is None:
        return ""
    text = str(content).strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)


def connect_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path), timeout=60)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def ensure_predictions_tables(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS phase2_inference_runs (
            inference_run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed')),
            baseline_run_id TEXT NOT NULL,
            baseline_dir TEXT NOT NULL,
            model_artifact_path TEXT NOT NULL,
            vectorizer_artifact_path TEXT NOT NULL,
            input_scope_json TEXT NOT NULL,
            selected_review_count INTEGER NOT NULL,
            predicted_label_distribution_json TEXT,
            output_predictions_csv TEXT,
            output_summary_json TEXT,
            output_note_md TEXT,
            notes TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS phase2_review_predictions (
            inference_run_id TEXT NOT NULL,
            review_id TEXT NOT NULL,
            review_at TEXT,
            prepared_text TEXT NOT NULL,
            predicted_label TEXT NOT NULL,
            predicted_probability REAL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(inference_run_id, review_id),
            FOREIGN KEY(inference_run_id) REFERENCES phase2_inference_runs(inference_run_id)
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_phase2_review_predictions_review_id ON phase2_review_predictions(review_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_phase2_review_predictions_label ON phase2_review_predictions(predicted_label)"
    )


def select_inference_reviews(
    con: sqlite3.Connection,
    app_id: str,
    limit: int,
    excluded_review_ids: list[str],
) -> list[sqlite3.Row]:
    if not excluded_review_ids:
        raise SystemExit("Excluded gold review_id set is empty; cannot validate unlabeled inference scope")

    placeholders = ",".join(["?"] * len(excluded_review_ids))
    sql = f"""
    SELECT review_id, at AS review_at, content
    FROM reviews
    WHERE app_id = ?
      AND review_id NOT IN ({placeholders})
    ORDER BY COALESCE(at, '') DESC, review_id ASC
    LIMIT ?
    """
    params: list[object] = [app_id, *excluded_review_ids, limit]
    return con.execute(sql, params).fetchall()


def write_predictions_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "inference_run_id",
        "run_created_at",
        "review_id",
        "review_at",
        "prepared_text",
        "predicted_label",
        "predicted_probability",
    ] + [f"proba_{label}" for label in FROZEN_LABELS]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def save_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def build_markdown_note(summary: dict[str, object]) -> str:
    distribution = summary["predicted_label_distribution"]
    assert isinstance(distribution, dict)

    lines = [
        "# Slice 6 Batch Inference Summary",
        "",
        "## Scored Review Set",
        "",
        (
            "Scored the most-recent eligible reviews from SQLite `reviews` for app_id "
            f"`{summary['scope']['app_id']}` after excluding all review_ids from the frozen gold set "
            "`data/gold_eval/phase_ii_gold_eval_set_v1.csv`."
        ),
        f"Selection ordering: `{summary['scope']['selection_order']}`.",
        f"Selection limit: `{summary['scope']['limit']}`.",
        "",
        "## Counts",
        "",
        f"- Selected and scored reviews: `{summary['counts']['selected_reviews']}`",
        f"- Predictions written: `{summary['counts']['predictions_written']}`",
        "",
        "## Frozen Artifacts Used",
        "",
        f"- Baseline run id: `{summary['baseline']['baseline_run_id']}`",
        f"- Model artifact: `{summary['baseline']['model_artifact_path']}`",
        f"- Vectorizer artifact: `{summary['baseline']['vectorizer_artifact_path']}`",
        "",
        "## Predicted Label Distribution",
        "",
    ]

    for label in FROZEN_LABELS:
        lines.append(f"- `{label}`: `{int(distribution.get(label, 0))}`")

    lines.extend(
        [
            "",
            "## Operational Notes",
            "",
            f"- Skipped rows: `{summary['operational']['skipped_rows']}`",
            f"- Validation failures: `{summary['operational']['validation_failures']}`",
            f"- Deterministic scope check: `{summary['operational']['deterministic_scope_validated']}`",
            "",
            "## Phase II Closure",
            "",
            "The batch workflow is closed end to end at batch level: frozen baseline artifacts were loaded, deterministic unlabeled scope was scored, and predictions were written back to durable repository-managed outputs and SQLite.",
            "",
        ]
    )

    return "\n".join(lines)


def validate_prediction_rows(selected_rows: list[sqlite3.Row], prediction_rows: list[dict[str, object]]) -> None:
    if len(selected_rows) != len(prediction_rows):
        raise SystemExit(
            f"Prediction row count mismatch: selected={len(selected_rows)} predictions={len(prediction_rows)}"
        )

    selected_review_ids = [str(row["review_id"]) for row in selected_rows]
    predicted_review_ids = [str(row["review_id"]) for row in prediction_rows]

    if len(set(predicted_review_ids)) != len(predicted_review_ids):
        raise SystemExit("Prediction output has duplicate review_id rows")

    if set(selected_review_ids) != set(predicted_review_ids):
        raise SystemExit("Prediction review_id set does not exactly match selected review_id set")

    bad_labels = sorted({str(row["predicted_label"]) for row in prediction_rows} - set(FROZEN_LABELS))
    if bad_labels:
        raise SystemExit(f"Predictions include labels outside frozen taxonomy: {bad_labels}")


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    baseline_dir = Path(args.baseline_dir).resolve()
    if not baseline_dir.exists():
        raise SystemExit(f"Baseline directory not found: {baseline_dir}")

    gold_path = Path(args.gold_labels).resolve()
    output_root = Path(args.output_dir).resolve()

    baseline_config, model, vectorizer, model_path, vectorizer_path = load_baseline_artifacts(baseline_dir)
    baseline_run_id = str(baseline_config.get("run_id", baseline_dir.name))
    inference_run_id = args.run_id or default_run_id(baseline_run_id)
    run_created_at = utc_now_iso()

    run_dir = output_root / inference_run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    predictions_csv = run_dir / "predictions.csv"
    summary_json = run_dir / "inference_summary.json"
    note_md = run_dir / "inference_note.md"

    settings = load_settings()
    con = connect_db(settings.db_path)

    excluded_gold_ids = load_gold_review_ids(gold_path)
    selection_order = "COALESCE(at, '') DESC, review_id ASC"

    input_scope = {
        "app_id": args.app_id,
        "limit": int(args.limit),
        "selection_order": selection_order,
        "exclude_gold_review_ids_from": str(gold_path),
        "exclude_gold_review_ids_count": len(excluded_gold_ids),
    }

    try:
        ensure_predictions_tables(con)

        con.execute(
            """
            INSERT INTO phase2_inference_runs(
                inference_run_id, created_at, status, baseline_run_id, baseline_dir,
                model_artifact_path, vectorizer_artifact_path, input_scope_json,
                selected_review_count, notes
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inference_run_id,
                run_created_at,
                "started",
                baseline_run_id,
                str(baseline_dir),
                str(model_path),
                str(vectorizer_path),
                json.dumps(input_scope, ensure_ascii=False, sort_keys=True),
                0,
                "slice6_batch_inference",
            ),
        )
        con.commit()

        selected_rows = select_inference_reviews(
            con=con,
            app_id=args.app_id,
            limit=args.limit,
            excluded_review_ids=excluded_gold_ids,
        )
        if not selected_rows:
            raise SystemExit("No eligible unlabeled rows found for inference scope")

        prepared_texts = [build_prepared_text(row["content"]) for row in selected_rows]
        x_infer = vectorizer.transform(prepared_texts)
        predicted_labels = [str(v) for v in model.predict(x_infer)]

        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(x_infer)
            class_order = [str(v) for v in getattr(model, "classes_", [])]
        else:
            probabilities = None
            class_order = []

        prediction_rows: list[dict[str, object]] = []
        for i, row in enumerate(selected_rows):
            probability_payload: dict[str, float | None] = {}
            predicted_probability: float | None = None
            if probabilities is not None:
                row_proba = probabilities[i]
                predicted_probability = float(max(row_proba))
                for label in FROZEN_LABELS:
                    if label in class_order:
                        probability_payload[f"proba_{label}"] = float(row_proba[class_order.index(label)])
                    else:
                        probability_payload[f"proba_{label}"] = None
            else:
                for label in FROZEN_LABELS:
                    probability_payload[f"proba_{label}"] = None

            prediction_rows.append(
                {
                    "inference_run_id": inference_run_id,
                    "run_created_at": run_created_at,
                    "review_id": str(row["review_id"]),
                    "review_at": row["review_at"],
                    "prepared_text": prepared_texts[i],
                    "predicted_label": predicted_labels[i],
                    "predicted_probability": predicted_probability,
                    **probability_payload,
                }
            )

        validate_prediction_rows(selected_rows, prediction_rows)

        for row in prediction_rows:
            con.execute(
                """
                INSERT INTO phase2_review_predictions(
                    inference_run_id, review_id, review_at, prepared_text,
                    predicted_label, predicted_probability, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["inference_run_id"],
                    row["review_id"],
                    row["review_at"],
                    row["prepared_text"],
                    row["predicted_label"],
                    row["predicted_probability"],
                    run_created_at,
                ),
            )

        predicted_label_distribution = {
            label: int(Counter([str(r["predicted_label"]) for r in prediction_rows]).get(label, 0))
            for label in FROZEN_LABELS
        }

        write_predictions_csv(predictions_csv, prediction_rows)

        summary_payload = {
            "inference_run_id": inference_run_id,
            "created_at": run_created_at,
            "script_path": str(Path(__file__).resolve()),
            "db_path": str(settings.db_path),
            "frozen_contract": {
                "task": "single-label pain-point classification",
                "representation": "tfidf",
                "model": "logistic_regression",
                "taxonomy": list(FROZEN_LABELS),
            },
            "baseline": {
                "baseline_run_id": baseline_run_id,
                "baseline_dir": str(baseline_dir),
                "model_artifact_path": str(model_path),
                "vectorizer_artifact_path": str(vectorizer_path),
            },
            "scope": input_scope,
            "counts": {
                "selected_reviews": int(len(selected_rows)),
                "predictions_written": int(len(prediction_rows)),
                "sqlite_rows_inserted": int(len(prediction_rows)),
            },
            "predicted_label_distribution": predicted_label_distribution,
            "operational": {
                "skipped_rows": 0,
                "validation_failures": 0,
                "deterministic_scope_validated": True,
            },
            "artifacts": {
                "predictions_csv": str(predictions_csv),
                "inference_summary_json": str(summary_json),
                "inference_note_md": str(note_md),
                "sqlite_table_runs": "phase2_inference_runs",
                "sqlite_table_predictions": "phase2_review_predictions",
            },
        }

        note_md.write_text(build_markdown_note(summary_payload), encoding="utf-8")
        save_json(summary_json, summary_payload)

        con.execute(
            """
            UPDATE phase2_inference_runs
            SET status=?, selected_review_count=?, predicted_label_distribution_json=?,
                output_predictions_csv=?, output_summary_json=?, output_note_md=?
            WHERE inference_run_id=?
            """,
            (
                "completed",
                len(selected_rows),
                json.dumps(predicted_label_distribution, ensure_ascii=False, sort_keys=True),
                str(predictions_csv),
                str(summary_json),
                str(note_md),
                inference_run_id,
            ),
        )
        con.commit()

        print(json.dumps(summary_payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception:
        con.rollback()
        try:
            con.execute(
                "UPDATE phase2_inference_runs SET status=? WHERE inference_run_id=?",
                ("failed", inference_run_id),
            )
            con.commit()
        except Exception:
            pass
        raise
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
