# ADR 0028 — Sequential plan-building and the steering taxonomy rework

- **Status:** Accepted — 2026-08-04 (owner, with the 028 plan approval)
- **Date:** 2026-08-04
- **Task:** 028-ux-refinement · contract approved 2026-08-04
- **Binding design records:** `docs/tasks/028-ux-refinement/mockup/planning-stage.html`,
  `mockup/checkin-taxonomy.html`, `mockup/tab-ia-options.html`

## Context

Four internal policy-team interviews on the 027 build found users lost
during planning (split attention between chat and plan pane), overwhelmed
at check-ins (up to ~13 options, machinery language), and unaware when a
run was waiting on them. Live data confirmed and sharpened all three: the
planner demanded 5–9 confirmations to mark a plan ready (walking steer-point
defaults one turn each); a live authored check-in option carried an invented
delta (`recover_full_text` — no such capability) that would have silently
no-opped; timing medians showed synthesise (~580s) dominating wall time
while the landscape depth's skipped components saved ~13s.

## Decisions

1. **Planning is sequential parts on the existing turn machinery.** The
   planner (`planner_v6`) proposes at most one structured part per turn —
   question · scope · thoroughness — persisted verbatim on the transcript
   row (one additive JSONB column); button confirmations are ordinary
   planning turns referencing part-id + option-id; free text beats buttons
   everywhere; answered parts pre-confirm in bulk; the ready plan renders
   as an inline chat card, the only start surface (as built — corrected at
   the 028 review stack, F31: approval happens server-side when the turn
   reaches ready; Start dispatches against the already-approved plan and
   requires one, 400 otherwise; the stale-start fence demotes on a newer
   completed turn). No check-in question: steering
   is **unattended by default** and requested in words. Steer-point
   defaults compile from the mode — never a conversation.
   *Rejected:* a form/wizard (free text is the 024 spine; humans steer in
   compound sentences — both live human sessions prove it); asking about
   effort/depth axes directly (no user has ever varied them; presets are
   outcome-first with a customise path).

2. **Report length is a first-class plan lever.** Additive optional
   `section_budget` compiled from the thoroughness preset, honoured by the
   sections-planning prompt and enforced as the synthesis cap. This is the
   only lever that materially moves wall time; the Quick preset is honest
   because of it.

3. **One checkpoint steers one component.** The steer-point taxonomy
   reworks to single-subject stops that show the thing being decided:
   P1 search review (was failure-only) · P2 evidence base + themes (with
   rename-without-rerun, a durable edit-delta) · P3 reading list ·
   Groups (new lattice point, deep-only, after group) · P4 report plan
   (submits the displayed section list; inline per-section editing;
   structural roles fixed). Mode table: frequent all-always + boundary
   check-ins · moderate P1+P4 always, rest fired · minimal all fired ·
   **unattended default**. Watch promotions keep lattice identity.
   *Rejected:* a separate groups pause (same chain gap as P4 — one
   interruption, two sequenced questions instead).

4. **Authored options are validated substrate, not guarded frontend.** One
   grammar, one validator, all three option producers: authored deltas
   compile at authoring time (drop + log + event on failure), are exposed
   over HTTP with ids + `suggested` + why (they are not exposed today),
   and revalidate at apply; non-compiling deltas are loud refusals, never
   silent no-ops. Endorsements of floor options render as the reason under
   the blue primary — never duplicate buttons.

5. **The summaries navigation layer activates** per the existing
   provenance-grounding § Summaries spec (block + artefact summaries,
   flat faithfulness judging, display invariant); collapsed report
   sections are its drill-down. Fallbacks (legacy/failed) render with
   their marker.

## Consequences

Six lead-authored prompt surfaces change/appear in one slice; the steering
mode default flip touches every moderate-default test deliberately; the
planning dc.html mock-up is superseded by the binding records where they
conflict; check-in read models gain a typed bundle so cards can show what
they decide; re-runs stop silently excluding newer documents (default
upper date bound removed). Full contract-lane findings and their
adjudications: `docs/tasks/028-ux-refinement/adversarial-review-contract.md`.
