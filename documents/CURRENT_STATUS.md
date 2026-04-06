# Current Status

## What This File Is

- quick orientation for the current repo state
- a dated delta log for recent changes
- a navigation layer pointing back to frozen milestone and evidence documents

## What This File Is Not

- not a replacement for historical milestone documents
- not the source of truth for prior milestone conclusions
- not a place to upgrade maturity claims beyond what frozen evidence documents or directly validated current updates support

## Current State At A Glance

- current milestone reflected by the latest documented update: Phase II is closed end to end at batch level as a minimal offline batch AI workflow prototype for single-label pain-point classification
- latest directly validated update: frozen labeling rules, frozen gold eval asset, deterministic feature pipeline, reproducible baseline training, offline evaluation, and additive batch prediction write-back have all been accepted and documented
- bounded next step recorded in the latest update: a tightly controlled reviewer-insight layer restricted to high-confidence `other` and low-confidence predictions, without changing the accepted Phase II workflow or taxonomy

## Update — 2026-04-06

### Objective

Record the current accepted repo state after Phase II workflow closure, while preserving earlier Phase I and feature-layer notes as historical snapshots rather than current next-step guidance.

### What changed

- current repo framing is now anchored to the accepted Phase II closed loop rather than the earlier feature-layer initialization checkpoint
- the accepted current reviewer entry points are `documents/PHASE_II_CONTRACT.md`, `documents/PHASE_II_STATUS.md`, and `documents/Phase_II_Reviewer_Summary.md`
- the verified workflow is now: `reviews -> review_features -> gold_eval -> baseline train/evaluate -> batch predictions written back to SQLite`
- the current status of the repo is no longer "prepare a sentiment baseline"; that was an earlier pre-Phase-II plan and is now superseded

### What remains unchanged

- `schema/reviews_schema.sql` remains the canonical ingestion schema
- `reviews` remains the canonical upstream review table
- `review_id` remains the canonical review key
- `content` remains the canonical stored review text field
- historical Phase I and early feature-layer documents remain preserved as historical evidence snapshots rather than being rewritten

### What is verified now

- Phase II closed a minimal, additive, reviewer-auditable offline batch AI workflow
- the frozen task remains single-label pain-point classification with TF-IDF plus Logistic Regression
- the frozen six-label taxonomy remains unchanged
- batch inference was executed deterministically and predictions were written back additively into SQLite
- the correct interpretation remains narrow: the repo now proves offline batch workflow closure, not production ML readiness

### What is still unverified

- model quality beyond baseline level
- robustness of weak and residual classes, especially `other`
- any online serving, API, dashboard, or production-style operational posture

### Immediate next step

- if work continues beyond accepted Phase II, keep it bounded to a reviewer-insight layer restricted to high-confidence `other` and low-confidence predictions; do not treat clustering, taxonomy expansion, or broader analytics as part of the accepted closed loop

### Risks / open items

- held-out baseline quality is modest and should not be overstated
- predicted labels are skewed toward `pricing_access_limits` in the accepted Slice 6 batch run
- `other` remains weakly supported and should be handled cautiously in any post-Phase-II review extension

### Evidence links

- [PHASE_II_CONTRACT.md](PHASE_II_CONTRACT.md)
- [PHASE_II_STATUS.md](PHASE_II_STATUS.md)
- [Phase_II_Reviewer_Summary.md](Phase_II_Reviewer_Summary.md)
- [PHASE_II_LABELING_RULES.md](PHASE_II_LABELING_RULES.md)
- [PHASE_II_SLICE_2_GOLD_EVAL_NOTE.md](PHASE_II_SLICE_2_GOLD_EVAL_NOTE.md)

## Update — 2026-04-05

### Objective

Record the initial feature-layer setup and small-scope validation work as an additive extension on top of the ingestion foundation, without changing canonical ingestion/storage behavior.

### What changed

- canonicality alignment was completed for the current repo structure
- the additive feature storage schema was created in `schema/feature_schema_extension_v1.sql`
- the feature-generation contract was documented in `documents/feature_contract.md`
- a minimal first-pass feature pipeline was added in `scripts/run_feature_pipeline_v1.py`
- the additive feature schema was applied to the real local SQLite database used by current repo settings
- one controlled real run was completed for `com.openai.chatgpt` with `limit = 20`
- that run created `feature_run_id = 221f7b8447c9` and inserted 20 rows into `review_features`

### What remains unchanged

- `schema/reviews_schema.sql` remains the canonical ingestion schema
- `reviews` remains the canonical upstream review table
- `review_id` remains the canonical review key
- `content` remains the canonical stored review text field
- the historical Phase I ingestion conclusions remain historical evidence snapshots and are not replaced by this update

### What is verified now

- the additive feature schema can exist alongside the canonical ingestion schema in the real local SQLite database
- the first-pass feature pipeline can write bounded document-level feature rows to the real local database
- the small real run completed with `feature_runs.status = completed`
- the inserted `review_features` rows were structurally aligned with the first-pass contract, including non-negative count fields and `aspect_count = 0`
- no canonical ingestion rows were modified during the small validation run

### What is still unverified

- sentiment quality is not yet validated; sentiment fields were NULL in the first real run
- keyword extraction is not implemented
- aspect extraction is not implemented
- `review_aspects` was not populated in the first pass
- no feature-quality or scale-readiness claim is supported by this update

### Immediate next step at that time

- controlled sentiment-baseline enablement using a lightweight method that fits current repo constraints

### Risks / open items

- no lightweight sentiment package is currently declared in repo dependencies
- the current feature-layer validation is plumbing validation, not feature-quality validation

### Evidence links

- [PHASE_I_INGESTION_VALIDATION_SUMMARY.md](PHASE_I_INGESTION_VALIDATION_SUMMARY.md)
- [PROJECT_EXECUTIVE_SUMMARY.md](PROJECT_EXECUTIVE_SUMMARY.md)
- [feature_contract.md](feature_contract.md)
- [../schema/feature_schema_extension_v1.sql](../schema/feature_schema_extension_v1.sql)
- [../scripts/run_feature_pipeline_v1.py](../scripts/run_feature_pipeline_v1.py)

## Historical Evidence Snapshots

- [PHASE_I_INGESTION_VALIDATION_SUMMARY.md](PHASE_I_INGESTION_VALIDATION_SUMMARY.md)
- [PROJECT_EXECUTIVE_SUMMARY.md](PROJECT_EXECUTIVE_SUMMARY.md)
- [pilot_sampling_plan.md](pilot_sampling_plan.md)
- [primary_app.md](primary_app.md)
- [../reports/current_chatgpt_20k_assessment/DATASET_ASSESSMENT.md](../reports/current_chatgpt_20k_assessment/DATASET_ASSESSMENT.md)

## Claim-Anchoring Rules

- claims in this file must be either directly validated in the latest dated update, explicitly anchored to a frozen evidence document, or explicitly marked unverified/open
- this file may summarize current state, but it may not replace historical milestone conclusions or introduce unsupported maturity judgments