# PHASE_II_CONTRACT

Reviewer navigation:

- status: [PHASE_II_STATUS.md](PHASE_II_STATUS.md)
- reviewer summary: [Phase_II_Reviewer_Summary.md](Phase_II_Reviewer_Summary.md)
- current status bridge: [CURRENT_STATUS.md](CURRENT_STATUS.md)

## Phase II Overview

The goal of Phase II is **not** to keep expanding the ingestion layer and **not** to build a general analytics platform. The goal is to move the current project from **review collection and storage** to a **minimal but credible batch AI workflow prototype**.

At the end of this phase, the project should clearly demonstrate the following pipeline:

`reviews -> review_features -> gold_eval_set -> baseline_train_eval -> review_predictions`

Phase II must remain tightly scoped.

### In Scope

- One task only: **single-label pain-point classification**
- One representation path only: **TF-IDF**
- One baseline model only: **Logistic Regression**
- Offline evaluation only
- **Chronological split**, not random split
- Batch inference only
- Prediction write-back to persistent storage

### Out of Scope

- Dashboard
- API
- Online serving
- RAG
- Agent workflows
- LLM fine-tuning
- Multi-model benchmarking
- Generic analytics platform expansion
- Sentiment classification as a second task
- Keyword extraction, aspect extraction, or clustering as Phase II completion requirements

The implementation approach should build on the existing project structure:

- `reviews_schema.sql`
- `feature_schema_extension_v1.sql`
- `feature_contract.md`
- `run_feature_pipeline_v1.py`

Phase II should be advanced through **small, sequential slices**, not through open-ended model experimentation.

---

## Target Workflow

Phase II is complete only if the project can credibly demonstrate this additive workflow:

1. Source reviews exist in `reviews`
2. Stable feature generation writes to `review_features`
3. A manually labeled gold evaluation set exists and links back to `reviews.review_id`
4. A baseline model is trained using the frozen task contract
5. Offline evaluation is reported using chronological split
6. Batch inference runs on reviews outside the training set
7. Predictions are written back to a persistent table such as `review_predictions`

This must be presented as an **AI workflow prototype**, not just an ingestion extension.

---

## Slice Plan

### Slice 0: Scope Freeze And Task Contract

#### Objective
Freeze the only Phase II task, label system, input/output boundaries, and non-goals.

#### Deliverables
A Phase II scope document or status update that explicitly states:

- Task: **single-label pain-point classification**
- Labels:
  - `performance_reliability`
  - `account_access`
  - `ui_navigation`
  - `pricing_access_limits`
  - `capability_answer_quality`
  - `other`
- Representation path: **TF-IDF**
- Baseline model: **Logistic Regression**
- Split strategy: **chronological split**
- Inference mode: **batch inference with prediction write-back**

The labels are defined as **primary user-perceived complaint types**, not as a broad inventory of product modules.

This can be added as a dated update to `CURRENT_STATUS.md` or as a dedicated Phase II status document.

#### Stop Condition
The task, labels, model, split strategy, and prediction write-back target are fully frozen.

It must also be explicitly stated that **keyword extraction and aspect extraction are not prerequisites for Phase II completion**.

#### Validation
- Manual review confirms there is no dual-task wording
- Manual review confirms non-goals are explicitly stated
- Manual review confirms the new Phase II framing does not conflict with prior ingestion milestones

---

### Slice 1: Label Taxonomy And Labeling Rules

#### Objective
Turn the classification idea into an executable labeling specification.

#### Deliverables
A labeling rules document under `documents/` that defines:

- Label boundary for each class, including positive, negative, and ambiguous boundaries
- Positive examples
- Negative examples
- Confusing or ambiguous examples
- A fixed single-label decision rule for collapsing multi-pain-point reviews
- Decision priority for the highest-risk confusion areas, especially:
  - `performance_reliability` vs `ui_navigation`
  - `performance_reliability` vs `capability_answer_quality`
  - `ui_navigation` vs `capability_answer_quality`
- When `other` should be used as a narrow residual class
- When `other` must not be used
- Which review types are present in the raw corpus but must be excluded from Slice 2 gold-set sampling rather than labeled as pain points
- How to handle:
  - unclear reviews
  - non-problem reviews
  - multi-label conflict
  - weak or indirect complaints

The labeling rules document must make clear that praise-only reviews, neutral comments, too-short-to-judge comments, and political or ideological boycott commentary are not valid Slice 2 pain-point samples unless they contain a concrete product complaint.

The document must also include a short trial-labeling note covering 20 to 30 samples, the most confusing label pairs observed, and any rule clarifications needed after the trial.

#### Stop Condition
Each label has a clear operational boundary and enough examples that another person could apply the rules independently.

The single-label decision rule, `other` policy, and Slice 2 exclusion rules are explicitly frozen.

After trial labeling, only minor wording clarifications may remain. If label semantics or class boundaries still need repeated revision, Slice 1 is not complete and Slice 2 must not begin.

#### Validation
- Trial labeling on 20 to 30 samples
- Record the most confusing label pairs, such as `ui_navigation` vs `capability_answer_quality`
- Record any review types that should be excluded from Slice 2 gold-set sampling instead of being labeled as `other`
- Confirm the trial did not cause major redefinition of label semantics
- If rules still change repeatedly after trial labeling, do not proceed to larger-scale eval set creation

---

### Slice 2: Gold Eval Set Build

#### Objective
Create a small but credible manually labeled evaluation asset for offline assessment.

#### Deliverables
A frozen gold evaluation set of approximately **150 to 300 reviews**.

Minimum fields:

- `review_id`
- `label`

Optional fields:

- `notes`
- `label_rationale`

The asset must also include sampling notes:

- source app
- time range
- whether sampling is class-balanced or approximately balanced
- link to the labeling rules document from Slice 1

#### Stop Condition
A frozen evaluation set exists and every record can be linked back to `reviews.review_id`.

The class distribution must not leave several classes empty.

#### Validation
- Spot check 20 to 30 rows to confirm `review_id` exists in `reviews`
- Manual review for obvious label contamination
- Produce a class distribution summary to confirm the set is usable for evaluation

---

### Slice 3: Feature Pipeline Hardened For Modeling

#### Objective
Move the current feature pipeline from “plumbing validated” to “stable for baseline training use.”

#### Deliverables
Either extend `run_feature_pipeline_v1.py` or add a versioned script that produces training-ready feature outputs while preserving current safety boundaries:

- upstream remains read-only on `reviews`
- canonical ingestion schema is not modified
- feature outputs continue to write to `review_features`

If TF-IDF is used, the recommended design is to produce reusable modeling inputs or serialized artifacts for training and inference, rather than attempting to store sparse matrices directly in SQLite.

#### Stop Condition
For the same input batch, the pipeline produces repeatable structured outputs.

Behavior for NULL and empty review text must remain consistent with the contract.

Outputs must be sufficient for training and batch inference without requiring ad hoc downstream patching.

#### Validation
- Re-run on a small batch and confirm stable output statistics
- Check expected row-count relationship between input reviews and `review_features`
- Verify stable handling of empty text, short text, and very long text

---

### Slice 4: Baseline Training

#### Objective
Train one interpretable, reproducible, offline-evaluable baseline model.

#### Deliverables
A training script, for example `train_baseline_model`, with fixed assumptions:

- Inputs:
  - `reviews`
  - `review_features`
  - gold eval set or gold-labeled training asset, depending on final split implementation
- Representation:
  - TF-IDF
- Model:
  - Logistic Regression
- Split:
  - chronological split

Training outputs should include:

- model artifact
- training configuration
- training summary

#### Stop Condition
One end-to-end training run completes successfully.

Chronological splitting must be genuinely enforced, not replaced by random splitting.

The model and configuration must be saved for reuse.

#### Validation
- Training logs explicitly state split strategy
- Saved artifacts are sufficient to reproduce the run
- No second-model branch or benchmark expansion is introduced

---

### Slice 5: Offline Evaluation And Error Analysis

#### Objective
Move the project from “model can train” to “evaluation is defensible.”

#### Deliverables
An evaluation script, for example `evaluate_model`, producing at minimum:

- macro F1
- weighted F1
- per-class precision
- per-class recall
- per-class F1
- confusion matrix or confusion hotspot summary
- failure case samples

Also produce a short evaluation summary artifact under `documents/` or `reports/`.

#### Stop Condition
A readable baseline evaluation exists and makes clear which classes are easier or harder to classify.

The evaluation must use the same frozen label taxonomy defined earlier in Phase II.

#### Validation
- Manual review confirms evaluation is not reduced to accuracy only
- Failure samples are real and support genuine error analysis
- Limitations are stated explicitly and model quality is not overstated

---

### Slice 6: Batch Inference And Prediction Write-Back

#### Objective
Move the project from “model experiment” to “workflow prototype.”

#### Deliverables
A batch inference script, for example `run_batch_inference`, and a new persistent table such as `review_predictions`.

Minimum fields for `review_predictions`:

- `review_id`
- predicted label
- model version or run identifier
- prediction timestamp

Optional but recommended:

- prediction confidence or score
- feature run identifier
- inference run identifier

The workflow must be explicit:

`reviews -> review_features -> model -> review_predictions`

#### Stop Condition
The system can run batch inference on reviews not used for training and write predictions back to SQLite.

Predictions must remain linkable to the source review through `review_id`.

#### Validation
- Run a small real inference batch
- Verify row counts, primary key strategy, and joinability
- Confirm no canonical ingestion rows are modified

---

### Slice 7: Documentation And Packaging

#### Objective
Make the project legible both to recruiters and to hiring managers.

#### Deliverables
At minimum:

- updated Phase II status document
- task definition and labeling rules document
- baseline evaluation summary
- limitations and next-step boundary update
- README or front-door status update that explains the AI workflow progression without overwriting historical ingestion milestones

#### Stop Condition
A stakeholder can answer all of the following within a few minutes:

- What has been built?
- What has been validated?
- What has not been validated?
- What is the current milestone?
- What is the next step?

Historical ingestion milestones must remain preserved and visible.

#### Validation
Read the repo from a stakeholder perspective and check whether the current system progression is obvious within three minutes.

Also verify preservation-safe behavior:

- historical conclusions are retained
- new AI workflow status is additive, not replacement
- ingestion work is not erased or diluted

---

## Acceptance Criteria

Phase II is accepted only if **all** of the following are true:

1. The task is frozen as **single-label pain-point classification**
2. A label rules document exists with clear boundaries and examples
3. A manually labeled evaluation set exists and links back to `review_id`
4. The feature pipeline stably writes `review_features` and behaves repeatably
5. Training uses **chronological split**, not random split
6. Exactly **one** defensible baseline model has been trained
7. Offline evaluation includes both aggregate metrics and error analysis
8. Batch inference can score unseen reviews and write results to `review_predictions`
9. Documentation frames the system as an **AI workflow prototype**, not only an ingestion pipeline
10. All new capabilities are additive and do **not** break the canonical ingestion contract in `reviews_schema.sql`

Phase II is **not complete** if any of the following are missing:

- prediction write-back
- manually labeled evaluation set
- chronological split
- workflow closure beyond training only

If the project only shows feature generation and model training, but not evaluation discipline and prediction persistence, Phase II has not been completed.

---

## Implementation Constraints

To prevent scope drift, the following constraints remain active throughout Phase II:

- Do not add a second task
- Do not introduce multi-label classification
- Do not add a second representation path
- Do not add a second baseline model
- Do not expand into dashboard or API work
- Do not modify canonical ingestion contracts
- Do not treat keyword, aspect, or clustering outputs as required for Phase II completion
- Do not convert this phase into a generic experimentation sandbox

The standard for Phase II is not breadth. The standard is **minimal, credible, end-to-end workflow closure**.

---

## Recommended Execution Pattern

Implementation should proceed in small, reviewable slices. Each slice should aim for one bounded code and documentation change set rather than broad parallel experimentation.

The preferred order is:

1. Scope freeze
2. Label rules
3. Gold eval set
4. Feature pipeline hardening
5. Baseline training
6. Offline evaluation
7. Batch inference and prediction write-back
8. Documentation and packaging

This order is intentional. It prevents premature model experimentation before task definition, labeling policy, and evaluation credibility are in place.

---

## Current Phase II Definition

Phase II should be described internally and externally as:

> A minimal but credible batch AI workflow prototype for single-label pain-point classification on app reviews, built on top of an already validated ingestion and storage foundation.

That is the correct frame.

Not:
- a general AI platform
- a full production ML system
- a multi-model benchmark suite
- a sentiment analysis project
- a generic review analytics tool

---

## Next-Step Boundary After Phase II

Anything beyond the following is Phase III or later:

- richer taxonomy refinement
- larger labeled dataset
- stronger models
- calibration improvements
- human review loop
- dashboard or analyst interface
- API or service layer
- online inference
- monitoring and retraining workflow

Those are valid future directions, but they are not required for Phase II acceptance.