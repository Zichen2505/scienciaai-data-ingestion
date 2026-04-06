# Slice 5 Offline Evaluation Summary

Baseline evaluated: `slice4_baseline_20260406T013500Z`
Held-out test rows: `30`

## Headline

The frozen Slice 4 baseline was evaluated on the reconstructed chronological held-out test split without changing task semantics, labels, representation, split policy, or model family.

Headline metrics: accuracy `0.5667`, macro F1 `0.4980`, weighted F1 `0.5595`.

## Label Performance

- Stronger label: `ui_navigation` with F1 `0.6667`, recall `0.7500`, support `4`.
- Stronger label: `account_access` with F1 `0.6667`, recall `0.6667`, support `3`.
- Weaker label: `other` with F1 `0.0000`, recall `0.0000`, support `1`.
- Weaker label: `capability_answer_quality` with F1 `0.4615`, recall `0.3333`, support `9`.
- Weaker label: `pricing_access_limits` with F1 `0.5263`, recall `1.0000`, support `5`.

## Main Confusions

- `capability_answer_quality` was most often predicted as `pricing_access_limits` `6` time(s).
- `performance_reliability` was most often predicted as `ui_navigation` `2` time(s).
- `account_access` was most often predicted as `capability_answer_quality` `1` time(s).
- `other` was most often predicted as `pricing_access_limits` `1` time(s).
- `performance_reliability` was most often predicted as `account_access` `1` time(s).

## Diagnosis

- Predicted-class concentration flag: `False`.
- Minority-label struggle flags: `other`.
- `other` overuse flag: `False`.
- Slice 6 recommendation: `pass`.

## Representative Errors

- `f4ef1826-93d0-4254-a648-6331fba90ac6`: gold=`capability_answer_quality`, predicted=`pricing_access_limits`, text=very bad photo generating reponse like gemini is more good than this very bad very pooor also sometime its donot provide correct info we have to teell it what is right like than why are we using it 🫡🤐
- `66d38b93-1878-4428-9bab-a6dafef7d772`: gold=`capability_answer_quality`, predicted=`pricing_access_limits`, text=This app is extremely frustrating. It didn’t respect my uploaded images, and the AI repeatedly changed or ignored what I wanted. Features feel very limited, and it blocks content even when it should be safe. I don’t reco
- `a491a6a6-36dd-4d1f-b161-e482b74be681`: gold=`capability_answer_quality`, predicted=`pricing_access_limits`, text=It was working really well, especially the coding part — I would rate it 9–10/10. But in the last few days it has become a total mess. The quality dropped massively and now it’s more like 2/10. Very disappointing.
- `07b594db-fef1-43ed-886c-895f73a00cd6`: gold=`performance_reliability`, predicted=`ui_navigation`, text=it's stuk on the loading screen
- `f98821c0-c12c-4dc1-bd4c-2b3e019b89e5`: gold=`performance_reliability`, predicted=`ui_navigation`, text=Why does the app delete my chats from a certain point whenever I reopen it? So, the context is that I had written said text during a time when I had no signal, yet when I came home and had stable wifi, I properly sent it
- `3deacdf9-37b8-4479-8b6b-6887870993f6`: gold=`ui_navigation`, predicted=`pricing_access_limits`, text=I love how every update more of user freedom is taken away. You can't even manually change or see what model you're currently using. Constantly asks me to turn on notifications (why would an AI app need that?) and to thi
- `e18b18aa-a534-4f67-b822-e0b65c651ac6`: gold=`performance_reliability`, predicted=`account_access`, text=been trying for weeks now..chatgpt is not working in my phone... Just keeps loading and turning
- `3226d505-96da-4a86-b84c-e6bcafbf13cd`: gold=`other`, predicted=`pricing_access_limits`, text=I just mistakenly deleted this app on my tablet realised it and want to download it it's telling me it is not compatible with my device any way it's a good app
- `05dc76b6-2d9a-44a6-a878-c5b4ac5da25f`: gold=`account_access`, predicted=`capability_answer_quality`, text=NOW IT WON'T EVEN LET ME DELETE ACCOUNT NOW! Have to update first Old review: It wanted me to be wrong so it said Kash Patel wasn't head of the FBI but Christopher. No more depending on this liar for my truths about heal
- `f09d81e1-6768-4d74-9110-778836db785a`: gold=`performance_reliability`, predicted=`pricing_access_limits`, text=Bugged and it won't let me use the speech to text feature
- `dc7ed282-d998-455f-836f-d161ea3372c1`: gold=`capability_answer_quality`, predicted=`pricing_access_limits`, text=worst app it can't count 1 to 100 atleast ahhh
- `db9f0748-a7aa-48e5-a2d3-ef39b14f8dd7`: gold=`capability_answer_quality`, predicted=`pricing_access_limits`, text=Stupid Ai. Give random information while I ask for spesific. Can't give an accurate data or at least close enough. F Stupid Ai ever

## Follow-Up Ideas

- Audit the weakest confusion pairs against the Slice 1 labeling rules to separate label-boundary noise from genuine model blind spots.
- Expand the frozen gold asset in a later slice with more chronologically recent examples for the weakest labels, especially low-support classes.
- Inspect the highest-confidence wrong predictions to identify missing lexical cues or wording patterns that TF-IDF is not separating well.
- Before large batch inference, add a lightweight manual QA pass on predicted `other` cases and the dominant confusion pairs to estimate operational review cost.
