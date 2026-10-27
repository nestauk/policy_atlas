# ADR 0041 — The options-scoping shortlist: a model judgement over every card, bounded by hard checks; risk appetite on the plan; the shortlist walk

- **Status:** Accepted — 2026-10-27 (owner, at the task 055 plan gate; the
  decisions below were ruled one by one in the contract interview, the
  contract-stage review and the plan-stage review the same day).
- **Date:** 2026-10-27
- **Task:** 055-scoping-shortlist (contract, rubric and plan under
  `docs/tasks/055-scoping-shortlist/`)
- **Relates to:** [ADR 0040](0040-options-scoping-longlist-refinement.md)
  (the longlist at reader grain; this ADR adds one component after its
  `theme` step and one card line to its profile); [ADR 0039](0039-options-scoping-longlist-option-searches-and-option-records.md)
  (the longlist walk; unchanged except the chain's last step);
  [ADR 0037](0037-options-scoping-task-kind-links-and-baseline-gate.md)
  (the scoping plan; one field added); [ADR 0013](0013-mandatory-eb-spine.md)
  (the spine; the new step is not spine); [ADR 0027](0027-durable-planning-transcript-artefact-streaming.md)
  (progress events; the existing `select` stage key reused).

## Context

The longlist (tasks 044–046) merged to `dev` on 2026-10-14 and is on staging
behind a build-time flag. The capability spec bundled the next stage as
"task 3: shortlist and assessment". The owner split it: assessment is a new
pipeline (a mini evidence search per option, full-text fetches that fail
half the time, verdict cells, a report rewrite) and carries the open design
questions; the shortlist is a screening step over data the longlist already
holds. This ADR records the shortlist's design.

The specs' shortlist rules were written before the longlist existed (one
place per primary lever type, chosen on one coverage axis by procedure; no
judgement before assessment). The owner asked that the specs be treated as
input, not authority. Three research reports (official appraisal guidance;
risk appetite and evidence maturity; decision science and tools) were read
first. Their findings that shaped the decisions: official guidance screens
pass/fail and keeps "around five", and recommends against weighted scoring
at this step; no guidance links the decision maker's risk appetite to
shortlisting, so asking for it is ahead of guidance, not against it; evidence
bodies separate "how much and what kind of evidence exists" from "what it
says", which gives a direction-free maturity label; fused scores fail on
scale choice and rank reversal; LLM listwise selection is position-sensitive
and its written reasons are plausible but not always faithful, so a reason
must point at something the user can open.

## Decisions

1. **The shortlist is a provisional allocation of reading effort, not a
   verdict.** About five places by default (`PLACES_TARGET = 5`), not a
   plan setting; the user adds past it. No score, no ordering, no claim that
   an option works. Study count and quality tier are never a reason.
   (Contract S6, S15; keeps concept rulings 6 and 37; replaces ruling 20's
   "one place per primary lever type".)

2. **Risk appetite is a plan field, chosen in the planning conversation and
   changeable later.** `ScopingPlan.risk_appetite ∈ {tried_only,
   mostly_tried, open_to_untested}`, default `mostly_tried`, offered by the
   Task Agent like depth, shown and patched in the plan document and on the
   shortlist view, never inferred. It sets the **mix** of tested and
   untested places, never an order. (S2–S4, S26.)

3. **Policy Atlas picks by one model call over the full card of every
   included option.** The call reads the plan, the baseline, the appetite,
   every option's card text (one shared serialiser from the read model the
   frontend renders, so what the model reads is what the user can see), the
   user's picks and set-asides, one line per excluded option, and the
   previous proposal. It returns the picks with one plain reason each and a
   short note on what the set leaves out. The prompt carries the rules (the
   mix, a preference for lever and ambition spread, potential impact, reach,
   plan fit, the reason rules); code checks only the hard things (ids,
   count, picks kept, set-asides not re-proposed, reasons present) with one
   re-ask, then the walk degrades and the previous places stay. Input is
   shuffled per attempt. The judgment model, not the mini model. Rejected:
   a deterministic quota ladder, a model-filled criteria table with rules
   over it, a pairwise tournament, enforced spread checks, a per-option
   "why not" sentence. (S11–S16.)

4. **The user's places are never removed by Policy Atlas.** Add and Remove
   from the list rows, grid tiles and card; a removed pick is set aside and
   not proposed again; removing does not refill; **Suggest more** fills to
   five when under five and adds one per press at five or more; a user's
   place is never merged or folded at a Rebuild and keeps its place through
   a constrain exclusion, with the breach shown. (S5, S7–S9, O1.)

5. **Re-proposal runs as a one-component shortlist walk.** An appetite
   change (when the longlist's inputs are otherwise unchanged) and Suggest
   more open it; the longlist chain gains `shortlist` after `theme` so a
   Rebuild proposes again around the user's picks. The walk shows under the
   existing stage key `select` with a scoping-only label. Update-in-place of
   the longlist stays deferred; Rebuild stays. (S10, S17, S25.)

6. **Potential impact is a ninth "What it would take" line and a reason to
   pick.** One conditional sentence per option from `option_profile`,
   reasoned from the mechanism against the baseline's drivers, the reach
   (who it would apply to, against who it has been tried on) and the user's
   outcomes as written — not from outcome mention counts. It rests on model
   reasoning and is labelled so, like the legal-change line. The words "size
   of the prize" are never used. Direction of effect stays with assessment.
   The trust rule is amended: a labelled conditional magnitude may inform
   the pick; an unconditional magnitude, a probability, a number or a
   forecast may not. (S19–S22, S24; spec changes 4, 4b.)

7. **The maturity rung is computed by code, never by a model.** Proposal
   only · Described · Evaluated · Reviewed, from document roles and the
   evaluating documents' evidence types, with the modifiers "none in your
   setting" and "most recent evaluation before YEAR". Coverage gains the two
   keys it needs. (S18.)

8. **Storage: three columns, no new table.** `option.shortlist_state`
   (proposed · added_by_you · set_aside) and `shortlist_reason`;
   `longlist_result.shortlist` JSONB (the note and provenance, including
   per-attempt usage). Each proposal is also one append-only
   `shortlist.proposed` event, which is the assembly record the spec asks
   for and the source of "the previous proposal" after a Rebuild. The
   `evidence_scope.purpose` check admits `shortlist`.

9. **Staleness is a projection, not a version number.** `longlist_inputs(plan)`
   names the plan fields the longlist reads; `plan_inputs_changed` compares
   the current plan to the longlist's pinned version through it, so an
   appetite change never asks for a Rebuild. `shortlist.stale` is derived
   from the last proposal's appetite against the plan's.

10. **Assessment is shown and disabled.** "Assess these N" is present with
    one line saying assessment is not yet available; unattended runs end
    after the shortlist until it lands. (S23, O4.)

## Rollback

One alembic revision. `alembic downgrade -1`: sets shortlist scopes'
purpose to null and restores the old check; drops the three columns; strips
`risk_appetite` from every `plan.payload` (lossy for that field, because the
previous image's strict plan model rejects unknown keys). Deploy the
previous image. Read-model changes are additive, so longlists built by this
slice stay readable by the previous image.

## Evidence

The contract's staged check: the seven stored tasks under three appetites
plus three repeat runs (24 proposals) read by hand against the cards (M1,
M2, M4 pass; M3, M5, M6 reported); one live rapid run in the browser (M7).
Results in `docs/tasks/055-scoping-shortlist/verification.md`.

## Consequences

- The shortlist has judgement in it, bounded and inspectable: every reason
  points at a card fact the user can open; the mix is a prompt rule the
  build measures, not a guarantee.
- Run-to-run variation is accepted and recorded; the eval measure for the
  shortlist is recall of the eventual best option after assessment, deferred
  to the eval slice.
- Assessment (task 4) starts from a shortlist with places, reasons, an
  appetite and a maturity rung per option, and the Assess gate already in
  the view.
- The `VITE_OPTIONS_SCOPING` production flag stays until assessment lands.
