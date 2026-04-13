# Flagship Final Report

## Current Flagship Scope

This upload presents the current flagship issue-identification and prioritization output for one bounded ChatGPT Android Google Play review window. The uploaded material is intentionally minimal: one core flagship logic module, the final top-issues deliverables, and a small set of supporting summary artifacts.

## Current Status

The current flagship has produced a bounded final issue report with ranked issue outputs and supporting stage summaries. This upload preserves the flagship result and enough surrounding context to show what was produced, while leaving heavier internal execution packaging, governance surfaces, and intermediate review artifacts private.

## What The System Can Do

The current flagship can turn a bounded review slice into a ranked issue output that highlights the most important issue patterns in the selected release window. The included final deliverables show issue titles, issue counts, severity-oriented ranking signals, and concise evidence-oriented summaries for the top returned issues.

## Method / Logic Chain

The flagship logic follows a staged path:

1. Issue-bearing reviews are separated from non-issue reviews.
2. Eligible reviews are transformed into a review-to-issue representation surface.
3. Issue-like complaints are grouped into issue clusters.
4. The flagship logic converts those clustered signals into ranked issue objects and final top-issues deliverables.

The uploaded core logic module captures the flagship ranking and issue-object construction layer, while the uploaded summary artifacts show the gated input and representation stages that feed the final result.

## Deliverables Included In This Upload

- `scripts/phase5/flagship_mainline_v2_logic.py`
  Core flagship logic for issue formation, ranking, and final deliverable construction.
- `ref/top_issues.md`
  Human-readable final flagship demo output.
- `ref/top_issues.json`
  Machine-readable final flagship demo output.
- `ref/relevance_gate_summary.json`
  Supporting summary for the issue-bearing routing stage.
- `ref/representation_summary.json`
  Supporting summary for the representation stage.

## Evidence Links List

- Final flagship demo output: `ref/top_issues.md`
- Final flagship demo output: `ref/top_issues.json`
- Relevance-gate summary: `ref/relevance_gate_summary.json`
- Representation summary: `ref/representation_summary.json`
- Core flagship logic: `scripts/phase5/flagship_mainline_v2_logic.py`