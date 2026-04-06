# Feature Contract v1

Historical note: this file preserves the earlier feature-generation prototype contract. It is not the current frozen Phase II definition and should not be read as the accepted current repo scope or next-step plan.

## 1. Purpose

This document defines the **generation contract** for the current feature-engineering prototype.

It answers four questions:

1. What each feature field means
2. What upstream source fields it depends on
3. How it is generated in v1
4. What is required now vs. what is optional/future work

This contract is intentionally lightweight and prototype-oriented.
It is designed to keep implementation aligned with the current project scope:

- use the canonical `reviews` table as upstream source
- generate simple but interpretable text features
- avoid heavy modeling or over-complex pipelines
- support later promotion from prototype outputs to durable workflow artifacts

---

## 2. Canonical Upstream Assumptions

The following are fixed for v1:

- canonical upstream review table: `reviews`
- canonical review key: `reviews.review_id`
- canonical stored review text field: `reviews.content`
- optional auxiliary upstream fields:
  - `reviews.rating`
  - `reviews.at`
  - `reviews.app_id`
  - `reviews.lang`
  - `reviews.country`

Important:
- `cleaned_text` is **not** assumed to already exist in the base schema
- any prepared/cleaned text used during feature generation is an internal derived representation, not a canonical upstream field unless explicitly added later

---

## 3. v1 Scope

## In scope
- basic text statistics
- lightweight sentiment baseline
- keyword extraction
- aspect extraction
- quality flags
- versioned feature runs

## Out of scope
- fine-tuned sentiment models
- LLM-based extraction as a required baseline
- embedding vectors stored in SQLite
- required aspect-level sentiment
- advanced semantic grouping as a required component
- changes to canonical ingestion tables

---

## 4. Run-Level Contract

## Table
`feature_runs`

## Role
Tracks one execution of the feature-engineering pipeline.

## Required fields and generation rules

### `feature_run_id`
- type: TEXT
- required: YES
- generation:
  - unique ID created at pipeline start
  - may be UUID, timestamp-based ID, or another stable unique run identifier
- purpose:
  - versioned storage of feature outputs
  - prevents collisions across repeated runs

### `created_at`
- type: TEXT
- required: YES
- generation:
  - UTC ISO-8601 timestamp at feature run creation time
- purpose:
  - auditability
  - run ordering

### `status`
- type: TEXT
- required: YES
- allowed values:
  - `started`
  - `completed`
  - `failed`
- generation:
  - set `started` at beginning
  - update to `completed` after successful end-to-end write
  - update to `failed` if pipeline aborts after run creation
- purpose:
  - prevents partial or failed runs from being mistaken for valid outputs

### `upstream_run_id`
- type: TEXT
- required: NO
- generation:
  - populate only if the feature job is explicitly tied to a known ingestion run
  - otherwise NULL
- purpose:
  - lineage back to ingestion when available

### `feature_version`
- type: TEXT
- required: YES
- generation:
  - manually defined version string for the feature logic
  - example: `feature_v1`
- purpose:
  - reproducibility
  - comparison across iterations

### `text_prep_version`
- type: TEXT
- required: YES
- generation:
  - manually defined version string for text preprocessing rules
  - example: `prep_v1`
- purpose:
  - separates text-prep changes from downstream feature logic changes

### `extractor_config_json`
- type: TEXT
- required: NO
- generation:
  - JSON snapshot of key extraction settings
  - may include:
    - short-text threshold
    - sentiment method
    - keyword method
    - aspect extraction method
    - stopword settings
- purpose:
  - makes runs interpretable and reproducible

### `notes`
- type: TEXT
- required: NO
- generation:
  - optional operator note
- purpose:
  - lightweight operational context

---

## 5. Prepared Text Contract

Before document-level features are computed, the pipeline may produce an internal **prepared text** representation derived from `reviews.content`.

## Prepared text rules for v1
- input source: `reviews.content`
- use a lightweight deterministic preprocessing routine
- preserve semantic content
- do not over-normalize

## Allowed v1 preprocessing
- trim surrounding whitespace
- collapse repeated internal whitespace
- optional lowercase normalization
- optional basic punctuation normalization
- optional sentence splitting/tokenization support

## Not allowed in v1 unless explicitly documented
- aggressive stemming as a required default
- removing all punctuation blindly if it destroys aspect phrases
- translation
- LLM rewriting/paraphrasing
- any preprocessing that makes the original review difficult to relate back to

Important:
- prepared text is an internal feature-generation artifact
- it is not required to be stored in SQLite in v1

---

## 6. Document-Level Feature Contract

## Table
`review_features`

## Grain
One row per (`feature_run_id`, `review_id`)

---

### `feature_run_id`
- source: pipeline runtime
- required: YES
- rule:
  - must match an existing row in `feature_runs`
- failure behavior:
  - do not insert feature rows without a valid run row

### `review_id`
- source: `reviews.review_id`
- required: YES
- rule:
  - copied directly from canonical review row
- failure behavior:
  - if no review_id exists, no feature row can be created

---

### `char_count`
- source: prepared text derived from `reviews.content`
- required: YES
- definition:
  - number of characters in prepared text
- rule:
  - integer >= 0
- purpose:
  - basic length signal
  - QA / anomaly checks

### `word_count`
- source: prepared text derived from `reviews.content`
- required: YES
- definition:
  - number of whitespace-delimited or tokenizer-defined words/tokens
- v1 rule:
  - use one deterministic method consistently across the run
  - simplest acceptable baseline: whitespace token count after prep
- purpose:
  - interpretable text-length feature
  - supports filtering and QA

### `sentence_count`
- source: prepared text derived from `reviews.content`
- required: YES
- definition:
  - number of sentences in prepared text
- v1 rule:
  - use lightweight deterministic sentence segmentation
  - if no robust sentence splitter is available, use a simple punctuation-based approximation and document it in config
- purpose:
  - captures review complexity beyond raw length

---

### `sentiment_compound`
- source: prepared text derived from `reviews.content`
- required: NO, but strongly expected in v1
- definition:
  - continuous scalar sentiment signal for the whole review
- recommended v1 baseline:
  - a lightweight lexicon/rule-based sentiment method
- required properties:
  - deterministic
  - reproducible
  - easy to explain
- purpose:
  - supports distribution analysis
  - supports comparison with star rating
  - supports thresholding into sentiment labels

### `sentiment_label`
- source: derived from `sentiment_compound`
- required: NO, but strongly expected in v1
- allowed values:
  - `positive`
  - `neutral`
  - `negative`
  - optionally `mixed`
- recommended v1 rule:
  - define fixed thresholds in extractor_config_json
- example threshold policy:
  - compound >= positive_threshold -> `positive`
  - compound <= negative_threshold -> `negative`
  - otherwise -> `neutral`
- optional mixed rule:
  - use only if your chosen sentiment method meaningfully supports it
  - otherwise omit and stay with 3 labels
- purpose:
  - human-readable sentiment grouping

Important:
- do not invent confidence scores in v1
- do not use opaque model outputs without documenting method and thresholds

---

### `keyword_topk_json`
- source: prepared text derived from `reviews.content`
- required: NO, but expected in v1
- definition:
  - JSON array of top extracted keywords or short phrases for the review
- recommended v1 approaches:
  - lightweight keyword extraction
  - noun phrase extraction
  - TF-IDF-style ranking over current batch if done consistently
- required properties:
  - interpretable
  - deterministic within a run
  - short enough for inspection
- recommended output style:
  - JSON array of strings
- example:
  - `["voice feature", "slow update", "crash"]`
- purpose:
  - fast qualitative validation
  - reviewer-friendly interpretability

Rules:
- do not dump the whole token list
- do not include meaningless stopword-heavy phrases
- keep top-k small and readable

---

### `aspect_count`
- source: count of linked rows in `review_aspects` for the same (`feature_run_id`, `review_id`)
- required: YES
- definition:
  - number of extracted aspect records associated with the review
- rule:
  - must equal the count written into `review_aspects` for that review/run
- purpose:
  - coverage check
  - extraction QA

---

### `quality_flag_short_text`
- source: prepared text derived from `reviews.content`
- required: YES
- definition:
  - binary indicator for very short / low-information reviews
- recommended v1 rule:
  - set to 1 if word_count < configured threshold
- threshold:
  - must be explicitly stored in extractor_config_json
- purpose:
  - identify reviews where extracted signals are inherently weak

### `quality_flag_empty_after_prep`
- source: prepared text derived from `reviews.content`
- required: YES
- definition:
  - binary indicator for text that becomes empty after preprocessing
- rule:
  - 1 if prepared text length == 0
  - else 0
- purpose:
  - prevents silent contamination of downstream aggregates

---

## 7. Aspect-Level Contract

## Table
`review_aspects`

## Grain
One row per extracted aspect mention for a given (`feature_run_id`, `review_id`)

---

### `aspect_id`
- source: database-generated surrogate key
- required: YES
- rule:
  - assigned automatically by SQLite
- purpose:
  - stable row identity for aspect-level records

### `feature_run_id`
- source: pipeline runtime
- required: YES
- rule:
  - must match feature run row
- purpose:
  - run lineage

### `review_id`
- source: `reviews.review_id`
- required: YES
- rule:
  - copied directly from canonical review row
- purpose:
  - join back to review

### `aspect_rank`
- source: pipeline-generated within-review ordering
- required: YES
- definition:
  - stable order of extracted aspects for a given review within a run
- rule:
  - must start at 1
  - must be unique within (`feature_run_id`, `review_id`)
- purpose:
  - deterministic review-time inspection
  - stable uniqueness constraint

### `aspect_text`
- source: prepared text derived from `reviews.content`
- required: YES
- definition:
  - surface form of the extracted aspect phrase
- examples:
  - `voice feature`
  - `login issue`
  - `recent update`
- purpose:
  - human-readable extracted phrase

### `aspect_lemma`
- source: normalized version of `aspect_text`
- required: NO, but recommended
- definition:
  - normalized/lemmatized canonical phrase form
- examples:
  - `crash`
  - `update`
  - `voice feature`
- purpose:
  - de-duplication
  - aggregation across variants

### `extraction_method`
- source: pipeline method metadata
- required: YES
- allowed style:
  - short method identifier such as:
    - `noun_chunk`
    - `rule_match`
    - `tfidf_term`
- purpose:
  - provenance
  - method comparison
  - auditability

### `aspect_category`
- source: optional rule-based mapping from extracted phrase to category
- required: NO
- examples:
  - `performance`
  - `pricing`
  - `login`
  - `usability`
- v1 rule:
  - optional
  - only populate if you have a simple documented mapping rule
- purpose:
  - business-facing aggregation

### `is_primary_aspect`
- source: optional pipeline decision
- required: NO
- allowed values:
  - 0
  - 1
- v1 rule:
  - optional
  - only populate if your ranking logic is explicit and deterministic
- purpose:
  - simplified summarization when multiple aspects are present

Important:
- aspect-level sentiment is not required in v1
- do not add guessed polarity fields unless explicitly approved later

---

## 8. Minimum Acceptable v1 Implementation

The following is the minimum acceptable working prototype.

## `feature_runs`
Must populate:
- `feature_run_id`
- `created_at`
- `status`
- `feature_version`
- `text_prep_version`

## `review_features`
Must populate:
- `feature_run_id`
- `review_id`
- `char_count`
- `word_count`
- `sentence_count`
- `aspect_count`
- `quality_flag_short_text`
- `quality_flag_empty_after_prep`

Strongly preferred in v1:
- `sentiment_compound`
- `sentiment_label`
- `keyword_topk_json`

## `review_aspects`
Minimum acceptable:
- may be empty if aspect extraction is not yet implemented in the first execution pass

Preferred v1:
- populate:
  - `feature_run_id`
  - `review_id`
  - `aspect_rank`
  - `aspect_text`
  - `aspect_lemma`
  - `extraction_method`

This means the prototype can launch in two steps if necessary:
1. basic document-level features + sentiment
2. aspect extraction extension

---

## 9. Validation Contract

The feature pipeline must support qualitative validation.

At minimum, the implementation should make it easy to inspect:

- a sample of reviews with their sentiment outputs
- a sample of reviews with extracted keywords
- a sample of reviews with extracted aspects
- the distribution of:
  - word_count
  - sentiment labels
  - aspect_count
  - quality flags

The purpose is not to prove perfect accuracy.
The purpose is to demonstrate that the extracted features are:
- meaningful
- interpretable
- more useful for organization than raw text alone

---

## 10. Failure / Null Handling Rules

### If `reviews.content` is NULL or missing
- do not create a normal feature row unless project-specific policy says otherwise
- if processed, quality failure must be explicit

### If text becomes empty after preprocessing
- set:
  - `char_count = 0`
  - `word_count = 0`
  - `sentence_count = 0`
  - `quality_flag_empty_after_prep = 1`
- sentiment and keyword fields may be NULL
- aspect_count must be 0

### If sentiment method fails for a specific review
- sentiment fields may be NULL
- run should not automatically fail unless failure is systemic
- failure behavior should be documented in notes/logging outside this contract if needed

### If aspect extraction yields no valid aspects
- `aspect_count = 0`
- no rows inserted into `review_aspects` for that review/run

---

## 11. Non-Negotiable v1 Rules

1. Never overwrite or redefine canonical `reviews` data.
2. Always join feature outputs back through `review_id`.
3. Always version feature runs.
4. Do not invent unsupported upstream columns.
5. Do not treat internal prepared text as canonical base schema.
6. Do not add heavy or opaque modeling requirements into v1.
7. Keep methods deterministic and explainable.

---

## 12. Recommended First Implementation Order

1. create `feature_runs` row
2. read source rows from `reviews`
3. build prepared text
4. compute:
   - char_count
   - word_count
   - sentence_count
   - quality flags
5. compute lightweight sentiment
6. compute keywords
7. compute aspects
8. write `review_features`
9. write `review_aspects`
10. update run status to `completed`

If the pipeline aborts after run creation:
- update feature run status to `failed`

---

## 13. Summary

This contract defines a lightweight, versioned, interpretable feature-generation layer on top of the canonical review-ingestion schema.

The key principle is simple:

- upstream truth stays in `reviews`
- downstream engineered signals live in feature tables
- every derived field must have a documented source and deterministic generation rule