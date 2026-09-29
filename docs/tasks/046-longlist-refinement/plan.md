# Plan: 046-longlist-refinement

Items 1–26, rulings R1–R28, amendments AM1–AM21 and PA1–PA21, measures
M1–M9 and every term are defined in [contract.md](contract.md). This plan
cites them and adds nothing to scope. It was written against the as-built
code at `7c5ba2e2`, not against the contract's own claims.

> **Status:** drafted 2026-09-28 · lead; revised the same day for the
> owner's rulings R24–R27 (iteration loops) and the plan review.
> **Plan-stage adversarial review ran 2026-09-28** (fallback lane,
> `deep-reasoner`, read-only; the Codex lane has no budget): 21 findings,
> verdict "material change needed", folded in § Plan-review folds. The lead
> checked P3 and P7 in the code; they hold. The owner ruled PA3 ("Fine") and
> replaced PA9 by R28 (`theme` as a component of its own). **Plan approved
> (before implementation): 2026-09-28 · owner** ("yes, confirmed").
> **ADR [0040](../../adr/0040-options-scoping-longlist-refinement.md)**
> was written at step 4, after plan approval and before any build phase.

Executor marks per AGENTS.md § Agent-side model routing. **Owner ruling
2026-09-04 stands:** judgment-bearing phases go to `deep-reasoner`, not
`codex`; the family flip is at step 7. No phase is marked `codex`. Every
`lead` mark carries its reason. Prompt-bearing work is `lead`.
Taste-bearing frontend work and product copy are `lead` (owner ruling
2026-09-05). Seam semantics are fixed in this plan (P20); a delegate's
brief builds them and does not design them.

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline),
Phase 1 (the revision — schema class), Phase 2 (the runner and the chains)
and Phase 8 (step-6 exit). Phases 3 to 7 close on `make verify-fast` ·
`make prompt-guard` · `make drift-check`, plus `make frontend-verify` in
Phase 7. Phases 3 to 6 are logic in the scoping package with no schema and
no runner contact; Phase 7 is the reader contact and Phase 8 carries the
full gate. **One green commit per phase, and one per loop round that
changes a prompt.** The full gate runs serially.

**The order puts all plumbing before all prompt loops** (R24). Phases 1 and
2 change no prompt behaviour a reader can see. Phase 3 builds the replay.
Phases 4 to 6 are the loops, in pipeline order, so that a later stage is
tuned on the output of a stage that is already stable.

**Spec changes** (contract § Spec changes, AM12) are applied in Phase 8.
The lead puts the wording of each change to the owner and applies only
accepted wording.

## Decisions fixed here (lead seam design)

S1. **The chains** (R13, R18, AM1, AM4, P13). In `runtime/scoping_plan.py`:
`LONGLIST_CHAIN` = `inherit → suggest → acquire → screen_abstract →
classify → appraise → extract_interventions → longlist → constrain →
theme`. `theme` has `spine=False`.
`TARGETED_CHAIN` (the add walk) = `acquire → screen_abstract → classify →
appraise → extract_interventions`. `ACQUIRE_ONLY_CHAIN` = `acquire`.
`run_option_search` writes `acquire_only: true` into the scope's context
when `parent_capability_run_id is not None`. `CapabilitySpec.compose`
becomes `Callable[[Any, str | None, Mapping | None], ComposedChain]`; the
Evidence search's `compose` takes and ignores the third parameter. The
three compose sites (`runner.py:898`, `continuation_state.py:179`,
`api/continuation.py:1540`) pass the scope's context, which each reads
beside the purpose. Scoping walks never park, so the resume sites change
for the signature only. ADR 0040 amends ADR 0039 decision 2: the chain is
recoverable from the purpose and the scope's context.

S2. **The join** (R18). In `runtime/runner.py` the join condition changes
from `step.component == "longlist"` to `step.component ==
"screen_abstract"`. The review confirmed the rest: the parent's acquire
commits before the screen step starts, the join waits for a terminal status
of each child, and the stage-1 load has no scope filter. A child cut off by
the join timeout can still add documents later (PA21): M9 counts documents
with no screen row in the longlist scope.

S3. **Units** (AM5, P8). `_option_search_scopes` adds `where
parent_capability_run_id is null`. `_own_units` reads the union of the
longlist scope and the add-walk scopes, then: (a) compares each record's
extraction fingerprint with the fingerprint of the current plan's tagging
context and reads a mismatch as "not tagged" (tags null in the unit
payload); (b) runs the thinning of S10 over the union, so a document
profiled in two scopes counts once.

S4. **The tagging context** (R3, AM3). `TaggingContext(target_unit,
outcomes, intended_change)` in `interventions_records.py`, built by the
scoping side from the plan with `strip_place` (S6) applied to the target
unit and the intended change. Carrier: an optional `interventions_context`
keyword on `extract_scope`, passed by `_run_extract_interventions` in
`runtime/harness.py` (which reads the plan of the scope's `plan_id` on the
component's connection), threaded to `_run_profile`, to
`_interventions_fingerprint` and to `OpenAIInterventionsBackend`. The
fingerprint gains `context_hash`. IOF and ICF paths do not receive the
keyword.

S5. **The revision** (PA14). One alembic revision on `c7e2a9f4b1d8`: three
nullable text columns on `intervention_profile_record`; check constraints
on `population_tag` and `object_tag`; `outcome_tag` is free text (a plan
outcome's text, or `other`). Downgrade drops them.

S6. **The place strip** (R4, R19, PA11, P17). `strip_place(text,
where_text) -> tuple[str, list[str]]` in
`options_scoping/longlist/where_tried.py`. It removes (a) the plan's Where
text and (b) a place the matcher recognises **only when a preposition leads
it** ("in", "living in", "across", "within", "from"), with that
preposition. It uses the matcher's country and sub-national names, never
its adjective entries, so a nationality stays. Callers:
`compile_longlist_intent`, `longlist_screening_criteria`, constrain's
`_plan_data` (question and intended change), the tagging context.
Requirement texts and the baseline's intent are not stripped. The removed
spans are recorded in the longlist scope's context when the walk opens
(`api/longlist_start.py:207-211`) and in `provenance` of the longlist and
constrain results.

S7. **The screen input** (R15, R19). `longlist_screening_criteria` returns
two criteria: the wide target unit ("… aimed at {target unit}, or at a
wider or adjacent population") and the outcomes. No setting criterion.
`compile_longlist_intent` drops its `Setting:` sentence. Trailing stops are
stripped before composition.

S8. **Discovery** (items 1, 4; R1, R9, R14; AM9; P5, P6).
- Constants `LONGLIST_TARGET_SIZE = 20`, `LONGLIST_HARD_CEILING = 25`.
  `max_new = max(25 - len(seeds), 0)`; `max_labels = max(len(seeds) +
  max_new, len(seeds))`. `provenance.ceiling` records the excess over 25.
- The digest is built by code from the thinned units: folded intervention
  name → record count and counts by role, sorted by count, at most 400
  names.
- Folds. The discovery wire gains `folds: [{seed_label, into_label}]`.
  Code rejects a fold when: the seed's origin is `added_by_you`;
  `user_holds_state(exclusion)` is true for the seed; `into_label` is not a
  label of this discovery's result or of a seed; the seed or the target is
  already folded. A folded seed's label is removed from the labels
  `discover` returns, so no unit is assigned to it. New option rows are
  inserted before the `merged_into_option_id` update. Rejected folds are
  counted in `provenance`.
- The residual pass is a **second `cluster_units` call** made by
  `longlist_scope`, with a new backend instance, over the unclustered units
  only (not the not-an-option ones). It is skipped when what remains under
  the ceiling is 0 or when no unit is unclustered. Its discovery sees the
  digest of those units and the existing option labels as seeds; its
  `max_new` is what remains under the ceiling. Its assignment offers every
  option. Answers of the second call replace the first call's "ungroupable"
  for those units. The exhaustiveness invariant
  (`longlist.py:1368-1374`) is checked once, after the merge.
- The wire loses `is_bundle` and `components`; the package code is
  removed. The clustering engine has no source change.

S9. **Short ids** (item 2, P16). The map is built inside each `assign` call
(the engine runs four at once and sends repair calls with subsets). The
component's `answers` are keyed by the UUID after mapping back. An id the
model returns that is not in the call's map is passed to the engine as an
unknown id, so the engine's repair path works as today.

S10. **Thinning** (item 15; R17; AM14; P7, P15). In `_own_units`, over the
union of S3, in this order: drop `mentioned` records with no features and
no outcome; collapse records of one document with the same folded name
(keep the highest role); keep at most 8 per document, by role (evaluated,
described, recommended, mentioned), then by `created_at`, then by
`record_id`. Counts in `provenance.thinning`. **Title-only documents** are
dropped in the selection-free path before basis resolution and the memo:
no extraction record row is written, the extract summary counts them, and
`longlist_scope` copies that count into `longlist_result.counts.title_only`.

S11. **Outcomes, variants, tried on** (items 6, 23; AM6, AM20; P4).
- A discovered option's outcomes are set **at mint time**, when its members
  are known and before the writes: `design.outcomes_served` and
  `option.outcomes` = the distinct non-`other` outcome tags of its members.
  The discovery wire's `outcomes_served` is removed. When no member has a
  plan outcome, the list is empty and constrain's relevant screen judges
  the option from its design and description.
- `variants` = distinct folded names of members with document counts,
  folded seeds first, at most 8 by count. `tried_on` = the populations of
  `adjacent` members with document counts. Both are in
  `longlist_result.coverage` and are recomputed wherever coverage is
  (`membership_coverage` after a merge; `_search_coverage` for an added
  option).
- The setting code pass (fold labels; move a place to study geography when
  empty) runs in `coverage.py`, on the read side of the record, and counts
  its repairs there. The profile's stored record is not rewritten (P18).

S12. **Typing** (item 7, AM19, P12). `lever_types_v2` beside v1. Batches
run in a thread pool of 4. An invalid or failed typing leaves the option's
columns as they are, version included, and carries forward its runner-up
from the latest earlier result that has one.

S13. **Constrain** (items 5, 10–12; R21; P10). `distinct` leaves the
batches' requirement list. It is one call over the whole list, made before
the batches; its candidates are every option; the existing merge rules
apply to its result. A failed or malformed distinct call gives every option
`cannot_check` on `distinct` and no merge. Its verdicts are stored in
`judgements` under `distinct` as today. The batches run in a thread pool of
4. Every model call is made before the first write, as today.

S13a. **The `theme` component** (item 8; R28). A new package
`options_scoping/theme/` with `theme.py` (`theme_scope`) and the moved
`longlist_theme_prompt.py` (its path changes in `scripts/prompt_hashes.json`;
its text does not). `theme_scope` reads the latest `longlist_result` of the
scope and the options whose state is `included` and that are not merged;
runs the unseeded `cluster_units` call that `longlist_scope` runs today
(`longlist.py:1361-1409`), with the same policy and ceiling; writes
`themes`, `counts.themes`, `counts.no_theme` and the theme provenance into
that `longlist_result` row. `longlist_scope` writes `themes = []` and no
theme counts. `constrain_scope` has no theme code. Registered as component
`theme` (`requires: [evidence_scope_id]`) in `runtime/run_spec.py`,
`runtime/harness.py` and `runtime/task_plan.py`; stage key `theme` in
`api/stage_vocabulary.py`. A `ClusteringFailure` fails the step; the step
is not spine, so the walk ends `degraded` and the verdicts stay. The
replay tool has `theme` as a stage.

S14. **Read models** (additive; P3, P12). `OptionSummaryOut`:
`runner_up_lever_type`, `tried_on`. `OptionOut`: `variants`.
`LonglistOut.counts`: the thinning counts and `title_only`.
`LonglistOut.lever_type_definitions_by_version`. `EvidenceProfileOut`:
`tried_on`. Chat citation facts: `text_basis` (PA3, if accepted), added in
`api/answer_core.py` beside `source_title`. OpenAPI by `make openapi-sync`.

S15. **The replay** (R12, R24; AM11; P1). `evidence/pre-contract-runs/
replay.py` and `clone.py` (gitignored; development tools, not product
code).
- **Clone.** Hand-written rows for one new task per stored task: `task`;
  the approved `plan` row with the stored payload; the baseline's
  `evidence_scope`, `capability_run`, `runs`, `artefact` and
  `synthesis_result` rows (so that `baseline_sections` reads the stored
  baseline); `task_link` rows; one `task_source_snapshot` row per stored
  document, pointing at the shared snapshot (chunks and embeddings belong
  to the snapshot). Each foreign key is listed in the script's header.
- **Stage replay.** Each stage is a function call on the clone, with its
  own `runs` row: `screen` (the whole cloned pool, once, under the new
  input), `classify`, `appraise`, `profile`, `suggest`, `longlist`,
  `constrain`. A stage reads what the stage before it stored. `suggest`
  mints seeds with no search of their own.
- **Planning replay** (PA1). The seven original questions are put to the
  planning prompt through the Task Agent turn function; the script prints
  the target unit, Where, constraints and Your context of each draft.
- **Unchanged check.** Row counts and a hash of the option, membership and
  `longlist_result` rows of each stored task, before and after.
- **Round record.** Each round writes one file: the prompt diff, the
  figures, the read-back.

## The loop (R24–R27)

Each loop is `lead`. Reason: prompt-bearing work and adjudication.

1. Change the prompt. Name the finding that causes the change.
2. Re-pin. Commit on a green `make verify-fast` · `make prompt-guard`.
3. Replay the stage on the **tuning set** (obesity, refugees, caregiving,
   energy).
4. Read the results against the stage's measures. Write the round record.
5. Stop when the measures pass, or after five rounds. Then replay once on
   the **check set** (NEET, heat pumps, cohesion), read it, and report to
   the owner. The owner decides if the stage is good.

A wire-field change that a prompt round needs is made by the lead inline
when it is one field, and by a `deep-reasoner` brief when it is more.

## Open at the plan gate

1. **PA3:** the *abstract only* label on the shared chat path — **ruled**
   (owner: "Fine").
2. **PA9:** replaced by R28 — **ruled** ("Yes, three components").
3. **S1:** the registry's `compose` signature gains one parameter that the
   Evidence search ignores. Lead call.
4. **S15:** the clone is hand-written rows in a development script. Lead
   call; the review showed that no API can make it.

## Phase 0 — Build-open baseline — `lead` (inline)

Reason: a one-command check. Full `make verify`. Commit ADR 0040 (step 4)
before Phase 1.

## Phase 1 — The revision, the place strip and the profile plumbing (items 13–15 part, 26 part; AM3; P2)

**`deep-reasoner`.** Brief (S4, S5, S6, S10 title-only part): the alembic
revision with its round-trip; `strip_place` with its tests (the refugee
target unit; "in the UK"; a text with no place; "Polish migrant workers"
keeps "Polish"; a requirement text is left alone); the where-tried
sub-national table; the three tags on the wire model and the table, with
the **present prompt unchanged** (the tags are optional on the wire and
stored null until Phase 4); `interventions_context` threaded as S4 says;
the fingerprint's `context_hash`; title-only documents dropped and counted.
Tests: the contract's bullets for items 13 and 15 (document rules); IOF and
ICF fingerprints and payloads byte-identical (existing tests, no edit);
null tags read as "not tagged". Done when full `make verify` is green.

Gate: **full `make verify`**. Commit.

## Phase 2 — The walk and the screen input (items 10 part, 18, 22, 23, 26 part; R13, R15, R18, R19; AM1, AM4, AM5, AM17)

**`deep-reasoner`.** Brief (S1, S2, S3, S7, S13a): the three chains; the
`theme` component as a move of the present theme code with its prompt
unchanged, registered and with its stage key; the compose signature; the `acquire_only` flag; the join before `screen_abstract`;
`_option_search_scopes` parentless only; the fingerprint rule of S3; the
two compose functions with the strip. Tests: the contract's bullets for
items 8, 18, 22 and 23; an add walk runs the full targeted chain; a failed
child degrades the walk; the existing steering tests pass with no edit; a
rebuild of a task built before this slice counts no document twice; the
composed text stays under the screen's 2,000-character ceiling. Done when
full `make verify` is green.

Gate: **full `make verify`**. Commit.

## Phase 3 — The replay tool (R24; AM11; PA1)

**`deep-reasoner`.** Brief (S15). Done when: one stored task is cloned; the
screen, classify, appraise and profile stages replay on the clone; the
stored task's rows are unchanged by count and hash; the planning replay
prints seven draft plans. The tool is in the gitignored evidence folder and
is not part of `make verify`.

Then the **baseline read — `lead`.** Reason: adjudication. Clone the seven
tasks. Replay screen, classify, appraise and the profile (present prompt)
once on all seven. Record the pool size and the cost. These are the saved
inputs of the loops.

Gate: `make verify-fast`. Commit (no product code changes in this phase
other than fixes the tool shows to be necessary).

## Phase 4 — Loop: the plan and the profile (items 10 part, 13, 14, 16; R19, R20; AM6, AM8)

4.1 **Planning loop — `lead`.** `task_agent_scoping_v4`: the target unit
holds no place and no setting; a setting stated without a requirement goes
to Your context. Measure: the planning replay on the seven questions shows
no place and no setting in a target unit.

4.2 **Profile loop — `lead`.** `extract_interventions_v2`: the three tags
(AM6 for the outcome tag), the setting rule, the negative examples for the
recommended role. Measures: M5 (setting labels), M9 (share tagged `other`),
the object tag on the heat pump records (check set), the pathway outcomes
on the obesity records.

4.3 **Setting code pass and coverage additions — `deep-reasoner`.** Brief
(S11): the coverage functions and the setting pass, with the contract's
item-14 tests.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`.
Commit. Report to the owner (R25).

## Phase 5 — Loop: suggest and the longlist (items 1–4, 6, 7, 9, 15 unit part, 26 part; R1, R2, R9, R14; AM9, AM14, AM19, AM20)

5.1 **The component — `deep-reasoner`.** Brief (S8–S12): the constants;
the digest; folds with the four guards; the residual pass as a second
`cluster_units` call; short ids; thinning over the union; package code
removed; outcomes at mint time; typing in parallel with the keep-previous
rule; `baseline_sections` passed to discovery and typing. It lands with the
first version of the three prompts from the lead (5.2 round 0), so the wire
and the code agree. Tests: the contract's bullets for items 1, 2, 4, 6, 7,
15 (unit rules) and 26; the clustering engine has no source change.

5.2 **Suggest, discovery, assignment and typing loop — `lead`.**
`longlist_suggest_v2`, `longlist_cluster_v2`, `lever_typing_v2`,
`lever_types_v2`; the option design prompt only on a finding. Measures:
M1, M2, M3, M9 (flag rate); the lever spread; the item-2 model measurement
(the mini model on the new assignment rule; a move to the judgment model
only on a recorded failure).

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`.
Commit. Report to the owner (R25).

## Phase 6 — Loop: constrain and theme (items 5, 8, 10 part, 11, 12; R4, R21, R28; AM7)

6.1 **The component — `deep-reasoner`.** Brief (S6, S13): the payload
without place and without `where_tried`; the baseline passed in; the
distinct call; batches in parallel.
It lands with round 0 of `constrain_v2` from the lead. Tests: the
contract's bullets for items 5, 8, 10 and 11; AM6's pathway test.

6.2 **Constrain and theme loop — `lead`.** `constrain_v2`; the theme
prompt only on a finding (the replay reads the themes of the included
options against the seven stored theme sets). Measures: M4, M6, M9 (`cannot_check` per run); the exclusions
read one by one.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`.
Commit. Report to the owner (R25).

## Phase 7 — Read models and the views (items 3, 7 part, 22 part, 23; AM10, AM15, AM21; PA3)

7.1 **Read models — `fast-worker`.** Brief (S14): the additive fields from
an exact list; `make openapi-sync`. Done when `make drift-check` is green
and the diff is additive.

7.2 **Structure — `fast-worker`.** The card's new lines and the list's
*tried on* facet as unstyled structure, with vitest tests from the
contract's frontend bullets; the chat citation's label; the `theme` stage
in `runProgress.ts`, with the theme count read from its summary.

7.3 **Words and finish — `lead`.** Reason: taste-bearing surfaces and
product copy. The *tried on* line, the variants block, the runner-up line,
"not stated in the abstract", the *abstract only* citation label, the stage
blurb in `api/stage_vocabulary.py:40`. With the `impeccable` skill.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check` ·
`make frontend-verify`. Commit.

## Phase 8 — Live check, evidence, specs, step-6 exit — `lead`

Reason: adjudication and the owner's words on spec changes.

8.1 Three live rapid runs on new tasks (obesity, refugees, caregiving);
M1–M9; the browser check on obesity.
8.2 Report to the owner; the owner decides on the other four.
8.3 Spec changes with the owner's accepted wording; `docs/specs/log.md`;
`docs/deferred.md` deltas (rubric box 21); `verification.md` with the round
records' figures.

Gate: **full `make verify`** (step-6 exit). Commit.

## Amendment 2 (2026-09-29)

Rulings R34–R53 are in [contract.md](contract.md) § Amendment 2; the design
detail is in [amendment-2-final.md](amendment-2-final.md) ("final" below).
This section adds phases 9 to 14 and changes no phase above.

> **Status:** written 2026-09-29 from the final document, which the owner
> decided the same day after the adversarial review. The eight build
> questions (final § 7.3, B1–B8) are the lead's decision (data shape or name); the owner can change it. No open question
> blocks a phase.

Executor marks as above: every prompt and its refine loop is `lead`
(prompt-bearing work and adjudication); judgement-bearing code is
`deep-reasoner`; mechanical work is `fast-worker`; taste-bearing frontend
work and final words are `lead`, with the `impeccable` skill. Every loop
follows § The loop and names **one stop measure**; the other measures are
reported (R48). The stop measures of 9L and 12L are proposed here; the lead
confirms each at round 0.

**Verify gates.** Full `make verify` at Phase 9.0, Phase 10 (the schema
revision) and Phase 14. Other phases close on the gates named below. One
green commit per phase, and one per loop round that changes a prompt.

### Phase 9.0 — Build-open baseline — `lead` (inline)

Reason: a one-command check. The tree changed after the step-6 exit gate
(verification.md § Amendment pass 1).

Gate: **full `make verify`**.

### Phase 9 — The plan (R34, R53; R35 withdrawn)

**`deep-reasoner`** (plan model) · **`fast-worker`** (the one-off script,
plan screen structure, read model fields). `requirement` → `boundary` in
`ConstraintKind`, `CHECKED_AT_BY_KIND` (`runtime/scoping_plan.py:94`,
`:99-105`) and the planning wire; the kind `consideration` with `aspect`
(one of the eight line keys or `transferability`, B1) and `hard`;
`consideration` checked at `assessment` in `CHECKED_AT_BY_KIND`, no new
`CheckedAt` value (B3); the aim stays `intended_change` (B2). No plan slot
"Who decides". The one-off script in the gitignored evidence folder
corrects the replay clones' test plans: it renames `requirement` to
`boundary` and rewrites the test statements about who can act as
considerations on `who_decides` (B7). It is not product code. No code for plans of an earlier iteration (R52).

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`. Commit.

### Phase 9L — Planning loop — `lead`

`task_agent_scoping_v5`: the five kinds; A4–A6 as copied in final § 2.1; the
deadline rule; one consideration per line for a sentence that names several
things; the new question about who can act, stored as a consideration on
"who decides"; B8 as a planning rule. Replay: the seven questions and the
probe `9-plan-probe-temporary-accommodation.json`.

Stop measure (proposed): every statement of the seven questions and the
probe lands in the right kind and line, read by hand.

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 10 — The schema revision (R45) — `deep-reasoner`

One reversible alembic revision on `d8f3b6a2c4e1`: the JSON column
`longlist_result.option_profile`, keyed by option id and design version as
`judgements` is. Per option: for each line key (`cost`, `time_to_set_up`,
`time_to_effect`, `workforce`, `who_decides`, `dependencies`,
`coordination`, `delivery_complexity`) the sentence and the mark (`less`,
`more` or null); the setting. No entry = not profiled yet (B6). Round-trip test. No other schema change.

Gate: **full `make verify`**. Commit.

### Phase 11 — Outcome counts (R42) — `fast-worker`

Brief (exact rule from R42): in coverage, per option, in documents: the
documents that evaluate the option and, among them, the documents for each
plan outcome (a document counts when one of its evaluating records has that
`outcome_tag`). No schema, no prompt change.

Gate: `make verify-fast` · `make drift-check`. Commit.

### Phase 12 — The component `option_profile` (R36, R37, R40, R41, R52)

**`deep-reasoner`** (component, the move of lever typing, storage) ·
**`fast-worker`** (replay stage wiring, stage key and progress label
structure, tests from an exact list). Brief, the same kinds of work as S13a
did for `theme`:

- A spine component between `longlist` and `constrain`: `LONGLIST_CHAIN` in
  `runtime/scoping_plan.py` becomes `… → longlist → option_profile →
  constrain → theme`. Registered in `runtime/run_spec.py`,
  `runtime/harness.py`, `runtime/task_plan.py` and `LLM_BEARING_COMPONENTS`
  (`runtime/runner.py:175-192`); stage key `option_profile` in
  `api/stage_vocabulary.py`; the stage in
  `frontend/src/views/workspace/runProgress.ts`; its package under
  `options_scoping/`, prompt hashes pinned in `scripts/prompt_hashes.json`.
- Lever typing moves from `longlist` (its step 6) into `option_profile` as
  built, with the R29 lever reason and the keep-previous rule for one
  invalid typing (S12; B8). `longlist` writes no typing and no ambition.
  `suggest` does not change.
- Inside it, at one time: one call per line over the whole list, the
  ambition call and the setting call. Input per call: the plan (Where for
  "who decides" only), the baseline, and per option its design and at most
  5 records by role; the caps are constants; the judgment model.
- Writes: the lines and the setting to `longlist_result.option_profile`;
  the lever type to the option columns; ambition's mark (`less`, `more` or
  null) to `option.ambition` and its sentence to `option.ambition_reason`. No special failure rule: a failed call is
  tried again by the existing means, then the step fails.
- A full rebuild makes all again. "Add an option" does not change.
- The replay tool has `option_profile` as a stage.

Tests: the chain order; the registry, the harness graph, the plan mapping,
`LLM_BEARING_COMPONENTS` and the run stream know `option_profile`; `longlist`
writes no typing and no ambition; a failed call fails the step.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`. Commit.

### Phase 12L — Profile loop — `lead`

The line prompt(s), the ambition prompt, the setting prompt, lever typing.
Checks: final § 6. Also the first read of the R29 lever reasons and the R31
designs, which no round has read.

Stop measure (proposed): none of the six known faults of final § 6.1 on the
tuning set, read by hand. Reported: M10, M12, M14, stability, the overlap of
coordination with delivery complexity.

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 13 — Constrain (R38) — `deep-reasoner`

Constrain reads `option_profile`. The authority label from the line "who
decides" and the user's consideration on it; never an exclusion; no label
without the consideration. The place exception: constrain reads that line;
all other plan data stays place-stripped. D1 is not in amendment 2 (B5):
constrain's exclusions do not change. It lands with round 0 of `constrain_v3` from the
lead.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`. Commit.

### Phase 13L — Constrain loop — `lead`

`constrain_v3` on the hard-requirement test data
(`9-constrain-hard-requirements.txt`, the clones as Phase 9's script left
them, with the statements about who can act as considerations on
`who_decides`).

Stop measure: M11, the authority label right for at least 9 of 10 options,
read by hand. Reported: no exclusion comes from "who decides".

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 14a — Read models and views (R40, R43, R44)

14a.1 **Read models — `fast-worker`.** Remove `ambition_bands` and the
ambition group source; add the fields of final § 3 "Contract parts that
change"; `make openapi-sync`.

14a.2 **Structure — `fast-worker`.** Plain rows (no ambition word); grouping
by theme and lever type only; the authority-label filter; "What it is" with
ambition after the lever line and the setting; "What it would take"
collapsed by default (a row of eight cells), expanded the eight lines,
hidden for an added option before a rebuild; the outcome counts in "What the
evidence base holds so far"; the grid column chooser with "Middle" and
"Untagged"; the Setting facet from the option-level setting; the plan
screen's kinds; no compare table. Vitest tests.

14a.3 **Design and words — `lead`.** The block in both states, the heading
label, the level words; the tints put to the owner on the built screen.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check` ·
`make frontend-verify`. Commit.

### Phase 14 — Live check, evidence, specs, exit — `lead`

Three live rapid runs (obesity, refugees, caregiving); M1–M12 and M14 read
back from saved files; spec changes with the owner's accepted wording
(`option_profile` included); `docs/specs/log.md`; `docs/deferred.md`
(burden, a grounded legal-change line, the outcome direction and the limits
for task 3, building an added option in place); `verification.md`.

Gate: **full `make verify`**. Commit.

## Plan-review folds (2026-09-28, fallback lane)

| # | Finding | Fold |
|---|---|---|
| P1 | The replay cannot be made through the API; the clone needs hand-written rows; the planning prompt is not tested by it | S15; the planning replay (PA1); open item 4 |
| P2 | Phase 1 needs `strip_place` | `strip_place` is in Phase 1 |
| P3 | Chat citations carry no text basis | S14; PA3 accepted |
| P4 | Tag-derived outcomes never reach constrain | S11: set at mint time |
| P5 | The fold guard misses user-held state | S8: four guards |
| P6 | The residual pass cannot be in the backend wrapper | S8: a second `cluster_units` call |
| P7 | How a title-only document is recorded | S10: dropped before the memo, counted |
| P8 | Stale tags have no mechanism | S3: the fingerprint comparison |
| P9 | Themes at the end of constrain | S13a: `theme` is a component of its own (R28) |
| P10 | The whole-list distinct call changes the merge logic | S13 |
| P11 | The strip removes nationalities | S6 (PA11) |
| P12 | Lever definitions per version; a kept typing's runner-up | S12, S14 |
| P13 | The registry signature; where the flag is written | S1 |
| P14 | Check constraints and rubric box 16 | S5; the box is reworded (PA14) |
| P15 | "Profile order" cannot be rebuilt | S10: `created_at`, then `record_id` |
| P16 | Short-id maps per call | S9 |
| P17 | Where the place removal is recorded | S6 |
| P18 | The setting pass has no location | S11: in `coverage.py` |
| P19 | Gate text; the stage blurb | The gate header and lines agree; the blurb is in 7.3 |
| P20 | Seam design was delegated | The semantics are in S1–S15 |
| P21 | A late child adds documents after the screen | S2; known limit (PA21) |

## Out-of-plan reminders

- The build runs in a fresh conversation with `task-cycle-build`.
- Never `ruff format` the tree; `ruff check --fix` on touched files only.
- Every figure in `verification.md` is read back from a saved result file.
- The Evidence search screen, search loop, search prompts, synthesis
  backend and baseline targets have no source change. A need to change one
  is a stop condition.
- A prompt changes only on a finding from a round (R27).
