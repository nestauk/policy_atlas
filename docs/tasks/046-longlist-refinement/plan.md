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

Rulings R54–R75 are in [contract.md](contract.md) § Amendment 3; the design
detail, the loop checks and the answered questions (Q1–Q26, none open) are
in [amendment-3-final.md](amendment-3-final.md) ("final 3" below). This section adds phases 15 to 23 and changes no phase above.
Rounds 2–5 of 12L (`evidence/rounds/12L-profile-loop.md`) are built and are
not phases here.

> **Status:** written 2026-09-30 from final 3; updated the same day with the
> 18 answers, the adversarial review (34 findings, the lead's rules and the
> owner's decisions), the owner's two later decisions (no place list;
> `unit` in the finding records) and the answers to Q20–Q25 (Q24 the
> owner's), then with the plan-stage adversarial review (15 findings, the
> lead's file `a3-plan-findings.md`, all accepted; finding 3 decided by the
> owner, record § "The reach of the rename"). The seams S21–S28 are
> **proposals for the lead to confirm at the plan gate**; none is the
> owner's. "(PRn)" names the plan-review finding a change closes.

Executor marks: prompts and their loops are `lead`; judgement-bearing code is
`deep-reasoner`; mechanical work is `fast-worker`; the card's final words and
polish are `lead`, with the `impeccable` skill. Every loop follows § The loop
and names **one stop measure**; the others are reported (R69). A prompt
change that a code phase needs lands as round 0 of its loop in the same
commit as that code.

**Verify gates** (lead, A14). Full `make verify` at 15.0, at 16 (the one
schema revision, R71) and at 23. Elsewhere `make verify-fast`, plus
`make prompt-guard` at 16R, 16W, 18P, 20, 20L (and 18C if a round runs),
`make drift-check` and `make openapi-sync` where the API changes (16, 16W,
17, 18, 21), `make frontend-verify` where the frontend changes (16, 16W, 17,
18, 21, 22a, 22c, 22b). Each phase that removes an API field deletes, in the
same commit, the frontend lines and fixtures that read it (`OptionCard.tsx`,
`LonglistView.tsx`, `longlistPresentation.ts`, `mock/fixtures.ts`,
`mock/api.ts`), so `frontend-verify` stays green (PR6). Phase 21's new read
route is marked for `/security-review` (PR13). One green commit per phase,
and one per loop round that changes a prompt.

### Decisions proposed here, amendment 3 (lead seam design, to confirm)

Checked against the code at `34bba89f`.

S21. **The folding calls and their maps** (R54, R55; lead, B4, B5, B10, A6).
*Input:* for each facet, the distinct words of the whole list's coverage —
the record's `unit` words (today's key `populations`, `coverage.py:404-410`)
for Tried on, the `outcome` words (`outcomes`) for Measures — over every
member, not the profile calls' 5 records (`option_profile.py:448-504`); short
ids `w1 … wN`, mapped back in code, as the profile calls' `o1 … oN`
(`option_profile.py:507-529`); the plan's target unit and outcomes as
reference. *Output:* each word id with its kind; a kind that is a plan
outcome is returned as that outcome's own text (A4). *Run:* two more calls in
the profile step's pool (`OPTION_PROFILE_MAX_CONCURRENT`,
`option_profile.py:101`), the mini model (`LONGLIST_ASSIGNMENT_MODEL`,
`longlist_backend.py:117-118`), one retry; an invalid response after the
retry fails the step (`option_profile.py:755-761`); a word missing from the
output keeps its own text as kind; a kind not built from input words is
dropped (B10; Q20). *Store (B4):* the maps at list level in the profile
column, `longlist_result.option_profile["folds"] = {"tried_on": {word: kind},
"measures": {word: kind}}` (the column is written whole at
`option_profile.py:836-843`; the read model's per-option read,
`_design_record(result, "option_profile", …)`, never reads the key `folds`).
*Count (B5):* `option_profile` recomputes, from the members' records through
the maps (a database read, no model), documents per kind per option into
coverage `tried_on_kinds` and `measures_kinds`; `option_coverage`
(`coverage.py:294`) takes the maps as an argument, so the merge recompute in
constrain (`constrain.py:985-1000`, written at `:1109`) and an added option's
read-time coverage (`repository.py:3431-3465`) apply the stored maps. The
old `tried_on`, the unit-word and record `settings` keys stay for constrain
(`constrain.py:360-384`). No schema change for this seam.

S22. **The record's three fields** (R63, R72, R73; lead, B1, B12, B19, Q19).
The wire (`evidence_search/extract/interventions_records.py`):
`programme_name` and `study_country` beside `study_geography` (`:118`);
`population` → `unit` (`:101-103`, description: "who or what the
intervention was delivered to: people, organisations, sites or things");
`population_tag` → `unit_tag` (`:140`, `:312`, `:349`, `:371`, `:471`); the
nullable text fields (`:220`); the record (`:365`) and the writer (`:467`);
`SCHEMA_VERSION` bump (`:28`); `PROMPT_VERSION` → `extract_interventions_v3`
(`extract_interventions_prompt.py:44`); the prompt text beside the
`study_geography` rule (`:252`), the lead's; `interventions_records.py` joins
the prompt hash guard's list (`scripts/prompt_hash_guard.py`). Coverage:
`CoverageMember` (`coverage.py:133-170`) gains `programme_name` and
`study_country` and renames `population`, `population_tag`; filled by
`_coverage_member` (`longlist.py:1398-1415`) and `_search_coverage`
(`repository.py:3442-3465`). `examples` = the distinct programme names
(case-folded key, the smallest spelling shown, as `_show`,
`coverage.py:232-236`) with documents, at most 5, by documents then name;
`folded` = the folded seeds' names (A2); `variants`, `VARIANTS_MAX` go
(`coverage.py:68-70`, `:422-459`); "also found as" joins `_also_found_as`
(`repository.py:2949-2959`) and `folded`; served as `examples` in place of
`variants` (`read_models.py:1205-1219`, `:1258`; `repository.py:2849-2863`,
`:3997`). The cluster prompt does not change for examples; its discovery prompt takes the place rule (R74, Q25).

S23. **Where tried from `study_country`** (R59, R72; lead, B6, A3). Per
record: `study_country` holds every named country, separated ("United
Kingdom; United States"), each as its short English name (Q22, Q23); one
country → that country; two or more, or "multiple" (a group) → "multiple
countries", derived in code; case folded only; empty with `study_geography` stated → "other"; both empty → "not
stated". Per document (B6 applied): one country if every record with a
country gives the same one; "multiple countries" if two or more, or any
"multiple"; else "other" if any record states a place; else "not stated".
The level below: `study_geography` as written. The country filter matches a
document under "multiple countries" whose countries include it (Q22). Coverage's `where_tried`
(`coverage.py:349`, `:391-392`, `:471`) becomes a list of `{top, documents,
places: [{place, documents}]}`; a "multiple countries" entry also carries
`countries` (its component countries, from `study_country` split on ";",
case-folded), which the filter reads (PR5); the `countries` key (`:350`, `:393-397`) and
the `home` argument go. Removed in Phase 18: `WhereGroup`, `WHERE_GROUPS`,
`COMPARABLE_LABEL`, `OECD_CODES`, `COUNTRY_ADJECTIVES`, `COUNTRY_GROUPS`,
`OECD_MARKERS`, `countries_in`, `where_group`, `where_labels`
(`where_tried.py:33-41`, `:254-308`, `:320-360`, `:376-418`; `ABBREVIATIONS`, `:310-318`, stays for the strip until 18P); the provenance key
`where_tried_labels` (`longlist.py:1967`); `WhereTriedGroup`, `WhereTriedOut`
(`read_models.py:734`, `:817-830`); `_WHERE_GROUPS`, `_where_tried_out`,
`_where_label` (`repository.py:2810`, `:2833-2835`, `:3199-3202`) where
nothing else reads them; and, whatever M4 shows, `where_codes`
(`where_tried.py:363-373`, which calls `countries_in` at `:372`) and its only
use, `home` (`longlist.py:1520`, `:1808`; `_home`, `repository.py:3502-3503`)
(PR4). The name tables the place strip uses (`COUNTRY_NAMES`,
`SUBNATIONAL_PLACES`, `ABBREVIATIONS`) wait for Phase 18P.

S24. **The outcomes table's data** (R56, R64; lead, A4). `outcome_counts`
(`coverage.py:381-386`, `:484-490`): each plan outcome carries `documents`
and `evaluated`, counting records with that `outcome_tag` and records tagged
`other` or null whose Measures kind is that outcome's own text, one document
once per row; a list `other` carries each Measures kind that is not a plan
outcome, counting only `other`/null records. The "serves" mark reads
`outcomes_served` (`repository.py:3122`). Read model: `OutcomeCountOut` and
`OutcomeCountsOut` (`read_models.py:920-941`) gain `evaluated` and `other`;
`EvidenceProfileOut` loses `populations`, `settings`, `outcomes`, and
`tried_on` becomes the kinds (`read_models.py:1122-1128`); the same on
`OptionSummaryOut.tried_on` (`:1029`). `runner_up_lever_type`
(`repository.py:2866`, `:3132`, `:3586`), `where_label`, `depth_label`
(R61) and `transferability` (R66) leave the option read models where nothing
else reads them (B13).

S25. **The documents** (R67, R68; lead, Q13, Q15, B17). `_option_documents`
(`repository.py:3741-3911`) and `_search_documents` (`:3467-3499`): one entry
per document, keyed by coverage's `document_key(doi=normalise_doi(…))`
(`coverage.py:94-130`), the task's own row as the id that opens the dossier;
**role** = the highest role under this option (evaluated, then described,
then the rest); order evaluated first, then quality score descending, then a
stable key (the lead's at build); **place** = the document's top level
(S23); **`year`** from the snapshot metadata (read at
`repository.py:3846-3848`); the title through an HTML-entity decode in
`_title` (`repository.py:152`). `OptionDocumentOut` (`read_models.py:1179-1202`)
loses `where_tried_group` and gains `year` and `place`. No row in this task
(`task_source_snapshot_id` null, `read_models.py:1195`): plain-text title.
The card's own de-duplication (`OptionCard.tsx:186-194`) and chips
(`:431-437`, the "inherited" chip included) go.

S26. **The dossier's slot on a scoping task** (R67; lead, Q14, B8). Owner-scoped:
built by `deep-reasoner`, marked for `/security-review` (PR13). A new read
route beside `GET /tasks/{task_id}/sources/{source_id}`
(`routers/read_models.py:155-167`), for example
`GET /tasks/{task_id}/sources/{source_id}/records?option_id=`, owner-scoped
as `_readable` does: the intervention profile records of that document that
are members of an option (`option_membership` ⋈ `intervention_profile_record`,
`core/schema.py:1635`, `:1088`, the join at `option_profile.py:470-485`), each
with the option id and name and the record's own words: intervention name,
setting, tried on (`unit`), outcomes measured (`outcome`), where
(`study_geography`), role; every record; filtered to one option when
`option_id` is given; the DOI twins of S25 included. Frontend: a hook beside
`useFindings` (`queries.ts:357-370`); `SourceDossierBody`
(`SourcesView.tsx:962`) shows the records in the findings slot (`:1055-1064`)
under "In this option" (from a card) or its scoping name (from Sources) when
`task.capability === "options_scoping"` (`api/contract/tasks.py:232`) and the
document has records; else its findings, as today (B8). Only the card's
document list opens the exported `SourceDossier` (`ArtefactView.tsx:1034-1082`)
with the option id, through the `source` search parameter
(`ArtefactView.tsx:1401-1416`); the Sources tab's copy (`SourcesView.tsx:884-910`,
used at `:418`) passes no option.

S27. **The revision and the rename sites** (R71, R73, R75; owner, "The reach
of the rename"). One revision on `e9a4c1f7b3d2`
(`backend/alembic/versions/e9a4c1f7b3d2_longlist_option_profile.py`). Four
kinds of site (PR3):

- **Columns** (the revision): add `programme_name`, `study_country`; rename
  `population` → `unit` and `population_tag` → `unit_tag` on
  `intervention_profile_record` (`core/schema.py:1103`, `:1111`, the check
  `ck_ipr_population_tag` and its constants `:1077-1080`, `:1127-1129`);
  rename `population` → `unit` on `intervention_outcome_finding` (`:959`)
  and `implementation_context_finding` (`:1019`); drop and recreate
  `finding_reference_union` with `unit` (`:1145-1185`). Code readers of the
  columns: `coverage.py`, `longlist.py`, `constrain.py`, `repository.py`
  (`:3343`, `:3385`, `:3451`), `extract.py:1239`, `:1282`, `:2095-2133`,
  `extraction_backend.py:388`, `:394`, `quote_verify.py:78`, `:616`, `:646`,
  `:701`, `:736`, `:803`, `group/group.py:1187`,
  `synthesis/synthesis_tools.py:217`, `:253`, `:2112`, `:2196`.
- **The facet key** (the revision, with a data migration): `"population"`
  → `"unit"` in `GROUPING_FACETS` (`core/schema.py:1249`), `GroupingFacet`
  (`runtime/task_plan.py:49`), the API contract (`api/contract/task_agent.py:54`),
  `group/facet_values.py:20`; `group.py:1291` reads `row[facet]` from the
  view, so the key and the view change together. **Data migration**, in the
  same revision, reversible: rewrite the stored facet value `"population"`
  → `"unit"` in the plan payloads in production (`task_plan.payload`,
  `core/schema.py:1376-1408`, the `grouping_facets` list,
  `runtime/task_plan.py:749`), the keys of `grouping_result.groups`
  (`core/schema.py:1272`, read by `groups_out`, `repository.py:600-615`) and
  the facet in `grouping_result.grouping_provenance` (`core/schema.py:1263-1267`)
  (lead, Q26); no reader keeps an alias; the downgrade writes all three back.
- **Payload keys sent to the models** (16W, word swap): `longlist.py:559`,
  `:745`; `synthesis_tools.py:2022`, `:2068`; `synthesise.py:1543`, `:1584`;
  `extract.py:2108`, `:2133`.
- **Prompt words** (16W, word swap): the record wires' names and
  descriptions (the intervention record's in 16R); `finding_references.py:37`,
  `:56`, `:66`; `longlist_cluster_prompt.py:269`;
  `synthesis/synthesis_prompts_v6.py:148`; `synthesis/grounding_judge.py:112`.

Grep `population` again at build start; after 16W the word is gone from the
product (the record). Stored JSON keys of earlier records (`field_coverage`,
grounding) are not rewritten (R52). The evidence scripts that read the
renamed columns or keys are updated in 16 (`evidence/pre-contract-runs/
live_metrics.py:32`, `readback.py:84`, `:89`, `analyse_profile.py`,
`analyse_longlist.py`); `replay.py check-stored` hashes rows as text
(`replay.py:470-479`), so the stored-task reference is saved again right
after the migration and recorded in `verification.md` (PR9).

S28. **The place rule in words** (R74). The rule "the place in the question
is the user's place, not a criterion; judge as if the question named no
place" enters: the screen criteria and intent composed by
`longlist_screening_criteria` and `compile_longlist_intent`
(`longlist_intent.py:77`, `:100`; the screen prompt itself is a "keep"); the
tagging context (`plan_tagging_context`, `:150`, carried into the record
prompt; its hash is a fingerprint component, `interventions_profile.py:83-86`);
constrain's plan data and prompt (`constrain.py:245-261`, `constrain_prompt.py`,
`constrain_v3` → v4); the option design prompt (`runtime/option_design_prompt.py:26`,
`option_design_v2` → v3) and its placeless pass (`design.py:162-163`). If M4
holds: delete `strip_place` and its helpers (`where_tried.py:421-510`), the
name tables and `ABBREVIATIONS` (`:47-318`), `names_place` and the setting
pass (`:513-534`; `coverage.py:203-219`); the module `where_tried.py` goes
if nothing is left (`where_codes` goes in Phase 18, PR4). Callers of the
strip (PR11): `longlist_intent.py:73`, `:139-141`, `:165-166`
(`screen_target_unit`, `longlist_plan_data`); `api/longlist_start.py:54`,
`:218` (the scope's `place_removed`); `constrain.py:259-261`, `:884-886`,
`:1088`; `design.py:162-163`; the replay tool (`replay.py:73`, `:160`); tests
`test_longlist_intent`, `test_constrain`, `test_longlist_start`,
`test_strip_place` (retired tests listed under edited tests). Q25 (lead): every prompt that read
the stripped text takes the rule — also those fed by `longlist_plan_data`
(`longlist_intent.py:125-148`): discovery (`longlist_cluster_prompt.py`,
`DISCOVERY_SYSTEM_PROMPT`, via `longlist.py:1648`), lever typing
(`option_profile/lever_typing_prompt.py`), the eight lines and ambition
(`option_profile/option_profile_prompt.py`), via `option_profile.py:722`;
the folding prompts take the rule in Phase 20's round 0 (PR2).

### Phase 15.0 — Build-open baseline — `lead` (inline)

Gate: **full `make verify`**.

### Phase 15 — ADR 0040 amendment 3 — `lead`

ADR 0040 (`docs/adr/0040-options-scoping-longlist-refinement.md`, § Amendment
2 at `:204`) gains § Amendment 3: the folding calls and their maps (S21);
where tried from `study_country`, the matcher removed, superseding ADR 0039
decision 10 (S23); the three record changes and `unit` in the finding
records (S22, S27); the place rule in words and the conditional removal of
the place strip (S28); the revision and its rollback (`alembic downgrade
-1`). Own commit before Phase 16.

Gate: `make verify-fast`. Commit.

### Phase 16 — The schema revision and the rename sites (R71; S27)

**`deep-reasoner`** (the revision, the view, the facet-key data migration,
the downgrade) · **`fast-worker`** (the column readers and the facet-key
sites of S27 from an exact list; the frontend reads of the facet key and
their fixtures; the evidence scripts; tests that hold the literal). The wire
names, the payload keys and the prompt words stay as they are until 16R and
16W; the writer maps the wire to the new columns (PR3).

Tests: round trip up and down; an old row reads null in the two new columns
and keeps its text under `unit`; the union view returns `unit` from all
three branches; a stored plan with `grouping_facets` holding `"population"`,
and a stored grouping result with a `"population"` key in `groups` and in
`grouping_provenance`, read `"unit"` after the upgrade and `"population"`
after the downgrade (Q26); a
grouping run on the `unit` facet reads the view; the Evidence search tests
pass unedited except for the field and facet name.

After the migration on the dev database: `replay.py check-stored` reports
the new columns as a change; the stored-task reference is saved again and
the step is recorded in `verification.md` (PR9).

**Production** (owner, Q24: "Keep in this amendment."): Evidence search is
live, so the revision reaches production data. It must run there without a
re-extraction: the finding tables' rename is a plain column rename with no
version change on the finding records (their schema and prompt versions stay,
so their fingerprints and memo rows stay valid); the intervention record's v3
(16R) re-extracts options-scoping tasks only, on their next run. The facet
key's data migration rewrites the stored plans of Evidence search tasks in
production (owner, "The reach of the rename": "1."). Rollback on production:
`alembic downgrade -1` reverses the three renames, writes `"population"`
back into the three stored places (plan payloads, `grouping_result.groups`
keys, `grouping_provenance`) and drops the two new columns; deploy the
previous image. Tests run the downgrade on a finding row and on a stored
plan and read the text back.

Gate: **full `make verify`** (with `make openapi-sync` and
`make frontend-verify` inside it: the facet key is in the API). Commit.

### Phase 16R — The record prompt loop (R63, R69, R72, R73; S22) — `lead` · `fast-worker`

`fast-worker`: the wire fields, the nullable-field list, the record, the
writer, `SCHEMA_VERSION`; `CoverageMember` gaining `programme_name` and
`study_country` and its loaders (`longlist.py:1398-1415`;
`repository.py:3343`, `:3385`, `:3451`) (PR10); an explicit extra-files list
in `scripts/prompt_hash_guard.py` (today it takes only files named
"*prompt*", `:39-43`), holding `interventions_records.py` (PR8); tests from
an exact list (a record with and without a name; blank → null; `unit_tag`
values unchanged). `lead`: the prompt text for `programme_name`,
`study_country` and `unit` (the wider definition), v3, as round 0 in the same
commit; then rounds. Replay: `replay.py stage profile <slug> --fresh`
(`evidence/pre-contract-runs/replay.py:77-90`; `--fresh` bypasses the memo,
which is per task, `extract.py:368-375`) on the tuning set, one read of the
check set; at most five rounds (A5). At the last round, `replay.py stage
longlist <slug> --fresh` on the tuning set reads M1 and M2 (PR14).

Stop measure (proposed): on the tuning set, every non-null `programme_name`
is a proper name the abstract gives for this intervention, not one it sits
within, and every `study_country` is the country of the stated place,
"multiple" for a group, empty when nothing is stated; read by hand.
Reported: records with a name and records by `study_country` value per list;
programme-name misses on the check set; `unit` values beyond people; the
other fields and tags unchanged in kind (a sample read).

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 16W — The word swap: finding records, payload keys, prompt words (R73, R75; S27) — `lead`

The word swap of S27 (owner, "The reach of the rename": "1."), like for like
under the 038 ruling. The payload keys sent to the models (`longlist.py:559`,
`:745`; `synthesis_tools.py:2022`, `:2068`; `synthesise.py:1543`, `:1584`;
`extract.py:2108`, `:2133`); the prompt words (`longlist_cluster_prompt.py:269`,
`synthesis_prompts_v6.py:148`, `grounding_judge.py:112`); the IOF and ICF wire fields `population` → `unit` (`iof_records.py:152`,
`:314`; `icf_records.py:97`, `:193`) and their descriptions with the wider
definition (`finding_references.py:37`; the prompt texts `iof_prompt.py`,
`icf_prompt.py:257`, their examples); `IofFindingOut`, `IcfFindingOut`
(`read_models.py:277`, `:294`); the findings view label
(`frontend/src/views/FindingsView.tsx:172`, `:215`, `:288`). Hashes
re-pinned; the diff read as words only and recorded; no replay (the owner's
038 ruling). **No version change** on the finding records (owner, Q24), so
no document is extracted again; `iof_records.py`, `icf_records.py` and
`finding_references.py`, and `grounding_judge.py` (not named "*prompt*"),
join the extra-files list of `scripts/prompt_hash_guard.py` that 16R added,
and are hashed in `scripts/prompt_hashes.json` (PR8). After 16W, a grep of
`backend/src` and `frontend/src` finds no "population" in product code.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check` ·
`make openapi-sync` · `make frontend-verify`. Commit.

### Phase 17 — The documents (R67, R68; S25) — `fast-worker`

Brief (exact rules from S25). `place` and the removal of
`where_tried_group` land in Phase 18. `make openapi-sync`.

Tests: the same DOI under two snapshot ids gives one entry, the task's own
row as its id; a document with an `evaluated` and a `mentioned` record reads
`evaluated`; evaluated before described; a higher quality score first among
equals; `year` from metadata; `&amp;` in a stored title reads `&`.

Gate: `make verify-fast` · `make drift-check` · `make openapi-sync` ·
`make frontend-verify`. Commit.

### Phase 18 — Where tried from `study_country` (R59, R72; S23)

**`deep-reasoner`** (the per-record and per-document rule) ·
**`fast-worker`** (the removal sites of S23, `where_codes` and `home`
whatever M4 shows (PR4), the read model, `place` and the multiple-country
`countries` (PR5), OpenAPI, and the frontend reads of `where_tried` and
`where_tried_group` with their fixtures, in this commit (PR6)).

Tests: a country → that country; "multiple" → "multiple countries"; a place
with an empty `study_country` → "other", its text below; nothing →
"not stated"; a document whose records give two countries → "multiple
countries" with both texts; no code reads the publisher, journal,
institutions or publication country; counts in documents, DOI-collapsed; no
"comparable" or "OECD" as a label or heading.

Gate: `make verify-fast` · `make drift-check` · `make openapi-sync` ·
`make frontend-verify`. Commit.

### Phase 18P — The place rule loop (R74; S28) — `lead` · `fast-worker`

**18P.0 — the screen reset** (`fast-worker`, the gitignored replay tool)
(PR1): the replay tool refuses `--fresh` for the screen
(`replay.py:90`, `:353-354`), a second screen run screens 0 documents
(`replay-out/refugees-toolbuild/screen-rerun.json`) and the scope's intent is
fixed at clone time (`replay.py:156-160`). The tool gains a screen reset for
a clone: a new replay scope per round with the round's intent and criteria,
or the clone's stage-1 rows moved aside; M4 and the screen's pass count are
read from it. It never touches a stored task (`guard_clone`).

`lead`: the rule in words, as round 0, in every prompt that read the
stripped text (Q25): the screen criteria and intent (`longlist_intent.py:77`,
`:100`), the tagging context (`:150`), `constrain` (v4,
`constrain_prompt.py:53`), `option_design` (v3,
`runtime/option_design_prompt.py:26`), discovery
(`longlist_cluster_prompt.py:37`, v3), lever typing
(`option_profile/lever_typing_prompt.py`), the line and ambition prompts
(`option_profile/option_profile_prompt.py`); then rounds. The folding
prompts do not exist yet: they take the rule in Phase 20's round 0 (PR2).
Replays, for every stage that reads the plan (PR2): the screen (through
18P.0), `longlist` (discovery and typing), `option_profile`, `constrain` and
`suggest`, on the tuning set (obesity, refugees, caregiving, energy; energy
is where M4 was read in stage 1, AM18); one read of the check set (NEET,
heat pumps, cohesion; cohesion is check only, PR12). Stop measure: **M4** — no exclusion and no screen failure because of
place, read by hand. Reported: M1, M2, the screen's pass counts beside the
last loop's (Q25).

`fast-worker`, only if M4 holds: delete the strip and its helpers, the name
tables, `names_place` and the setting pass (S28), the callers' uses named in
S28 (`api/longlist_start.py:54`, `:218`; `constrain.py:884-886`, `:1088`;
`replay.py:73`, `:160`) and their tests' literals; retired tests
(`test_strip_place`) listed under edited tests (PR11). (`where_codes` went in
Phase 18.) If M4 fails, nothing is deleted and the round record and
`verification.md` say so (R74).

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 18C — The "not stated" check (R59; Q18) — `lead`

On the replay clones after 16R (v3 records), and again on Phase 23's live
lists; no extra live run (PR7). The records whose top level is "not
stated": how many abstracts name the place of the study, read by hand, with
`study_geography` and `study_country` beside; a fault only where the abstract
names it. Round record `evidence/rounds/18C-not-stated.md`: counts only, no
abstract text. A fault leads to a round of the 16R loop.

Gate: the round record; `make verify-fast` · `make prompt-guard` if a round
runs. Commit.

### Phase 19 — Outcome counts, Examples and `folded` in coverage (R56, R63; S22, S24) — `fast-worker`

Brief (exact rules): plan outcomes over any role with `evaluated` separate
(the Measures part of A4 waits for Phase 20); `examples` from
`programme_name`; `folded`; `variants` removed; "also found as" joins
`folded`. The existing test "described counts for nothing"
(`test_longlist_coverage_046.py`) is replaced, with the reason in the commit.

Tests: a `described` member counts in `documents`, not in `evaluated`; at
most 5 examples; two spellings of one name are one example; no `variants`
key; a folded seed shows in "also found as".

Gate: `make verify-fast` · `make drift-check`. Commit.

### Phase 20 — The folding calls (R54, R55; S21)

**`deep-reasoner`** (the calls, the maps at list level, the counts into
`tried_on_kinds` and `measures_kinds`, `option_coverage` applying the maps,
the merge and added-option paths, A4's cross-rows) · **`lead`** (20L round 0
in the same commit: the two folding prompts, with the place rule of R74 in
them (PR2), in a new prompt module under
`options_scoping/option_profile/`).

Tests: an invalid response twice fails the step and writes nothing; a word
missing from the output keeps its own text; a kind not built from input
words is dropped; two words of one kind in one document count one document;
the target unit's kind first; a record tagged `other` whose kind is a plan
outcome counts on that plan row once; a constrain merge recomputes the kinds
from the stored maps; constrain still gets its old keys; the stub gives a
deterministic map.

Gate: `make verify-fast` · `make prompt-guard` · `make drift-check`. Commit.

### Phase 20L — Folding loops — `lead`

The two folding prompts; `replay.py stage option_profile <slug> --fresh`.
Checks: final 3 § 6.

Stop measure (lead, A6): on the tuning set, no two kinds on one list name the
same kind, and at most 12 kinds per list per facet, read by hand. Reported:
kinds per list for each facet; the kinds that use the plan's words; the
target unit first; words kept as their own text; M6's replacement.

Gate: `make verify-fast` · `make prompt-guard`. Commit. Report to the owner
(R25).

### Phase 21 — Read models and the dossier's records (S24, S26)

**`fast-worker`** (the fields of S24 and the removals, B13; `examples`; the
frontend lines and fixtures that read each removed field — `variants`,
`populations`, `runner_up_lever_type`, `transferability`, `depth_label` — in
`OptionCard.tsx`, `LonglistView.tsx`, `longlistPresentation.ts`,
`mock/fixtures.ts`, `mock/api.ts`, in this commit, PR6) · **`deep-reasoner`**
(the owner-scoped route and read model of S26, **marked for
`/security-review`**, PR13). `make openapi-sync`.

Tests: the table's rows (plan outcomes in plan order with `serves`, then
`other`); a scoping document's records, one per option, each in its own
words, and filtered by option; a document with no record under the option
reads its findings; an Evidence search task's findings route unchanged;
owner scoping (an unreadable task is 404; another owner's option id gives
nothing).

Gate: `make verify-fast` · `make drift-check` · `make openapi-sync` ·
`make frontend-verify`; `/security-review` on the route before the commit.
Commit.

### Phase 22a — The card: structure — `fast-worker`

From final 3 § 2.5 with the exact words of the record: the header's grey
line; no `SnapshotCells` or chip (`OptionCard.tsx:244`, `:302-309`); "What it
is": "Lever: <primary>, with <secondary types>." with the reason under it,
no runner-up line (`:340`), no authority line (`:343`), delivered through,
design features ≤ 6, Examples; "What it would take" with Ambition first, the
authority label beside "Who decides" (word with colour, then the sentence,
only with an entry), and **seven cells** with "Middle"
(`OptionCard.tsx:368-411`); the evidence section in order (outcomes table;
roles; where tried two levels; tried on, all kinds; "Read from titles and
abstracts only"; the document list: linked title or plain text, meta line,
five then "Show all N", "No documents found yet."); checks (the user's
boundaries and preferences first, built-ins in one line unless one fails, no
transferability line, `:449-477`); no "What it is for" and no origin section
(`:356-366`, `:479-481`); the 16 px sentences of A10. Box 28's card tests
edited for the label's place (`OptionCard.test.tsx:241-259`, B14). Vitest
tests for each.

Gate: `make verify-fast` · `make frontend-verify`. Commit.

### Phase 22c — Facets, grid, dossier slot: structure — `fast-worker` (PR15)

Facets without counts: Setting, Tried on, Where tried (top level); Tried on
and Where tried filter as Setting does (`LonglistView.tsx:143-156`), a
country chip also matching "multiple countries" documents through their
`countries`; each folds after 8 chips (`SETTING_FACET_LIMIT`, `:57`); no
Measures facet (`:438-515`; `triedOnFacet`, `longlistPresentation.ts:285`).
`CELL_LIMIT` 4 (`LonglistGrid.tsx:29`). The dossier: only the card's
document list opens `SourceDossier`; the slot of S26 in `SourceDossierBody`
(`SourcesView.tsx:962`, `:1055-1064`). Vitest tests for each.

Gate: `make verify-fast` · `make frontend-verify`. Commit.

### Phase 22b — Card design and final words — `lead` (`impeccable`)

Section titles (name, not explain); the lever line's final words (no "also
touches"); the label "Policy Atlas's estimate" (`OptionCard.tsx:71`), checked
at 390 px (the reason for D16); the grey lines at 16 px; the table; the
seven cells; the authority word's colour; the tints put to the owner.

Gate: `make verify-fast` · `make frontend-verify`. Commit.

### Phase 23 — Live check, evidence, exit — `lead`

- Three live rapid runs (obesity, caregiving, refugees), on v3 records;
  M1–M5, M7–M10, M12 and M14 read back from saved files (M6 retired; M4
  beside the 18P result); new figures: kinds per folding facet per list, the
  top-level where values per list, records with a `programme_name` and by
  `study_country` value, options with examples; the 18C "not stated" read
  on these lists (PR7).
- The browser check (desktop and 390 px): the card top to bottom; the seven
  cells; the authority label beside "Who decides" (refugees); the outcomes
  table; where tried both levels; a document opening the dossier with "In
  this option"; the Sources tab's dossier on the same task; an Evidence
  search task's dossier, findings view and grouping by the `unit` facet (the
  word "population" nowhere); the facets
  filtering; the grid with a cell of five or more.
- `verification.md` § Amendment 3: gates, commits, round records, the 16W
  diff read, the OpenAPI diff, the revision and its rollback (the facet-key
  data migration included), the stored-task reference saved again after the
  migration (PR9), the edited
  tests, the known limits of final 3 § 7.3, the 18P outcome (list deleted or
  kept), and a line naming rounds 2–5 of 12L as built before this amendment.
  Spec-change proposals (the owner decides the wording); `docs/deferred.md`.

Gate: **full `make verify`**. Commit.

## Amendment 4 (2026-10-09)

Rulings R76–R91 are in [contract.md](contract.md) § Amendment 4; the
reasons in ADR 0040 § Amendment 4. This section adds phases 24 to 31 and
changes no phase above. The working record and the design pages are local
(`amendment-4-proposed.md`; `evidence/amendment-4-design/`).

> **Status:** written 2026-10-09 from the approved record; the seams
> S29–S36 are **proposals for the lead to confirm at the plan gate**; none
> is the owner's. The plan-stage adversarial review follows.

Executor marks as for amendment 3: prompts and their loops are `lead`;
judgement-bearing code is `deep-reasoner`; mechanical work is
`fast-worker`; the card's and the list's final words and polish are
`lead`, with the `impeccable` skill. Every loop follows § The loop and
names **one stop measure**; the others are reported (R69). A prompt change
that a code phase needs lands as round 0 of its loop in the same commit as
that code.

**Verify gates.** No schema revision. Full `make verify` at 24.0 and 31.
Elsewhere `make verify-fast`, plus `make prompt-guard` at 26, 26L, 27, 28,
29; `make drift-check` and `make openapi-sync` at 25 and 26; `make
frontend-verify` at 25, 30a, 30c, 30b. A phase that removes an API field
deletes, in the same commit, the frontend lines and fixtures that read it
(`OptionCard.tsx`, `LonglistView.tsx`, `longlistFacets.ts`,
`longlistPresentation.ts`, `mock/fixtures.ts`, `mock/api.ts`). One green
commit per phase, and one per loop round that changes a prompt.

### Decisions proposed here, amendment 4 (lead seam design, to confirm)

Checked against the code at `8bc6ec2e`. "(PA4-n)" names the plan-review
finding a decision closes (§ Plan-review folds, amendment 4).

S29. **The evidence signal fields** (R76, R85). *Where (PA4-1):* in
`option_coverage` (`coverage.py:400`), which already calls `document_where`
per document (`coverage.py:563`) and knows each document's role; it writes
two coverage keys: `evaluated_countries: [{country, documents}]` (the
documents whose role is `evaluated`, their top level resolved by S29a, the
levels "not stated", "multiple countries" and "other" left out (PA4-3)),
and `outcomes_evaluated: int` (entries of `outcome_counts.by_outcome` with
`evaluated ≥ 1`). `_option_summary_fields` (`repository.py:3348`) reads
them from the stored coverage as it reads `documents`; no query is added
to the list read. An added option gets them through `_search_coverage`
(`repository.py:3460`), which calls the same builder (PA4-10). *Order:* the
country of the built-from plan's Where (S29a on the plan text; PA4-16)
first, then by document count, then name. *The total (PA4-16):*
`outcomes_total: int`, the built-from plan's outcome count, served beside
`outcomes_evaluated` so a later plan edit cannot mix versions. *Words:* one
presentation function in `longlistPresentation.ts` builds the line from the
three fields, used by the card header and the row.

S29a. **One country resolver** (R76, R87; PA4-2). A function in
`where_tried.py`, `resolve_country(text) -> tuple[str, str] | None`:
the text with a leading "the" stripped, case-folded, looked up in
`COUNTRY_NAMES`, then `ABBREVIATIONS`, then `SUBNATIONAL_PLACES`
(`where_tried.py:139, ~235, ~347`), returns `(iso_code, display_name)`, one
display name per code (a new small table code → short English name, built
from `COUNTRY_NAMES`' canonical entries). `countries_named` keeps its
contract; the signal, the place order, the geography-to-country match
(S32) and the plan's Where go through the resolver, so "England", "UK",
"the United Kingdom" and "Britain" are one country. A text the resolver
does not know is kept as written and counted (S32); nothing is deleted.

S30. **The document lines' record fields** (R81). *Where:* `_option_documents`
(`repository.py:3993`) and the added option's `_search_documents`
(`repository.py:3715`) (PA4-10), through one helper that takes the
document's member records under the option (the join `source_records_out`
uses, `repository.py:2577`, restricted to the option; for an added option
the `_SearchUnit` records), ordered by `OPTION_PROFILE_ROLE_ORDER` then
`created_at`, and takes the first: `programme_name` (through the S33 fold
once Phase 27E lands; the raw name before that), `tried_on_kind` (the
record's `unit` through the stored `folds["tried_on"]`, the record's own
text when the map lacks it, as S21), `measured` (the plan outcome's text
when `outcome_tag` names one; else `outcome` through `folds["measures"]`),
`place_detail` (`study_geography` when it differs from the top level),
`records_count`. *Model:* `OptionDocumentOut` gains the five fields, all
optional. *The maps:* read once per option from
`longlist_result.option_profile["folds"]`; when the profile has not run
(the window of amendment 3 § 7.3) the kinds are the records' own words.
*Cost:* the card read only; the list never reads documents.

S31. **The place-sentence call** (R80). *Where:* `option_profile`, as a
second wave after the pool block (`option_profile.py:882-893`) has written
the folded coverage keys, one call per option in a pool of the same width,
on `LONGLIST_ASSIGNMENT_MODEL` (`longlist_backend.py:130`). *Input builder
(code):* a function over an abstract per-record input that both
`MembershipRead` and `_SearchUnit` supply (PA4-10): the option's `evaluated`
documents grouped by top level (S29a), places ordered as S29 with one last
group "No single place" holding "multiple countries", "not stated" and
"other" (PA4-3); place ids `p1 … pN` and document ids `d1 … dM` (PA4-15);
each document as `{id, programme_name, unit, tried_on_kind, setting,
outcome, measured, study_geography, tier, evidence_type, year}`; the
plan's outcomes in the plan's words; the option's name; the list's folded
kinds as the vocabulary. A place with more than 12 documents sends the
first 12 by role then quality and the count. *Wire:*
`PlaceSentencesWire{places: [{place_id, sentence}]}`, `extra="forbid"`,
**no `max_length` on the wire** (PA4-9): the ceiling is checked in code
per sentence so one long sentence costs one place, not the option. The
wire and its field descriptions live in `place_sentences_prompt.py`
(prompt text: lead; PA4-12). *Run:* one retry; an invalid response after
the retry leaves the option on template sentences, counted as
`failed_call`, and the step continues. *Trace check (code; PA4-8):* the
allowlist for a place is every input field text of that place's documents
plus the evidence types, the tiers, the folded kinds and the plan's
outcomes. (1) Numbers: every integer and every number word from one to
twenty in the sentence must equal a count of the place's documents grouped
by any one input field (documents, evaluations, documents per tier, per
type, per programme) or occur as a token inside an allowlisted text ("9-to-
10-year-olds", "Change4Life"). (2) Strength words ("very strong", "strong",
"moderate", "limited", "weak", "not rated") must be the tier of a document
of the place, unless the word occurs inside an allowlisted text
("moderate-to-vigorous physical activity"). (3) Every capitalised run,
including at position 0 and single tokens, minus sentence-start function
words, must occur case-folded inside an allowlisted text. A failing
sentence is replaced by the template and counted as `failed_trace`; a
sentence over the ceiling (220 characters to start) likewise, counted as
`failed_length`. The counts go to
`provenance.option_profile.place_sentences = {generated, template,
failed_trace, failed_length, failed_call}`. *Template (code):*
"{Programme}: " when one programme name holds the place's documents; "{n}
{strength} {type}" with plural forms and the commonest tier and type; "with
{kind}" from the folded Tried on kind of the first document; "in
{sub-place}" when a `study_geography` adds a word; "measuring {outcome}"
from `measured`. *Store:* coverage key `place_sentences: [{place,
sentence, generated}]` on the option, written after the second wave;
remade on a rebuild. Constrain's merge recompute (`constrain.py:991-1005,
1113`) carries the key through unchanged for the kept option and drops it
for the merged one; the read model builds template sentences at read time
from the same input builder whenever the key is absent (an added option,
a merged-into option whose documents changed), so the block never empties
and no model runs on a read (PA4-15). *Read model:* `OptionOut.place_sentences`.
*Prompt:* `place_sentences_prompt.py` under `option_profile/`, version
`place_sentences_v1`, picked up by the hash guard by name
(`scripts/prompt_hash_guard.py:51-55`). *Replay:* the replay tool's
`option_profile` stage runs the second wave, so 26L replays as 20L did.

S32. **Places** (R87). *Prompt:* `extract_interventions` v4: the rule in
words for `study_geography` and `study_country`; `SCHEMA_VERSION` bump;
the replay with the memo bypassed as 16R. *Checks (code, coverage time;
PA4-4, PA4-18):* a `study_country` the resolver (S29a) does not know is
**kept as written** (it is still a country to the reader: Tajikistan,
Paraguay, Jordan and Lebanon are on the tuning lists and not in
`COUNTRY_NAMES`), counted in the coverage under `places_unknown_country`
with the text, and reported per list; `COUNTRY_NAMES` is extended at build
from the ISO-3166 table the Evidence search sourcing already holds
(`country_filters.py:21`, `ISO_3166_ALPHA2`) so the unknown count on the
tuning lists reaches zero; a `study_geography` that the resolver maps to a
country becomes the top level with no level below; a geography under
"multiple countries" is not served as a place; the place key in coverage's
`places` loop (`coverage.py:~566-570`) normalises hyphens, spaces and a
leading "the". **R87's words "counts as not stated" are softened to "kept
as written and reported"** (a minor contract fold put to the owner, § Plan-review folds).

S33. **Example-name fold** (R88; PA4-13). One function in `coverage.py`,
`fold_programme_name(name) -> tuple[str, str | None]` (the key and the
acronym key): casefold; strip punctuation, possessives and a leading
"the"; a parenthesised acronym becomes the second key and two names with
one acronym key fold together; a leading country word is stripped when the
remainder's key matches another name's, the country words being the keys
of `COUNTRY_NAMES` and `ABBREVIATIONS` ("uk", "us") and an adjective list
written in the module from the tuning lists' records (british, english,
scottish, welsh, irish, american, australian, canadian, dutch, german,
french, spanish, swedish, danish, finnish, estonian, chinese, chilean,
tajik; extended at build as the records show); the shown spelling is the
most frequent then the shortest (the setting rule, `coverage.py:597-606`).
Applied in the `examples` loop and in S30's `programme_name`.

S34. **The folding round and the F4 guard** (R86; PA4-14). *Guard:* in
`_checked_folds` (`option_profile.py`), for the Measures facet only: a
returned kind that contains one plan outcome's text as whole words,
case-folded, maps to that outcome's own text (A4 extended); one containing
two or more maps to the first and is counted; the count of rewritten kinds
per list goes to provenance and the round record. *Round 6 (20L):* the
rules in words in `folding_prompt.py` (no fold across an age group the plan
names; an outcome folds to a plan outcome only when it measures it;
abbreviations fold to their expansion); the stop measure read on 30 random
folds per facet per list, sampled with a fixed seed by the read-back
script, on the v4 records (after Phase 27).

S35. **"Who decides" and the authority** (R89; PA4-7). *The fact:* the
authority call in constrain reads the `who_decides` sentence as its main
input (`constrain.py:737-752, 891-895`), and constrain runs after the
profile, so the verdict is not known when the line is written; a body
written into the sentence would make the label agree because the label
reads the sentence. *Proposed (for the owner, § Plan-review folds):* when
the plan holds a who-can-act consideration, the `who_decides` line
receives the consideration texts as context (there is no structured body:
`who_decides_considerations`, `constrain.py:723-734`), with the rule in
words: name the one body whose decision the option cannot go ahead
without; when that body is the one the user's consideration names, use
the consideration's name for it. The label is then read from a sentence
that names the right body in the user's words. *The measure (two-sided):*
M18 reads, on refugees, every "within your power" option for whether the
named body can adopt the option, and reports the count of "within your
power" labels before and after the round on every tuning list; a rise is
read option by option. Box 83's test becomes: the consideration texts
reach the line when the plan holds the consideration.

S36. **The frontend structure** (R77–R85). *Card:* `SECTIONS` becomes
`how-it-works`, `what-it-would-take`, `evidence-base`; the signal line
component (shared with the row); the lever line and reason; the lead-in
template in `longlistPresentation.ts` (kind → preposition map with "in" as
the default); the opener; the outcomes lines; the place block; the
disclosure (`<details>`, closed; the groups; the lines; "+N more" to the
dossier through the existing `source=` and `option=` search parameters,
`OptionCard.tsx:88`, `ArtefactView.tsx:1418` (PA4-19)); the callout
reusing the exclusion callout's component; the Checks section, Examples,
Where tried, Tried on, the roles sentence and the outcomes table deleted
with their tests. *List:* the header's excluded link to `EXCLUDED_ANCHOR`;
the four facets and their state removed from `LonglistView.tsx` and
`longlistFacets.ts`; the row's grey line through the shared signal
function. *The removed API fields (PA4-11):* `OptionSummaryOut.where_tried`
and `.tried_on` (so `LonglistOut.options[]` changes; `LonglistOut`'s own
fields do not), `EvidenceProfileOut.where_tried`, `.tried_on` and
`.measures`, `OutcomeCountsOut.other`, `OptionOut.examples`; they are
removed in 30a and 30c with their readers, not in 25, so no in-between
card ships. *Fixtures:* `mock/fixtures.ts` and `mock/api.ts` updated in
the same commits.

### The order of the phases (PA4-6)

The sentence loop reads v4 records, folded programme names and the round-6
kinds, so it runs after them. The order is 24.0 → 24 → 25 → 27 → 27E → 28
→ 26 → 26L → 29 → 29F → 30a → 30c → 30b → 31. 25 can run beside 27
(different files: `repository.py`, `read_models.py` against
`interventions_records.py`, the prompt). 27E and 28 run after 27 (the
kinds and names are read on v4 records). 29 and 29F run after 26L because
29 shares `option_profile.py` and `longlist_backend.py` with 26. File
ownership per phase is named in the phase; two agents never hold one file.

### Phase 24.0 — Build-open baseline — `lead` (inline)

Full `make verify` on the branch head before any change; the figures in `verification.md`.

### Phase 24 — ADR 0040 amendment 4 — `lead`

Already written in the design phase; this phase checks it against the
seams as confirmed at the plan gate and amends it if a seam changed. Own
commit before 25. Gate: `make verify-fast`.

### Phase 25 — Read models, additive (R76, R81; S29, S29a, S30) — `deep-reasoner` · `fast-worker`

Files: `coverage.py` (the two signal keys), `where_tried.py` (the
resolver and its table), `repository.py`, `read_models.py`, the frontend
fixtures. `deep-reasoner`: the resolver, the signal keys in coverage and
in `_search_coverage`, the document-records helper for both document paths
and its tests. `fast-worker`: the output models (additions only), the
fixtures, `make openapi-sync`. No field is removed here. Gate: `make
verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify`. Commit.

### Phase 27 — Places (R87; S32) — `lead` · `fast-worker`

Files: `extract_interventions_prompt.py`, `interventions_records.py`,
`where_tried.py` (`COUNTRY_NAMES` extended), `coverage.py` (the unknown
count, the place key). `fast-worker`: the checks with tests on the
survey's cases and the extended table. `lead`: v4, the bump, the replays,
the rounds (record `27-places-loop.md`); stop measure M16; M1, M2 read
back; the unknown-country count per list reported. Gate: `make
verify-fast` · `prompt-guard`. Commit per round.

### Phase 27E — Example-name fold (R88; S33) — `fast-worker`

Files: `coverage.py`, `repository.py` (S30's name through the fold). The
function and its tests on the survey's cases. Gate: `make verify-fast`.
Commit.

### Phase 28 — Folding round 6 and the F4 guard (R86; S34) — `lead` · `fast-worker`

Files: `option_profile.py` (`_checked_folds`), `folding_prompt.py`, the
read-back script. `fast-worker`: the guard with tests. `lead`: the rules
in words, the round on the v4 replays, the seeded 30-fold read per facet
per list (record `28-folding-round-6.md`); stop measure M17. Gate: `make
verify-fast` · `prompt-guard`. Commit.

### Phase 26 — The place sentences (R80; S31) — `deep-reasoner` · `lead`

Files: `option_profile.py` (the second wave, the write), `longlist_backend.py`
(the call), `place_sentences_prompt.py` (new), `coverage.py` (the key),
`repository.py`, `read_models.py` (the field; the read-time template), the
replay tool, the fixtures. `deep-reasoner`: the input builder over the
abstract record input, the second wave, the trace check with one test per
rule and per hole named in PA4-8, the per-sentence ceiling, the template
with plural forms, the coverage write and the merge carry-through, the
read-time template, the provenance counts, the read model field.
`lead`: the wire's field descriptions and `place_sentences_v1` as round 0
in the same commit; the hash guard. Gate: `make verify-fast` ·
`prompt-guard` · `drift-check` · `openapi-sync`. Commit.

### Phase 26L — The sentence loop — `lead`

On v4 records with folded names and round-6 kinds. Tuning set then one
read of the check set; at most five rounds. Stop measure M15: zero
`failed_trace`, zero `failed_length` **and zero `failed_call`** on the
tuning set (PA4-9). Reported: the readability read, the plan's words, the
fold's words, no merit words, the template share, the wall-clock time of
the second wave per list (PA4-15). Record
`evidence/rounds/26L-place-sentences-loop.md`. Gate per round: `make
verify-fast` · `prompt-guard`. Commit per round.

### Phase 29 — "Who decides" and the authority (R89; S35) — `lead` · `fast-worker`

After 26L (shared files). Files: `option_profile.py`, `option_profile_prompt.py`,
`longlist_backend.py`. `fast-worker`: the consideration texts passed to
the line (the plumbing only; the data-block words are the lead's, PA4-12),
with a test. `lead`: the data-block wording and profile round 6 (record
`29-who-decides-round-6.md`); the two-sided M18 on refugees; the "within
your power" counts before and after on every tuning list. Gate: `make
verify-fast` · `prompt-guard`. Commit. **Waits on the owner's answer on
S35.**

### Phase 29F — The feature rule (R77; PA4-5) — `lead`

Files: `longlist_cluster_prompt.py` (`design_features` for discovered
options, `:71`) and `runtime/option_design_prompt.py` (`option_design_v3`,
the user's own options). The rule in words in both; one round on the
replays; the count of features that restate the setting or the target
unit per list, before and after, reported (rubric box 73); re-pinned.
Gate: `make verify-fast` · `prompt-guard`. Commit.

### Phase 30a — The card: structure (R77–R82; S36) — `fast-worker`

The sections, the signal line, the lever lines, the lead-in, the opener,
the outcomes lines, the place block, the disclosure, the callout; the
removed blocks, their API fields (S36's list) and their tests deleted in
the same commit; the vitests of rubric boxes 72–76 (the card half), 78.
Gate: `make verify-fast` · `drift-check` · `openapi-sync` ·
`frontend-verify`. Commit.

### Phase 30c — The list: structure (R83–R85; S36) — `fast-worker`

The header, the facets removed with their state, code and the summary
fields they read, the row's signal; the vitests of box 79. Gate: `make
verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify`. Commit.

### Phase 30b — Card and list design and final words — `lead` (`impeccable`)

The signal line's words and weight; the lead-in template's prepositions;
the opener's and the groups' words; the tint of the plan's Where row (D23
open; box 76's tint vitest here, PA4-17); the disclosure's line lengths at
390 px; the callout; checked against the design pages. Gate: `make
verify-fast` · `frontend-verify`. Commit.

### Phase 31 — Live check, evidence, exit — `lead`

- Three live rapid runs (obesity, caregiving, refugees) on v4 records; read
  back from saved files: M15–M18 on the live lists; per option, evaluations
  and countries; per list, sentences generated vs template vs failed
  (trace, length, call), the second wave's wall-clock time, the
  unknown-country count, the "within your power" count, kinds per facet,
  the "not stated" count before and after.
- The browser check (desktop and 390 px): a rich, a thin and an empty option
  top to bottom; the signal line's four forms; the disclosure opened on the
  rich option and a wrong fold looked for and recorded; an added option's
  card (template sentences, document lines filled); the callout on
  caregiving's failing option; the list header with and without an
  excluded option; Group by; the grid unchanged.
- `verification.md` § Amendment 4: gates, commits, round records, the
  OpenAPI diff, the edited tests, the known limits, the figures above.
  Spec-change proposals 10–14 (the owner decides the wording).

Gate: **full `make verify`**. Commit.

### Checks for the loops (amendment 4)

| Check | Loop | Stop measure |
|---|---|---|
| Trace, length and call: zero `failed_trace`, `failed_length` and `failed_call` on the tuning set | 26L | **M15** |
| Outcomes in the plan's words; "on whom" in the fold's words where the kind fits | 26L | reported |
| No merit words; the strength word is the tier's word; the template share; wall-clock | 26L | reported |
| Readability: the lead reads every sentence of both sets; the count a reader would rewrite | 26L | reported |
| No `study_geography` that is an organisation, a person, a programme, a document, a date or an adjective; "not stated" before and after; unknown countries per list | 27 | **M16** (reported: the counts) |
| M1, M2 do not regress | 27 | reported |
| At most one wrong fold in a read of 30 per facet per list on v4 records; kinds per list; kinds the guard rewrote | 28 | **M17** |
| No kind restates a plan outcome (the guard, a test) | 28 | test |
| Every "within your power" option on refugees names a body that can adopt the option; the "within your power" count before and after on every tuning list | 29 | **M18** (two-sided) |
| The survey's duplicate example names fold to one; duplicates left on the check set | 27E | test (reported) |
| Features that restate the setting or the target unit, per list, before and after | 29F | reported |

### Known limits (amendment 4)

- An added option, and a merged-into option whose documents changed, show template sentences built at read time until the profile step next runs for the list.
- The trace check reads numbers, strength words and names against the place's input; a wrong relation between true facts is caught by the loop's read only.
- A wrong fold shows on the document line beside its title; the round lowers the count, it does not reach zero.
- The signal's countries and the place order rest on `study_country` and the document role, both model fields; a country the resolver does not know is shown as written.
- The authority label reads the "Who decides" sentence; S35 makes the sentence name the right body in the user's words, it does not make the label independent of the sentence.
- The year and the broken-title placeholder stay on document lines until the deferred Overton fix (R91).
- The "Who decides" sentence keeps its form ("The X must decide to …").

## Plan-review folds, amendment 4 (2026-10-09, `deep-reasoner` lane, 19 findings)

| # | Finding | Fold |
|---|---|---|
| PA4-1 | The signal would add per-option document queries to the list read | S29: computed in coverage, stored, read from the summary |
| PA4-2 | `countries_named` does not resolve "England"; aliases double-count | S29a: one resolver text → code → display name |
| PA4-3 | The "other" top level unhandled | S29: left out of the signal; S31: under "No single place"; **R80's words** (contract fold) |
| PA4-4 | "Not in `COUNTRY_NAMES` → not stated" would drop Tajikistan, Paraguay, Jordan, Lebanon | S32: kept as written and reported; the table extended from ISO-3166; **R87's words softened, to the owner** |
| PA4-5 | R77's feature rule had no phase | Phase 29F |
| PA4-6 | 27, 27E, 28, 29 cannot run beside 25 and 26 | § The order of the phases; file ownership per phase |
| PA4-7 | S35 circular: the label reads the sentence; box 83 untestable as worded | S35 rewritten: the consideration texts as context, a two-sided M18; box 83 reworded; **to the owner** |
| PA4-8 | The trace check's holes and false positives | S31: the three rules rewritten with the allowlist |
| PA4-9 | `max_length` on the wire fails the whole option; M15 blind to `failed_call` | S31: the ceiling in code per sentence; M15 includes `failed_call` |
| PA4-10 | The added-option paths missed | S29, S30, S31: `_search_coverage`, `_search_documents`, an abstract record input |
| PA4-11 | The removed fields' paths ambiguous; removals pulled into 25 | S36 lists the paths; removed in 30a/30c; 25 is additive; **the contract's "`LonglistOut` loses no field"** reworded |
| PA4-12 | Prompt text delegated (the data-block words; the wire descriptions) | The lead writes both; the wire lives in the prompt file |
| PA4-13 | `COUNTRY_ADJECTIVES` does not exist; "UK" is in `ABBREVIATIONS` | S33 names the sources and writes the adjective list |
| PA4-14 | The containment guard can create wrong folds and feed the signal | S34: whole words, Measures only, rewrites counted |
| PA4-15 | Place ids; a merge drops the key; wall-clock unreported | S31: `p1 … pN`; the merge carry-through and the read-time template; 26L and 31 report wall-clock |
| PA4-16 | The outcome total from a different plan version | S29: `outcomes_total` from the built-from plan; the Where likewise |
| PA4-17 | Box 76's vitests assigned to 26 | 30a (the block), 30b (the tint) |
| PA4-18 | `_clean` is the wrong function; the country match too narrow | S32: the place key in coverage; the resolver |
| PA4-19 | The dossier link's parameter | S36: `source=` and `option=` |

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
