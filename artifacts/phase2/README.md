# Phase II Artifact Convention

This directory is the reserved location for machine-consumable Phase II workflow artifacts and now contains accepted Slice 6 batch-inference outputs.

Forward-looking convention:

- put machine-oriented intermediate or reusable workflow outputs for later Phase II slices under `artifacts/phase2/`
- keep human-readable review evidence, summaries, and historical slice outputs under `reports/` and `documents/`
- historical Slice 3 and Slice 4 outputs are intentionally left in `reports/` to avoid broad churn during the cleanup slice

This convention is structural only. It does not change any frozen Phase II task, taxonomy, model, evaluation, or ingestion-contract semantics.