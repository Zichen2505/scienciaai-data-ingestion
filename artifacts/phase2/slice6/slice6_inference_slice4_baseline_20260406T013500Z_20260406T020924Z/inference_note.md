# Slice 6 Batch Inference Summary

## Scored Review Set

Scored the most-recent eligible reviews from SQLite `reviews` for app_id `com.openai.chatgpt` after excluding all review_ids from the frozen gold set `data/gold_eval/phase_ii_gold_eval_set_v1.csv`.
Selection ordering: `COALESCE(at, '') DESC, review_id ASC`.
Selection limit: `5000`.

## Counts

- Selected and scored reviews: `5000`
- Predictions written: `5000`

## Frozen Artifacts Used

- Baseline run id: `slice4_baseline_20260406T013500Z`
- Model artifact: `C:\Users\26716\Dev\AI\scienciaai-data-ingestion\reports\phase_ii_slice4\slice4_baseline_20260406T013500Z\baseline_logistic_regression.pkl`
- Vectorizer artifact: `C:\Users\26716\Dev\AI\scienciaai-data-ingestion\reports\phase_ii_slice4\slice4_baseline_20260406T013500Z\baseline_tfidf_vectorizer.pkl`

## Predicted Label Distribution

- `performance_reliability`: `450`
- `account_access`: `52`
- `ui_navigation`: `244`
- `pricing_access_limits`: `4177`
- `capability_answer_quality`: `77`
- `other`: `0`

## Operational Notes

- Skipped rows: `0`
- Validation failures: `0`
- Deterministic scope check: `True`

## Phase II Closure

The batch workflow is closed end to end at batch level: frozen baseline artifacts were loaded, deterministic unlabeled scope was scored, and predictions were written back to durable repository-managed outputs and SQLite.
