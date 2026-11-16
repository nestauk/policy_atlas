# Task contract: 055-scoping-shortlist

One implementation slice. It adds the **shortlist** stage to Options
scoping: when the longlist is built, Policy Atlas proposes about five
options for deep reading, with one plain reason each, and the user adds,
removes and asks for more. It is task 3 of the capability. Assessment,
which the capability spec bundled with the shortlist as "task 3", is split
off into the next task (owner, 2026-10-27: "Assessment seems like it could
get quite chunky").

> **Status:** drafted 2026-10-27 · lead; rulings S1–S25 taken from the
> owner in an interview the same day and quoted below. Three research
> reports informed the criteria (§ Read first). The owner read the draft;
> **the contract-stage adversarial review ran 2026-10-27** (`codex-rescue`,
> read-only; 30 findings, "material change needed"); 26 folded (§ Amendments
> from the review), five put to the owner and **ruled 2026-10-27** (O1–O5,
> S26). **Contract approved 2026-10-27 · owner ("Yes, approved").** **Plan
> approved 2026-10-27 · owner ("Yes")** after the plan-stage review (§ Amendments
> at the plan gate). **ADR [0041](../../adr/0041-options-scoping-shortlist.md)**
> — Accepted 2026-10-27. **Design phase closed; the build runs in a fresh
> conversation with `task-cycle-build`.**
>
> **Branching:** `task/055-scoping-shortlist` from `dev` at `eedf9ef9`
> (after PR #69 merged the longlist). PR target: `dev`, squash, per
> [options-scoping-staging-merge]. The `VITE_OPTIONS_SCOPING` production
> flag stays until shortlist **and** assessment land.
>
> **Inputs.** The options-scoping specs record pre-longlist thinking and
> are input, not authority (owner, 2026-10-27: "we shouldn't necessarily
> treat the specs as gospel as that was done pre longlist implementation
> and my thinking might have evolved since then"). Where a spec and a
> ruling below differ, the ruling wins and § Spec changes lists the edit
> for the owner to accept. The three research reports in `research/`
> (gitignored) are AI-written input, cited where a ruling rests on them.

## Goal

A user who has a built longlist gets a **proposed shortlist**: about five
options Policy Atlas judges most worth the user's and the tool's reading
effort, given the plan, the baseline, the user's **risk appetite** and the
full card of every option. Each place carries one reason in plain words
that the user can check against the card. The user adds and removes
places, asks for more, and changes the appetite; Policy Atlas proposes
again around the user's own picks and never removes one. The shortlist is
a provisional allocation of reading effort, not a verdict: no fused score,
no ordering, no claim about whether an option works.

The three ways a user fills the list (owner): "They pick all spots of the
shortlist themselves. They pick a 1 to a few and Policy atlas picks the
rest. Or policy atlas picks the whole shortlist." All three are one
mechanism (S6–S10).

## Deliverable

A PR into `dev` that lands items 1–14:

1. **Risk appetite on the plan** (S2, S3): one field, three answers in
   words, default the middle one; set at plan time and changed later from
   the longlist; an appetite-only change does not make the longlist stale.
2. **Shortlist state on an option** (S6–S10): *Policy Atlas's pick* (with
   its reason) · *added by you* · *set aside*; the actions *Add to
   shortlist* and *Remove from shortlist* on list rows, grid tiles and the
   option card.
3. **The `shortlist` component** (S11–S16): one model call over the full
   card text of every included option, the plan, the baseline, the
   appetite, the user's picks and set-asides; returns the picks with one
   reason each and a short *what this leaves out* note; code checks only
   the hard things.
4. **The shortlist walk** (S17): a one-component walk that re-proposes
   when the appetite changes or the user presses *Suggest more*; the
   longlist chain gains `shortlist` after `theme`, so a rebuild proposes
   again around the user's picks.
5. **Suggest more** (S8, S9): fills to five when fewer than five places
   exist; adds one place per press at five or more.
6. **The Potential impact line** (S19–S22): a ninth "What it would take"
   line on every card, written by `option_profile` from the mechanism, the
   reach, the ambition of the design and the user's outcomes as written.
7. **The maturity rung** (S18): *Proposal only · Described · Evaluated ·
   Reviewed*, with the modifiers *none in your setting* and *most recent
   evaluation before YEAR*, computed by code from coverage, on the card's
   Evidence section and on every shortlist row.
8. **The shortlist view** (S23): a third mode of the longlist beside List
   and Grid: the places with their reasons and maturity, Remove, Suggest
   more, the appetite as a control, the not-covered note, *Assess these N*
   present and disabled with one line, then *Other options* with *Add to
   shortlist*.
9. **Chat and plan surfaces**: the Task Agent offers the appetite in the
   planning conversation like depth (S26, A14); the plan document shows and
   edits it; `SCOPING_STEPS` and the Task Agent scoping prompt say the
   shortlist is built and assessment is not yet available.
10. **One alembic revision** (additive; § Constraints).
11. **ADR** (next free number): the shortlist as a model judgement over
    card text, bounded by hard checks; the appetite as a plan field; the
    shortlist walk.
12. **Tests** (§ Acceptance checks) and the stub backend's new queues.
13. **The staged check** (§ Acceptance checks): the seven stored tasks
    under three appetites, read by hand; one live rapid run in the
    browser.
14. **`docs/deferred.md` deltas** and the spec changes the owner accepts.

## Terms

| Term | Meaning |
|---|---|
| **place** | One slot on the shortlist, held by one option. A place is *Policy Atlas's pick* or *added by you*. Stored as `option.shortlist_state` (§ Constraints). |
| **proposal** | The set of places Policy Atlas fills in one call, with the not-covered note. Re-made at once on an appetite change and on Suggest more; after a Rebuild when a longlist input changes (A24). Each proposal is recorded by one `shortlist.proposed` event (A7). |
| **pick** | Short for *Policy Atlas's pick*: a place Policy Atlas filled. User-visible label: "Policy Atlas's pick". |
| **added by you** | A place the user filled. Never removed by Policy Atlas (S6). User-visible label: "Added by you". |
| **set aside** | An option the user removed from a place that Policy Atlas had filled. Not proposed again (S9). Not shown as a state; it only stops a re-proposal. |
| **Suggest more** | The one action that asks Policy Atlas for more places (S8). |
| **risk appetite** | The plan field `risk_appetite` with values `tried_only` · `mostly_tried` · `open_to_untested`; shown as the answers in S2. It sets the **mix** of tested and untested places (S4), never an ordering. |
| **mix** | How many of the proposed places have evaluating documents behind them and how many have none (the table in S4). |
| **maturity rung** | A code-computed word per option from coverage roles and evidence types: *Proposal only* (no document describes an implementation or evaluates it) · *Described* (an implementation is described; none evaluated) · *Evaluated* (at least one evaluating document) · *Reviewed* (at least one evaluating document whose evidence type is a review). With the design mix as text ("1 RCT, 2 observational") and two modifiers. Research report 2 § 8.4. |
| **modifiers** | Two facts beside the rung: *none in your setting* (no evaluating document in the plan's Where country) and *most recent evaluation before YEAR* (the newest evaluating document is older than `MATURITY_RECENT_YEARS`). |
| **Potential impact** | The ninth "What it would take" line: one conditional sentence on how big a difference the option could make to the user's outcomes if it works, reasoned from the mechanism, the reach and the baseline (S19–S22). A marked line since the review (lower · middle · higher, shown as the grid's last column; owner, 2026-10-27, at the step-9 decisions: "I think we should give the lower/middle/higher mark and grid column for this"; this replaces A23 and the plain-line words below). Key `potential_impact`. |
| **reach** | Who the option would apply to in the user's setting (read from the specified design against the plan's target unit) against who it has been tried on (the record units already on the card's document lines and place sentences). Not a stored field; the Potential impact sentence names it (S21). |
| **card text** | The option card serialised to text for the model by one shared builder from the same read model the frontend renders (`OptionOut`), so what Policy Atlas reads is what the user can see (S13). |
| **the not-covered note** | Two or three sentences from the same call on what the proposed set leaves out (a lever type, an ambition band, an excluded option that would have covered something) and, at a re-proposal, which places changed and why (S15). Replaces the spec's gap messages and warnings. |
| **shortlist walk** | A run whose chain is the one component `shortlist`, opened by an appetite change or Suggest more (S17). Shows under the existing stage key `select` ("Shortlisting"). |
| **longlist walk** | The existing run that builds the longlist (`LONGLIST_CHAIN`, `runtime/scoping_plan.py`). This slice appends `shortlist` to it. |
| **judgment model · mini model** | `LONGLIST_JUDGMENT_MODEL` and `LONGLIST_ASSIGNMENT_MODEL` in `options_scoping/longlist/longlist_backend.py`. The pick and the Potential impact line run on the judgment model (S14). |
| **S1 … S24** | The owner's rulings in this contract (§ Rulings). The rubric and the plan cite them. |
| **R-numbers, D-numbers, rulings 1–50** | Earlier slices' rulings: task 046 (R), task 045 (D), the concept rulings in the spec bundle. Cited where this slice changes them. |

## Read first

- [OS capability](../../specs/capabilities/options-scoping/capability.md) § Pipeline and gates,
  § Output structure (Longlist: list · grid · shortlist views; the card), the "Shortlist assembly
  is separate from screening" and "One shortlist action" items, § Open decisions (open question 2,
  the price envelope).
- [OS components](../../specs/capabilities/options-scoping/components.md) § 1 plan, § 6a
  option_profile, § 7 constrain (the reasoned guesses rule), § 8 shortlist, the chain diagram.
- [OS trust](../../specs/capabilities/options-scoping/trust.md) § Reasoned guesses, § Screening
  and shortlisting.
- Task 046 [contract](../046-longlist-refinement/contract.md): the card (R76–R82, amendment 4),
  the lines (R37–R47, amendment 2), the vocabulary rule R90; task 045
  [contract](../045-scoping-longlist/contract.md) D12 (the reduced grid) and the longlist actions.
- `docs/deferred.md` § task 045 seams (open question 7) and § task 046 seams.
- Research (gitignored, `research/`): `1-official-guidance.md` (Green Book "around five", pass/fail
  not scoring, the bracket shape, the demand for a visible discarded list), `2-risk-appetite-
  evidence.md` (the UK risk-appetite scale, the maturity rungs, the mix table, reasons as facts),
  `3-decision-science-procedures.md` (fused-score failure modes, LLM position bias, recall as the
  eval measure).
- Code: `runtime/scoping_plan.py` (`ScopingPlan`, `LONGLIST_CHAIN`, `compose_scoping`,
  `SCOPING_STEPS`), `options_scoping/theme/theme.py` (the component template),
  `options_scoping/option_profile/` (the lines), `options_scoping/longlist/coverage.py`,
  `api/readmodels/repository.py` (`option_out`, `longlist_out`), `api/routers/longlist.py`,
  `api/routers/task_agent.py` (`patch_plan`), `frontend/src/views/longlist/`,
  `frontend/src/views/workspace/planStart.ts`, `PlanDocument.tsx`.

## Surface map

What the slice touches, what it shows today, and what changes. "Keep" rows carry the same
weight as "change" rows.

| Surface | Today | After this slice | Item |
|---|---|---|---|
| Plan payload (`ScopingPlan`) | No appetite | `risk_appetite`, default `mostly_tried` | 1 |
| Plan document (`PlanDocument.tsx` · ScopingSettings) | Depth, steering | + "Risk appetite" with the three answers; a direct patch, no chat seeding | 1, 9 |
| "Rebuild longlist" state (`planStart.ts`) | `currentVersion > longlist.plan_version` | Uses `LonglistOut.plan_inputs_changed` (server-computed; ignores appetite) | 1 |
| `option` row | No shortlist state | `shortlist_state`, `shortlist_reason` (A22: no timestamp column) | 2, 10 |
| `evidence_scope.purpose` check | baseline · longlist · variant · targeted | + `shortlist` (A1) | 4, 10 |
| `coverage[oid]` | evidence types over all documents; no year | + `evaluating_evidence_type`, `latest_evaluation_year` (A3) | 7 |
| List rows (`LonglistView`) | Exclude · Include again | + Add to shortlist · Remove from shortlist; a "Policy Atlas's pick" / "Added by you" word on the grey line | 2 |
| Grid tiles (`LonglistGrid`) | Reduced grid (045 D12: no shortlist state) | + the same word and action | 2 |
| Option card (`OptionCard.tsx`) | Exclude · Include again | + Add/Remove from shortlist; the maturity rung in the Evidence opener; the Potential impact line in "What it would take" | 2, 6, 7 |
| Longlist modes | List · Grid | List · Grid · **Shortlist** | 8 |
| `LONGLIST_CHAIN` | … constrain, theme | … constrain, theme, **shortlist** (not spine) | 4 |
| Purposes / chains | baseline, longlist, targeted, acquire-only | + `SHORTLIST_PURPOSE` → `(("shortlist", False),)` | 4 |
| `longlist_result` | themes, coverage, judgements, guesses, option_profile, counts, provenance | + `shortlist` JSONB (the note, provenance) | 3, 10 |
| `option_profile` lines | 8 lines (6 marked, 2 plain) | 9 lines: + `potential_impact` (plain) | 6 |
| `OptionSummaryOut` | … | + `shortlist` (state, reason, at), `maturity` | 2, 7 |
| `LonglistOut` | … | + `shortlist` (note, provenance, `places_target` = 5), `plan_inputs_changed` | 3, 8 |
| Routes (`routers/longlist.py`) | get longlist, get option, add, exclude, include | + `POST /{task_id}/options/{option_id}/shortlist`, `…/unshortlist`, `POST /{task_id}/shortlist/suggest` | 2, 5 |
| `patch_plan` | Mints a version; 409 when a run is active | Also: appetite-only change opens a shortlist walk when a longlist exists | 1, 4 |
| `SCOPING_STEPS` step 3 | "Shortlist and assessment … Not in this release." | "Shortlist" built; "Assessment … not in this release" | 9 |
| Task Agent scoping prompt + `ScopingPlanDraftWire` | Offers depth; describes the steps | + offers the appetite as three labelled options with stable ids; `risk_appetite` on the draft wire; the step wording (`task_agent_scoping_v6`) | 9 |
| Stage vocabulary | `select` = "Shortlisting" exists | `shortlist` registry name maps to `select` | 4 |
| Chat verbs (`longlist_turns`) | add · exclude · include_again | **Keep.** No shortlist verbs by chat (⏸ deferred) | — |
| Rebuild longlist | Re-runs the whole chain | **Keep.** Picks survive by option id; the chain now ends in a proposal (S5) | 4 |
| Evidence search components | — | **Keep.** No file under `evidence_search/` changes | — |
| Excluded options | Shown struck through with the reason | **Keep.** Not candidates for a place | — |

## Rulings (owner, 2026-10-27)

Quoted from the design interview. Each later section cites these.

| # | Ruling | Owner's words |
|---|---|---|
| S1 | **Shortlist and assessment are separate tasks.** This slice is the shortlist only; assessment is the next task. | "Do you think we should split the shortlisting and assessment into separate tasks? Assessment seems like it could get quite chunky" → agreed. |
| S2 | **Risk appetite is stated in the plan and changeable later.** Three answers in words: *Only options tried elsewhere* · *Mostly tried, one or two new* · *Include the biggest ideas, even untested*. Default: the middle. Never inferred from the plan's wording. | "Stated in the plan, but let the user change it later"; D1 "Sounds good". |
| S3 | **Why appetite matters.** | "sometimes the biggest, most ambitious changes are the least evidenced, due to their scope they might not have actually been tried but are mentioned in grey literature, these would suit users with a higher risk appetite. Users with lower risk appetite might only want to consider options that have been tried elsewhere." |
| S4 | **Appetite sets the mix, never an order.** *Tried elsewhere only*: every pick has at least one evaluating document, a comparable setting preferred. *Mostly tried*: three or four picks Evaluated or Reviewed, one or two Proposal-only or Described, from the Bigger band or an uncovered lever type. *Biggest ideas*: one Evaluated anchor; the rest chosen for ambition and lever spread, untested allowed. The mix is a rule in the prompt, not enforced by code (S16). | D2 "Ok". |
| S5 | **Re-propose at once on any change; keep the user's picks; say what changed.** Appetite change, plan change (through Rebuild) and Suggest more all re-propose. User-added places are never touched. | "Yes, re-propose straight away and keep my picks". |
| S6 | **About five by default; not a plan setting; the user adds past it.** | "About five by default, let me add more"; "No I don't think the user should say the longlist length at plan time, I think 5 is a good default." |
| S7 | **Removing a place does not refill it.** A shortlist of three is a valid shortlist. | "The user might want to remove an option because they want less than 5 assesments. so the spots should[n't] necessarily auto fill". |
| S8 | **Suggest more: fill to five, then one at a time.** Under five places: one press fills the open places up to five. At five or more: one press adds one pick with its reason. | "some users might realise that there's lots of good options and they'd like to assess more. But I don't think PA should always suggest multiple. It should be one at a time after 5". |
| S9 | **The whole list is proposed without any click; a removed pick is set aside.** The first proposal comes at the end of the longlist walk. | "What if they just want the whole shortlist proposed? Would they have to click suggest more for each slot?" → no; set-aside agreed in the same thread. |
| S10 | **Update-in-place of the longlist is out; Rebuild stays.** An appetite change bypasses Rebuild. Picks survive Rebuild by option id. | "What does that even mean to rebuild in place? Do we really need to worry about this?" → no. |
| S11 | **Policy Atlas picks by model reasoning over every option card.** Not a rule ladder, not a model-filled criteria table. | D3 "I think we should make use of model reasoning here, and it should read the options cards of every option in the longlist. So something like C sounds like it could work. Your proposal sounds a bit convoluted though". |
| S12 | **No enforced spread checks, no per-option "why not" sentences.** The lever and ambition spread is a preference in the prompt; the not-covered note replaces gap messages. | D5 "Do we really need this? Feels like unneccessary complexity"; D6 "a lot of the reasons will be arbitrary". |
| S13 | **The pick reads the full card of every included option**, the same content the user sees, not counts or summaries. | "it would read pretty much all the content in the options cards for every option right? We should make sure it has enough in its context to make an informed decision." |
| S14 | **Judgment model**, not the mini model, for the pick and for the Potential impact line. | Lead's rule, stated to the owner with S13; not objected. |
| S15 | **One reason per place, citing a card fact; the not-covered note.** Reasons never use study count, quality tier, or any claim that the option works. | Lead's folding of D3/D6 and research report 3 § 6; "That sounds better". |
| S16 | **Code checks only the hard things:** picks kept, set-asides not proposed, ids exist and are included, the count is right, reasons present. One re-ask, then the walk degrades and the previous proposal stays. The list goes to the model shuffled. | D3 ("convoluted") → the simplified version accepted: "That sounds better." |
| S17 | **Re-proposal runs as a shortlist walk.** | Lead's as-built decision (components run only in walks); recorded for the owner's review. |
| S18 | **The maturity rung** from counts and evidence types only, with the two modifiers. | D4 "Ok". |
| S19 | **Potential impact is a reason to pick.** Not taking potential into account "feels counter-productive"; policy analysts name it as a shortlist factor. | "Don't you think that users would want the options with the most potential to be the ones that are shortlisted? … When asking policy analysts, they mentioned 'the size of the prize' as being an important factor in shortlisting." |
| S20 | **Never the words "size of the prize".** The line is called **Potential impact**. | "I don't think we should literally use the words size of the prize that was just an analogy"; "Yes, go with Potential impact". |
| S21 | **Reasoned from the mechanism, not from outcome mentions.** The sentence reasons how the option, as specified, would act on the drivers the baseline names for the user's outcomes as written; the reach (would apply to, against tried on); the scale of the change. For an untried option this is the model's reasoning from general knowledge, labelled as such like the legal-change line (046 R38). | "just reasoning impact based on outcomes being named seems a bit coarse. For ambitious options that haven't been tried yet, outcomes might not even be mentioned never mind measured"; "what if an option was tried and worked in a subset of a population but could potentially work on wider populations". |
| S22 | **No effect comparison at the shortlist; no proxy for hard-to-measure outcomes; direction of effect stays with assessment** (046 R42 not reopened). A reason may say "bears on trust in services, which the records rarely measure". | "What about differences in outcome effects and different measures. What about things that aren't as easily measurable." → the lead's three answers accepted with "go with Potential impact". |
| S23 | **The shortlist view before assessment**: places with reasons and maturity, Remove, the not-covered note, Other options with Add to shortlist; **Assess shown disabled** with one line. No verdict columns. | "Yes, show the Assess button disabled". |
| S24 | **No Reach line on the card.** 046 removed *Tried on* as a block for density (amendment 4, D6, D10) and the data still show per document and per place; the missing half (would apply to) lives inside the Potential impact sentence. | "I think it does show the populations/unit somewhere still right?" → yes; one new line only. |
| S25 | **Re-proposal runs as a shortlist walk** (promotes S17 from the lead's as-built decision to a ruling). | "The walk is fine". |
| S26 | **The review's open items O1–O4 as proposed; O5 = (b): the Task Agent offers the appetite in the planning conversation, like depth.** | "I'll take your proposals for all except 5, let's go with (b)". |

## Amendments from the review (2026-10-27)

The contract-stage adversarial review (`codex-rescue`, read-only) returned 30 findings,
verdict "material change needed". The lead checked the code claims of findings 1–6, 12, 14 and
16; they hold. Resolutions below; the sections they touch are edited in place. Four findings
(A2, A7, A9, A10) needed the owner and are ruled in the right-hand column.

| # | Finding (short) | Resolution |
|---|---|---|
| A1 | `ck_scope_purpose` admits only baseline · longlist · variant · targeted (`core/schema.py:416-437`) | The migration replaces the check constraint to add `shortlist`; the downgrade restores it after clearing shortlist-purpose scopes' purpose to null. § Constraints. |
| A2 | A user place can be merged away or excluded at a Rebuild; constrain protects user-held *exclusion* state only (`constrain.py:848-875`, `longlist.py:1096-1129`) | **Owner: as proposed (O1).** An `added_by_you` place is user-held: never merged away and never folded by discovery; constrain still screens it and a breach shows on it, but the place stays (capability spec: "An option the user added keeps its place through re-runs; screens still run on it and their finding shows on it"). A pick (Policy Atlas's) that constrain excludes or merges is cleared before the chain's `shortlist` proposes again. |
| A3 | Coverage counts evidence types over all documents and holds no year; the review type's exact name | Coverage gains `evaluating_evidence_type` (types over evaluating documents only) and `latest_evaluation_year`; the review type is `"Systematic Review and Meta-Analysis"`. JSONB keys, no migration. § Potential impact and the maturity rung. |
| A4 | `patch_plan` returns inside its transaction; opening a walk needs commit first (`task_agent.py:1494-1545`) | The patch commits the version, then an opener runs as `confirm_baseline` → `_open_confirmed_longlist` does; if the opener is refused (`run_active`, capacity), the response carries the new version with `opened_run = null` and a `shortlist_pending: true` flag the view shows as "Press Suggest more to re-propose". § The user's actions. |
| A5 | The shortlist walk's own scope has no `longlist_result` row | `shortlist` resolves the task-wide newest `longlist_result` (`latest_longlist` without `scope_id`) and locks it `FOR UPDATE`; no row → `ShortlistFailure` ("no longlist"). § The component. |
| A6 | "Every field except `risk_appetite`" is not a safe staleness rule | A `longlist_inputs(plan)` projection: `intended_change`, `target_unit`, `where`, `outcomes`, `depth`, `constraints`, `your_options`, `your_context`, `linked_task_ids`, `removed_defaults` (the fields `compose_scoping` reads). `plan_inputs_changed` = projection(current) ≠ projection(the longlist's pinned version). Older payloads project with defaults. § The user's actions. |
| A7 | Overwriting columns loses the shortlist assembly record the spec requires (capability § Output structure) | One append-only event per proposal, `shortlist.proposed`, payload: places (option id, name, state, reason), the note, appetite, plan version, prompt version, model, the walk id. User actions already append events. No new table. **Owner: as proposed (O2).** |
| A8 | The trust rules "asserted effects are grounded" and "scoping does not forecast" are not in § Spec changes | Added as spec change 4b: a labelled conditional magnitude ("large if it works"), bound to a pathway and a reach, is permitted on the card and in a reason; an unconditional magnitude, a probability, or a number is not. |
| A9 | The spec's fixed "Do nothing / the situation today" reference is absent from the shortlist view | **Owner: as proposed (O3).** One line above the places, "The situation today: Baseline" linking the baseline artefact; never a place. |
| A10 | Unattended mode cannot pass the "Assess these N" gate while Assess is disabled | **Owner: as proposed (O4).** Spec change 8: unattended Options scoping ends after the shortlist proposal until assessment lands; the plan's steps say so. |
| A11 | The note may name excluded options but the model sees only counts | The model receives one line per excluded option: name, primary lever type, ambition, the exclusion reason. § The component, In. |
| A12 | The card renders callouts the serialiser does not list | Card text matrix added: in: the no-in-scope-evidence line, the search-pending line, the constraint callouts (judgements and guesses in words); out: the exclusion block (excluded options are not candidates), action buttons, the documents' links. A golden test renders a fixture `OptionOut` with every conditional block and asserts each block's words appear once. § The component. |
| A13 | A token ceiling needs a tokenizer | A character ceiling: `SHORTLIST_INPUT_CHARS_MAX` = 400,000 (about 100k tokens on the judgment model's tokenizer; measured in the build). Cut rule: the document lines of every option are trimmed from the oldest year upward, one line per option per round, until under the ceiling. No new dependency. |
| A14 | "Set at plan time" vs a Task Agent that cannot ask for the appetite | **Owner: (b)** (S26). The Task Agent offers the appetite in the planning conversation the way it offers depth: three labelled options with stable ids (`APPETITE_OPTION_IDS`, the pattern of `DEPTH_OPTION_IDS` in `task_agent_scoping_prompt.py`), `ScopingPlanDraftWire.risk_appetite` set only after the user chose one or asked in their own words (`_appetite_from`, the pattern of `_depth_from` in `task_agent_scoping.py`), the stub backend's options for tests, and the default `mostly_tried` when the user does not choose. `task_agent_scoping_v6` carries the offer and the step wording. The plan document still shows and patches it later (S2). |
| A15 | The downgrade rewrites plan payloads; call it lossy | § Risk tier: the downgrade is lossy for `risk_appetite`; one `UPDATE plan SET payload = payload - 'risk_appetite'` over every row; the round-trip test seeds three plan versions. |
| A16 | "Same rule as Exclude" is a parentless walk or a dispatch reservation | Wording fixed: `admit_longlist_action` as built. The shortlist walk is parentless, so it blocks the actions while it runs. |
| A17 | The mock API returns 404 for new routes | The mock gains stateful handlers for the three routes and the appetite patch, with the 409 cases. § Constraints, Frontend. |
| A18 | The three routes lack bodies, responses and status semantics | Route table added. § The user's actions. |
| A19 | = A2 | See A2 / O1. |
| A20 | M1–M4 "pass" contradicts M3 "not a gate" | Prose fixed: M1, M2, M4 and M7 pass; M3, M5 and M6 reported. |
| A21 | M6 needs runs the procedure does not define | Three extra runs: the `mostly_tried` appetite on three check-set tasks, run twice (24 proposals in all). |
| A22 | `shortlist_at` order can read as a ranking | Places shown grouped: Added by you, then Policy Atlas's picks; alphabetical within each. `shortlist_at` dropped (the event carries the time). Three new columns, not four. |
| A23 | "In the grid" contradicts "no new column" | "and in the grid" removed. |
| A24 | "Re-made whenever the plan changes" vs appetite-only walks | Terms fixed: at once on an appetite change; after Rebuild on a longlist-input change. |
| A25 | One label map for the three answers | `RISK_APPETITE_LABELS` in `planVocabulary.ts`, used by both controls; tested for all three values. |
| A26 | Denominators for M1, M4, M7 | M1: reasons passing / all reasons across the 24 proposals. M4: lines passing / all options on the three check-set tasks. M7: a seeded live task with two user places and one set-aside; 2 checks (Rebuild, appetite change). |
| A27 | The shuffle test is not reproducible | Two named seeds; both exact orders asserted. |
| A28 | "`gh run list` green" is not tickable | Rubric 15: the `verify` workflow's conclusion on the branch head SHA, URL recorded in `verification.md`. |
| A29 | The sense-check branch has a different shortlist rule | Stated: explore branch only; the sense-check composition (rulings 25, 37) stays deferred with the branch itself. |
| A30 | Public evidence rule | The seven stored tasks and the live task are the team's test questions (NEET, obesity, refugees, caregiving…), not user data; option names and quoted reasons are public-safe for them, as 046 did. A task of a real user is never used. |

### Ruled by the owner 2026-10-27 (O1–O5; S26)

| # | Question | Ruling |
|---|---|---|
| O1 | At a Rebuild, what happens to a place you added when constrain excludes or merges that option? | As proposed: never merged; the place stays; the breach shows on the row (the spec's existing rule). |
| O2 | One `shortlist.proposed` event per proposal as the assembly record? | As proposed: yes (no new table; History shows "Policy Atlas proposed 5 places"). |
| O3 | "The situation today: Baseline" as one fixed line above the places? | As proposed: yes. |
| O4 | Unattended runs end after the shortlist until assessment lands? | As proposed: yes, recorded as a spec change. |
| O5 | Does the Task Agent ask for the appetite when it proposes the plan (b), or does it start at the default and get chosen in the plan document (a)? | **(b).** See A14. |

## The component: `shortlist` (items 3–5)

- **In.** The plan (question, intended change, target unit, where, outcomes as written,
  constraints with their kind and limit, your context, `risk_appetite`); the baseline artefact's
  text; every included, unmerged option as **card text** (S13), in a shuffled order (S16); the
  user's current places marked *keep* (added by you) with their card text; the set-asides marked
  *do not propose*; one line per excluded option: name, primary lever type, ambition, exclusion
  reason (A11); the previous proposal, when there is one (its picks and note), so the note can
  say what changed (S5); the number of places to fill. The component resolves the task-wide
  newest `longlist_result` (`latest_longlist` with no `scope_id`) and locks it `FOR UPDATE`
  for the write; no row → `ShortlistFailure` (A5).
- **Places to fill.** At the end of a longlist walk and at an appetite change:
  `max(0, PLACES_TARGET − user places)`, where `PLACES_TARGET = 5` (S6); existing picks are
  released and refilled. At Suggest more: `PLACES_TARGET − places` when under five, else 1 (S8).
  Zero places to fill still writes the note.
- **Out.** The picks: `{option_id, reason}` each; the not-covered note. Written to
  `option.shortlist_state = "proposed"` and `shortlist_reason`, and
  `longlist_result.shortlist = {note, provenance}` on the task-wide newest row; then one
  `shortlist.proposed` event with the full assembly (places with state and reason, the note,
  appetite, plan version, prompt version, model, run id) as the record the spec asks for (A7).
  Before a chain proposal at a Rebuild, a pick whose option constrain excluded or merged is
  cleared; an added-by-you place is never merged or folded and stays through an exclusion,
  with the breach shown on its row (A2, O1).
- **The prompt carries** (lead-authored, hash-pinned, `shortlist_v1`): the purpose (an
  allocation of reading effort, not a verdict); the mix table for the stated appetite (S4); a
  preference for a spread of lever types and ambition (S12); potential impact, reach, fit with
  the plan's constraints and preferences, and which outcomes the option bears on as the things
  to weigh (S19, S21); the reason rules (S15): one or two sentences, plain words, names a fact
  on the card, never study count, quality tier, "works", "effective", "strong evidence",
  "promising", "proven"; a conditional ("if it works") where it speaks of potential; the note
  rules (S15, S5); the vocabulary rule (046 R90: "evaluated", "documents", never "studies" in
  authored copy).
- **Code checks** (S16): every id is an included, unmerged option of this task; no set-aside;
  no user place re-proposed; the count equals the places to fill (or every candidate, when
  fewer remain); every reason is non-empty and under `SHORTLIST_REASON_MAX_CHARS` (400). On a
  failed check the call is repeated once with the failure named; a second failure raises
  `ShortlistFailure`, the walk ends `degraded`, and the previous places stay. Nothing else is
  enforced (S12).
- **Card text** (S13): one builder, `option_card_text(OptionOut, lines=...)`, in the read-model
  package, rendering what `OptionCard.tsx` renders, in the card's order (A12):

  | Block | In the card text |
  |---|---|
  | Header: name, origin, relations, also found as, the evidence signal | yes |
  | The no-in-scope-evidence line; the search-pending line | yes, in their words |
  | How it works: description, design features, lever line with its reason | yes |
  | What it would take: ambition and reason, the nine lines with marks, the setting | yes |
  | Constraint callouts: judgements (verdict, constraint, reason) and guesses (leaning) in words | yes |
  | Evidence: your-outcomes lines, place sentences, the maturity rung and modifiers | yes |
  | Document lines: title, programme, place, tried-on kind, outcome, evidence type, tier, year | yes (the only block the ceiling cuts) |
  | The exclusion block | no (excluded options are not candidates) |
  | Action buttons, links, the documents' URLs, the Documents disclosure state | no |

  A golden test renders a fixture `OptionOut` with every conditional block present and
  asserts each block's words appear once. A field the user cannot see never reaches the
  model. When the serialised input would exceed `SHORTLIST_INPUT_CHARS_MAX` (400,000
  characters; about 100k tokens, measured in the build; no tokenizer dependency, A13), the
  document lines are trimmed one per option per round, oldest year first, until under the
  ceiling; the cut is counted in provenance and shown in the note's footer ("Policy Atlas
  read N of M document lines").
- **Static Langfuse name** `longlist:shortlist`; usage event `longlist.shortlist.usage`;
  `models` and `prompt_versions` recorded in `longlist_result.shortlist.provenance` and the
  walk's `component.completed` summary `{"component": "shortlist", "filled", "kept",
  "set_aside", "input_tokens", "document_lines_cut"}`.

## The user's actions (items 2, 5)

| Route | Body | Returns | Refusals |
|---|---|---|---|
| `POST /{task_id}/options/{option_id}/shortlist` | none | 200 `OptionOut` | 404 unknown option; 409 `run_active` (A16: a parentless walk or a dispatch reservation, as `admit_longlist_action` rules today); 409 `not_included` for an excluded or merged option. Repeating on an added place is a no-op 200. |
| `POST /{task_id}/options/{option_id}/unshortlist` | none | 200 `OptionOut` | 404; 409 `run_active`; repeating on an option with no place is a no-op 200. |
| `POST /{task_id}/shortlist/suggest` | none | 202 `OpenedRunOut` (the existing opened-run shape) | 409 `run_active`; 409 `nothing_to_propose` when every included option holds a place or is set aside; 404 `no_longlist`. |

- **Add to shortlist**: sets `added_by_you`; a previous pick on the same option becomes
  `added_by_you` (the user has now chosen it).
- **Remove from shortlist**: a pick becomes `set_aside`; an added-by-you place clears to no
  state. No refill (S7).
- **Suggest more**: opens a shortlist walk (S8, S25).
- **Appetite change**: `PATCH /plan` with `risk_appetite` changed mints a plan version as
  today. When a longlist exists, the route **commits the version first, then** opens a
  shortlist walk through the same opener `confirm_baseline` uses (A4); the response's
  `opened_run` names it. If the opener refuses (`run_active`, capacity), the response carries
  the new version and `opened_run = null`; the shortlist view's derived `shortlist.stale`
  (PG1) then shows "Press Suggest more to re-propose". `plan_inputs_changed` on `LonglistOut` is
  `longlist_inputs(current) ≠ longlist_inputs(pinned)`, where `longlist_inputs(plan)` projects
  `intended_change`, `target_unit`, `where`, `outcomes`, `depth`, `constraints`,
  `your_options`, `your_context`, `linked_task_ids`, `removed_defaults` — the fields
  `compose_scoping` reads — and older payloads project with defaults (A6). The frontend's
  Rebuild state reads it instead of comparing version numbers (S10).
- **Exclude** of an option holding a place clears the place (an excluded option cannot be a
  candidate). **Include again** does not restore it.
- Events: `option.shortlisted`, `option.unshortlisted` with the actor, like
  `option.excluded` today (`decided_by: user`); the component's picks appear through
  `component.completed`, not per option.

## Potential impact and the maturity rung (items 6, 7)

- **Potential impact** is the ninth key in `LINE_QUESTIONS`, plain (no mark), written in the
  same whole-list call pattern as the other lines on the judgment model. Its call receives,
  beyond the per-option payload the other lines get: the plan's outcomes as written, the
  target unit and Where; the baseline text; per option the record units (tried on) and the
  evaluated countries and role counts. The sentence: a magnitude in plain words bound to a
  condition ("large if it works"; "moderate if scaled"), then the pathway against the
  baseline's drivers, then the reach (would apply to, against tried on), then the evidence
  footing in one clause ("the records describe proposals only"). The prompt asks for about 300
  characters and never more than 380; a line over `POTENTIAL_IMPACT_MAX_CHARS` (400) is kept with
  a warning and only a line over `POTENTIAL_IMPACT_HARD_MAX_CHARS` (600) fails the attempt, because
  the profile step is a spine step (owner, 2026-10-27, at the step-9 decisions: "I'll take your
  recommendations"; the review's deviation 15). The line's label on the card is "Potential impact".
  **Review amendment (owner, 2026-10-27):** the line carries a mark like the six marked lines —
  `less` · none · `more`, shown as Lower · Middle · Higher — written after the sentence by comparing
  the options of the list on their conditional potential, and the grid gains a Potential impact
  column (A23 withdrawn; the owner's words: "I think we should give the lower/middle/higher mark
  and grid column for this"). The magnitude is a labelled
  conditional, never an unconditional claim, a probability or a number (A8; spec change 4b).
  `OPTION_PROFILE_PROMPT_VERSION` → `option_profile_v4`.
- **The rung** is computed in coverage (`coverage.py`). Coverage gains two keys (A3):
  `evaluating_evidence_type` (`{type: n}` over documents whose role is `evaluated`) and
  `latest_evaluation_year` (the newest `year` among them, or null). Reviewed when
  `evaluating_evidence_type` holds `"Systematic Review and Meta-Analysis"` (the classify
  vocabulary's review type, `core/schema.py` `EVIDENCE_TYPES`); Evaluated when
  `role.evaluated > 0`; Described when `role.described > 0` or `role.recommended > 0`;
  Proposal only otherwise (including options with no document, which keep the card's "No
  document names this option yet." line). The design mix is `evaluating_evidence_type` as
  text. Modifiers: *none in your setting* when `role.evaluated > 0` and the plan's Where
  country is not among `evaluated_countries`; *most recent evaluation before YEAR* when
  `latest_evaluation_year` is older than `MATURITY_RECENT_YEARS` (5) before today. Served as
  `OptionSummaryOut.maturity`. No model call; no migration (JSONB keys; older rows compute
  the rung at the next coverage write and read as "not yet computed" until then). The words
  are authored copy under R90.

## The shortlist view (item 8)

A third mode, **Shortlist**, in `LonglistView`'s mode switch. Top to bottom:

1. Header: "N places" · the appetite as a control ("Appetite: Mostly tried, one or two new ·
   Change"), which patches the plan and so re-proposes (S5); while a walk runs, the existing
   activity line shows "Shortlisting".
2. One fixed line, "The situation today: Baseline", linking the baseline artefact; never a
   place (A9, O3).
3. The places, grouped **Added by you** then **Policy Atlas's picks**, alphabetical within
   each group so no order reads as a ranking (A22); each a row: the option name (link to the
   card) · lever type · ambition · the maturity rung with modifiers · the reason (or "Added by
   you") · a breach notice when constrain excluded a user place (O1) · Remove from shortlist.
4. **Suggest more** (label "Suggest more"; disabled while a walk runs or nothing is left to
   propose, with the reason as its title).
5. The not-covered note, under the label "What this shortlist leaves out".
6. **Assess these N** — present, disabled, with one line beneath: "Assessment is not yet
   available." (S23).
7. **Other options**: the included options not holding a place, grouped as the list mode
   groups (Theme · Lever type), each row with its grey line and *Add to shortlist*. Excluded
   options are not listed here (they have their own section in List mode).

Empty states: no longlist → the mode is absent; a longlist with no proposal yet (walk running)
→ the places list shows "Policy Atlas is proposing a shortlist…"; a degraded proposal → the
previous places with a notice "Policy Atlas could not propose; your places are unchanged."

The design of these rows follows the list rows (R85) and the card's grey lines; no new visual
language. Copy follows the copy-text principle: labels over explainers.

## Spec changes (proposed; the owner decides each before it is applied)

Applied only on the owner's word, in accepted wording, with one line each in
`docs/specs/log.md`.

1. OS capability § Pipeline and gates and § "Shortlist assembly is separate from screening":
   **five places by default** with lever and ambition spread as a preference (replaces ruling
   20's "one place per primary lever type"); reasons may cite potential impact, reach, outcomes
   borne on, plan fit and the appetite (widens ruling 37); the appetite field; Suggest more;
   the not-covered note (replaces gap messages and warnings); the 🟡 for task 3 (R47) resolved
   as "the profile lines, including Potential impact, feed the pick" (S19–S21).
2. OS capability § Output structure: the shortlist view before assessment (S23); the Assess
   button disabled; the ninth card line; the maturity rung on the Evidence opener.
3. OS components § 1 plan: `risk_appetite`. § 6a option_profile: the ninth line, its inputs.
   § 8 shortlist: rewritten to this contract (one call over card text; the hard checks; the
   shortlist walk). The chain diagram: `theme → shortlist`, and the shortlist walk.
4. OS trust § Reasoned guesses and § Screening and shortlisting: **labelled reasoned estimates
   on the card may inform the pick** when stated as conditionals (amends ruling 19's "guesses
   must not feed the proposal"); what stays out is any claim of reported effect,
   cost-effectiveness or evidence strength, study count and quality tier.
4b. OS trust § Principles ("asserted effects are grounded"; "scoping does not forecast") and
   the "structurally impossible" rule (A8): a **labelled conditional magnitude** on the card
   and in a reason ("large if it works", bound to a pathway and a reach) is permitted; an
   unconditional magnitude, a probability, a number or a forecast of what will happen is not.
   The Potential impact line is the model's reasoning, labelled like the legal-change line.
4c. OS capability § Output structure: the fixed "The situation today: Baseline" line on the
   shortlist view before assessment (A9, O3); the explore branch only — the sense-check
   branch's shortlist composition (rulings 25, 37) stays deferred with the branch (A29).
5. `vocabulary.md`: place · Policy Atlas's pick · added by you · set aside · Suggest more ·
   risk appetite · maturity rung · Potential impact · the not-covered note.
6. `docs/deferred.md`: update-in-place stays deferred (S10); chat verbs for the shortlist;
   shortlist recall as an eval measure (research 3 § 4); a comparability rule for settings;
   inferring appetite; abstract-level direction of effect (046 R42, still with assessment).
7. Decision sheet / concept rulings 6, 19, 20, 37: decision column updated.
8. OS capability § Unattended mode (A10, O4): an unattended Options scoping run ends after the
   shortlist proposal until assessment lands; the plan's steps say so.
9. OS capability § Output structure: the `shortlist.proposed` event as the shortlist assembly
   record (A7, O2); History shows "Policy Atlas proposed N places".

## Amendments at the plan gate (2026-10-27)

The plan-stage review ([plan.md](plan.md) § Plan-review folds) changed four details of this
contract. None changes a ruling.

| # | Earlier text | Now |
|---|---|---|
| PG1 | `PlanOut.shortlist_pending` (A4) | No flag. `LonglistOut.shortlist.stale: bool`, derived: the latest proposal's appetite differs from the plan's, or a built longlist has no proposal. The view says "Press Suggest more to re-propose" when true. |
| PG2 | The ceiling cuts document lines only | The baseline text is capped at 20,000 characters for the pick (and 12,000 for the Potential impact call); a cut is counted as `baseline_chars_cut` and named in the note's footer beside the document-line count. The whole request is under the ceiling or the proposal fails with a named error — never a silent truncation. |
| PG3 | Registry `shortlist` under stage `select` with its shared words | Still under `select` for the stage key; its label and blurb are a per-registry override ("Shortlisting", "Proposing places for close reading.", words at 6b) because the shared blurb "The strongest, most varied set" is a ranking claim. **Built as its own stage key `shortlist`** with those words (verification.md deviation 2); accepted by the owner at the step-9 decisions, 2026-10-27 ("I'll take your recommendations"). |
| PG4 | "21 proposals" in § Verification evidence | 24 proposals (21 + the three second `mostly_tried` runs of A21). |

## Scope / Out of scope

- **In:** items 1–14 as the surface map states them; one migration; the ADR; tests; the staged
  check; `docs/deferred.md` deltas; the spec changes the owner accepts.
- **Out, to the assessment task:** the Assess action's behaviour; the verdict columns and the
  comparison table (6c); full-text fetch; direction of effect; the price envelope (open
  question 2).
- **Out, deferred (S10, S12):** update-in-place of the longlist and the removal of Rebuild;
  enforced spread checks; per-option "why not" sentences; a shortlist size setting; inferring
  appetite; shortlist verbs by chat; a comparability rule for settings; a Reach line (S24).
- **Out, rejected:** a model-filled criteria table (research 3 procedure B); a rule ladder
  (procedure A); a pairwise tournament (procedure C's tie-break); auto-refill on removal (S7);
  "Suggest more" adding several at once past five (S8); a "Propose for me" switch.
- **Out, other:** any change under `evidence_search/`; any Evidence search output; the grid's
  columns; the list row's grey line beyond the one place word; the Langfuse naming scheme.

## Constraints & approval gates

Approval is this contract's sign-off.

- **Schema (one alembic revision on head `f1b6d3a8c2e5`):** `option` gains `shortlist_state`
  Text nullable with a check constraint over `("proposed", "added_by_you", "set_aside")` and
  `shortlist_reason` Text nullable (A22: no timestamp column); `longlist_result` gains
  `shortlist` JSONB NOT NULL default `'{}'` (the default dropped after backfill, as
  `e9a4c1f7b3d2` did); `ck_scope_purpose` on `evidence_scope` is replaced to admit
  `shortlist` (A1). Downgrade: drops the three columns; sets `purpose = NULL` on shortlist
  scopes and restores the old check; and **strips `risk_appetite` from every `plan.payload`**
  (`payload - 'risk_appetite'`), which is lossy for that field (A15). No other value rewrite;
  no new table. The plan payload gains `risk_appetite` with a default, so stored plans
  validate unchanged (JSONB; no migration). The `option_profile` JSONB gains the
  `potential_impact` key; old rows read as "no line" and the card hides it, as it hides the
  other lines before a profile exists. Coverage gains two JSONB keys (A3).
- **Stored data / staging:** options scoping is on staging. Existing longlists stay readable:
  null shortlist state reads as "no place"; a list with no `shortlist` row data shows the
  Shortlist mode with no places and Suggest more enabled. No staging wipe.
- **Runtime egress:** the same hosts and verbs as today. One new call per proposal on the
  judgment model with card text for up to 25 options (about 55k tokens; measured in the
  build); one new whole-list line call in `option_profile`. The baseline text and the plan
  reach the inference route in both, as they do today for suggest and typing.
- **Public interface, additive only:** `risk_appetite` on `ScopingPlan`, `ScopingPlanPatch`
  and `PlanOut`; `shortlist` (with `stale`, PG1) and `maturity` on
  `OptionSummaryOut`; `shortlist` and `plan_inputs_changed` on `LonglistOut`;
  `potential_impact` in `ProfileLineKey`; the three routes of § The user's actions with
  their refusal codes; three event types (`option.shortlisted`, `option.unshortlisted`,
  `shortlist.proposed`); the registry name `shortlist` under stage `select`. OpenAPI
  regenerated by `make openapi-sync`; `risk_appetite` on `ScopingPlanDraftWire` (S26).
- **Prompts (lead-authored, hash-pinned):** `shortlist_v1` (new); `option_profile_v4` (the
  ninth line); `task_agent_scoping_v6` (the appetite offer and the step wording; S26). All
  other prompts keep their hashes.
- **Runner / chains:** `LONGLIST_CHAIN` gains `("shortlist", False)` after `theme`;
  `SHORTLIST_PURPOSE` and its one-step chain; the five registration points
  (`OPTIONS_SCOPING_STEPS`, `COMPONENT_REGISTRY`, `LLM_BEARING_COMPONENTS`,
  `_SCOPING_STEPS`, `build_graph`) and `STAGE_BY_REGISTRY`. The Evidence search graph and
  the park-and-resume path are not touched.
- **Frontend:** no new dependency; the existing mode switch, action button and grey-line
  patterns; one label map `RISK_APPETITE_LABELS` in `planVocabulary.ts` for both controls
  (A25); the mock API gains the new fields **and stateful handlers for the three routes and
  the appetite patch, with their 409 cases** (A17), in the same commits (046 C9 precedent).
- **Dependencies, CI, auth, production config:** none. The `VITE_OPTIONS_SCOPING` flag is
  unchanged.

## Public / private boundary

Contract, rubric, plan, ADR and `verification.md` are public-safe. The research reports,
the read-backs of the 24 proposals, traces and any drive script stay in the gitignored
`research/` and `evidence/` folders. `verification.md` carries counts, option names and the
reasons as quoted sentences only.

## Model route

OpenAI under the approved controls, behind the `LonglistBackend` seam (`OpenAILonglistBackend`
live, `StubLonglistBackend` in tests). The pick and the Potential impact line on the judgment
model (`LONGLIST_JUDGMENT_MODEL`, S14); nothing moves to the mini model. The build records
the measured input tokens and cost per proposal on the seven stored tasks beside the per-run
cost of the longlist walk.

## Disciplines binding this slice

- **Screening is not ranking.** No score, no order, no "most promising" (concept rulings 6,
  19, 37 as amended by spec change 4).
- **A reason is a checkable fact plus, at most, a labelled conditional.** Never study count,
  quality tier, or a claim that the option works (S15).
- **The user's places are never removed by Policy Atlas** (S5, S6). A set-aside is never
  proposed again (S9).
- **What Policy Atlas reads is what the user can see** (S13).
- **Flag, don't drop.** A thin option is a candidate; the maturity rung says how thin.
  Excluded options are not candidates but are counted in the note.
- **Honest absence.** The note's footer states any document lines cut from the input; the
  rung says "in the documents we found" where it would otherwise read as a fact about the
  world (research 2 § 8.5).
- **Owner decides spec changes.** Vocabulary under 046 R90.

## Known limits accepted

- **Position and run-to-run variation.** One call, shuffled input; a second run can pick a
  different fifth option. Recorded, not fixed; the eval measure is recall after assessment
  (deferred).
- **Reasons are the model's words.** The prompt requires a card fact; code does not verify
  the citation (S12, S16). The hand reading in the staged check is the measure.
- **The mix is a prompt rule.** A proposal that breaks the stated mix is shown as it is; the
  build reads the 24 proposals and reports how often it happens (M3).
- **Potential impact rests on model reasoning**, as the legal-change line does (046 R38),
  labelled as such.
- **Maturity depends on retrieval**: "Proposal only" means no evaluating document among the
  documents we found.

## Stop conditions

Halt and escalate when: a schema change beyond § Constraints is needed; the card text does not
fit the judgment model's input limit even after the document-line cut; the Potential impact
line cannot be written without a mark or a second call; a change to any file under
`evidence_search/` seems needed; the appetite-only plan change cannot be told apart from a
longlist-input change with the version mechanism as built; scope would grow into assessment.

## Acceptance checks

- `make verify` green.
- **Deterministic tests** (stub backend; one test DB per agent):
  - migration round-trip; null shortlist columns read as no place; an old `option_profile`
    row without `potential_impact` renders eight lines.
  - item 1: a plan with no `risk_appetite` validates to `mostly_tried`; an appetite-only
    patch mints a version, leaves `plan_inputs_changed` false and opens a shortlist walk when
    a longlist exists, no walk when none exists; the version is committed before the opener
    runs, and after a refused opener `LonglistOut.shortlist.stale` is true (A4, PG1); an outcome change sets
    `plan_inputs_changed` true and opens no walk; `longlist_inputs` projects an older payload
    with defaults (A6); the migration round-trip seeds three plan versions and the downgrade
    strips the key from each (A15).
  - items 3, 4: the longlist chain ends in `shortlist` after `theme`, not spine; a failed
    `shortlist` ends the walk `degraded` with themes stored and previous places kept; the
    shortlist walk runs the one component; the stage frame is `select`; the registry, the
    harness graph and the plan mapping know `shortlist`.
  - item 3 checks: an id outside the included options, a set-aside id, a user place, a wrong
    count and an empty reason each cause one re-ask then `ShortlistFailure`; two named seeds
    give two known, different orders (A27); excluded options are never candidates and reach
    the input as one line each (A11); the golden card-text test (A12); the character ceiling
    cuts document lines oldest-first, one per option per round, only over the ceiling, and
    counts the cut (A13); the component reads the task-wide newest `longlist_result` from a
    shortlist-purpose scope (A5); the `shortlist.proposed` event carries the full assembly
    (A7).
  - item 3 places: at the end of a longlist walk with two user places, three are filled; with
    five user places, none, and the note is written; a previous pick not re-proposed is
    cleared (not set aside); user places are untouched; at a Rebuild, a user place whose
    option constrain excludes keeps its place with the breach served, and is never merged or
    folded (O1); a pick whose option is excluded or merged is cleared before the proposal.
  - item 5: Suggest more with three places fills two; with five, one; with six, one; 409 when
    nothing remains or a walk is active.
  - item 2: Add on a pick turns it `added_by_you`; Remove on a pick sets `set_aside` and does
    not open a walk; Remove on an added place clears it; Exclude clears a place; Include again
    does not restore it; events carry the actor.
  - item 6: `potential_impact` is a plain line in `LINE_QUESTIONS`; its call receives the
    baseline text and the outcomes as written; the version string is `option_profile_v4`;
    the prompt hash guard passes.
  - item 9: the Task Agent's plan proposal carries the three appetite options with their
    ids; a user turn choosing one by marker or in their own words sets the draft's
    `risk_appetite`; no choice → `mostly_tried`; the stub backend offers the options
    (`test_task_agent_scoping_prompt`, `test_task_agent_scoping` patterns for depth).
  - item 7: the rung for each of the four cases and both modifiers from fixture coverage;
    "Proposal only" for an option with no document; the review evidence type yields Reviewed.
  - frontend (vitest): the Shortlist mode renders places, reasons, rung words, Remove, Suggest
    more (and its disabled states), the note, the disabled Assess with its line, and Other
    options with Add; list rows and grid tiles show the place word and action; the card shows
    the ninth line and the rung; the plan document shows and patches the appetite; the Rebuild
    state reads `plan_inputs_changed`.
- **Prompt hashes:** `shortlist_v1`, `option_profile_v4`, `task_agent_scoping_v6` pinned;
  every other hash unchanged.
- **No AI eval in this slice.** Proposal quality is read by hand (below). Shortlist recall
  after assessment is recorded in `docs/deferred.md` for the eval slice.
- **The staged check:**
  1. **Stored, the seven tasks.** The Potential impact line written for every option by a
     one-off script that runs only the new line call over the stored lists (no search, no
     rebuild; script in the gitignored evidence folder); then a shortlist walk per task under
     each of the three appetites (21 proposals), plus a second `mostly_tried` walk on each of
     the three check-set tasks for M6 (24 proposals in all; A21). Prompt tuning in the build
     uses four of the seven; three are read once as the check set, figures reported as they
     are. The stored tasks are the team's own test questions, not user data (A30).
  2. **Live, one rapid run on a new task**, opened in the browser: the proposal appears when
     the longlist finishes; Add, Remove, Suggest more at four and at five places, an appetite
     change, a Rebuild after an outcome change (places survive). About 15 minutes. No Evidence
     search live run.
- **Measures, read from the saved results.** M1, M2, M4 and M7 are pass conditions; M3, M5
  and M6 are reported (A20). Each is `passing / total` with the denominator named (A26).

  | # | Measure | Stage | Denominator | Pass |
  |---|---|---|---|---|
  | M1 | Reasons that name a fact on the option's card | 1 | every reason across the 24 proposals (about 100) | all |
  | M2 | Reasons or notes using study count, tier, "works", "effective", "proven", "promising", "strong/weak evidence", "studies" | 1 | every reason and note | none (lexical check by code in the script, then hand) |
  | M3 | Proposals whose mix matches the stated appetite (S4) | 1 | the 21 first proposals, per appetite | reported; not a gate |
  | M4 | Potential impact lines in conditional form, naming a pathway and a reach, no claim of effect | 1 | every option on the three check-set tasks | all |
  | M5 | Input characters and tokens, output tokens, cost and wall time per proposal; document lines cut | 1, 2 | the 24 proposals + the live run | reported; 0 cuts expected |
  | M6 | Same picks between the two `mostly_tried` proposals of one task | 1 | 3 tasks × 5 places | reported |
  | M7 | User places and set-asides preserved across a Rebuild and an appetite change | 2 | the live task seeded with two user places and one set-aside; 2 checks | all |

## Verification evidence expected

Command tails; the migration round-trip; the OpenAPI diff; the three prompt texts and the hash
diff; the 24 proposals (option names, reasons, notes) and the M1–M7 table, each number read
back from the saved file; the hand reading per proposal; the token and cost figures beside the
longlist walk's; the browser check notes with the places before and after each action; known
gaps; the `docs/deferred.md` delta; the spec changes applied, each with the owner's accepting
words.

## Risk tier & review focus

**Tier 4** — a migration, a new model call that reads the whole list, a change to the longlist
chain, three prompt revisions. ADR with a rollback plan; adversarial review at the contract and
plan stages (`codex-rescue`, read-only; `deep-reasoner` if Codex is not available); the step-7
stack per the spine; `/security-review` on the three routes and the plan patch path.

Rollback shape: `alembic downgrade -1` drops the three columns, restores the purpose check
(clearing shortlist scopes' purpose first) and strips `risk_appetite` from every
`plan.payload`, because the previous image's strict plan model would reject the key; that
step is lossy for the appetite and is written as such in the revision (A15). Deploy the
previous image. Longlists built by this slice otherwise stay readable by the previous image,
because every read-model change is additive.

Review focus: no file under `evidence_search/` changes; a user place is never changed by code
or model; a set-aside is never re-proposed; an excluded option is never a candidate; the card
text contains nothing the frontend does not render; the appetite-only plan change opens no
longlist walk and marks nothing stale; reasons carry no forbidden words (M2); the migration's
downgrade handles the plan payloads; no new table.
