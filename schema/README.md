Schema README — Phase I ingestion

Canonical file: schema/reviews_schema.sql

Overview:
- This file defines the SQLite tables used by the ingestion code:
  - ingestion_runs: run-level metadata
  - apps: app-level metadata (app_id primary key)
  - app_runs: link between runs and apps (for rollback)
  - reviews: canonical review storage (review_id primary key)
  - review_runs: link between runs and reviews (for rollback)
  - raw_samples: raw JSON files stored for auditing
  - failures: recorded failures per run

Reviews table (fields):
- review_id (TEXT): primary key. Use provider id if available, otherwise stable hash.
- app_id (TEXT): app identifier (e.g., com.openai.chatgpt). Foreign key to apps.app_id.
- source (TEXT): data source string, e.g., "google_play".
- user_name (TEXT): review author handle (nullable).
- rating (INTEGER): numeric score from provider (nullable).
- content (TEXT): review text content.
- thumbs_up_count (INTEGER): provider thumbs-up metric.
- at (TEXT): original review timestamp in ISO-8601 UTC (e.g., 2023-01-02T15:04:05Z).
- reply_content (TEXT): developer reply text (nullable).
- replied_at (TEXT): reply timestamp in ISO-8601 UTC (nullable).
- app_version (TEXT): app version string reported with the review.
- lang (TEXT): language code used for the review.
- country (TEXT): country code used for the review.
- content_hash (TEXT): SHA256 hash of stable content fields; used for change detection.
- first_seen_at (TEXT): ingestion timestamp when review first seen.
- last_seen_at (TEXT): ingestion timestamp when review last seen.

Notes:
- Source-of-truth: `schema/reviews_schema.sql`. Update schema here first.
- Mapping: `src/sciencia_ingestion/sources/google_play/normalize.py` must output keys matching the reviews table column names.
- Keep `content_hash` non-null to detect identical content across scrapes.
- For any schema evolution: add new columns in the SQL file and handle `ON CONFLICT` or migration scripts in code.