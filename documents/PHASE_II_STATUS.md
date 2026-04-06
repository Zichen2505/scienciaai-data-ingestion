# Phase II Status

Reviewer navigation:

- contract: [PHASE_II_CONTRACT.md](PHASE_II_CONTRACT.md)
- reviewer summary: [Phase_II_Reviewer_Summary.md](Phase_II_Reviewer_Summary.md)
- current status bridge: [CURRENT_STATUS.md](CURRENT_STATUS.md)

## Current Frozen State

Current Phase II scope is frozen as a minimal batch AI workflow prototype for single-label pain-point classification.

Frozen task settings:

- task: single-label pain-point classification
- representation: TF-IDF
- baseline model: Logistic Regression
- split strategy: chronological split
- inference mode: batch inference with prediction write-back

Frozen taxonomy:

- `performance_reliability`
- `account_access`
- `ui_navigation`
- `pricing_access_limits`
- `capability_answer_quality`
- `other`

Current milestone:

- Slice 1 accepted and frozen
- Slice 2 accepted and frozen
- Slice 3 accepted and frozen
- Slice 4 accepted and frozen
- Slice 4.5 accepted as minimal structural cleanup
- Slice 5 accepted and frozen
- Slice 6 accepted and frozen
- Slice 7 accepted for documentation and packaging closure
- Phase II workflow is closed end to end at batch level

## Update — 2026-04-05

### Slice 1 completion update

Slice 1 is complete for the current Phase II scope.

An executable labeling rules document now exists in `documents/PHASE_II_LABELING_RULES.md`.

Slice 1 did the minimum work required to make Slice 2 credible:

- positive, negative, and ambiguous boundaries for each label
- a fixed single-label decision rule for multi-pain-point reviews
- a narrow-use policy for `other`
- exclusion rules for reviews that should not enter the Slice 2 gold set
- a 25-sample trial-labeling note and the main confusion pairs observed

Current Slice 1 verdict:

- accepted and frozen as the labeling-policy baseline for downstream slices
- no further taxonomy expansion is required before Slice 3

Evidence links:

- [PHASE_II_CONTRACT.md](PHASE_II_CONTRACT.md)
- [PHASE_II_LABELING_RULES.md](PHASE_II_LABELING_RULES.md)

### Slice 2 completion update

Slice 2 is complete for the current Phase II scope.

A frozen gold evaluation asset now exists at `data/gold_eval/phase_ii_gold_eval_set_v1.csv`.

Gold-set construction remained single-label only. No multi-label annotation was introduced.

Slice 2 did the minimum work required to support later training and evaluation:

- `performance_reliability`: 31
- `account_access`: 25
- `ui_navigation`: 25
- `pricing_access_limits`: 31
- `capability_answer_quality`: 30
- `other`: 8

Total labeled rows: 150.

Sampling and validation notes are recorded in `documents/PHASE_II_SLICE_2_GOLD_EVAL_NOTE.md`.

Current Slice 2 verdict:

- accepted and frozen for downstream offline evaluation use
- taxonomy was applied without modification and remained single-label only
- ready to advance to Slice 3 feature-pipeline hardening

Evidence links:

- [PHASE_II_LABELING_RULES.md](PHASE_II_LABELING_RULES.md)
- [PHASE_II_SLICE_2_GOLD_EVAL_NOTE.md](PHASE_II_SLICE_2_GOLD_EVAL_NOTE.md)
- [../data/gold_eval/phase_ii_gold_eval_set_v1.csv](../data/gold_eval/phase_ii_gold_eval_set_v1.csv)

### Slice 3 completion update

Slice 3 is complete for the current Phase II scope.

The feature pipeline has been hardened with a versioned successor script:

- `scripts/phase2/run_feature_pipeline_v2.py`

The hardened path keeps canonical constraints unchanged:

- upstream `reviews` remains read-only
- no canonical ingestion schema changes were introduced
- structured feature outputs still write to `review_features`

What was hardened in Slice 3:

- deterministic bounded selection order for reproducible batch runs (`coalesce(at, '') desc, review_id asc`)
- stable text-preparation path for TF-IDF-ready modeling inputs
- reusable exported modeling-input artifact (CSV) for later training and batch inference reuse
- run-summary artifact with input scope, feature run id, output artifacts, row counts, edge-case counts, stable hashes, and read-only snapshot checks

Evidence artifacts from executed bounded runs:

- `reports/phase_ii_slice3/feature_pipeline_v2_730978fe4d01_20260406T011920Z_modeling_input.csv`
- `reports/phase_ii_slice3/feature_pipeline_v2_730978fe4d01_20260406T011920Z_run_summary.json`
- `reports/phase_ii_slice3/feature_pipeline_v2_f74cac5ec367_20260406T011924Z_modeling_input.csv`
- `reports/phase_ii_slice3/feature_pipeline_v2_f74cac5ec367_20260406T011924Z_run_summary.json`
- `reports/phase_ii_slice3/slice3_repeatability_check_20260406T012000Z.json`

Bounded-run validation summary:

- input scope: `app_id=com.openai.chatgpt`, `limit=120`
- feature run ids: `730978fe4d01`, `f74cac5ec367`
- input rows selected per run: 120
- output rows written to `review_features` per run: 120
- repeatability check: stable modeling-input hash matched across runs
- read-only check: review snapshot before/after each run unchanged

Edge-case behavior is now explicit and consistent:

- NULL text -> empty prepared text, zero counts, empty flag set
- empty text -> empty prepared text, zero counts, empty flag set
- short text -> deterministic short-text quality flag based on threshold
- very long text -> preserved in prepared text (no truncation), deterministic counts

Current Slice 3 verdict:

- accepted for frozen TF-IDF-only Phase II path
- no second representation path introduced
- no second model branch introduced
- ready to evaluate Slice 4 baseline-training entry

What remains unvalidated for later slices:

- chronological split implementation in training/evaluation scripts (Slice 4/5)
- end-to-end model training artifact generation (Slice 4)
- batch inference write-back flow (Slice 6)

### Slice 4 completion update

Slice 4 is complete for the current Phase II scope.

One reproducible baseline training path now exists for the frozen task contract:

- training script: `scripts/phase2/train_baseline_model.py`
- representation used: TF-IDF only
- model used: Logistic Regression only
- split strategy used: chronological split only

Training inputs were kept inside the frozen Phase II path:

- frozen gold labels: `data/gold_eval/phase_ii_gold_eval_set_v1.csv`
- hardened Slice 3 modeling input: `reports/phase_ii_slice3/feature_pipeline_v2_474c66fcfef2_20260406T013120Z_modeling_input.csv`
- Slice 3 export summary for the training input: `reports/phase_ii_slice3/feature_pipeline_v2_474c66fcfef2_20260406T013120Z_run_summary.json`

Chronological split implementation:

- join frozen gold labels to Slice 3 modeling input on `review_id`
- sort joined labeled rows by `review_at asc`, then `review_id asc`
- take the oldest 120 labeled rows as train
- reserve the chronologically newest 30 labeled rows as test

Executed Slice 4 baseline training artifacts:

- run id: `slice4_baseline_20260406T013500Z`
- model artifact: `reports/phase_ii_slice4/slice4_baseline_20260406T013500Z/baseline_logistic_regression.pkl`
- TF-IDF artifact: `reports/phase_ii_slice4/slice4_baseline_20260406T013500Z/baseline_tfidf_vectorizer.pkl`
- training config: `reports/phase_ii_slice4/slice4_baseline_20260406T013500Z/training_config.json`
- training summary: `reports/phase_ii_slice4/slice4_baseline_20260406T013500Z/training_summary.json`

Training run summary:

- joined labeled rows: 150
- train rows: 120
- test rows: 30
- train window: `2026-02-23T06:48:45Z` to `2026-02-27T13:27:12Z`
- test window: `2026-02-27T15:06:28Z` to `2026-03-16T10:19:59Z`

Class counts by split:

- train: `performance_reliability=23`, `account_access=22`, `ui_navigation=21`, `pricing_access_limits=26`, `capability_answer_quality=21`, `other=7`
- test: `performance_reliability=8`, `account_access=3`, `ui_navigation=4`, `pricing_access_limits=5`, `capability_answer_quality=9`, `other=1`

Validation outcome for Slice 4:

- one end-to-end baseline training run completed successfully
- chronological split was genuinely enforced and not replaced by random splitting
- only TF-IDF plus one Logistic Regression classifier was used
- frozen taxonomy remained unchanged and was validated before training
- saved model, vectorizer, config, and summary artifacts are sufficient to rerun the training path and reuse the baseline offline later
- no canonical ingestion contracts were modified

Current Slice 4 verdict:

- accepted for frozen baseline-training scope
- ready to enter Slice 5 offline evaluation

What remains unvalidated for later slices:

- Slice 5 evaluation metrics and error analysis have not yet been produced
- Slice 6 batch inference and prediction write-back have not yet been executed

### Slice 4.5 structural cleanup update

Slice 4.5 is complete as a minimal repo-structure cleanup for reviewer orientation.

Minimal structural changes introduced:

- active Phase II scripts are now grouped under `scripts/phase2/`
- forward-looking machine-consumable Phase II artifacts now have a reserved convention at `artifacts/phase2/`
- historical Slice 3 and Slice 4 evidence remains in `reports/` to avoid churn and preserve established review paths
- README now includes a short Phase II execution map for contract, status, labeling rules, gold asset, active scripts, and artifact/report locations

Files moved in this cleanup:

- `scripts/run_feature_pipeline_v2.py` -> `scripts/phase2/run_feature_pipeline_v2.py`
- `scripts/train_baseline_model.py` -> `scripts/phase2/train_baseline_model.py`

Semantics unchanged by this cleanup:

- no Phase II task, taxonomy, gold asset, model path, or evaluation semantics changed
- no canonical ingestion behavior or contract changed
- no historical Phase I evidence structure was rewritten
- no new representation path, model path, dashboard, API, or service layer was introduced

Reviewer note:

- existing historical report artifacts keep their original output locations and may still record the pre-cleanup script path from the run that produced them; the canonical script entry path going forward is now under `scripts/phase2/`

### Slice 5 offline evaluation update

Slice 5 is complete for the current Phase II scope.

One reproducible offline evaluation path now exists for the frozen Slice 4 baseline:

- evaluation script: `scripts/phase2/evaluate_baseline_model.py`
- evaluated baseline: `reports/phase_ii_slice4/slice4_baseline_20260406T013500Z`
- split reconstruction source of truth: frozen Slice 4 `training_config.json` and `training_summary.json`

Executed Slice 5 evaluation artifacts:

- run id: `slice5_eval_slice4_baseline_20260406T013500Z_20260406T020150Z`
- artifact folder: `reports/phase_ii_slice5/slice5_eval_slice4_baseline_20260406T013500Z_20260406T020150Z`
- metrics summary: `reports/phase_ii_slice5/slice5_eval_slice4_baseline_20260406T013500Z_20260406T020150Z/evaluation_summary.json`
- held-out predictions: `reports/phase_ii_slice5/slice5_eval_slice4_baseline_20260406T013500Z_20260406T020150Z/test_predictions.csv`
- misclassified reviews: `reports/phase_ii_slice5/slice5_eval_slice4_baseline_20260406T013500Z_20260406T020150Z/misclassified_reviews.csv`
- reviewer note: `reports/phase_ii_slice5/slice5_eval_slice4_baseline_20260406T013500Z_20260406T020150Z/evaluation_note.md`

Deterministic held-out split verification:

- joined labeled rows reconstructed: 150
- train rows: 120
- test rows: 30
- reconstructed test window matched frozen Slice 4 boundary: `2026-02-27T15:06:28Z` to `2026-03-16T10:19:59Z`
- reconstructed split row counts, boundary review IDs, and per-class train/test counts matched the frozen Slice 4 summary

Headline held-out metrics:

- accuracy: 0.5667
- macro precision: 0.5623
- macro recall: 0.5417
- macro F1: 0.4980
- weighted precision: 0.6979
- weighted recall: 0.5667
- weighted F1: 0.5595

Per-class highlights:

- stronger labels on this test slice: `performance_reliability` F1=0.6667, `account_access` F1=0.6667, `ui_navigation` F1=0.6667
- weaker labels on this test slice: `capability_answer_quality` F1=0.4615, `pricing_access_limits` precision=0.3571 despite recall=1.0000, `other` F1=0.0000 on support=1

Main confusion patterns:

- `capability_answer_quality` -> `pricing_access_limits`: 6 cases
- `performance_reliability` -> `ui_navigation`: 2 cases
- single-case spillover also appeared for `account_access` -> `capability_answer_quality`, `performance_reliability` -> `account_access`, and `other` -> `pricing_access_limits`
- predicted-label distribution did not collapse into one class, but `pricing_access_limits` was over-selected relative to its true support (14 predictions vs 5 gold rows)
- the model never predicted `other` on the held-out set

Slice 5 decision note:

- the frozen baseline is measurable and inspectable enough to support a reviewer decision
- no blocking inconsistency was found between the saved Slice 4 artifacts and the evaluation reconstruction logic
- no task semantics, taxonomy, representation path, split policy, or model family were changed
- recommendation: pass Slice 5 and allow Slice 6 batch inference to proceed, with manual caution around `capability_answer_quality` vs `pricing_access_limits` confusions and low-support `other` behavior

Current Slice 5 verdict:

- accepted for frozen offline-evaluation scope
- baseline is credible enough to continue to Slice 6 batch inference

What remains for later slices:

- Slice 6 batch inference execution and prediction write-back remain unvalidated

### Slice 6 batch inference and prediction write-back update

Slice 6 is complete for the current Phase II scope.

One deterministic batch inference path now exists and has been executed end to end:

- script: `scripts/phase2/run_batch_inference.py`
- frozen baseline source: `reports/phase_ii_slice4/slice4_baseline_20260406T013500Z`
- frozen model artifact loaded: `baseline_logistic_regression.pkl`
- frozen vectorizer artifact loaded: `baseline_tfidf_vectorizer.pkl`

Inference scope used for this accepted run:

- app scope: `app_id=com.openai.chatgpt`
- exclusion rule: exclude all `review_id` values present in `data/gold_eval/phase_ii_gold_eval_set_v1.csv`
- deterministic ordering: `COALESCE(at, '') DESC, review_id ASC`
- bounded limit: 5000 rows

Executed Slice 6 artifacts:

- run id: `slice6_inference_slice4_baseline_20260406T013500Z_20260406T020924Z`
- artifact directory: `artifacts/phase2/slice6/slice6_inference_slice4_baseline_20260406T013500Z_20260406T020924Z`
- predictions CSV: `artifacts/phase2/slice6/slice6_inference_slice4_baseline_20260406T013500Z_20260406T020924Z/predictions.csv`
- run summary JSON: `artifacts/phase2/slice6/slice6_inference_slice4_baseline_20260406T013500Z_20260406T020924Z/inference_summary.json`
- reviewer note: `artifacts/phase2/slice6/slice6_inference_slice4_baseline_20260406T013500Z_20260406T020924Z/inference_note.md`

SQLite write-back (additive, non-destructive):

- run metadata table: `phase2_inference_runs`
- predictions table: `phase2_review_predictions`
- rows inserted for this run: 5000
- no overwrite of prior runs; rows are keyed by `(inference_run_id, review_id)`

Run-level validation outcome:

- model and vectorizer loaded from frozen Slice 4 artifacts; no retraining performed
- selected rows: 5000; predictions generated: 5000
- exactly one prediction per selected review_id
- predicted labels constrained to the frozen six-label taxonomy
- prediction artifact fields include: `review_id`, `review_at`, `prepared_text`, `predicted_label`, `inference_run_id`, `run_created_at` (plus optional probabilities)
- run summary records model artifacts, selection scope, counts, label distribution, and output targets

Predicted label distribution for this run:

- `performance_reliability`: 450
- `account_access`: 52
- `ui_navigation`: 244
- `pricing_access_limits`: 4177
- `capability_answer_quality`: 77
- `other`: 0

Current Slice 6 verdict:

- accepted for frozen batch-inference scope
- Phase II workflow is now closed end to end at batch level
- no task semantics, taxonomy, representation path, model family, labeling policy, or split policy were changed

### Slice 7 documentation and packaging update

Slice 7 is complete for the current Phase II scope.

The required reviewer-facing packaging surface now exists and is aligned to the accepted frozen Phase II workflow.

Delivered documentation surface:

- updated Phase II status document: `documents/PHASE_II_STATUS.md`
- task definition and labeling rules: `documents/PHASE_II_LABELING_RULES.md`
- baseline evaluation and workflow summary surfaces: `documents/Phase_II_Reviewer_Summary.md` and the accepted Slice 5 section in this status file
- limitations and bounded next-step framing: `documents/CURRENT_STATUS.md`, `documents/Phase_II_Reviewer_Summary.md`, and `documents/PROJECT_EXECUTIVE_SUMMARY.md`
- front-door execution map preserving historical context: `README.md`

What Slice 7 validated:

- a stakeholder can identify what was built: frozen labeling rules, gold eval asset, deterministic feature generation, one baseline training path, one offline evaluation path, and one batch inference write-back path
- a stakeholder can identify what was validated: closed end-to-end offline batch workflow with additive SQLite prediction write-back
- a stakeholder can identify what remains unvalidated: model quality beyond baseline level, robustness of weak classes, and any production-style serving or operational posture
- a stakeholder can identify the current milestone: Phase II closed as a constrained offline batch AI workflow prototype
- a stakeholder can identify the bounded next step: reviewer-insight analysis restricted to high-confidence `other` and low-confidence predictions only

Preservation-safe packaging outcome:

- historical Phase I evidence remains preserved and visible
- new Phase II framing is additive and does not replace canonical ingestion conclusions
- the repo front door now points reviewers toward current accepted AI workflow documents without erasing earlier ingestion milestones

Current Slice 7 verdict:

- accepted for documentation and packaging closure
- Phase II now has an explicit reviewer-facing closure path from contract through status, evaluation, and bounded next-step framing
- no new task scope, representation path, model branch, taxonomy expansion, dashboard, API, or production claim was introduced
