# Current ChatGPT 20k Dataset Assessment

## What was analyzed

Computed directly from current files:
- raw dataset: `data/checkpoints/com.openai.chatgpt_recent_window_raw_f942add8.jsonl`

Read as saved repo artifacts:
- `reports/raw_to_sqlite_run_summary_2895d451b8c3.json`
- `reports/quantile_sample_summary_165578901.json`
- `documents/PHASE_I_INGESTION_VALIDATION_SUMMARY.md`

## What is directly verified

- total_rows = 20000
- unique_review_ids = 20000
- observed_min_at = 2026-02-23T03:59:11+00:00
- observed_max_at = 2026-03-16T15:50:42+00:00
- observed_span_days = 21.494109
- duplicate_review_id_count = 0
- null_content_count = 0
- empty_content_count = 0
- null_timestamp_count = 0
- malformed_timestamp_count = 0
- rating_distribution = {"1": 1167, "2": 315, "3": 746, "4": 1938, "5": 15834}
- text_length_summary = {"count": 20000, "min": 1, "max": 500, "mean": 28.609, "median": 11.0, "p25": 6.0, "p75": 27.0, "short_text_lt_10_count": 9056}
- timestamp_distribution_summary = {"parseable_timestamp_count": 20000, "observed_min_at": "2026-02-23T03:59:11+00:00", "observed_max_at": "2026-03-16T15:50:42+00:00", "observed_day_count": 22, "daily_review_count_min": 2, "daily_review_count_max": 4410, "daily_review_count_median": 4.0}

## What the current files support

Computed from current files:
- The raw ChatGPT dataset can support direct counts, duplicate checks, null/empty checks, malformed timestamp checks, rating distribution, timestamp span, daily timestamp counts, and text-length summary statistics.

Already present in saved repo artifacts:
- raw-to-SQLite replay summary confirms 20,000 input rows and 0 failed rows in `reports/raw_to_sqlite_run_summary_2895d451b8c3.json`.
- formal 1k pilot summary confirms a 1,000-row within-window pilot artifact in `reports/quantile_sample_summary_165578901.json`.
- Phase I validation summary contains conservative written conclusions in `documents/PHASE_I_INGESTION_VALIDATION_SUMMARY.md`.

Recent-window bounded support:
- status = supported_by_saved_artifact
- value = True
- source_file = documents/PHASE_I_INGESTION_VALIDATION_SUMMARY.md

## What is still missing / not verified

- Multi-year historical coverage is not verified by the current files.
- A strong signal-quality-at-scale claim is not verified by the current files.
- The current files do not provide a richer saved timestamp distribution analysis beyond range and lightweight daily counts.
- The current files do not justify representativeness claims beyond the current observed recent-window dataset.

## Strongest safe conclusion

The current repository contains a 20,000-row recent-window raw artifact with directly computable rating, timestamp-span, text-length, and basic QA metrics, plus saved artifacts for a formal 1k pilot and raw-to-SQLite replay evidence where those files are present. The current files support a recent-window-bounded characterization only where saved repo artifacts say so. They do not support claims of multi-year historical coverage, broad representativeness, or strong signal quality at scale.
