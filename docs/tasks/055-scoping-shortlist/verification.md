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
| `make verify` (step-6 exit, full) | pass | on the gated snapshot `055bd662` = commit `7a8d0563`'s tree: okf-validate 174 concepts 0 violations · backend 3742 passed (14 min 51 s) · eval-check · infra test · audit-paths 202 files 0 violations · prompt-guard 36 unchanged · font-guard · drift-check OK · frontend typecheck, lint, 929 vitest passed, build |
| `make test` | pass | inside the above |
| `make typecheck` | pass | mypy 430 source files, no issues |
| `make lint` | pass | ruff, all checks passed |
| `make build` | pass | frontend build inside `frontend-verify` |

Every intermediate gate ran on a snapshot in the second worktree `../policy_atlas-gate` and the
commit was made only when the index tree still equalled the gated tree (six gates; the first exit
attempt was red at `prompt-guard` only, after the last ceiling edit; re-pinned and re-run green).

## Phase commits

| Phase | Commit | Gate |
|---|---|---|
| 0 | `9f77bf82` | baseline (above) |
| 1 | `83fa1bfd` | full `make verify` on snapshot `8543cfa0`: 3608 backend passed, 882 frontend passed, drift-check OK, prompt-guard OK |
| 2a + 3a + 5a (prompts) | `d1e4cd96` | shares the Phase 2 gate tree (snapshot `15620802`); the three lead-authored prompts were written before the plumbing was delegated, as the plan requires, and committed together with their re-pin |
| 3b | `612f3f80` | full `make verify` on snapshot `d17d465c` (3715 backend passed, 928 frontend passed, prompt-guard 36 unchanged, drift-check OK); shared with 5b and 6a |
| 5b | `9c71237e` | shares the Phase 3 gate tree (the plan's Phase 5 full gate ran here, before Phase 4; Phase 4 closes on `verify-fast` and the step-6 exit's full gate) |
| 6a | `ef3c63f0` | shares the Phase 3 gate tree |
| 4 (+ lead edits: step wording, view polish, walk kind, Potential impact round 2) | `257faff8` | `verify-fast` + `prompt-guard` + `openapi-sync` (clean) + `drift-check` + `frontend-verify` on snapshot `572b58af` (3741 backend, 929 frontend); the Phase 5 full gate ran before Phase 4 (above), so Phase 4 is covered by the step-6 exit's full gate |
| 7–8 (prompt rounds, the ceiling, evidence, deferred) | `7a8d0563` | full `make verify` on snapshot `055bd662` (3742 backend, 929 frontend) |
| 8 (this file's closing lines) | _the commit after `7a8d0563`_ | docs only |
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
wire description; `option_profile_v4` keeps its name (it has not shipped) and is re-pinned. 

**Round 2** (all seven tasks, one attempt each, 204 lines): 10 lines at or near the cap and cut
mid-word, 8 of them on obesity-deprived; several of those stop short of 400 without a full stop. That
showed the real cause: `max_length=400` on the wire makes the constrained decoder stop at the limit
mid-word instead of failing the attempt (the plan P13 assumed a longer answer would fail). **Round 3**
removes `max_length` from the wire and enforces the 400-character ceiling in the code check (a longer
answer fails the attempt; the existing one retry applies), with the prompt's 300/380 rule unchanged.
Flagged as a plan-assumption correction (minor; the contract's rule "under 400, a longer answer fails
the attempt" is now true). Reading 3 is reported below.

**Round 3** (all seven tasks, one attempt each, 204 lines, longest 397, mean 344 characters; no
over-ceiling retry happened): 0 lines cut or over 400; every line ends with a full stop. Hand reading
of the check set (reading 3; 75 lines) and a re-read of the tuning set: all hold the form; the code
word-check finds no hit. Per task (round 3): neet 37 lines, tokens 14,150/3,222, 47 s · heat-pumps 43,
14,284/3,579, 49 s · caregiving 24, 12,176/2,989, 47 s · obesity 25, 11,652/3,518, 53 s · refugees 23,
9,450/3,285, 52 s · obesity-deprived 24, 12,318/3,815, 60 s · social-cohesion 28, 12,503/2,406, 39 s.

**M4 = 75 / 75 lines on the three check tasks in conditional form naming a pathway and a reach, no
claim of effect** (reading 3, after the code-check fix; reading 1 was 71 / 75 with four lines cut at
the wire cap). The loop ran three rounds: words (round 1, no change needed), length headroom (round
2), the ceiling moved from the wire to a code check (round 3).

#### Stage 1b — the shortlist (Phase 7b)

Driver: `evidence/run_shortlist_check.py` (gitignored) against the local dev stack: per task it
patches the appetite `tried_only → mostly_tried → open_to_untested` through `PATCH /plan` (each
change opens a shortlist walk), waits for the walk, and reads back the places, reasons, note and
provenance into `evidence/proposals/<slug>-<appetite>.json`; `measures.json` holds M2 (code), M3, M5
and M6.

**Round 1, tuning set (12 proposals).** All 12 walks succeeded with five places; wall 10–26 s per
proposal; input 115k–164k characters (ceiling 400k; no document line cut). M3 (code, from the picks'
rungs): 12 / 12 match the appetite's mix. M2 (code): 8 hits, all the word "works" inside the permitted
conditional "if it works"; read by hand, 0 breaches. M1 (hand): 60 / 60 reasons name a fact on the
card (a design feature, the lever type, the rung, an evaluated country, the outcome borne on). One
defect in a note: caregiving / open_to_untested named the changed places by their short ids ("o12 and
o17 remain …"), which the reader never sees. **Round 2** adds one note rule to `shortlist_v1`: "Name
options by their names, never by their ids" (re-pinned; the version name keeps, it has not shipped).

**Round 2, tuning set (12 proposals; round-1 files kept in `evidence/proposals-round1/`).** All 12
succeeded with five places; wall 9–27 s; input 117k–164k characters, 0 document lines cut. M3: 12 /
12. M2: 8 hits, all "if it works" conditionals; 0 breaches. M1 (hand): 60 / 60 reasons name a card
fact. Notes: 0 ids; every note says what the set leaves out and, at a re-proposal, which places
changed and why, by name. Round 2 changed no reading on the tuning set, so the loop ended there and
the check set was run once with `shortlist_v1` as now committed.

**Check set (12 proposals: three appetites × 3 tasks + a second `mostly_tried` on each; A21).** All
12 succeeded with five places; wall 10–20 s; input 101k–131k characters; 0 cuts; 1 attempt each. The
24 proposals of the staged check = the 12 round-2 tuning proposals + these 12 (`evidence/proposals/`
holds all 24; `measures.json` is computed over them).

#### Measures (read back from `evidence/measures.json` and the proposal files)

| # | Measure | Result | Pass? |
|---|---|---|---|
| M1 | Reasons that name a fact on the option's card (hand) | 120 / 120 reasons across the 24 proposals (60 tuning round 2 + 60 check) | pass |
| M2 | Reasons or notes using study count, tier, "works", "effective", "proven", "promising", "strong/weak evidence", "studies" | code: 15 hits over 120 reasons + 24 notes, every one the word "works" inside the permitted conditional "if it works"; hand: 0 breaches | pass |
| M3 | Proposals whose mix matches the stated appetite (S4) | 21 / 21 first proposals (the script's rule: tried_only = all picks Evaluated/Reviewed; mostly_tried = 1–2 untested of 5; open_to_untested = at least one Evaluated/Reviewed anchor) | reported |
| M4 | Potential impact lines in conditional form, naming a pathway and a reach, no claim of effect | 75 / 75 on the three check tasks (reading 3; reading 1 was 71 / 75, see above) | pass |
| M5 | Per proposal (24): input characters 100,675–164,389 (mean 131,344); input tokens 19,601–31,717 (mean 25,872); output tokens 546–1,731 (mean 857); model time 8.5–26.8 s (mean 13.5 s); wall 9–27 s; document lines cut 0; baseline characters cut 0; attempts 1. Cost (Langfuse, by run id, 24 / 24 matched): USD 0.111–0.182 per proposal, mean 0.150, 3.59 in all; beside the longlist walk's per-run cost of USD 3.29–4.32 after task 046's amendment 2 (046 verification M7) | reported; 0 cuts as expected |
| M6 | Same picks between the two `mostly_tried` proposals of one check task | 9 / 15 (obesity-deprived 4 / 5, refugees 3 / 5, social-cohesion 2 / 5) | reported |
| M7 | User places and set-asides preserved across a Rebuild and an appetite change (live task) | 2 / 2 checks: appetite change (2 user places kept, 0 of 4 set-asides re-proposed) and Rebuild after an outcome change (same) | pass |

The ceiling (400,000 characters) is far above what a 25–43 option list produces (≈165k); the
contract's estimate "about 55k tokens for 25 options" is close to the measured 20k–32k.

#### Stage 2 — the live rapid run in the browser (M7)

New task on 2026-10-27, the team question "How can we reduce loneliness among people aged 75 and over
who live alone in England?", rapid depth, opened at `http://localhost:5173` through Claude in Chrome.
Screenshots in `evidence/live-shots/` (gitignored).

1. **Planning conversation.** The opening message said "Rapid scoping please, and I am open to the
   biggest ideas even if untested"; the Task Agent (`task_agent_scoping_v6`) read both: "I've set this
   up for Rapid scoping and an ambitious shortlist that can include untested ideas". The plan document
   showed Risk appetite = "Include the biggest ideas, even untested" and step 3 "Shortlist" with the
   new blurb. Two turns to ready.
2. **Baseline walk** ran and paused (about 5 minutes); the plan was confirmed against it.
3. **Longlist walk** (18 options in 5 themes) ended in the `shortlist` step. The profile step failed
   once on its first attempt (two Potential impact lines of 405 and 427 characters failed the strict
   400 code check twice; the runner's retry succeeded) — the cause of the ceiling fix recorded above;
   with the fix the same lines would have been kept with a warning. The proposal appeared in the
   Shortlist mode without any click: 5 places, every reason naming a card fact, the note "No place is
   devoted to an Inform-only approach; Social connection education would cover that lever. Both plan
   outcomes are covered, but none of the proposed places has been evaluated in England." The running
   card read "The shortlist is proposed · Read the shortlist"; History read "Policy Atlas proposed 5
   places."
4. **Remove** on a pick: 5 → 4 places; the option moved to Other options (set aside, no refill).
5. **Add** "Digital connection packages": 4 → 5, grouped under "Added by you".
6. **Suggest more at five:** one place added (6 places, about 15 s); buttons disabled while the walk
   ran; the note rewritten and naming the removed option by name.
7. **Remove** two picks (6 → 4), **Add** "Community group activity programmes" (→ 5), **Remove** one
   pick (→ 4): 2 user places, 2 picks, 4 set-asides.
8. **Suggest more at four:** filled one (→ 5); the new pick was not a set-aside.
9. **Appetite change** to "Mostly tried, one or two new" from the header select: "Shortlisting…"
   shown, a shortlist walk opened at once (`opened_run` on the patch), and the proposal was re-made:
   both user places kept, 5 places, one pick changed, none of the four set-asides re-proposed. The
   Rebuild control did not appear (appetite only). **M7 check 1: pass.**
10. **Outcome change** (a third outcome through `PATCH /plan`): version 3, `opened_run = null`,
    `plan_inputs_changed = true`, `stale = false`; the plan document showed "Longlist built from plan
    version 1 · the plan has changed · Rebuild longlist". **Rebuild** pressed.
11. **After the Rebuild** (the whole chain re-ran, about 10 minutes; the longlist grew to 28 options
    with the third outcome; `plan_inputs_changed = false`, `stale = false`): both user places kept
    (`added_by_you`), all four set-asides kept (`set_aside`) and none re-proposed, three picks
    proposed around the user's places (two of the previous three kept, one replaced), the note naming
    the change by option name. **M7 check 2: pass. M7 = 2 / 2.**

Known gap found in the live check: the **baseline check-in card's settings summary** (Who · Where ·
Outcomes · Depth, served by the backend's check-in bundle) does not list the risk appetite; the plan
document beside it does. Not in the contract's surface map; recorded in `docs/deferred.md`.

### Prompts (rubric 11)

Three prompt files changed; every other hash in `scripts/prompt_hashes.json` is unchanged. The
texts are in the tracked files (commit `d1e4cd96` and the rounds after it); the hash diff from the
branch base `e3e60392`:

| File | Version | Hash before → after |
|---|---|---|
| `options_scoping/option_profile/option_profile_prompt.py` | `option_profile_v4` | `d02c7843…` → `57da8122…` (three rounds: words; length headroom; ceiling moved to code) |
| `options_scoping/shortlist/shortlist_prompt.py` (new) | `shortlist_v1` | — → `d0077c39…` (two rounds: the names-not-ids note rule) |
| `runtime/task_agent_scoping_prompt.py` | `task_agent_scoping_v6` | `c08fdab0…` → `82036a24…` |

### OpenAPI diff (since `e3e60392`, regenerated by `make openapi-sync`)

New paths: `POST /api/v1/tasks/{task_id}/options/{option_id}/shortlist`, `…/unshortlist`,
`POST /api/v1/tasks/{task_id}/shortlist/suggest`. New schemas: `MaturityOut`, `ShortlistOut`,
`ShortlistStateOut`. Changed (additive): `LonglistOut`, `OptionOut`, `OptionSummaryOut`, `PlanOut`,
`PlanStep` (the `shortlist` stage), `ProfileLineOut` (`potential_impact`), `ScopingConstraintOut`
(the aspect may name the ninth line), `ScopingPlanDraft`, `ScopingPlanPatch` (`risk_appetite`), the
four SSE frames (the stage enum).

### Migration round-trip

`tests/core/test_migration_055_shortlist.py` (upgrade → downgrade → upgrade on `b33ffb8c3a16`,
three plan versions, a placed option, a shortlist scope; the key stripped from every payload after the
downgrade) passes in every full gate above. `alembic heads` → `b33ffb8c3a16 (head)`.

## End-to-end command

The staged check, from the repo root with the dev stack up (`make dev`; the local compose Postgres
migrated to `b33ffb8c3a16`):

```
# the Potential impact line and the coverage keys on the seven stored tasks (live judgment model)
for t in neet heat-pumps caregiving obesity refugees obesity-deprived social-cohesion; do
  uv run --project backend python docs/tasks/055-scoping-shortlist/evidence/write_potential_impact.py --task $t
done
# the shortlist proposals through the API (three appetites per task; check tasks run mostly_tried twice)
uv run --project backend python docs/tasks/055-scoping-shortlist/evidence/run_shortlist_check.py \
  --role tuning --token-file docs/tasks/055-scoping-shortlist/evidence/token.txt
uv run --project backend python docs/tasks/055-scoping-shortlist/evidence/run_shortlist_check.py \
  --role check --token-file docs/tasks/055-scoping-shortlist/evidence/token.txt
```

The live browser check (stage 2) is described under § The staged check.

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
11. **Post-build contract amendment (owner, 2026-10-27, "Sounds good" to the lead's proposal): the
    Shortlist is its own Result view**, a fourth tab Baseline · Longlist · Shortlist · Report, not a
    third mode of the longlist (contract item 8, S23 "a third mode"). The page: the question as the
    title under the kind row "Shortlist"; a facts strip Places · Appetite (select) · The situation
    today → Baseline; the places in the two groups (A22 unchanged) as hairline rows with the reason
    first and one grey line (lever type · ambition · rung word · modifiers; the design mix stays on the
    card's Evidence section, off the row); Suggest more beside a link "Add more from the longlist →";
    the note; "Assess these N" disabled as the page's end. "Other options" is removed from the page:
    Add to shortlist lives on every longlist row, tile and card. The per-row word "Added by you" is
    dropped under the group heading of the same name. A finished shortlist walk links to
    `?view=shortlist`. Tests moved to `ShortlistView.test.tsx`.
    **Second round on the owner's feedback the same day:** each place shows the option's
    description, then "Policy Atlas's reason" under a small label; the "The situation today:
    Baseline" line is dropped (the owner's own O3 ruling, reversed on their word: "Do we really need
    the 'situation today baseline' thing at the top?"); the appetite select sits on the "Policy Atlas's
    picks" heading, since it is what it steers, and the facts strip is gone; the not-covered note is a
    labelled paragraph at the foot of the picks; "Suggest more" is the page's primary button (Assess
    is disabled) and "Add more from the longlist" a secondary button; the grey line is lever type plus
    the evidence footing in plain words ("Evaluated, including a review, not in England, last before
    2021" · "Described, not evaluated" · "Not yet tried anywhere"), ambition and the design mix
    staying on the card; Add to shortlist, Remove from shortlist, Exclude and Include again are icon
    buttons (four inline SVG glyphs in `ui/brand/ActionIcons.tsx`, no icon library in the app) with
    the action name as accessible label and tooltip, on the longlist rows, tiles and card too. Two of
    the owner's questions were left for their ruling, not built: a lower/middle/higher mark and a grid
    column for Potential impact (contract S22, A23 say no mark; a mark turns a labelled conditional
    into a ranking), and whether the rung overlaps the longlist's "N evaluated it · M more describe it"
    (recommendation: longlist rows keep the counts; the rung is the shortlist's and the card's word).
    **Third round (owner, 2026-10-27): the three appetite answers reworded** after a wording
    discussion ("tried" blurs implemented with measured; "evidence" is what every option rests
    on; "evaluated" is the civil servant's word and does not collide because Policy Atlas *assesses*
    and documents *evaluate*). Contract S2's answers become stances with the mix as the clause:
    "Cautious: only options that have been evaluated somewhere" · "Balanced: mostly evaluated, plus
    one or two not yet evaluated" · "Ambitious: the biggest ideas, even those never implemented"
    (ladder 1: the cautious set stays evaluated-only, S4 unchanged). The control is named "Risk
    appetite" and sits in the actions row beside Suggest more, the two controls that re-propose. The
    rung's words become "Proposed, not yet implemented" · "Implemented, not yet evaluated" ·
    "Evaluated" · "Evaluated, including a review" on the rows, the card and the card text the model
    reads; the Task Agent's offer and its free-text parser take the stance words;
    `task_agent_scoping_v6` and `shortlist_v1` re-pinned (neither has shipped).
    Gate: `make frontend-verify` and the full `make verify` on the final snapshot (below).
12. **A missing longlist answers the generic 404** (`not_found`) on Suggest more, not a `no_longlist`
    code: the app's 404 handler hides whether a task exists (the existing access-control rule), so the
    contract's named 404 code cannot reach the client. The frontend's `no_longlist` sentence is unused.
13. **Add to shortlist on a merged option answers 409 `not_included`** (the shared lookup had to admit
    merged rows for this one action); Remove on a merged option stays a 404.
14. **The local dev database was migrated to `b33ffb8c3a16`** by the driver-script delegate (needed for
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

- The contract's rulings S1–S26 and amendments A1–A30, O1–O5, PG1–PG4 are the authority; the plan's
  decisions P1–P17 fix the seams. Where the build found a plan assumption wrong (the wire cap; the
  baseline reader; the stage key), it took the smaller as-built-consistent route and flagged it above.
- Prompt versions `option_profile_v4`, `shortlist_v1` and `task_agent_scoping_v6` kept their names
  through the build's prompt rounds because none had shipped; each round re-pinned the hash.
- The spec changes 1–9 and 4b–4c of the contract are **not applied**: each needs the owner's accepting
  words (owner-decides-spec-changes). The contract's wording stands as the proposal; the review
  conversation puts them to the owner.
- The seven stored tasks and the live task are the team's own test questions (A30); their option
  names and quoted reasons are public-safe.

## Known unverified items

- The `verify` workflow's conclusion on the branch head (rubric 15) is read after the push, which is
  the owner's step; the local full gate is recorded above.
- Cost per proposal was read from Langfuse by run id for all 24 proposals; the live task's walks were
  not costed.
- Proposal quality beyond the measures (whether the five picks are the five a policy analyst would
  read first) is not measured in this slice; shortlist recall after assessment is the deferred
  measure.

## Public safety

This file carries counts, option names, quoted reasons and notes from the team's test questions
only. The proposal JSONs, the Potential impact JSONs, the drive scripts, the dev token and any
screenshots are in the gitignored `evidence/` folder. No secret, trace or raw source text is in the
tracked tree.

## Review handoff (step-7/8 inputs)

- **Adjudication items:** the flagged deviations 1–13 in § Diff summary; the spec changes awaiting
  the owner; the three 409 sentences in `frontend/src/lib/errors.ts` (delegate's words).
- **Executor provenance (family flip):** Phases 1, 3b and 4 `deep-reasoner` (Opus); Phases 2b, 5b
  and 6a `fast-worker` (Sonnet); the drivers `deep-reasoner`; prompts, copy, the two Potential impact
  fixes, the shortlist note rule, `SCOPING_STEPS`, the walk kind and the view polish: lead. No Codex.
- **Diff-scoping exclusions:** `frontend/openapi.json`, `frontend/src/api/gen/types.ts` (generated);
  `backend/tests/api/fixtures/option_out_full.json` (fixture); `scripts/prompt_hashes.json` (re-pin).
- **Live-trace pointers:** Langfuse session id = task id for the seven stored tasks; static names
  `longlist:shortlist` and `option_profile:potential_impact`; the proposal JSONs carry each walk's
  `run_id`.
- **Knowledge candidates:**
  - Docker Desktop's engine stopped answering after six days up; every `docker` call (and so
    `make verify`) hung with no error. `docker desktop restart` from the shell recovered it
    without the GUI; a scripted quit-and-reopen of the app was refused by the permission mode.
  - A `max_length` on a structured-output wire field does not fail a long answer: the constrained
    decoder stops at the limit mid-word (and sometimes a few characters short of it). A character
    ceiling belongs in the code check after the call, with the target stated in the prompt — and on
    a spine step the code check must not be strict at the target: the live run produced 405- and
    427-character lines twice in a row and the strict check failed the profile step once (the
    runner's retry saved the walk). Target in the prompt, hard bound in code, warning in between.
  - uvicorn `--reload` waits for open connections before it restarts; the frontend's event stream
    (and the Vite proxy's keep-alive) holds one open, so a backend file save during a browser session
    leaves the dev server "Waiting for connections to close" until the stack is restarted.
  - A listwise model call that gets short ids will use them in free text (the note) unless told
    that the reader never sees them.
  - `test_every_depth_runs_the_same_pass_and_cuts_at_its_caps` asserted plan order over calls
    recorded in thread order; green on CI, red on an Apple laptop. Order-sensitive assertions over
    a thread pool need one worker in the test.
  - The gate-snapshot method (stage → `write-tree` → `commit-tree` → check out in a second worktree
    → gate → commit only when the index tree still equals the gated tree) held through six gates
    with three delegates editing the main tree; splitting one gated tree into several commits works
    with a temporary `GIT_INDEX_FILE` fed by `git ls-tree -r <gated tree> -- <paths>`. macOS `xargs`
    has no `-a`.
  - The Task Agent stub's `to_ready` helper is shared by many API tests; adding a plan part (the
    appetite) adds a turn for every one of them.
  - `_folded_coverage` copies only `outcome_counts`; recomputing stored coverage for a new key goes
    through `read_membership(...).coverage(...)` with the stored folds.
  - The app's 404 handler returns the generic `not_found` for every missing resource (the
    access-control pin), so a route cannot expose a named 404 code such as `no_longlist`.
  - The runner retries a failed model-calling step once on top of a component's own re-ask, so a
    degraded `shortlist` (or `theme`) walk can have made four model calls.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) (to be written in Phase 8).
