# Plan-stage adversarial review: 056-cost-latency

Reviewer: a fresh Opus deep-reasoner standing in for the Codex pass (workspace spend cap).
Read-only. 24 findings: 2 blockers, 14 major, 8 minor. Adjudicated by the lead 2026-10-30.
"Owner" marks an item for the plan gate; "folded" is applied in plan draft 2.

| # | Sev. | Finding (short) | Disposition |
|---|---|---|---|
| 1 | blocker | X5 is infeasible as written: the ledger is in the section task message from the first turn, and there is no separate write turn; overlapping N's judge with N+1's reads changes N+1's ledger unless the ledger moves to a later message (a prompt-shape change not on the re-pin list). | **Owner:** drop X5 from this slice (lead's lean; the gain is seconds per section and the ledger move belongs with the synthesis task), or approve moving the ledger as prompt-bearing work. |
| 2 | blocker | `steering_triggers.py:298-306` compares `quality_score <= 2` per group; an unrated row's None score raises TypeError, and the total starts counting unrated rows. | Folded: the query filters `quality_score IS NOT NULL`; a test asserts the trigger's output is unchanged with unrated rows present; same check for `select.py` (null → missing, as today). |
| 3 | major | No fixed-question run before P1. | Folded: Phase 0 runs the four questions on `bedrock` and NEET on `openai-direct` after N1 lands, with `cost_per_run.py` on each. |
| 4 | major | The steps table breaks the naming rule, misses `option_profile:line`, mis-tiers the fold and place-sentence calls (they run on `longlist_assignment`, fast), lists `longlist_assign_themes` wrongly, leaves agent rows unnamed, ignores the V2 and Claude rows and the `bedrock-claude` route. | Folded: the full table is generated from the inventory by the naming rule (`experiments/steps-table-056.md`) and copied into the plan with today's model per route, tier, effort, exception after the switch; `bedrock-claude` follows `bedrock`; the fast-worker sweep gets that exact table. |
| 5 | major | D2's per-model knob table conflicts with D4's per-step effort; a luna `none` knob would override classify's measured `medium`. | Folded: the per-step effort replaces the model-keyed knob table, which is deleted; contract D2's knob wording is corrected to "per-step effort as D4" (minor contract edit, noted). |
| 6 | major | "Provider default is medium" is unverified; GPT-6 was probed at `none` only. | Folded: Phase 0 live probe (omitted vs explicit `medium` reasoning tokens per model and route; every effort value and request shape the new route file will send), output saved. |
| 7 | major | The no-behaviour-change fixture cannot be captured after step 3 changes the code; the extraction fingerprint embeds the vetter effort constants. | Folded: capture and commit the kwargs fixture on the Phase 0 tree; the resolution test plus one forwarding test per request path meets rubric 14; the fingerprint value is pinned before the constants move. |
| 8 | major | `parallel_tool_calls=True` on the forced turn plus the existing `require_single_tool_call` would fail the run on a second call; `allowed_tools` with one tool was never tested. | Folded: the forced turn keeps the named-function force T5 tested; a second tool call on the forced turn or the repair takes the first `emit_section` / `emit_repairs` and is counted and logged, with a test. |
| 9 | major | X3's `lookup` description is prompt-bearing but marked deep-reasoner. | Folded: lead writes the kinds and description; deep-reasoner the plumbing and test. |
| 10 | major | Re-pins not on the contract's list: `ranking.py`, `theme_grouping.py`, `group_clustering.py` joining `EXTRA_FILES`; per-site caching constants editing pinned files; a conditional repair-template wording change. | Folded: caching modes live in one committed table module keyed by call name; Phase 4 changes no wording. **Owner:** approve the three extra pins at this gate. |
| 11 | major | The cost script is new work (by call name; new buckets; both usage shapes). | Folded: deep-reasoner with the lead's exact spec; done is reproducing the § Goal table on the listed sessions. |
| 12 | major | N1's usage shape unspecified; flat keys may double-net. | Folded: `cache_write_tokens` under `prompt_tokens_details` and `reasoning_tokens` under `completion_tokens_details` (Langfuse maps and nets them); the live check confirms both prices. |
| 13 | major | S5's counts would be free text in an ephemeral tick. | **Owner:** add typed `fetched` and `parsed` count fields to the tick frame under the approved S5 change (lead's lean), or accept note text. |
| 14 | major | D7's reader coverage narrowed; S3's "in `SCORE_LABELS`" cannot hold for a null key. | Folded: every label surface listed with its handling (including `answer_core.py`, `chat_scope.py`, `steering_bundles.py`, `characterise.py`). **Owner:** note the S3 wording deviation (a separate `UNRATED_LABEL`). |
| 15 | major | Phase 0's gate is weaker than the tidy-ups' "make verify is the whole check". | Folded: full `make verify` at the end of Phase 0. |
| 16 | major | N8's byte-identity test depends on a gitignored corpus. | Folded: a small openly licensed fixture corpus is committed (sanitized-fixtures policy) or the existing determinism test is extended; the saved-corpus check stays a local verification line. |
| 17 | minor | Migration heavier than needed: a CHECK passes on NULL, so only `DROP NOT NULL` plus the consistency check are needed. | Folded. |
| 18 | minor | Missing gate items: Europe PMC egress approval; the `components.md` § 9 "micro-call" wording item; the web-api scoping-stage fix exceeds S5. | Folded: "Owner items at this gate" list added; the scoping-stage fix dropped. |
| 19 | minor | XML safety wording imprecise. | Folded: Python 3.12 expat with its amplification limits and no external entity fetching; billion-laughs and external-entity tests; undefined JATS entities handled by a declared fallback. |
| 20 | minor | Cold-reader slips (`traced_parse` location, "S4", "finding 21", file locations). | Folded. |
| 21 | minor | Deferred-log entries belong to step 8. | Folded. |
| 22 | minor | Some measures have no source (vetters and annotator absent at standard depth; X3 count; X5 time; N10 HTML branch). | Folded: sources named; X5 dropped if the owner agrees; N10's HTML branch deferred to the parsing task. |
| 23 | minor | Steps beyond the contract: `longlist_assign_themes` tier; X4 widened; the N8 batch hand-over fix. | Folded: the tier stays as today; X4 = `extract_interventions` on gpt-6-luna and the fold calls on gpt-6.1-terra (their new tier). **Owner:** the batch hand-over fix in N8, conditional scope (lead's lean: in). |
| 24 | minor | Phase 2 measurement precedes its plumbing; "prefix over 1,024" confused with the request threshold. | Folded: the measurement driver builds requests from the product's message builders with a local kwargs override; "off" applies to any call whose whole prompt exceeds 1,024 tokens. |

Owner items at the plan gate: X5 (drop or approve the ledger move); the three extra prompt
pins; typed count fields for S5; the S3 label wording deviation; the N8 batch hand-over
fix; the Europe PMC egress approval (host `www.ebi.ac.uk`, data sent: a PubMed Central id);
the `components.md` § 9 repair wording as an owner spec item for D10.
