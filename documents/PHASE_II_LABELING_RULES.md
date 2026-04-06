# Phase II Labeling Rules

## Purpose

This document defines the frozen labeling rules for Phase II single-label pain-point classification.

The immediate goal is to support Slice 2 gold evaluation set construction with a rule set that another annotator can apply independently, without oral clarification from the author.

This document is not a model spec, not a data sampling spec, and not a sentiment annotation guide.

## Task Definition

Annotate each eligible review with exactly one primary user-perceived complaint label:

- `performance_reliability`
- `account_access`
- `ui_navigation`
- `pricing_access_limits`
- `capability_answer_quality`
- `other`

If a review does not contain a valid product pain point for this task, exclude it from the Slice 2 gold set instead of forcing one of the six labels.

The task is pain-point classification only. It is not:

- sentiment classification
- multi-label classification
- product feature inventorying
- political or moral stance coding

## Annotation Unit

The annotation unit is one review.

Use the review text itself as the primary evidence. Do not infer a label from star rating alone.

## Eligibility Gate For Slice 2

Before assigning a label, decide whether the review is eligible for the Slice 2 gold set.

Exclude the review if any of the following is true:

- It is praise-only or mostly positive with no concrete complaint.
- It is neutral commentary with no clear product pain point.
- It is too short, too vague, or too noisy to support a stable label.
- It is mainly political, ideological, moral, or boycott commentary about the company rather than the product experience.
- It is pure emotion, insult, or competitor preference with no identifiable complaint.
- It is so mixed or unclear that the primary complaint cannot be determined reproducibly.

Examples that should usually be excluded from Slice 2:

- "bad"
- emoji-only or abuse-only reviews
- "install another app" with no product reason
- political boycott commentary with no concrete product complaint

## Single-Label Decision Procedure

For each eligible review, apply the following process:

1. Identify the user's primary complaint, not every complaint mentioned.
2. Prefer the most concrete and operationally verifiable complaint over a more emotional or generic complaint.
3. If multiple complaints appear, use the decision priority below.
4. Use `other` only if the review is clearly a product complaint but does not fit the first five labels.

Decision priority for multi-pain-point reviews:

1. `account_access`
2. `pricing_access_limits`
3. `performance_reliability`
4. `ui_navigation`
5. `capability_answer_quality`
6. `other`

This priority is intentional. It favors account state and access constraints first, then hard product failures, then interaction-flow problems, then output-quality complaints.

## Label Definitions

### `performance_reliability`

Definition:
The core complaint is that the app or a feature does not work reliably or does not complete as expected because of a technical failure.

Use this label when:

- the app is slow, buggy, frozen, or crashing
- a conversation fails to load
- chat content disappears or is not saved correctly
- a feature fails to execute
- the app is stuck on a loading state
- upload, send, or sync behavior fails as a product reliability issue

Do not use this label when:

- the feature runs, but the answer quality is poor
- the complaint is mainly about paywalls, quotas, or gated access
- the complaint is mainly about account status
- the complaint is mainly about confusing navigation rather than failure

Ambiguous boundary guidance:

- If the user says a chat is gone or will not load, use `performance_reliability` unless the complaint is clearly about not being able to find an existing chat in the interface.
- If the user says file or image handling failed, use `performance_reliability` if the upload or action itself failed. Use `capability_answer_quality` if the upload succeeded but the model mishandled the content.

Positive examples:

- Reopening the app deletes part of the chat history.
- The conversation does not load and the app feels buggy and slow.
- The app is stuck on the loading screen.

Negative examples:

- The answer is wrong or low quality.
- The app keeps hitting message limits.
- The model-switch prompt ruins the flow, but the app still works.

### `account_access`

Definition:
The core complaint is that the user cannot access, authenticate, maintain, or manage their account state.

Use this label when:

- the user cannot log in or sign in
- the account is flagged, banned, blocked, or otherwise disabled
- the app becomes unusable because of account state
- the user cannot delete or manage the account as expected

Do not use this label when:

- the complaint is mainly about subscription value or quotas
- the complaint is mainly about model or feature limits
- the complaint is about device compatibility without an account-state issue

Ambiguous boundary guidance:

- If the user says "I paid but my account was flagged and now the app does not work," use `account_access` because account state is the main blocker.
- If the user says "I paid but I still hit message limits," use `pricing_access_limits`.

Positive examples:

- The account was flagged for account sharing and the app stopped working.
- The app will not let the user delete the account.

Negative examples:

- The subscription is too expensive.
- The model was removed from the paid plan.

### `ui_navigation`

Definition:
The core complaint is about interface structure, discoverability, interaction flow, or workflow disruption rather than technical failure.

Use this label when:

- the user cannot easily find a feature, setting, or prior chat
- the app interrupts the workflow with unnecessary prompts or switches
- the user complains about confusing layout, needless UI changes, or poor interaction flow
- a feature is present but hard to reach or hard to use because of the interface

Do not use this label when:

- the feature fails technically or does not load
- the complaint is mainly about quotas or gated access
- the complaint is mainly about answer quality

Ambiguous boundary guidance:

- "I cannot find my last chat" is `ui_navigation` if the complaint is discoverability. It is `performance_reliability` if the complaint is that the chat disappeared or failed to load.
- "The app keeps showing a useless model-switch message and ruins the chat flow" is `ui_navigation` unless the review is really about model access limits.

Positive examples:

- A model-switch prompt keeps interrupting the chat flow.
- The user cannot easily find the previous chat.
- Frequent UI changes remove useful controls and make the app harder to use.

Negative examples:

- The app is stuck and will not load.
- The model gives poor answers.

### `pricing_access_limits`

Definition:
The core complaint is about pricing, subscription value, usage caps, access limits, or removal of model or feature access.

Use this label when:

- the user complains about paywalls or premium pricing
- the user hits message limits or quota limits
- the user loses access to a model or feature they expected to have
- the complaint is about subscription value relative to access granted
- the app downgrades available model access after limits are reached

Do not use this label when:

- the main issue is account lockout or account state
- the feature fails technically despite access being available
- the main issue is poor answer quality rather than gated access

Ambiguous boundary guidance:

- If a review says the model is bad and also complains that better capabilities are behind a paywall, use `pricing_access_limits` if access restriction is the more concrete complaint.
- If a paid user cannot use the app because the account is flagged, use `account_access`.

Positive examples:

- The app only allows a small number of messages every few hours.
- Image creation or premium features are limited behind payment.
- Frequently used models were removed from the subscription offering.

Negative examples:

- The app is buggy and loses chats.
- The answer is wrong even though access is available.

### `capability_answer_quality`

Definition:
The core complaint is about the quality, correctness, usefulness, obedience, or capability of the model output.

Use this label when:

- the model gives wrong answers
- the model ignores instructions or changes the user's intended wording
- image or text generation quality is poor
- the user says the model has become worse, dumber, less useful, or less capable
- the model over-blocks, refuses, or misbehaves even though the feature itself runs

Do not use this label when:

- the app fails technically before the task can run
- the complaint is mainly about quotas, paywalls, or access limits
- the complaint is mainly about interface friction

Ambiguous boundary guidance:

- If the review says the model ignored uploaded content, use `capability_answer_quality` if the upload succeeded and the problem is interpretation or output behavior.
- If the review says a safe request was blocked, treat that as `capability_answer_quality` for this taxonomy unless the complaint is clearly about a missing feature gate.

Positive examples:

- The AI changed the user's wording against their instructions.
- The model gives incorrect information.
- Photo generation quality is poor and the model does not follow the request well.

Negative examples:

- The app is slow or the chat disappears.
- The app only allows a small number of messages.

### `other`

Definition:
The review contains a real product pain point, but it does not fit the first five labels cleanly.

Use this label only when all of the following are true:

- the review contains a concrete product complaint
- the complaint is in scope for product experience
- the complaint does not fit the first five labels after applying the decision rules
- the review is still clear enough for stable annotation

Do not use this label for:

- praise-only reviews
- neutral comments
- abuse-only comments
- very short or vague complaints
- political, ideological, or boycott commentary
- competitor comparisons with no concrete product complaint

Ambiguous boundary guidance:

- Device compatibility or installation-eligibility issues may fall into `other` if they are clear product complaints but not account, pricing, reliability, navigation, or answer-quality issues.

Positive examples:

- The app can no longer be installed on a device after a reinstall, and the complaint does not clearly fit another label.

Negative examples:

- "This company has no morals."
- "Use another app."
- "Bad."

## Rules For Weak, Indirect, And Mixed Complaints

### Weak Or Indirect Complaints

If a complaint is too weak to support a stable label, exclude it from Slice 2.

Examples:

- "terrible decision" with no explanation
- "trash"
- "bring back what you took" with no clear product issue

If the review is short but still points to one identifiable product problem, it may still be labeled.

Example:

- "it keeps giving me limits" can still be labeled `pricing_access_limits`

### Multi-Pain-Point Reviews

When a review mentions multiple complaints, assign one label using the decision priority stated above.

Operational rule:

- prefer the complaint that most directly explains why the user could not achieve the intended task
- prefer the more concrete complaint over a broader emotional reaction
- do not try to average across multiple complaints

Examples:

- "The AI is bad and the good features are behind a paywall" -> `pricing_access_limits`
- "My account was flagged and now the paid app does not work" -> `account_access`
- "The app is buggy, slow, and deletes chats" -> `performance_reliability`

## Trial Labeling Note

Date: 2026-04-05

Manual trial labeling was performed on 25 current-dataset reviews from the recent-window ChatGPT app-review corpus.

Summary outcome:

- The six-label system is workable if Slice 2 excludes non-pain-point reviews instead of forcing them into `other`.
- The highest-risk confusion pairs were `performance_reliability` vs `capability_answer_quality`, `performance_reliability` vs `ui_navigation`, and `pricing_access_limits` vs `capability_answer_quality`.
- No new label was required after the trial.
- The main clarification added after the trial was that political boycott commentary, praise-only reviews, and too-vague complaints must be excluded from Slice 2 rather than labeled as `other`.

Stability verdict:

After this trial, only wording clarifications remained. The label semantics and label inventory did not require further expansion.

## Trial Sample Decisions

| Review ID | Decision | Notes |
| --- | --- | --- |
| `f98821c0` | `performance_reliability` | Chat content disappears after reopening the app. |
| `b1879dfd` | `performance_reliability` | Buggy, slow, conversation does not load, chat parts disappear. |
| `07b594db` | `performance_reliability` | App is stuck on the loading screen. |
| `40a402ec` | `account_access` | Account was flagged and the app stopped working. |
| `05dc76b6` | `account_access` | User cannot delete the account. |
| `af978a67` | `ui_navigation` | Useless model-switch prompt disrupts chat flow. |
| `3deacdf9` | `ui_navigation` | UI changes removed controls and hurt workflow. |
| `1a2ce2ef` | `ui_navigation` | User cannot find the last chat. |
| `b81d7ea7` | `pricing_access_limits` | Image creation is limited by access restrictions. |
| `474358f6` | `pricing_access_limits` | Message cap and missing model access are the most concrete complaints. |
| `a43efc64` | `pricing_access_limits` | Repeated usage limits are the main issue. |
| `6eecbbb2` | `pricing_access_limits` | Removed models and poor subscription value. |
| `e616d0d4` | `pricing_access_limits` | Mixed review, but paywall and restricted access are the clearest operational complaint. |
| `66d38b93` | `capability_answer_quality` | Model ignored images and user intent; complaint centers on output behavior. |
| `f4ef1826` | `capability_answer_quality` | Poor photo generation and incorrect information. |
| `e81bf97e` | `capability_answer_quality` | Model changes wording against user request. |
| `dc7ed282` | `capability_answer_quality` | Model cannot perform a simple counting task correctly. |
| `8da59924` | `capability_answer_quality` | Review complains that the model is useless, overly assertive, and does not learn. |
| `3226d505` | `other` | Device compatibility complaint does not fit the first five labels. |
| `c8c7a473` | Exclude | Political and data-sharing commentary, not a product pain point. |
| `dc27f7b5` | Exclude | Political condemnation with no product complaint. |
| `feb039af` | Exclude | Moral commentary only. |
| `fc8d7b9f` | Exclude | Boycott statement with no concrete product issue. |
| `6db1c737` | Exclude | Competitor preference with no identifiable complaint. |
| `9127bf9e` | Exclude | Too vague to recover a stable product complaint. |

## Review Checklist For A Second Annotator

Before finalizing any label, confirm all of the following:

1. The review is eligible for Slice 2 and should not be excluded.
2. The label reflects the primary complaint, not every complaint mentioned.
3. The label follows the priority order if multiple complaints are present.
4. `other` was used only after ruling out the first five labels.
5. The label could be defended to another annotator using only the text of the review.