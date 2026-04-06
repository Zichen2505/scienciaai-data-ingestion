# Phase II Slice 2 Gold Eval Note

## Asset

- frozen gold eval file: `data/gold_eval/phase_ii_gold_eval_set_v1.csv`
- intended use: downstream offline evaluation only
- frozen taxonomy source: `documents/PHASE_II_LABELING_RULES.md`

## Source Scope

- source app: `com.openai.chatgpt`
- source artifact: `data/checkpoints/com.openai.chatgpt_recent_window_raw_f942add8.jsonl`
- source time range: `2026-02-23T03:59:11Z` to `2026-03-16T15:50:42Z`
- source corpus size: 20,000 reviews in the frozen recent-window artifact

## Sampling Strategy

- manual, label-targeted screening from the frozen recent-window raw corpus
- eligibility gate applied before labeling using the frozen Slice 1 rules
- single-label assignment only; no multi-label annotation was introduced
- multi-pain-point reviews were resolved using the frozen priority order from `documents/PHASE_II_LABELING_RULES.md`
- approximately balanced across the five main complaint classes, with a deliberately smaller `other` bucket because residual-class candidates were materially rarer after exclusions

## Exclusions Applied

The following Slice 1 exclusion types were filtered out instead of being forced into `other`:

- praise-only or mostly positive reviews with no concrete complaint
- neutral-only or commentary-only reviews with no stable pain point
- too-short, too-vague, emoji-only, or otherwise noisy reviews
- political, ideological, moral, or boycott commentary not grounded in a concrete product complaint
- competitor-preference reviews with no identifiable ChatGPT product complaint

Manual screening cataloged 23 clear exclusion examples during sampling:

- 10 political, ideological, moral, or boycott cases
- 5 praise-only cases
- 5 too-vague, emoji-only, or noisy cases
- 3 competitor-preference cases without a concrete product complaint

## Final Size And Distribution

- total labeled rows: 150
- `performance_reliability`: 31
- `account_access`: 25
- `ui_navigation`: 25
- `pricing_access_limits`: 31
- `capability_answer_quality`: 30
- `other`: 8

No label is empty. The set is approximately balanced overall, with `other` intentionally narrower than the five primary classes.

## Validation Summary

- all 150 labeled `review_id` values were validated against the configured runtime SQLite `reviews` table used by current repo settings
- taxonomy used without modification: `performance_reliability`, `account_access`, `ui_navigation`, `pricing_access_limits`, `capability_answer_quality`, `other`
- excluded review types were filtered out rather than relabeled into `other`
- manual contamination pass focused on the highest-risk confusion pairs from Slice 1:
  - `performance_reliability` vs `capability_answer_quality`
  - `performance_reliability` vs `ui_navigation`
  - `pricing_access_limits` vs `capability_answer_quality`
- `other` was reserved for concrete residual complaints such as compatibility, recovery-gap, and platform-coverage issues that did not fit the first five labels cleanly

## Spot Check Against `reviews`

25 review IDs were spot-checked against the configured runtime SQLite `reviews` table and confirmed present:

- `b1879dfd-731e-4296-be54-0e01b2c7c04b`
- `f98821c0-c12c-4dc1-bd4c-2b3e019b89e5`
- `40a402ec-c3c0-4247-bcd8-a34810a2ebfb`
- `b0880095-1808-4318-ab1f-068649a54091`
- `af978a67-83af-4672-add7-0762385beb53`
- `026060ad-c84a-40d4-a15b-78057f0fbb51`
- `6eecbbb2-6f4f-4cb4-9911-8f8d97c3278a`
- `474358f6-a89e-44a3-9436-bf1635b48bc4`
- `66d38b93-1878-4428-9bab-a6dafef7d772`
- `c8ac2e45-6fa8-44c8-96c8-c3232faa58f0`
- `3226d505-96da-4a86-b84c-e6bcafbf13cd`
- `dd0862bf-af51-41c0-ada6-e020033ad584`
- `07b594db-fef1-43ed-886c-895f73a00cd6`
- `f9ecc61e-bec6-4a9b-b691-eb2795905fd2`
- `7a2e9758-3cb1-45ff-bea8-1243d2fa8074`
- `755b7d8b-55b3-429e-9941-82d98974b55a`
- `e81bf97e-f74a-4c90-a116-2c8fb6ecc0f9`
- `d44e4f30-b812-4001-9382-c536bcef494c`
- `173ebd30-1ab5-4cc9-abcc-80765747d000`
- `3e2f3c96-bd36-4f74-be88-b19e2ece600b`
- `f7ccc575-f303-4aba-a34b-6ff462de3b6d`
- `41860da5-24cd-468f-bfd7-142f556698ed`
- `b45a3741-fe45-4bc8-9276-1e515c003fda`
- `94d01f32-5f79-4a77-8a21-1323bfe6276d`
- `cf28737f-59eb-4a4a-a5d7-597c6ceec79d`

## Freeze Statement

This asset is frozen as `phase_ii_gold_eval_set_v1` and is intended for downstream evaluation use in later Phase II slices. It does not change the Slice 1 taxonomy, does not introduce multi-label annotation, and should not be backfilled with excluded review types.