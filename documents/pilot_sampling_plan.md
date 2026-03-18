# Pilot Sampling Plan

## Current validated constraint

The current Google Play access path for `com.openai.chatgpt` is recent-window bounded.
Based on validated runs, the accessible review window currently spans about 21.5 days, not multiple years of stable historical coverage.

## Pilot sampling approach

Because broad historical coverage has not been validated, the pilot sampling design has been narrowed to:

- current accessible recent-review window only
- within-window quantile time sampling
- balanced temporal buckets within the observed window
- no claim of long-term historical representativeness

## Formal pilot configuration

For the current formal pilot:

- app_id: `com.openai.chatgpt`
- input dataset: recent-window raw file
- total raw rows: 20,000
- sampling method: 5 quantile time buckets
- target sample size: 1,000
- target per bucket: 200

## Pilot objective

The objective of this pilot is to validate that the ingestion and sampling workflow is:

- reproducible
- schema-aligned
- dedupe-safe
- artifact-producing
- honest about current source limitations

This pilot does not establish broad historical review coverage.