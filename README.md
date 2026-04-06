# scienciaai-data-ingestion

## Quick Setup

1. Copy `.env.example` to `.env`.
2. Keep the default `SCIENCIAAI_DATA_DIR=.local/scienciaai` for a portable local setup, or point it at any writable directory on your machine.
3. Leave `DB_URL` unset to default to `<SCIENCIAAI_DATA_DIR>/ingestion.db`, or set it explicitly to an absolute SQLite path.
4. Install dependencies from `requirements.txt` in your virtual environment.

## Minimal Smoke Path

```bash
python scripts/collect_recent_window.py --app-id com.openai.chatgpt --target-days 21 --per-page 100 --max-pages 500 --num-buckets 10 --sample-per-bucket 100 --seed 0 --lang en --country us
python scripts/google_play_recent_window_raw_to_sqlite.py --raw-file ./data/checkpoints/com.openai.chatgpt_recent_window_raw_f942add8.jsonl --app-id com.openai.chatgpt --lang en --country us --batch-size 500
python scripts/verify_sqlite.py
```

## Phase II Execution Map

Phase II reviewer entry path:

- contract: [documents/PHASE_II_CONTRACT.md](documents/PHASE_II_CONTRACT.md)
- status: [documents/PHASE_II_STATUS.md](documents/PHASE_II_STATUS.md)
- reviewer summary: [documents/Phase_II_Reviewer_Summary.md](documents/Phase_II_Reviewer_Summary.md)
- labeling rules: [documents/PHASE_II_LABELING_RULES.md](documents/PHASE_II_LABELING_RULES.md)
- frozen gold eval asset: [data/gold_eval/phase_ii_gold_eval_set_v1.csv](data/gold_eval/phase_ii_gold_eval_set_v1.csv)

Active Phase II execution scripts:

- Slice 3 hardened feature pipeline: `python scripts/phase2/run_feature_pipeline_v2.py`
- Slice 4 frozen baseline training: `python scripts/phase2/train_baseline_model.py --modeling-input <slice3_modeling_input_csv>`
- Slice 5 offline evaluation: `python scripts/phase2/evaluate_baseline_model.py`
- Slice 6 batch inference: `python scripts/phase2/run_batch_inference.py`

Artifact and report locations:

- historical and current human-readable evidence remains under [documents](documents) and [reports](reports)
- forward-looking machine-consumable Phase II workflow artifacts should go under [artifacts/phase2](artifacts/phase2)
- historical Slice 3 and Slice 4 outputs remain in [reports/phase_ii_slice3](reports/phase_ii_slice3) and [reports/phase_ii_slice4](reports/phase_ii_slice4) to avoid churn

## Evidence

Curated Phase I evidence is kept under `documents/` and `reports/current_chatgpt_20k_assessment/`.
Noisy machine-local run artifacts are intentionally kept out of canonical history.

## Current Status

For quick orientation, start with [documents/CURRENT_STATUS.md](documents/CURRENT_STATUS.md).

That file is a current-state navigation and dated-update document. It does not replace the historical milestone and evidence documents, which remain the authoritative snapshots of what was verified and concluded at each earlier phase.

Current accepted repo interpretation: canonical ingestion remains intact, and Phase II has closed a minimal end-to-end offline batch AI workflow for single-label pain-point classification with additive SQLite prediction write-back. This is a constrained prototype, not a production ML system.

Historical evidence snapshots:
- [documents/PHASE_I_INGESTION_VALIDATION_SUMMARY.md](documents/PHASE_I_INGESTION_VALIDATION_SUMMARY.md)
- [documents/PROJECT_EXECUTIVE_SUMMARY.md](documents/PROJECT_EXECUTIVE_SUMMARY.md)
- [documents/pilot_sampling_plan.md](documents/pilot_sampling_plan.md)
- [reports/current_chatgpt_20k_assessment/DATASET_ASSESSMENT.md](reports/current_chatgpt_20k_assessment/DATASET_ASSESSMENT.md)

## Canonical Repo Conventions

- Base review entity: `reviews` is the canonical review table. `review_id` is the canonical review key. `content` is the canonical existing review text column.
- Derived text fields: `cleaned_text` is not part of the current base schema. Do not assume it exists unless it is explicitly added later as a derived field.
- Schema source-of-truth: `schema/reviews_schema.sql` is the current schema source-of-truth. Any future feature-engineering schema should extend this schema compatibly rather than replace it.
- Canonical local SQLite path: if `DB_URL` is unset, the repo defaults to `<SCIENCIAAI_DATA_DIR>/ingestion.db`. This is the canonical local SQLite path convention used by runtime settings and initialization.
- Non-canonical smoke artifacts: the `pages` table appears only in `scripts/smoke_fetch_store_sqlite.py` and should be treated as smoke-only, not as part of the canonical ingestion schema.
- Current implemented phase: canonical ingestion plus the accepted Phase II offline batch AI workflow are implemented. The accepted closed loop now includes deterministic feature generation, a frozen gold set, one frozen TF-IDF plus Logistic Regression baseline, offline evaluation, and additive batch prediction write-back.
- Current boundary after Phase II: clustering, automatic taxonomy expansion, broader analytics, dashboards, APIs, and production serving are not part of the accepted closed loop. Any next step should remain restricted to a tightly controlled reviewer-insight layer over high-confidence `other` and low-confidence predictions.

