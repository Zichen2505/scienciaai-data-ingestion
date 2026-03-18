## Latest validated status

The current Phase I ingestion workflow has now validated the following for the primary app `com.openai.chatgpt`:

- schema, normalize, and SQLite storage are aligned
- duplicate upsert behavior has been validated
- real-fetch smoke runs succeeded
- the current Google Play access path is recent-window bounded
- a formal 1,000-review pilot artifact has been completed using within-window quantile time sampling

## Formal 1k pilot result

Pilot configuration:
- input raw file: `data/checkpoints/com.openai.chatgpt_recent_window_raw_f942add8.jsonl`
- total input rows: 20,000
- buckets: 5
- target per bucket: 200
- total sampled rows: 1,000

Validation results:
- actual bucket counts: [200, 200, 200, 200, 200]
- duplicate review IDs: 0
- null content count: 0
- null at count: 0
- min_at: 2026-02-23T03:59:11+00:00
- max_at: 2026-03-16T15:50:42+00:00

## Interpretation

This validates a reproducible within-window sampling workflow over the currently accessible recent-review window.

It does not validate stable multi-year historical review coverage.