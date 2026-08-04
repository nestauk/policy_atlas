# 028 plan-phase adversarial review — findings & adjudication

> Lane: codex-rescue (read-only), job `task-msdwl2bh-boncq5`, 2026-08-04.
> 39 findings (35 MAJOR, 4 minor) against plan rev 1. **39/39 adjudicated
> IN** → plan rev 2 is a full rewrite. One finding corrects the approved
> contract's own lane-fix text (F13 — approval is at-ready as-built, not at
> Start; the contract's finding-6 mechanism wording updated, ruling intact).
> Clusters and dispositions:

- **Fit (F1–F7):** migration = 5 columns; P1 bundle carries per-backend
  counts + queries + sample titles; adjudicated fixes 1/19/20 named in F
  sub-phases; ADR (drafted `88f75d4`) + deferred.md updates homed in G;
  six-prompt-diff verification requirement homed in G; live check restores
  all contracted actions; security lane = step-7 review-stack lane with
  scope named in the handoff section (not a build phase).
- **Sequencing (F8–F12):** theme identity (id assignment + tags column +
  ThemeOut exposure) moves to A, rename delta stays D; check-in additions
  (bundle + authored exposure) move wholly to D with D's own client regen;
  budget threads into the P4 `propose_sections` call (C defines, D
  consumes); fixtures + vitest ride inside each F sub-phase; **D gates on
  full verify** (runner-adjacent, 027 precedent).
- **Pin corrections (F13–F21):** pin 3 rewritten on the as-built seam
  (approval at ready; reopen supersedes; turn linkage via
  `source_turn_index` in the plan payload; GET /plan serves a
  newer-than-approved draft with honest status — a named, gate-listed
  read-behaviour change; run-start 409 `plan_stale` when the approved
  plan's turn < newest completed turn). Promotion fix covers BOTH paths
  (after- and before-boundary, runner.py ~1439 and ~1654). P4 primary
  submits the displayed ORDINARY list (structural rows are display-only;
  grammar unchanged; bundle carries ordinary proposals only). Shared
  validator = lead-designed seam: one `validate_option_delta`-style
  signature with an explicit ctx (backend scope · current/completed
  components · rerun surface), used at router-compile, authoring, and
  apply; apply-time ctx reconstructs from pause payload + project state.
  Summaries follow the **027 emitter precedent**: minted AFTER the
  synthesise component transaction commits, in short standalone
  transactions, degrade-and-disable on provider failure (`failed` status,
  never a component failure); contention + rollback tests named.
- **Routing (F22–F25):** the newly-pinned seams make the codex briefs
  self-checkable; F sub-phases enumerate fast-worker vs lead; G lead mark
  justified (adjudication is judgment).
- **Sizing/live (F26–F31):** per-phase estimates added; F/G split into
  gated sub-phases; live check re-estimated honestly (~45–60 min, two legs;
  contract estimate line corrected); leg B runs FREQUENT on a Quick run
  (hits P1/P2/P3/P4 + a boundary check-in live); Groups/deep surfaces are
  covered by mock e2e + the backend matrix (bounded live scope, stated);
  spend allowance covers regenerate-on-fail + artefact summary.
- **Underspecification (F32–F39):** budget table pinned (Quick=3 ·
  Standard/Deep=null→as-today; custom 2–8 via free text; time-band table
  gains a small-budget row only); rehydration rules pinned (latest
  proposal per part-id wins · confirms referencing superseded proposals
  render as prose · reopening re-proposes; named tests); summary backend
  = two new protocol methods with stub/live impls + usage accounting;
  SectionOut.summary = blocks[0]'s summary (as-built one block/section;
  multi-block omits honestly — recorded seam); theme rename updates the
  display name on the id-keyed record (tags carry theme_id; member reads
  id-keyed); sort spec (nulls last · case-insensitive · asc default ·
  status by rank · stable id tie-breaker · unknown params 422); the plan
  header carries the full fresh-conversation re-grounding list.
