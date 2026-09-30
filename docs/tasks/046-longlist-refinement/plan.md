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
> questions (final § 7.3, B1–B8) are the lead's decisions (data shape or
> name); the owner can change each. The plan-stage adversarial review
> (2026-09-30) gave 13 findings; the lead accepted all, and they are folded
> here (the seams S16–S19, the rename sites, the typing data, the split of
> Phase 12, the ADR task, the replay-tool tasks). No open question blocks a
> phase.

Executor marks as above: every prompt and its refine loop is `lead`
(prompt-bearing work and adjudication); judgement-bearing code is
`deep-reasoner`; mechanical work is `fast-worker`; taste-bearing frontend
work and final words are `lead`, with the `impeccable` skill. Every loop
follows § The loop and names **one stop measure**; the other measures are
reported (R48). The stop measures of 9L and 12L are proposed here; the lead
confirms each at round 0. **A prompt change that a code phase needs lands
as round 0 of its loop in the same commit as that code** (the wire models
are prompt text, and `make prompt-guard` ties them to the hashes).

**Verify gates.** Full `make verify` at Phase 9.0, Phase 10 (the schema
revision) and Phase 14. Other phases close on the gates named below. One
green commit per phase, and one per loop round that changes a prompt.

### Decisions fixed here, amendment 2 (lead seam design)

Lead's decisions from the plan review (2026-09-30), in the form of S1–S15.
Checked against the code at the head of the branch.

S16. **Input of `option_profile`** (R37). It loads the walk's options that
are not merged (as `theme_scope` loads the walk's options, but not only the
included ones), each with its design and at most 5 member records ordered by
role (evaluated, described, recommended, mentioned); both caps are named
constants. Each line call gets the plan (Where only in the `who_decides`
call) and the baseline blocks (`baseline_sections`, `render_baseline_blocks`,
as `suggest` reads them). The judgment model.

S17. **Write target** (R37, R45; B6). It updates the latest `longlist_result`
row of the walk's scope, as `theme_scope` does: the new column
`option_profile` (final § 2.10: per option id and design version, the line
keys with sentence and mark `less` · `more` · null, and the setting), and the
typing keys of S20. Lever type and ambition go on the `option` row
(`primary_lever_type`, `secondary_lever_types`, `lever_none_fits_reason`,
`taxonomy_version`, `ambition`, `ambition_reason`).

S18. **The authority label** (R38). Constrain writes it in its own output,
`longlist_result.judgements` (keyed `[option_id][design_version]`,
`options_scoping/constrain/constrain.py:65-67`), as one labelled entry for
each option that has a label; never into the `option_profile` column. Its
input: the option's `who_decides` sentence and the plan's considerations on
`who_decides`. With no such consideration, no entry.

S19. **Read model** (R43). The option read model serves the lines, marks and
setting from `longlist_result.option_profile`, and the authority label from
`judgements` (the repository already reads `judgements` per design version,
`api/readmodels/repository.py:2975-2980`). An option with no entry (added,
not rebuilt) serves no profile.

S20. **The typing data moves with lever typing** (B8). Lever typing keeps its
behaviour as built: a failed or invalid typing batch keeps the previous
typing (`options_scoping/longlist/longlist.py:1386-1391`). Its data stays in
the same keys of the same `longlist_result` row, now written by
`option_profile`, so the read side does not change: `provenance.lever_reason`
and `provenance.runner_up` (read at `api/readmodels/repository.py:2849-2875`),
`provenance.typing` with `kept_ids`, `seed_ids`, `discovered_ids`
(`longlist.py:1469-1526`, `2051-2062`), `counts.typing_invalid`
(`longlist.py:2182`), `provenance.prompt_versions.typing` and
`provenance.models.typing` (`longlist.py:2200-2207`). A line, ambition or
setting call that still fails after the existing retry fails the step.

### Phase 9.0 — Build-open baseline — `lead` (inline)

Reason: a one-command check. The tree changed after the step-6 exit gate
(verification.md § Amendment pass 1).

Gate: **full `make verify`**.

### Phase 9 — The plan (R34, R53; R35 withdrawn)

**`deep-reasoner`** (plan model and rename) · **`fast-worker`** (the
one-off script, the replay-tool changes, plan screen structure) · **`lead`**
(the prompt and wire, as 9L round 0 in the same commit).

- Plan model: `requirement` → `boundary`; the kind `consideration` with
  `aspect` (one of the eight line keys or `transferability`, B1) and `hard`;
  `consideration` checked at `assessment` in `CHECKED_AT_BY_KIND`, no new
  `CheckedAt` value (B3); the aim stays `intended_change` (B2). No plan slot
  "Who decides". No code for plans of an earlier iteration (R52).
- **Rename sites** (grep `"requirement"` again at build start):
  `runtime/scoping_plan.py:94` (`ConstraintKind`), `:103`
  (`CHECKED_AT_BY_KIND`), `:300` (docstring), `:374`;
  `options_scoping/longlist_intent.py:46`; `options_scoping/suggest/suggest.py:207`;
  `options_scoping/constrain/constrain.py:252`; `api/contract/task_agent.py:216`;
  `frontend/src/views/workspace/planVocabulary.ts:316`;
  `frontend/src/mock/fixtures.ts:611`; the generated types
  (`make openapi-sync`); and the tests that hold the literal.
- **The prompt and wire rename is the lead's**
  (`runtime/task_agent_scoping_prompt.py:88-111`, `347-375`, `530-532`). It
  lands as 9L round 0 in the same commit as the Phase 9 code.
- **The one-off script** (gitignored evidence folder, not product code):
  renames every constraint of kind `requirement` to `boundary` in the plans
  of all seven replay clones, and rewrites the test statements about who can
  act (the refugees and obesity clones, `set_requirements.py`) as
  considerations on `who_decides` (B7). It keeps `guard_clone`
  (`clone.py:118-124`) and the name check of `set_requirements.py:29-30`, and
  never touches a row of the seven stored tasks. After Phase 9 no clone is
  made again, unless the clone tool applies the same rename.
- **The replay tool** (`fast-worker`): the planning replay sends one turn and
  prints kind and text only (`replay.py` `cmd_planning`); it gains a scripted
  second turn (the answer to the question about who can act) and prints
  `aspect` and `hard`.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check` ·
`make openapi-sync` · `make frontend-verify`. Commit.

### Phase 9L — Planning loop — `lead`

`task_agent_scoping_v5`: the five kinds; A4–A6 as copied in final § 2.1; the
deadline rule; one consideration per line for a sentence that names several
things; the new question about who can act, stored as a consideration on
`who_decides`; B8 as a planning rule. Replay: tuning set obesity, refugees,
caregiving, energy, plus the probe `9-plan-probe-temporary-accommodation.json`;
check set NEET, heat pumps, cohesion (the first build's split).

Stop measure (proposed): on the tuning set and the probe, every statement
lands in the right kind and line (`aspect`), read by hand.

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 10 — The schema revision (R45) — `deep-reasoner`

One reversible alembic revision on `d8f3b6a2c4e1`: the JSON column
`longlist_result.option_profile` (S17; shape in final § 2.10). Round-trip
test. No other schema change.

Gate: **full `make verify`**. Commit.

### Phase 11 — Outcome counts (R42) — `fast-worker`

Brief (exact rule from R42): in coverage, per option, in documents: the
documents that evaluate the option and, among them, the documents for each
plan outcome (a document counts when one of its evaluating records has that
`outcome_tag`). No schema, no prompt change.

Gate: `make verify-fast` · `make drift-check`. Commit.

### Phase 11A — ADR 0040 amendment — `lead`

ADR 0040 (committed on this branch at `5d9f206a`, not merged) is amended
before Phase 12: the walk becomes `longlist → option_profile → constrain →
theme`; lever typing is in `option_profile`; the place exception of R38. Its
own commit.

Gate: `make verify-fast`. Commit.

### Phase 12a — The component `option_profile`, typing moved (R37; S16, S17, S20)

**`deep-reasoner`** (component, the move of lever typing, the schema
read and write) · **`fast-worker`** (registration sites, stage key and
progress label structure, stub, replay stage, tests from an exact list).
No new prompt; behaviour is unchanged except where typing runs. Brief, the
same kinds of work as S13a did for `theme`:

- A spine component between `longlist` and `constrain`: `LONGLIST_CHAIN` in
  `runtime/scoping_plan.py` becomes `… → longlist → option_profile →
  constrain → theme`.
- **Registration:** `runtime/run_spec.py`; `runtime/harness.py` (the
  component map and the dispatch near `:717`); `runtime/task_plan.py`;
  `LLM_BEARING_COMPONENTS` (`runtime/runner.py:175-192`);
  `api/contract/sse.py` (both copies: `StageKey` and `STAGE_KEYS`,
  `:27-62`); `api/contract/task_agent.py:70-83`; `api/stage_vocabulary.py`
  (the stage map near `:64` and the blurb near `:44`; the blurb's words are
  the lead's); `frontend/src/views/workspace/runProgress.ts`.
- Lever typing moves from `longlist` (its step 6) into `option_profile` as
  built: the backend method and its stub (`longlist_backend.py:359-374`,
  stub near `:559`), the Langfuse name (`longlist:type`, `:374`), the typing
  data of S20. `longlist` writes no typing and no ambition. `suggest` does
  not change.
- Its package under `options_scoping/`; the lever typing prompt keeps its
  text and hash (only its path moves in `scripts/prompt_hashes.json`).
- The replay tool has `option_profile` as a stage.

Tests: the chain order; the registry, the harness graph, the plan mapping,
`LLM_BEARING_COMPONENTS`, the run stream and the stage map know
`option_profile`; `longlist` writes no typing; **the lever types, the typing
keys and the counts of a stub run are the same as before the move.**

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check` ·
`make openapi-sync` · `make frontend-verify`. Commit.

### Phase 12b — The line, ambition and setting calls (R36, R40, R41; S16, S17)

**`deep-reasoner`** (the calls, storage) · **`lead`** (12L round 0 in the
same commit: the line, ambition and setting prompts, and the typing wire
without `ambition` and `ambition_reason`).

- Inside `option_profile`, at one time: one call per line over the whole
  list, the ambition call and the setting call, with the input of S16; the
  backend methods, their stubs and their Langfuse names.
- Writes as S17: the lines and the setting to `longlist_result.option_profile`;
  ambition's mark (`less`, `more` or null) to `option.ambition` and its
  sentence to `option.ambition_reason`. A line, ambition or setting call that
  still fails after the existing retry fails the step (S20).
- A full rebuild makes all again. "Add an option" does not change.

Tests: each line key is written for every option; ambition values are
`less`, `more` or null; a failed line call fails the step; a failed typing
batch keeps the previous typing.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`. Commit.

### Phase 12L — Profile loop — `lead`

The line prompt(s), the ambition prompt, the setting prompt, lever typing.
Checks: final § 6. Also the first read of the R29 lever reasons and the R31
designs, which no round has read.

Stop measure (proposed): none of the six known faults of final § 6.1 on the
tuning set, read by hand. Reported: M10, M12, M14, stability, the overlap of
coordination with delivery complexity; **lever typing:** the lever spread
and the reasons read by hand beside the first build's final read; **ambition:**
the count of `less` / `more` / no mark per list, and the sentences read by
hand against "not the size of the studies, not whether it works".

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 13 — Constrain (R38; S18) — `deep-reasoner`

Constrain reads `option_profile`. The authority label as S18, from the
`who_decides` sentence and the plan's considerations on `who_decides`; never
an exclusion; no label without the consideration. The place exception:
constrain reads that line; all other plan data stays place-stripped. D1 is
not in amendment 2 (B5): constrain's exclusions do not change. It lands with
round 0 of `constrain_v3` from the lead.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`. Commit.

### Phase 13L — Constrain loop — `lead`

`constrain_v3` on the refugees and obesity clones, whose plans hold the
test statements about who can act (`9-constrain-hard-requirements.txt`),
rewritten by Phase 9's script as considerations on `who_decides`.

Stop measure: M11, the authority label right for at least 9 of 10 options,
read by hand. No check-set read is possible for M11: only these two clones
hold such statements. Reported: no exclusion comes from `who_decides`.

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 14a — Read models and views (R40, R43, R44; S19)

14a.1 **Read models — `fast-worker`.** Remove `ambition_bands` and the
ambition group source; add the fields of final § 3 "Contract parts that
change" as S19; `make openapi-sync`.

14a.2 **Structure — `fast-worker`.** Plain rows (no ambition word); grouping
by theme and lever type only; the authority-label filter; "What it is" with
ambition after the lever line and the setting; "What it would take"
collapsed by default (a row of eight cells), expanded the eight lines,
hidden for an added option before a rebuild; the outcome counts in "What the
evidence base holds so far"; the grid column chooser with "Middle" and
"Untagged"; the Setting facet from the option-level setting; no compare
table. (The plan screen's kinds are done in Phase 9.) Vitest tests.

14a.3 **Design and words — `lead`.** The block in both states, the heading
label, the level words; the tints put to the owner on the built screen.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check` ·
`make frontend-verify`. Commit.

### Phase 14 — Live check, evidence, specs, exit — `lead`

- Three live rapid runs (obesity, refugees, caregiving); M1–M10, M12 and M14
  read back from saved files. M11 is read in 13L from the refugees and
  obesity clones, not from live runs.
- The browser check on the live obesity run (rubric box 33): the card in
  both states, the grid with a chosen line, the list rows, the filter.
- `verification.md` gains: the overlap figure (box 38), the round records of
  every loop (box 35) and of the one-off script (box 45), the OpenAPI diff
  (box 46), the rollback as the contract states it, and the known limits of
  final § 2.10.
- Spec changes with the owner's accepted wording (`option_profile`
  included); `docs/specs/log.md`; `docs/deferred.md` (burden, a grounded
  legal-change line, the outcome direction and the limits for task 3,
  building an added option in place, "studied in").

Gate: **full `make verify`**. Commit.

## Amendment 3 (2026-09-30)

Rulings R54–R71 are in [contract.md](contract.md) § Amendment 3; the design
detail, the loop checks and the answered questions Q1–Q18 (and the open Q19)
are in [amendment-3-final.md](amendment-3-final.md) ("final 3" below). This
section adds phases 15 to 23 and changes no phase above. Rounds 2–4 of 12L
(`evidence/rounds/12L-profile-loop.md`) are built and are not phases here.

> **Status:** written 2026-09-30 from final 3; updated the same day with the
> answers to the 18 build questions (Q1, Q5, Q10, Q11 by the owner; the
> others by the lead, who the owner can overrule). The seams S21–S26 are
> **proposals for the lead to confirm at the plan gate**; none is the
> owner's. Q19 (the record prompt's version) is open and touches Phase 16R
> only. The adversarial passes (record, build list item 6) run on final 3,
> the contract items and the rubric, then on this section, before 15.0.

Executor marks: prompts and their loops are `lead`; judgement-bearing code is
`deep-reasoner`; mechanical work is `fast-worker`; the card's final words and
polish are `lead`, with the `impeccable` skill. Every loop follows § The loop
and names **one stop measure**; the others are reported (R69). A prompt
change that a code phase needs lands as round 0 of its loop in the same
commit as that code.

**Verify gates.** Full `make verify` at 15.0, at 16 (the one schema revision,
R71) and at 23. Elsewhere `make verify-fast`, plus `make prompt-guard` where
a prompt changes, `make drift-check` and `make openapi-sync` where the API
changes, `make frontend-verify` where the frontend changes. One green commit
per phase, and one per loop round that changes a prompt.

### Decisions proposed here, amendment 3 (lead seam design, to confirm)

Checked against the code at `685c7157`.

S21. **The folding calls** (R54, R55; Q4, Q17). *Input:* for each facet, the
distinct words of the list's member records — `population` for Tried on,
`outcome` for Measures (`CoverageMember`, `coverage.py:146-148`) — keyed
whitespace-collapsed and case-folded (`_clean`, `coverage.py:239-243`), over
the options `option_profile` loads (not merged, `option_profile.py:181-205`)
and their units as `membership_coverage` reads them (`longlist.py:1458-1535`);
short ids `w1 … wN`, mapped back in code, as the profile calls' `o1 … oN`
(`option_profile.py:507-529`); the plan's target unit and outcomes from the
place-stripped plan data (`option_profile.py:722`). *Output:* each word id
once, with its kind; a kind that matches the plan names the plan text it
matches (the target unit or one outcome, copied), so the code puts the target
unit first and a kind equal to a plan outcome makes no separate row (Q4).
*Run:* two more calls in the profile step's pool
(`OPTION_PROFILE_MAX_CONCURRENT`, `option_profile.py:101`), the mini model
(`LONGLIST_ASSIGNMENT_MODEL`, `longlist_backend.py:117-118`), one retry, then
the step fails, as the other profile calls (`_profile_call`,
`option_profile.py:607-636`); backend methods, stubs and Langfuse names beside
`profile_setting` (`longlist_backend.py:540-551`, stub near `:914`).
*Store:* the map in `longlist_result.provenance.option_profile.folds`
(`{"tried_on": {word: kind}, "measures": {word: kind}}`, written with the
provenance at `option_profile.py:815-843`). *Count:* `option_coverage`
(`coverage.py:294`) takes the map and writes per option the kinds with
documents (DOI-collapsed) under new keys; `option_profile` rewrites those
keys of each option's `longlist_result.coverage` entry after its calls;
constrain's merge recompute (`constrain.py:985-1000`) and an added option's
read-time coverage (`repository.py:3431-3465`) pass the stored map; a word
not in the map counts under no kind (Q17, a known limit). The old
`tried_on` and record `settings` keys stay in coverage for constrain
(`constrain.py:360-384`; Q9). No schema change.

S22. **`programme_name` and Examples** (R63, R71; Q1–Q3). The record wire
gains `programme_name: str | None` beside `study_geography`
(`evidence_search/extract/interventions_records.py:118`), the nullable text
fields (`:220`), the record (`:367`) and the writer (`:467`); the column on
`intervention_profile_record` (`core/schema.py:1088-1135`); the prompt text
beside the `study_geography` rule (`extract_interventions_prompt.py:252`),
the lead's. Coverage: `CoverageMember` gains `programme_name`
(`coverage.py:133-170`), filled by `_coverage_member` (`longlist.py:1398-1415`)
and by `_search_coverage` (`repository.py:3442-3465`); `examples` = the
distinct programme names (case-folded key, the smallest spelling shown, as
`_show`, `coverage.py:232-236`) with documents, at most 5 (a constant), by
documents then name; `variants`, `VARIANTS_MAX` and the folded-seed list go
(`coverage.py:68-70`, `:422-459`); served as `examples` in place of
`variants` (`read_models.py:1205-1219`, `:1258`; `repository.py:2849-2863`,
`:3997`). The cluster prompt does not change.

S23. **Where tried in coverage** (R59; Q6, Q7). Per record, from
`study_geography` after the setting pass (`coverage.py:203-219`):
`countries_in` (`where_tried.py:337-360`) gives one code and no group word →
that country's name (a new code → name table beside `COUNTRY_NAMES`,
`:47-133`); two or more codes, or a group word → "multiple countries"; a
non-empty text that matches nothing → "other places"; an empty text → "not
stated". The group words: `OECD_MARKERS` (`:321`) becomes "oecd", "europe",
"european", "north america", "nordic", "countries" (Q6). The level below is
the record's text as written. Per document: all its records name one country
→ that country; two countries → "multiple countries", both texts below (Q7);
the precedence between "other places" and "not stated" across a document's
records is the lead's at build. Coverage's `where_tried` (`coverage.py:349`,
`:391-392`, `:471`) becomes a list of `{top, documents, places: [{place,
documents}]}`. Removed: `WhereGroup`, `WHERE_GROUPS`, `COMPARABLE_LABEL`,
`OECD_CODES`, `where_group`, `where_labels` (`where_tried.py:33-41`,
`:376-418`); the provenance key `where_tried_labels` (`longlist.py:1967`);
`WhereTriedGroup`, `WhereTriedOut` (`read_models.py:734`, `:817-830`);
`_WHERE_GROUPS`, `_where_tried_out`, `_where_label` (`repository.py:2810`,
`:2833-2835`, `:3199-3202`) where nothing else reads them. Kept:
`countries_in`, `strip_place`, `names_place` and the name tables. Constrain's
summary carries no where tried (`constrain.py:363`) and does not change.

S24. **The outcomes table's data** (R56, R64; Q4). `outcome_counts`
(`coverage.py:381-386`, `:484-490`): each plan outcome carries `documents`
(members of any role with that `outcome_tag`) and `evaluated` (members with
role `evaluated`); a list `other` carries each Measures kind that matches no
plan outcome, with `documents` and `evaluated`. The "serves" mark reads
`outcomes_served` (`repository.py:3122`). Read model: `OutcomeCountOut` and
`OutcomeCountsOut` (`read_models.py:920-941`) gain `evaluated` and `other`;
`EvidenceProfileOut` loses `populations`, `settings`, `outcomes`, and
`tried_on` becomes the kinds (`read_models.py:1122-1128`); the same on
`OptionSummaryOut.tried_on` (`read_models.py:1029`). The card's runner-up line
goes (Q10); `runner_up_lever_type` (`repository.py:2866`, `:3132`, `:3586`)
leaves the read model when nothing else reads it.

S25. **The documents** (R67, R68; Q13, Q15). `_option_documents`
(`repository.py:3741-3911`) and `_search_documents` (`:3467-3499`): one entry
per document, keyed by coverage's `document_key(doi=normalise_doi(…))`
(`coverage.py:94-130`); **role** = the document's highest role under this
option (evaluated, then described, then the rest); order evaluated first,
then quality score descending, then a stable key (the lead's at build);
**place** = the document's top level (S23); **`year`** from the snapshot
metadata (`source_snapshot.metadata`, read at `repository.py:3846-3848`); the
title through an HTML-entity decode in `_title` (`repository.py:152`).
`OptionDocumentOut` (`read_models.py:1179-1202`) loses `where_tried_group`
and gains `year` and `place`. A document with no row in this task
(`task_source_snapshot_id` null, `read_models.py:1195`) shows its title as
plain text (Q15). The card's own de-duplication (`OptionCard.tsx:186-194`)
goes.

S26. **The dossier's slot on a scoping task** (R67 refined; Q14, Q16). A new
read route beside `GET /tasks/{task_id}/sources/{source_id}`
(`routers/read_models.py:155-167`), for example
`GET /tasks/{task_id}/sources/{source_id}/records?option_id=`, owner-scoped
as `_readable` does: the intervention profile records of that document that
are members of an option (`option_membership` ⋈ `intervention_profile_record`,
`core/schema.py:1635`, `:1088`, the join `_evidence_records` uses,
`option_profile.py:470-485`), each with the option id and name and the
record's own words: intervention name, setting, tried on (`population`),
outcomes measured (`outcome`), where (`study_geography`), role; every record,
several per document (Q14); filtered to one option when `option_id` is given;
the DOI twins of S25 included. Frontend: a hook beside `useFindings`
(`queries.ts:357-370`); `SourceDossierBody` (`SourcesView.tsx:962`) shows the
records in the findings slot (`:1055-1064`) under "In this option" (from a
card) or its scoping name (from Sources) when `task.capability ===
"options_scoping"` (`api/contract/tasks.py:232`), else as today; the card's
document list — and nothing else on the card (Q16) — opens the exported
`SourceDossier` (`ArtefactView.tsx:1034-1082`) with the option id, through
the `source` search parameter as the report does (`ArtefactView.tsx:1401-1416`);
the Sources tab's own copy (`SourcesView.tsx:884-910`, used at `:418`) passes
no option.

### Phase 15.0 — Build-open baseline — `lead` (inline)

Gate: **full `make verify`**.

### Phase 15 — ADR 0040 amendment 3 — `lead`

ADR 0040 (`docs/adr/0040-options-scoping-longlist-refinement.md`, § Amendment
2 at `:204`) gains § Amendment 3: the folding calls in `option_profile` on
the mini model (S21); where tried as countries in two levels, four top-level
values, superseding ADR 0039 decision 10 (S23); `programme_name` on the
record and Examples from it (S22); the revision and its rollback
(`alembic downgrade -1`). Own commit before Phase 16.

Gate: `make verify-fast`. Commit.

### Phase 16 — The schema revision (R71) — `deep-reasoner`

One reversible alembic revision on `e9a4c1f7b3d2`
(`backend/alembic/versions/e9a4c1f7b3d2_longlist_option_profile.py`): the
nullable Text column `intervention_profile_record.programme_name`, and the
column in `core/schema.py` (`:1088-1135`). Round-trip test; an old row reads
null. No other schema change.

Gate: **full `make verify`**. Commit.

### Phase 16R — The record prompt round (R63, R69; S22) — `lead` · `fast-worker`

`fast-worker`: the wire field, the nullable-field list, the record and the
writer (S22), with tests from an exact list (a record with and without a
name; blank → null). `lead`: the prompt text for `programme_name` ("the
proper name of the programme, scheme or law that the abstract gives for this
intervention, or null") as round 0 in the same commit; the version per the
owner's answer to **Q19**; then one refine round.
Replay: `replay.py stage profile <slug> --fresh`
(`evidence/pre-contract-runs/replay.py:77-90`) on the tuning set, one read
of the check set.

Stop measure (proposed): on the tuning set, every non-null `programme_name`
is a proper name the abstract gives, and none is a plain phrase, read by
hand. Reported: records with a name per list; the other fields and tags
unchanged in kind (a sample read); options with no example.

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 17 — The documents (R67, R68; S25) — `fast-worker`

Brief (exact rules from S25): one entry per document by DOI key; the highest
role; the order; `year`; the entity decode; plain-text title for a document
with no row here. `place` and the removal of `where_tried_group` land in
Phase 18. `make openapi-sync`.

Tests: the same DOI under two snapshot ids gives one entry; a document with
an `evaluated` and a `mentioned` record reads `evaluated`; evaluated before
described; a higher quality score first among equals; `year` from metadata;
`&amp;` in a stored title reads `&`.

Gate: `make verify-fast` · `make drift-check` · `make openapi-sync` ·
`make frontend-verify`. Commit.

### Phase 18 — Where tried (R59; S23)

**`deep-reasoner`** (the per-record rule, the group words, the document
grain) · **`fast-worker`** (the removal sites of S23, the read model,
`place` on a document, OpenAPI, the frontend types and the facet's data).

Tests: one country named alone → that country; two countries → "multiple
countries"; "12 OECD countries", "Europe", "Nordic countries" → "multiple
countries"; a place the matcher does not know → "other places", its text
below; empty → "not stated"; a document whose records name two countries →
"multiple countries" with both texts; the setting pass still moves a place
into an empty geography; no code reads the publisher, journal, institutions
or publication country; counts in documents, DOI-collapsed.

Gate: `make verify-fast` · `make drift-check` · `make openapi-sync` ·
`make frontend-verify`. Commit.

### Phase 18C — The "not stated" check (R59; Q18) — `lead`

On the three live lists of Phase 14 (tasks `8d73e096`, `161ac3d5`,
`1409ae63`), the records whose top level is "not stated": how many abstracts
name the place of the study, read by hand; a fault only where the abstract
names it. Round record `evidence/rounds/18C-not-stated.md`: counts only, no
abstract text. A fault leads to a refine round of `extract_interventions`
(Q18), recorded as a 16R round.

Gate: the round record; `make verify-fast` · `make prompt-guard` if a round
runs. Commit.

### Phase 19 — Outcome counts and Examples in coverage (R56, R63; S22, S24) — `fast-worker`

Brief (exact rules): a plan outcome's `documents` counts documents with a
member of any role whose `outcome_tag` is that outcome; `evaluated` counts
documents with an `evaluated` member with it; `evaluating_documents` stays.
`examples` from `programme_name` as S22; `variants` removed. The `other` list
waits for Phase 20. The existing test "described counts for nothing"
(`test_longlist_coverage_046.py`) is replaced, with the reason in the commit.

Tests: a `described` member counts in `documents`, not in `evaluated`; at
most 5 examples; two spellings of one name are one example; no `variants`
key.

Gate: `make verify-fast` · `make drift-check`. Commit.

### Phase 20 — The folding calls (R54, R55; S21)

**`deep-reasoner`** (the calls, the map, the counts, the coverage rewrite,
the merge and added-option paths) · **`lead`** (20L round 0 in the same
commit: the Tried on and Measures folding prompts, in a new prompt module
under `options_scoping/option_profile/`).

Tests: every word id once or the call is malformed; a malformed call twice
fails the step and writes nothing; two words of one kind in one document
count one document; the target unit's kind first; a kind equal to a plan
outcome makes no `other` row; a constrain merge recomputes the kinds from the
stored map; a word not in the map counts under no kind; constrain still gets
its old `tried_on` and `settings` keys; the stub gives a deterministic map.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`. Commit.

### Phase 20L — Folding loops — `lead`

The Tried on and Measures prompts; `replay.py stage option_profile <slug>
--fresh`. Checks: final 3 § 6.

Stop measure (proposed; confirmed at round 0): on the tuning set, no two
kinds on one list name the same kind, read by hand. Reported: kinds per list
for each facet; the kinds that use the plan's words; the target unit first;
the words that fell under no kind; M6's replacement (Tried on shows kinds
beyond the target unit where the evidence has them).

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 21 — Read models and the dossier's records (S24, S26) — `fast-worker`

The fields of S24 (the outcomes table, the kinds for Tried on and Measures,
the removals, `runner_up_lever_type` if nothing else reads it); `examples`;
the route and read model of S26; `make openapi-sync`.

Tests: the table's rows (plan outcomes in plan order with `serves`, then
`other`); a scoping document's records, one per option, each in its own
words, and filtered by option; an Evidence search task's findings route
unchanged; owner scoping (an unreadable task is 404).

Gate: `make verify-fast` · `make drift-check` · `make openapi-sync` ·
`make frontend-verify`. Commit.

### Phase 22a — Card, facets, grid, dossier slot: structure — `fast-worker`

From final 3 § 2.5 with the exact words of the record: the header's grey
line and no `SnapshotCells` or chip (`OptionCard.tsx:244`, `:302-309`); "What
it is": the lever line "Lever: <primary>, with <secondary types>." with the
reason under it, no runner-up line (`:340`), no authority line (`:343`),
delivered through, design features ≤ 6, Examples; "What it would take" with
Ambition first, the authority label beside "Who decides" (word with colour,
then the sentence, only with an entry), and the collapsed row of **seven
cells** with "Middle" (`OptionCard.tsx:368-411`); the evidence section in
order (outcomes table; roles; where tried two levels; tried on, all kinds;
the note "Read from titles and abstracts only"; the document list: linked
title or plain text, meta line, five then "Show all N", "No documents found
yet."); checks (the user's boundaries and preferences first, built-ins in one
line unless one fails, no transferability line, `OptionCard.tsx:449-477`); no
"What it is for" and no origin section (`:356-366`, `:479-481`). Facets
without counts: Setting, Tried on, Where tried (top level); Tried on and
Where tried filter as Setting does (`LonglistView.tsx:143-156`); each folds
after 8 chips (`SETTING_FACET_LIMIT`, `:57`); no Measures facet
(`LonglistView.tsx:438-515`; `triedOnFacet`, `longlistPresentation.ts:285`).
`CELL_LIMIT` 4 (`LonglistGrid.tsx:29`). The dossier: the card's documents
open `SourceDossier`; the slot of S26. Vitest tests for each.

Gate: `make verify-fast` · `make frontend-verify`. Commit.

### Phase 22b — Card design and final words — `lead` (`impeccable`)

Section titles (name, not explain); the lever line's final words (no "also
touches"); the label "Policy Atlas's estimate" (`OptionCard.tsx:71`), checked
at 390 px (the reason for D16); the grey lines at 16 px; the table; the
seven cells; the authority word's colour; the tints put to the owner.

Gate: `make verify-fast` · `make frontend-verify`. Commit.

### Phase 23 — Live check, evidence, exit — `lead`

- Three live rapid runs (obesity, caregiving, refugees), on records made
  after the revision (Q19); M1–M5, M7–M10, M12 and M14 read back from saved
  files (M6 retired); new figures: kinds per folding facet per list, the
  top-level where values per list, records with a `programme_name`, options
  with examples.
- The browser check (desktop and 390 px): the card top to bottom; the seven
  cells; the authority label beside "Who decides" (refugees); the outcomes
  table; where tried both levels; a document opening the dossier with "In
  this option"; the Sources tab's dossier on the same task; an Evidence
  search task's dossier unchanged; the facets filtering; the grid with a cell
  of five or more.
- `verification.md` § Amendment 3: gates, commits, round records, the OpenAPI
  diff, the revision and its rollback, the known limits of final 3 § 7.3, and
  a line naming rounds 2–4 of 12L as built before this amendment.
  Spec-change proposals (the owner decides the wording); `docs/deferred.md`.

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
