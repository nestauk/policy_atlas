# Verification: 055-scoping-shortlist

Evidence for the shortlist slice (contract, rubric and plan in this folder). Public-safe: counts,
option names and quoted reasons only; traces, read-backs and drive scripts stay in the gitignored
`evidence/` folder.

## Build-open baseline (Phase 0)

Branch head at open: `e3e60392` (ADR 0041 committed at step 4). `make verify` on 2026-10-27:
`4 failed, 3588 passed` in the backend suite.

- Three failures were `test_every_depth_runs_the_same_pass_and_cuts_at_its_caps[rapid|standard|deep]`
  (Evidence search sourcing). Pre-existing on this machine: the same three fail on the untouched
  `dev` head `eedf9ef9` in a second worktree, while CI's `verify` on that commit is green. Cause:
  the fake backends record calls in thread order and the test asserts plan order over eight
  threads. Fixed in the test only (one thread for that test), commit `9f77bf82`. No file under
  `evidence_search/` source changed.
- One failure, `test_an_intent_record_s_purpose_is_closed`, came from the Phase 1 delegate's
  in-flight schema change (the purpose check now admits `shortlist`) landing while the baseline
  ran; the test was updated in Phase 1.
- Docker Desktop's engine was wedged at open (every `docker` call hung); recovered with
  `docker desktop restart` before the baseline could run.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (step-6 exit) | _pending_ | |

## Phase commits

| Phase | Commit | Gate |
|---|---|---|
| 0 | `9f77bf82` | baseline (above) |
| 1 | `83fa1bfd` | full `make verify` on snapshot `8543cfa0`: 3608 backend passed, 882 frontend passed, drift-check OK, prompt-guard OK |
| 2a + 3a + 5a (prompts) | `d1e4cd96` | shares the Phase 2 gate tree (snapshot `15620802`); the three lead-authored prompts were written before the plumbing was delegated, as the plan requires, and committed together with their re-pin |
| 3b | `612f3f80` | full `make verify` on snapshot `d17d465c` (3715 backend passed, 928 frontend passed, prompt-guard 36 unchanged, drift-check OK); shared with 5b and 6a |
| 5b | `9c71237e` | shares the Phase 3 gate tree (the plan's Phase 5 full gate ran here, before Phase 4; Phase 4 closes on `verify-fast` and the step-6 exit's full gate) |
| 6a | `ef3c63f0` | shares the Phase 3 gate tree |
| 2b | `e771c16e` | `verify-fast` + `prompt-guard` + `openapi-sync` (clean) + `drift-check` + `frontend-verify` on snapshot `15620802`: 3630 backend passed, frontend green |

## Checks beyond the build

### Deterministic tests

_To be filled per phase._

### The staged check (item 13)

**The seven stored tasks** (team test questions, not user data; contract A30). Named here before
the first prompt round, as the plan requires:

| Slug | Role | Included options |
|---|---|---:|
| neet | tuning | 37 |
| heat-pumps | tuning | 43 |
| caregiving | tuning | 22 |
| obesity | tuning | 25 |
| refugees | check | 23 |
| obesity-deprived | check | 24 |
| social-cohesion | check | 28 |

Task ids are in `evidence/tasks.json` (gitignored).

#### Stage 1a — the Potential impact line (Phase 7a)

Driver: `evidence/write_potential_impact.py` (gitignored). For each task it recomputes the stored
coverage with the two new keys (so the maturity rung exists on stored lists) and runs only the ninth
line's call on the judgment model, writing `lines.potential_impact` into the stored `option_profile`.

Round 1 on the four tuning tasks (figures read from the driver's summary lines and the saved JSONs):

| Task | Options | Written | Attempts | Longest (chars) | Prompt / completion tokens | Wall (s) |
|---|---:|---:|---:|---:|---:|---:|
| neet | 37 | 37 | 1 | 384 | 14,131 / 3,983 | 54 |
| heat-pumps | 43 | 43 | 1 | 383 | 14,265 / 4,834 | 65 |
| caregiving | 24 | 24 | 1 | 355 | 12,157 / 3,158 | 45 |
| obesity | 25 | 25 | 1 | 382 | 11,633 / 4,144 | 55 |

Hand reading of the 129 lines against the contract's form (conditional magnitude · pathway against
the baseline · reach as "would apply to … tried on …" · evidence footing; no number, probability,
"works" as a claim, "studies" or "size of the prize"): all 129 hold the form. A code check over the
same words found only false positives (ages such as "16-to-24-year-olds"; "study" as a verb; "likely
to be owner-occupied" describing homes; "would apply through suppliers" for the reach). Round 1
changed no reading, so the loop ended after one round with `option_profile_v4` as committed. The
check set was then run (below, M4).

**Check set, reading 1** (refugees 23 · obesity-deprived 24 · social-cohesion 28 = 75 lines; one
attempt each; tokens 9,431/3,153 · 12,299/3,720 · 12,484/3,454; wall 45 · 53 · 49 s): 71 of 75 lines
hold the form in full. Four lines of obesity-deprived reached exactly 400 characters and were cut
mid-clause ("…recommendations, not", "…include evaluations in"): the prompt said "at most 400" and
the wire enforces 400, so the model filled to the cap. The lines are otherwise in form; the cut is a
prompt defect found on the check set. **Round 2** (flagged: a prompt change after a check reading)
gives the sentence headroom — "about 300 characters, never more than 380" in the system prompt and the
wire description; `option_profile_v4` keeps its name (it has not shipped) and is re-pinned. Reading 2
of the check set is reported below as it comes.

## End-to-end command

_To be filled._

## Diff summary

_Per-phase summaries are in the commit messages. The deviations below are the ones the review must
adjudicate (task-cycle-build § Step 5: minor, resolved within the contract's own vocabulary, flagged
here, not silent)._

### Flagged deviations and build-time decisions

1. **`longlist_result.shortlist` keeps its server default `'{}'`** (plan P3/PR1) where the contract
   § Constraints says "the default dropped after backfill". The plan is the later document; keeping
   the default avoids editing the longlist writer's insert. Contract text is out of date on this point.
2. **The stage key.** The `shortlist` component has its own stage key ("Shortlisting", "Proposing
   places for close reading.") instead of `select` with a per-registry override (contract PG3). Reason:
   every other scoping component (`theme`, `option_profile`, …) already has its own key, the registry
   guard tests assume `STAGE_BY_REGISTRY[c] == c`, and an override would have meant a new lookup at four
   call sites. The Evidence search's `select` words are untouched. Cost: one more value in a public enum
   (OpenAPI regenerated). Owner's call if the override is wanted instead.
3. **The baseline reader.** The component reads the baseline through the existing public
   `baseline_sections()` + `render_baseline_blocks()` (what every other longlist prompt reads), capped at
   20,000 characters with the cut counted (PG2). No new `baseline_text` helper was extracted from the
   chat renderer (plan P4/PR15): the public reader already existed.
4. **Picks are released at the final write, not before the call.** The harness commits a component's
   writes on a caught failure; releasing the previous picks before the model call would lose them on a
   degraded walk, which the contract forbids ("the previous places stay"). Clearing picks whose option
   was excluded or merged still happens first and stands (O1).
5. **`longlist_inputs` projects the ten fields of A6 exactly.** `question` is not among them although
   `suggest`, `constrain` and `theme` read it; a Task Agent re-approval that changes the question would
   not flag the longlist stale. The ten fields were fixed by the contract amendment; left as specified,
   raised for the review.
6. **Maturity's `where_country` is the plan the longlist was built from**, not the current plan, so the
   rung agrees with the coverage it is read from (the contract says "the plan's Where country").
7. **The Potential impact call's static Langfuse name** is `option_profile:potential_impact`, following
   the other profile calls' names, not `longlist:profile_potential_impact`.
8. **The appetite travels the seed and builder paths through wrappers in `task_agent_scoping.py`**
   (`_build_plan`, `_seed_draft`), because `scoping_plan.py` was under another delegate's edit at the
   time (PR11 satisfied; placement differs from the plan's P1 wording).
9. **The frontend reads the shortlist walk's purpose from the runs list** for the degraded notice
   (P17), since `LatestRun` carries no purpose. `walkKind` knows the `shortlist` purpose and stage; a
   finished shortlist walk links to `?view=longlist&mode=shortlist`, which the longlist view reads.
10. **Lead copy (Phase 6b), for the owner:** mode chip "Shortlist"; header "{N} places · Appetite
    [select]"; "The situation today: Baseline"; groups "Added by you" / "Policy Atlas's picks";
    place words "Policy Atlas's pick" / "Added by you"; "Add to shortlist" / "Remove from shortlist";
    "Suggest more" (disabled titles "A walk is running" / "Nothing left to propose"); "Press Suggest
    more to re-propose"; note label "What this shortlist leaves out"; "Assess these N" + "Assessment
    is not yet available."; "Other options"; empty "Policy Atlas is proposing a shortlist…"; degraded
    "Policy Atlas could not propose. Your places are unchanged."; rung words "Proposal only ·
    Described · Evaluated · Reviewed", modifiers "none in your setting", "most recent evaluation
    before {year}"; running card "Proposing a shortlist…" / "The shortlist is proposed"; step 3 of the
    plan "Shortlist — Policy Atlas proposes about five places for close reading, one reason each,
    mixed to your risk appetite. Add, remove, ask for more. Assessment of the shortlisted options is
    not in this release."; three 409 sentences in `lib/errors.ts` are the delegate's words.
11. **The local dev database was migrated to `b33ffb8c3a16`** by the driver-script delegate (needed for
    the staged check; additive, with a downgrade).

## Review findings

Added after the review stack (step 7).

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review:**
- **`/simplify`:**

## Rubric status

Filled by the review conversation.

## Intent & assumptions

## Known unverified items

## Public safety

## Review handoff (step-7/8 inputs)

- **Knowledge candidates:**
  - Docker Desktop's engine stopped answering after six days up; every `docker` call (and so
    `make verify`) hung with no error. `docker desktop restart` from the shell recovered it
    without the GUI; a scripted quit-and-reopen of the app was refused by the permission mode.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) (to be written in Phase 8).
