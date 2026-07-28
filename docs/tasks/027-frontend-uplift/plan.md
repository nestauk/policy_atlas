# Implementation plan: 027-frontend-uplift

> **Status:** rev 2 (2026-07-28) — **plan-phase adversarial review DONE**
> (codex job task-ms4ysawn-3226i1: 18 findings, 15 MAJOR, **18/18
> adjudicated in**; the two load-bearing refutations — the emitter deadlock
> via in-transaction `component.started` (harness.py:413, lead-verified) and
> the death of decisions-polling for the live search card — reshaped pins
> 1–3 and annex D‑1). Plan approval (before implementation): _pending_.
> Contract: [contract.md](contract.md) (FINAL). Annexes:
> [rehydration-mapping.md](rehydration-mapping.md) (rev 2) ·
> [read-model-additions.md](read-model-additions.md) (rev 2) ·
> [design-inputs.md](design-inputs.md). Tier 3 → ADR 0027 due; migration
> downgrade tested; security lane scoped.
> **Plan-gate items needing explicit owner sign-off:** (i) the
> component-lifecycle event placement delta (pin 3 — the one approved
> runner-behaviour change); (ii) the live search card's honest redefinition
> (annex D‑1 rev 2 — tick-notes live, per-backend detail at stage end);
> (iii) sizing at ~19–21 executor-days.

## Implementation pins (lead-designed; briefs reference, don't re-derive)

1. **Build order is substrate-out, and every shape-changing backend phase
   regenerates the client** (finding 11): phases A, B and C each end with
   `make openapi && pnpm gen`, committed, drift-check green inside that
   phase's gate. The frontend substrate builds only after C; views only
   after D. `make verify`'s drift-check is satisfiable at every gate by
   construction.
2. **Transcript persistence** per contract strand 12 +
   [rehydration-mapping.md](rehydration-mapping.md) rev 2: one
   `planning_transcript` table with **`turn_index` (monotonic per project,
   assigned at phase-1 insert) as the ordering coordinate** (finding 6 —
   `created_at` is display metadata, never the sort key). Rows store **both
   representations** (finding 3): `planner_state` (the raw `PlanDraftWire`
   dump the planner consumes) and `response` (the exact projected
   `PlanningTurnOut` returned, for durable idempotency verbatim). Two-phase
   writes per the contract; **retry rules pinned** (finding 6): only the
   latest row may be retried; a retry re-runs in place (same `turn_index`);
   a new `client_turn_id` while a `pending` row is fresh → 409
   `planning_turn_in_progress`; a `pending` row older than 10 minutes is
   failed-on-read; retrying a non-latest failed id → 409 `stale_turn`.
   **The turn lock survives as a process-local lock registry**
   (finding 4): `_turn_locks: dict[project_id, Lock]` — only *state* moves
   to rows; the 409 concurrency primitive is process-local by design under
   the one-instance posture (LISTEN/NOTIFY multi-instance stays the
   deferred 025 seam). **`GET /plan` is rewired and tested** (finding 5):
   unapproved drafts serve from the latest completed row; the
   draft-after-restart read is a named test.
3. **Component-lifecycle event placement — the one approved runner delta**
   (finding 1, lead-verified at harness.py:413): `component.started` (and
   the in-transaction `component.completed` append) move OUT of the
   component transaction into short standalone transactions at the runner's
   phase boundary — started commits before the component transaction opens,
   completed after it commits. Without this, the artefact emitter
   **deadlocks the walk** (the component transaction holds an uncommitted
   sequence and waits synchronously on an emitter blocked behind it).
   Consequences, pinned and tested: (i) `stage.started` becomes genuinely
   live (today it is only visible at component commit — a latent defect
   this fixes); (ii) a rolled-back component leaves a coherent
   started→failed event pair (the failure backstop already appends outside
   the transaction); (iii) the 025 CLI byte-pin tests and the SSE
   replay/pending tests are the regression net and must stay green
   unmodified; (iv) after the move, the synthesise transaction holds **no**
   uncommitted `event_log` rows, so the `ProgressEmitter` (own short
   `events.append` transactions, savepoint-retry allocator) is safe — and
   B.1 carries a contention test that streams artefact events while a
   synthesise transaction is deliberately held open.
4. **Artefact event vocabulary + emission points** (contract-pinned set;
   finding 9 sharpens identity): the **skeleton is emitted in presentation
   order** and its `index` is the **display index** — the single section
   identity all `artefact.*` events use; the emitter owns the
   synthesis-order → display-order mapping (key findings are *generated*
   last but *presented* first; conclusion foot is code-injected).
   `artefact.section_started {index}` fires **before that section's
   generation begins** (loop top — not around `_write_section`, which runs
   after the expensive work); `section_completed {index, title, prose}`
   after its write. Key-findings handling: the skeleton includes the
   key-findings slot; if synthesis ends with it empty, a
   `section_completed` with empty prose closes the slot and the frontend
   drops it (hide, never fake). Reducer: `liveSections` keyed by display
   index, cleared on a different run's `run.status(running)`.
5. **Findings discriminator is `profile`** (finding 8 — the as-built public
   field): the union discriminates on the existing `profile: "iof"|"icf"`
   literal; the filter param is `?profile=`. No `kind` field anywhere; the
   contract's "kind-aware" language binds behaviour, not naming.
6. **web-api.md flow-back** in the same commits as the behaviour: § Planning
   turns rewritten (durable transcript, `turn_index`, retry/staleness rules,
   restart semantics) · § SSE gains the three `artefact.*` frames, the
   presentation-record semantics **and the lifecycle-placement note (stage
   events commit at phase boundaries)** · § Read models gains the union +
   filters + dossier endpoint.
7. **Frontend layout unchanged** (025 pin 8). New code: `store/` reducer
   extensions + **the thread composition model** (finding 12 — D.1 owns it:
   run blocks anchored on the runs read, steering decisions by `event_log`
   sequence inside their block, planning turns by `turn_index` between
   blocks; a unit test builds the merged thread from fixture data) ·
   `views/workspace/` rail + panes · `ui/motion/` (CountUp + Tailwind-4
   `@utility` animations) · `lib/title.ts`. No new dependencies.
8. **Demo transcription discipline** (contract rev 2.1) + the annex §5
   transcription traps bound into every per-view brief. **Each per-view
   brief pins its URL state** (finding 17): findings `?profile=`, `?facet=`
   + `?group=`; sources `?status=`, `?cited=`, `?page=`; dossier `?source=`
   (existing). Row expansion is local state with the exclusion documented
   in verification.md (transient disclosure, not a named navigation
   target). **Accessible-name changes ship in the same commit as the view
   that renames them** (finding 16) — fe-api-smoke/journey name-sync is
   part of each E-task, not deferred to F.
9. **State/error matrix** extends to the new surfaces (unchanged from
   rev 1): streaming states (skeleton · writing · filled · terminal-partial
   banner), incomplete-turn render, rail collapsed/expanded, landing live
   refresh.
10. **Motion budget** (unchanged): rise/glow/breathe/bar + CountUp, only on
    data arrival/state change, quiet under `prefers-reduced-motion`.
11. **Brand reconciliation is a Phase-0 gate with an owner decision, not a
    silent deferral** (finding 15): T0.2 runs on owner-supplied access or
    screenshots at build open; if neither is available by T0.2's day, the
    **owner explicitly rules** defer-and-proceed-on-distillation vs block —
    recorded in verification.md either way. The plan does not self-serve
    the deferral.
12. **No new prompt surfaces** — hash guard stands; planner rehydration
    composes the existing moment (prompt change = stop condition).

## Contract-test matrix (single owner per test — finding 13)

| Contract-named test | Owner |
|---|---|
| Two-phase persistence + crash-between-phases pending render (API) | A.2 |
| Durable `client_turn_id` idempotency across restart (verbatim response) | A.2 |
| Retry/staleness rules (latest-only retry, 409 stale_turn, 10-min fail-on-read) | A.2 |
| Rehydration parity (mapping rev 2; unbroken ≡ rehydrated planner state) | A.2 |
| `GET /plan` draft-after-restart | A.2 |
| Transcript round-trip + pagination + owner-scoped 404 | A.2 |
| Migration up/down against populated DB | A.2 |
| Lifecycle-placement delta: started live mid-component · rollback leaves started→failed pair · CLI byte-pins + SSE replay/pending suites green unmodified | B.1 |
| Emitter contention test (streams while a synthesise TX is held open) | B.1 |
| Streamed-section replay idempotence (reconnect mid-synthesis) | B.1 |
| Display-index mapping incl. empty-key-findings close | B.1 |
| Terminal honesty — backend event trail after failure/interruption | B.1 |
| Server-side filter correctness (collection-true counts) | C.2 |
| Findings union narrows on `profile` (generated types) | C.1 |
| Dossier endpoint: dual-snapshot cited_in scoped to latest synthesis | C.1 |
| Reducer extension incl. new-run reset + thread composition (unit) | D.1 |
| Motion/CountUp under `prefers-reduced-motion` (component) | D.2 |
| Plan-pane label maps (unknown key omits) | E.1 |
| Answered-state check-in render | E.4 |
| Annotation slicing overlap/oversize + quote-highlight fallbacks | E.3 |
| Live-section fill-in + terminal-partial banner (render) | E.3 |
| Streamed-prose + ICF-field scrub (adversarial fixture strings) | E.3 / E.4 |
| Hygiene components (badge/title/404/boundary/toast) | F.1 |
| Mock journey updated + reduced-motion zero-error + `pnpm e2e` and `make fe-api-smoke` **executed in the gate** | F.2 |

## Tasks

### Phase 0 — baseline + brand (½–1 day)
- T0.1 `lead` inline: `make verify` green on branch base. **[FULL — mandatory]**
- T0.2 `lead`: brand reconciliation per pin 11 (owner-assisted; owner rules
  any deferral). *Taste-bearing.*

### Phase A — backend: transcript (2–2½ days)
- A.1 `codex` (pins 2 + mapping rev 2 are the brief): migration
  (+ downgrade), two-phase writes, `turn_index`, dual representation,
  lock-registry refactor, `_sessions` deletion incl. the `GET /plan`
  rewire, transcript GET (paginated, owner-scoped), staleness/retry rules;
  `make openapi && pnpm gen` at exit.
- A.2 `codex`: the A test set per matrix. **[FULL — schema]**

### Phase B — backend: lifecycle delta + artefact events (1½–2 days)
- B.1 `codex` (pins 3–4 verbatim in the brief): lifecycle-placement move +
  its regression net · `ProgressEmitter` + synthesise wiring per the
  emission points · SSE router forwarding · tests per matrix; regen at
  exit. **[FULL — runner-adjacent (the one behaviour delta)]**

### Phase C — backend: read-model enrichment + filters (2½–3 days)
- C.1 `codex`: [read-model-additions.md](read-model-additions.md) rev 2 §2
  exactly — `profile`-discriminated union, dossier endpoint (dual-snapshot
  `cited_in`, latest-synthesis scope), coverage/evidence/chunk-context
  additions, `ClaimOut.gap` (+ `weakly_grounded`), decisions widening, the
  two bug fixes, coverage-sentence map; regen at exit.
- C.2 `fast-worker`: filter params + collection-true count tests.
  **[FULL — read models]**

### Phase D — frontend substrate (1½ days)
- D.1 `codex`: reducer + narrow set + `liveSections` + thread composition
  model (pin 7) + transcript query/optimistic state + unit tests.
- D.2 `lead`: motion utilities + CountUp + the rail (keyboard-operable
  collapse, bounds). *Taste-bearing.* **[verify-fast]**

### Phase E — views (5–6 days; lead-bound per the 025 owner-routing precedent)
- E.1 `lead`: plan pane + thread polish (strands 2–3; composer states,
  incomplete-turn render, label maps + tests).
- E.2 `lead` integrating, `codex` first-pass card transcription per
  per-card briefs: journey pane (strand 1) — timeline · funnel · coverage
  (incl. `backends_detail`) · activity/tick card · groups · completion ·
  mini-nav · plan recap.
- E.3 `lead`: evidence-base page (strand 5) — A4 frame, snapshot (corrected
  copy), claim-type breadth + `gap`/`weakly_grounded` render, claim panel +
  highlight fallbacks, LiveArtefact states incl. terminal banner + its
  tests.
- E.4 `lead`: findings both-kinds view (strand 6, `profile` vocabulary,
  URL-pinned filters) + check-in card uplift (strand 4) + tests.
- E.5 `codex`: sources + dossier (strand 7) · landing rename/archive +
  stagger (strand 8) · decisions view incl. grouped search-terms row +
  client detail allowlist (strand 9, annex D‑4/D‑5) · chart token hygiene
  (strand 11). Name-sync per pin 8 rides each task. **[FULL — views
  complete]**

### Phase F — hygiene + e2e (1½ days)
- F.1 `fast-worker`: strand 14 mechanics + component tests.
- F.2 `fast-worker`: fixtures (streaming pause + partial-failure) · journey
  spec + CI lane; **gate = verify-fast + `pnpm e2e` + `make fe-api-smoke`
  run explicitly** (finding 16).

### Phase G — acceptance (1½ days)
- G.1 `lead`: the pinned live check (both restart legs, hygiene
  spot-checks; 45-min timeout).
- G.2 `lead`: verification.md · deferred.md updates · ADR 0027 · AGENTS.md
  note. **[FULL — step-6 exit]**

## Executor routing note

Unchanged rationale from rev 1 (025 owner precedent routes taste-bearing
views to the lead). A.1 moves to codex outright — pins 2 + the mapping annex
ARE the design; nothing left to hand-design at build time.

## Sizing (rev 2 — finding 18)

1 + 2.5 + 2 + 3 + 1.5 + 6 + 1.5 + 1.5 ≈ **17–19 executor-days** base, +20%
integration contingency → **~19–21**. This exceeds 025's 18–22 lower bound
deliberately reduced scope-for-scope (no hoist, no auth build), but carries
14 strands + a runner delta; the review-stack budget carries the standing
~3× retro flag.

## De-scope levers (escalation shortcuts, NOT pre-authorised cuts — finding 14)

Exercising ANY lever = an owner ping under the contract's honest-omission
floor; this list only fixes the order in which cuts would be *proposed*:
1. Dossier `cited_in` join · 2. Print stylesheet · 3. Groups-by-facet card ·
4. Journey mini-nav/card breadth (keep timeline/funnel/coverage).
**Never:** transcript correctness · streaming honesty · scrub/a11y floors ·
kind-aware findings · substrate invariants.

## Rollback (Tier 3)

One squash; API changes additive; migration downgrade drops
`planning_transcript` (tested); `artefact.*` events inert to old clients;
the lifecycle-placement delta is the one behaviour change — regression-
netted by the CLI byte-pins + SSE suites, and revertible independently
(its own commit). CI lane removal is one workflow hunk. No production
deploy in-slice.

## Review-stack sizing (conversation C)

Tier 3: contract-verifier · /code-review medium (angles: transcript
two-phase/idempotency/locking · lifecycle delta + emitter · read-model
union/filters/dossier · views a11y/vocabulary · scrub on new render paths)
· one security-auditor lane (transcript endpoint scoping + streamed-prose
injection) · codex adversarial · human deep review. Generated client +
lockfiles excluded from review diffs.
