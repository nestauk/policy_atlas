# Screening eval history

Headline rows are copied here by hand after a run worth keeping. The detail
of each run is the folder under `results/runs/`, and the same folder on
`s3://discovery-policy-atlas/eval/results/screening/` once it has been uploaded.

Pilots on a few questions and repeats of the same setting are left out unless they change
how a number should be read.

## How to add a run

1. Run `checks/run_screen.py`. It prints recall, precision, F2 and the dollar
   cost, and writes `eval_results.json` in the run folder.
2. Copy the row that matters into the table below. Say what changed (the model,
   how many replies per document) and anything that affects the reading.

## How to read the table

- **Recall** is the share of human-included documents the screen also kept.
  **Precision** is the share of kept documents that humans included. **F2**
  weights recall twice as heavily as precision.
- **Set** is `mini` (288 documents) or `full` (2,949), both over the same 30
  questions. Do not compare them directly: `mini` is half included documents,
  so its precision reads higher.
- **Questions**: rows before 2026-10-08 13:00 used hand-written questions (v1). Later
  rows say "questions v2" (published titles, `targets.json`) and whether criteria
  were added. Do not compare v1 and v2 rows directly.
- **Failed** is documents with too few parsed replies to decide. They count as
  not kept, so recall is then an undercount caused by the call, not the screen.
- **Cost** is tokens times the published OpenAI rate recorded in the run JSON.
  It does not include a flat subscription.

| Date | Model | Replies | Set | Recall | Precision | F2 | Cost (USD) | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-08 | gpt-5.4-mini | 3 | mini | 0.868 (125/144) | SYNERGY 0.714, all 0.654 | — | 0.92 | **Production baseline.** Recall 3ie 0.84, CSMeD 0.86, SYNERGY 0.90. 0 failed. Precision for SYNERGY (the clean one) and all sources together (see README). Run `20261008_121400-mini-gpt-5.4-mini-r3`. |
| 2026-10-08 | gpt-5.6-luna | 3 | mini | 0.896 (129/144) | SYNERGY 0.738, all 0.683 | — | 0.24 | Same prompt and vote. Recall 3ie 0.88, CSMeD 0.91, SYNERGY 0.90. Includes kept by Luna only 6, by mini only 2 (exact McNemar p = 0.29: no real difference). Run `20261008_121551-mini-gpt-5.6-luna-r3`. |
| 2026-10-08 | gpt-5.4-mini | 3 | mini | 0.840 (121/144) | SYNERGY 0.721, all 0.661 | — | 0.72 | Short system prompt `screen_short_v1` (59% shorter). Recall 3 points lower than the production prompt; 5 includes lost, 1 gained (p = 0.22). Run `20261008_122747-mini-gpt-5.4-mini-r3-screen_short_v1`. |
| 2026-10-08 | gpt-5.6-luna | 3 | mini | 0.861 (124/144) | SYNERGY 0.754, all 0.689 | — | 0.24 | Short system prompt `screen_short_v1`. Recall 3.5 points lower than Luna with the production prompt; 5 includes lost, 0 gained (p = 0.06). No saving: the shorter prompt lost the cache discount. Run `20261008_122924-mini-gpt-5.6-luna-r3-screen_short_v1`. |
| 2026-10-08 | gpt-5.4-mini | 3 | mini | 0.896 (129/144) | SYNERGY 0.676, all 0.620 | — | 0.91 | **Questions v2** (published titles), no criteria. Recall 3ie 0.82, CSMeD 0.95, SYNERGY 0.92. Against v1: 9 includes gained, 5 lost (p = 0.42). Run `20261008_135423-mini-gpt-5.4-mini-r3`. |
| 2026-10-08 | gpt-5.4-mini | 3 | mini | 0.854 (123/144) | SYNERGY 0.854, all 0.695 | — | 0.97 | Questions v2 **with criteria**. Stricter: recall 3ie 0.84, CSMeD 0.91, SYNERGY 0.82; 90 of 144 excludes dropped (65 without criteria). Against no criteria: 3 gained, 9 lost (p = 0.15). Run `20261008_135624-mini-gpt-5.4-mini-r3-criteria`. |
| 2026-10-08 | gpt-5.6-luna | 3 | mini | **0.938 (135/144)** | SYNERGY 0.716, all 0.659 | — | 0.23 | **Questions v2**, no criteria. Best recall so far: 3ie 0.92, CSMeD 0.93, SYNERGY 0.96. Against v1: 7 gained, 1 lost (p = 0.07). Against mini on v2: 10 gained, 4 lost (p = 0.18). Run `20261008_135807-mini-gpt-5.6-luna-r3`. |
| 2026-10-08 | gpt-5.6-luna | 3 | mini | 0.868 (125/144) | SYNERGY 0.909, all 0.714 | — | 0.23 | Questions v2 **with criteria**. Recall 3ie 0.88, CSMeD 0.93, SYNERGY 0.80; 94 of 144 excludes dropped (74 without). Against no criteria: 1 gained, 11 lost (**p = 0.006**). Run `20261008_140217-mini-gpt-5.6-luna-r3-criteria`. |
| 2026-10-08 | gpt-5.4-mini | 3 | mini | 0.917 (132/144) | SYNERGY 0.700, all 0.632 | F1 0.748, F2 0.841 | 0.95 | Prompt `screen_v3`, questions v2, no criteria. Against `screen_v2`: 5 gained, 2 lost (p = 0.45). Run `20261008_141941-mini-gpt-5.4-mini-r3-screen_v3`. |
| 2026-10-08 | gpt-5.4-mini | 3 | mini | 0.847 (122/144) | SYNERGY 0.851, all 0.697 | F1 0.765, F2 0.812 | 1.04 | Prompt `screen_v3`, with criteria. No change against `screen_v2` (4 gained, 5 lost): mini does not apply the new criteria rule. Run `20261008_142139-mini-gpt-5.4-mini-r3-screen_v3-criteria`. |
| 2026-10-08 | gpt-5.6-luna | 3 | mini | **0.965 (139/144)** | SYNERGY 0.671, all 0.641 | F1 0.770, **F2 0.876** | 0.23 | Prompt `screen_v3`, no criteria. Highest recall: 3ie 0.94, CSMeD 0.98, SYNERGY 0.98. Against `screen_v2`: 4 gained, 0 lost (p = 0.13); 8 fewer excludes dropped. Run `20261008_142328-mini-gpt-5.6-luna-r3-screen_v3`. |
| 2026-10-08 | gpt-5.6-luna | 3 | mini | 0.910 (131/144) | SYNERGY 0.863, all 0.701 | **F1 0.792**, F2 0.858 | 0.24 | Prompt `screen_v3`, with criteria. Against `screen_v2` with criteria: 6 gained, 0 lost (**p = 0.03**); 6 fewer excludes dropped. Best F1. Run `20261008_142816-mini-gpt-5.6-luna-r3-screen_v3-criteria`. |
| 2026-10-08 | gpt-5.6-luna | 3 | mini | 0.958 (138/144) | SYNERGY 0.681, all 0.639 | F1 0.767, F2 0.871 | 0.17 | Prompt `screen_v4` (related-population rule), no criteria. Run `20261008_144039-mini-gpt-5.6-luna-r3-screen_v4`. Not the target setting (owner: the product passes criteria). |
| 2026-10-08 | gpt-5.6-luna | 3 | mini | **0.917 (132/144)** | **SYNERGY 0.918**, all 0.698 | **F1 0.793, F2 0.863** | 0.19 | **Prompt `screen_v4`, with criteria: the main target.** Against `screen_v3` with criteria: 1 gained, 0 lost; 5 excludes newly dropped, 6 newly kept. Run `20261008_144452-mini-gpt-5.6-luna-r3-screen_v4-criteria`. |
| 2026-10-08 | gpt-5.6-luna | 3 | **full** | **0.900 (859/954)** | SYNERGY 0.688, all 0.642 | F1 0.749, F2 0.833 | 1.97 | **First `full` run: Luna + `screen_v4` + criteria.** Recall 3ie 0.884, CSMeD 0.964, SYNERGY 0.904; 1,515 of 1,995 excludes dropped; 1,339 of 2,949 kept. Expected one-call recall 0.899. Best non-AI baseline at the same workload, like for like (embeddings, same question and criteria): recall 0.799, F2 0.739; Luna kept 137 includes it missed, it kept 40 Luna missed (p < 0.001). With the question only, embeddings reach 0.811. Run `20261008_145739-full-gpt-5.6-luna-r3-screen_v4-criteria`. |
