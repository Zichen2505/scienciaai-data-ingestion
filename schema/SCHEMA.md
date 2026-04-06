# Feature Engineering Schema Extension v1

## 1. Purpose

This document defines the **feature-engineering schema extension** for the current Phase I review-ingestion project.

It is designed to be:

- **compatible** with the current canonical ingestion schema
- **additive**, not a replacement
- **minimal**, focused on the current prototype scope
- **extensible** for later promotion from report/export artifacts to SQLite tables

This schema supports a lightweight end-to-end transformation from raw stored reviews to structured review-level and aspect-level features.

---

## 2. Canonical Compatibility Rules

The following existing repo facts are treated as fixed constraints:

1. `reviews` is the canonical base review table.
2. `review_id` is the canonical review key.
3. `content` is the canonical stored review text field.
4. `cleaned_text` is **not** part of the current canonical base schema.
5. `reviews_schema.sql` remains the schema source-of-truth for the existing ingestion layer.
6. This feature-engineering schema must be treated as an **extension** to the current ingestion foundation.
7. Existing ingestion/run lineage structures must not be broken.

Implication:
- All feature outputs must map back to `reviews.review_id`.
- All text-derived features must be explicitly documented as derived from `reviews.content`.

---

## 3. Current Scope Boundary

This extension is for the current lightweight prototype stage.

### In scope
- basic text statistics
- lightweight review-level sentiment
- keyword extraction
- aspect extraction
- qualitative validation support

### Not yet in scope
- fine-tuned sentiment models
- aspect-level sentiment classification as a required field
- heavy embedding storage
- BERT/LLM-first pipelines
- production orchestration changes to the ingestion system

---

## 4. Design Principle

The feature layer should not overwrite or pollute the canonical review storage layer.

Therefore:

- `reviews` remains the source-of-truth for ingested review records
- derived feature outputs should live in separate structures
- feature extraction must be versioned
- repeated runs must remain distinguishable

---

## 5. Proposed Extension Objects

This extension defines three logical objects:

1. `feature_runs`
2. `review_features`
3. `review_aspects`

An optional read-friendly view may be added later:
4. `review_feature_summary_v1`

---

## 6. Table: `feature_runs`

### Role
Tracks each feature-engineering execution as a distinct run.

This is necessary because feature logic will change over time:
- preprocessing rules may change
- sentiment thresholds may change
- keyword/aspect extraction rules may change

Without a run/version table, feature outputs are not reproducible.

### Grain
One row per feature-engineering run.

### Columns

| column | type | null | description |
|---|---|---:|---|
| `feature_run_id` | TEXT | NO | Primary key for the feature run |
| `created_at` | TEXT | NO | UTC ISO-8601 timestamp for run creation |
| `status` | TEXT | NO | Run status (`started`, `completed`, `failed`) |
| `upstream_run_id` | TEXT | YES | Optional reference to ingestion run that supplied the review set |
| `feature_version` | TEXT | NO | Version label for the feature schema / extraction logic |
| `text_prep_version` | TEXT | NO | Version label for text preprocessing rules |
| `extractor_config_json` | TEXT | YES | JSON config snapshot for the extraction logic |
| `notes` | TEXT | YES | Optional short run note |

### Why each field is necessary

- `feature_run_id`: distinguishes multiple extractions over the same reviews
- `created_at`: supports auditability
- `status`: prevents failed runs from being mistaken for valid outputs
- `upstream_run_id`: preserves lineage back to ingestion when known
- `feature_version`: critical for reproducibility
- `text_prep_version`: separates text cleaning changes from downstream feature changes
- `extractor_config_json`: preserves rule/config context
- `notes`: minimal operational context without forcing schema changes

---

## 7. Table: `review_features`

### Role
Stores **document-level** engineered features.

This is the main `1 review : 1 row` output for the prototype.

### Grain
One row per (`feature_run_id`, `review_id`).

### Primary key
Composite primary key:
- `feature_run_id`
- `review_id`

### Source
Derived from:
- `reviews.review_id`
- `reviews.content`
- optionally `reviews.rating`
- optionally `reviews.at`

### Columns

| column | type | null | description |
|---|---|---:|---|
| `feature_run_id` | TEXT | NO | Feature run identifier |
| `review_id` | TEXT | NO | Review identifier from canonical `reviews` table |
| `char_count` | INTEGER | NO | Character count of prepared review text |
| `word_count` | INTEGER | NO | Word/token count of prepared review text |
| `sentence_count` | INTEGER | NO | Sentence count of prepared review text |
| `sentiment_compound` | REAL | YES | Continuous sentiment score |
| `sentiment_label` | TEXT | YES | Categorical label (`positive`, `neutral`, `negative`, optionally `mixed`) |
| `keyword_topk_json` | TEXT | YES | JSON array of extracted keywords/phrases |
| `aspect_count` | INTEGER | NO | Number of extracted aspects linked in `review_aspects` |
| `quality_flag_short_text` | INTEGER | NO | 0/1 flag for low-information short reviews |
| `quality_flag_empty_after_prep` | INTEGER | NO | 0/1 flag if text becomes empty after preprocessing |

### Why each field is necessary

#### `feature_run_id`
Necessary because the same review may be reprocessed under different logic versions.

#### `review_id`
Necessary because all outputs must join cleanly back to canonical review records.

#### `char_count`
Necessary because John explicitly asked for text-length-type distribution checks earlier in the project. It is also a basic QC signal.

#### `word_count`
Necessary because it is a more interpretable length signal than characters alone, and helps with QA, grouping, and later modeling.

#### `sentence_count`
Necessary because it captures review complexity better than raw length alone. A one-word complaint and a multi-sentence complaint are operationally different.

#### `sentiment_compound`
Necessary because a continuous score is more useful than label-only outputs:
- supports distribution plots
- supports threshold tuning
- supports sanity checks against star ratings

#### `sentiment_label`
Necessary because humans reviewing the output need a readable category, not just a floating-point score.

#### `keyword_topk_json`
Necessary because the prototype must show that extracted features are interpretable and useful. This is one of the most direct “show, don’t tell” outputs.

#### `aspect_count`
Necessary because it measures extraction coverage and helps identify failure modes:
- too many aspects = noisy extraction
- too few aspects = overly sparse extraction

#### `quality_flag_short_text`
Necessary because very short reviews (`good`, `bad`, `ok`) can distort aspect extraction and some validations.

#### `quality_flag_empty_after_prep`
Necessary because preprocessing failures must be explicit rather than silently contaminating summary statistics.

---

## 8. Table: `review_aspects`

### Role
Stores **aspect-level** extraction outputs.

This is the `1 review : N rows` detail layer.

This table is necessary because aspect information should not be trapped inside a single JSON field if we want meaningful aggregation.

### Grain
One row per extracted aspect mention for a given (`feature_run_id`, `review_id`).

### Primary key
Preferred:
- surrogate key `aspect_id`

### Columns

| column | type | null | description |
|---|---|---:|---|
| `aspect_id` | INTEGER | NO | Surrogate primary key |
| `feature_run_id` | TEXT | NO | Feature run identifier |
| `review_id` | TEXT | NO | Canonical review identifier |
| `aspect_rank` | INTEGER | NO | Stable within-review extraction order |
| `aspect_text` | TEXT | NO | Surface-form extracted aspect phrase |
| `aspect_lemma` | TEXT | YES | Normalized/lemmatized aspect form |
| `extraction_method` | TEXT | NO | Method used (`noun_chunk`, `rule_match`, `tfidf_term`, etc.) |
| `aspect_category` | TEXT | YES | Optional mapped business category (`performance`, `pricing`, `login`, etc.) |
| `is_primary_aspect` | INTEGER | YES | Optional 0/1 marker for dominant aspect in the review |

### Why each field is necessary

#### `aspect_id`
Necessary as a stable row identifier for aspect-level records.

#### `feature_run_id`
Necessary because aspect extraction rules may change across runs.

#### `review_id`
Necessary for clean joins to the canonical review entity.

#### `aspect_rank`
Necessary so repeated extraction over the same review has stable ordering for audit/review purposes.

#### `aspect_text`
Necessary because we need the human-readable extracted phrase.

#### `aspect_lemma`
Necessary because without normalization, simple counts become fragmented (`crash`, `crashes`, `crashing`).

#### `extraction_method`
Necessary because provenance matters. A phrase extracted by noun chunks is not the same as a phrase extracted by rule matching.

#### `aspect_category`
Necessary if we want later business-facing summaries, but optional in v1 because the initial prototype may stop at raw extracted phrases.

#### `is_primary_aspect`
Optional but useful for high-level summaries when a review mentions multiple issues.

---

## 9. Optional View: `review_feature_summary_v1`

### Role
Provides a reviewer-friendly flat summary.

This is not the canonical storage layer.
It exists only to make review and demonstration easier.

### Possible fields
- `review_id`
- `app_id`
- `rating`
- `at`
- `content`
- `sentiment_label`
- `sentiment_compound`
- `keyword_topk_json`
- aggregated top aspects

### Why this view is useful
It prevents reviewers from having to join multiple tables manually during inspection.

---

## 10. Persistence Convention for the Current Phase

For the current prototype phase:

- feature outputs **may begin as export/report artifacts**
- but they must follow the same field names and grain defined here
- if later promoted to SQLite tables, the names and grain should remain stable

This keeps current implementation lightweight while preserving a clean promotion path.

---

## 11. Non-Goals / Explicit Exclusions

The following should **not** be added in v1 unless separately approved:

- heavy embedding vectors stored inline in SQLite
- pseudo-confidence scores without calibration
- large numbers of weak surface heuristics
- required aspect-level sentiment classification
- modifications to canonical ingestion tables

---

## 12. Join Contract

### Canonical join path
- `review_features.review_id` -> `reviews.review_id`
- `review_aspects.review_id` -> `reviews.review_id`
- `review_features.feature_run_id` -> `feature_runs.feature_run_id`
- `review_aspects.feature_run_id` -> `feature_runs.feature_run_id`

### Important rule
`review_features` and `review_aspects` are derived layers.
They must not redefine the canonical review entity.

---

## 13. Recommended Minimal v1 Output Set

If implementation time is tight, the minimum acceptable outputs are:

### `feature_runs`
- all fields except `notes` optional

### `review_features`
- `feature_run_id`
- `review_id`
- `char_count`
- `word_count`
- `sentence_count`
- `sentiment_compound`
- `sentiment_label`
- `keyword_topk_json`
- `aspect_count`
- `quality_flag_short_text`
- `quality_flag_empty_after_prep`

### `review_aspects`
- `aspect_id`
- `feature_run_id`
- `review_id`
- `aspect_rank`
- `aspect_text`
- `aspect_lemma`
- `extraction_method`

This is the smallest version that is still structurally serious.

---

## 14. Rationale Summary

This design is chosen because it:

- preserves compatibility with the current ingestion schema
- avoids polluting canonical raw review storage
- supports reproducibility through versioned runs
- supports both document-level and aspect-level analysis
- stays within the lightweight prototype scope
- gives a clean path from exports to durable tables later