# Implementation plan: 027-frontend-uplift

> **Status:** drafted 2026-07-28 — plan-phase adversarial review _pending_ ·
> plan approval (before implementation) _pending_.
> Contract: [contract.md](contract.md) (FINAL, revs 2–3.3). Annexes:
> [rehydration-mapping.md](rehydration-mapping.md) ·
> [read-model-additions.md](read-model-additions.md) (the plan-gate-approved
> additive API list) · [design-inputs.md](design-inputs.md) (PR #35).
> Tier 3 → ADR due (0027), migration downgrade tested, security lane scoped.

## Implementation pins (lead-designed; briefs reference, don't re-derive)

1. **Build order is substrate-out:** backend transcript + events + read-model
   enrichment first (they change the generated contract), then `pnpm gen`
   once, then frontend substrate (reducer/types/rail/motion), then views,
   then hygiene + acceptance. Views are never built against an unpinned
   contract; the generated client regenerates exactly once per backend phase
   (drift-check gates each).
2. **Transcript persistence** per contract strand 12 +
   [rehydration-mapping.md](rehydration-mapping.md): one `planning_transcript`
   table; phase-1 insert (user message, `pending`) in a short transaction
   after the authz/409 gate; phase-2 completion (reply, `plan_draft`,
   `suggestions`, `completed`) in the same transaction as
   `persist_approved_plan` when the turn reaches ready. The in-memory
   `_sessions` cache is **deleted**, not wrapped (one source of truth;
   rows are the idempotency cache). Stale `pending` rows older than
   **10 minutes** are treated as failed on read (crash leftovers — planner
   turns complete in well under that; value revisitable in build with a
   comment, not a config).
3. **Artefact event emitter** (strand 13): a `ProgressEmitter` callable
   constructed in the runner (where `engine` lives) and **parameter-passed**
   into the synthesise path (module-global config is banned, 025). It
   appends via the existing `events.append` in its **own short
   `engine.begin()` transactions** — verified safe: boundary events already
   commit in short transactions and components hold no uncommitted
   `event_log` rows mid-run, so the emitter is a third short-lived writer
   under the existing savepoint-retry sequence allocator. Emission failure
   logs loudly and never fails the walk (presentation records). Default
   emitter for non-engine callers (unit harnesses) is a no-op.
4. **Event vocabulary** (contract-pinned): `artefact.skeleton {sections:
   [{index, title, focus}]}` (includes key-findings + conclusion positions) ·
   `artefact.section_started {index}` · `artefact.section_completed {index,
   title, prose}`. Durable event_type strings mirror the SSE frame types
   1:1 (no mapping indirection — these are new, unlike the legacy
   `run.started`→`stage.started` renames). The SSE router forwards them;
   `narrowSseFrame`'s pinned set grows from 9 to 12; the reducer gains
   `liveSections` state cleared on a different run's `run.status(running)`.
5. **Read-model additions** are exactly
   [read-model-additions.md](read-model-additions.md) — the plan-gate
   list. `FindingOut` becomes a discriminated union (`IofFindingOut |
   IcfFindingOut` on a `kind` literal, named OpenAPI components per the
   web-api typed-variants pin). Server-side filters land as query params on
   the existing list endpoints (evidence `status`, findings `kind` +
   facet/group) — page envelopes unchanged.
6. **web-api.md flow-back** in the same commits as the behaviour: § Planning
   turns rewritten (durable transcript, durable idempotency, restart
   semantics, staleness rule) · § SSE gains the three `artefact.*` frames +
   the presentation-record semantics · § Read models gains the union +
   filters.
7. **Frontend layout unchanged** (025 pin 8). New code lands as:
   `store/` reducer extensions · `views/workspace/` rail + panes ·
   `views/` per strand · `ui/motion/` (CountUp + the Tailwind-4 animation
   utilities in `index.css` `@utility` blocks) · `lib/title.ts`
   (document-title helper). No new dependencies — resize/collapse is CSS +
   pointer events; charts stay recharts 3.x.
8. **Demo transcription discipline** (contract rev 2.1): per-view briefs name
   the demo file as the UX spec; the executor transcribes markup/class
   strings/copy maps and rewires onto generated types + `scrub()` + real
   buttons + state matrix. Demo `Tip`/`SlideOver` usages map to prod
   `Tooltip`/`Popover`/`Sheet`. Every copy map keeps the locked-vocabulary
   rule: unknown key → omit (grep-checked, rubric 9).
9. **State/error matrix** (025 plan artefact) extends to the new surfaces:
   every new card ships loading/empty/error; the artefact page adds the
   streaming states (skeleton · writing · filled · terminal-partial banner);
   the thread adds the incomplete-turn (pending/failed) render; the rail
   adds collapsed/expanded; landing adds the live-status refresh.
10. **Motion budget** (strand 10): utilities `anim-rise`, `anim-glow`,
    `anim-breathe`, `anim-bar` + `CountUp` (rAF, ease-out) — applied only
    where data arrives or state changes; all quiet under
    `prefers-reduced-motion` (the existing e2e reduced-motion run stays the
    regression net). No animation without a data-arrival justification in
    the brief.
11. **Brand reconciliation before visual build** (contract Read-first): tokens
    + visual-identity component shapes checked against the comms Figma
    library; drift folds into `nesta-brand-tokens.md` + `index.css` only.
    Owner supplies access or screenshots; **fallback if unavailable by
    Phase D: build proceeds on the in-repo distillation and the pass is
    recorded as a deferred check** — not a blocker (the distillation is the
    committed baseline).
12. **No new prompt surfaces** — the 025 prompt-family hash guard stands;
    planner rehydration composes the existing moment (a prompt change is a
    stop condition, contract § Model route).

## Contract-test matrix (every contract-named test → one task)

| Contract-named test | Task |
|---|---|
| Two-phase persistence + crash-between-phases pending render | A.2 |
| Durable `client_turn_id` idempotency across restart | A.2 |
| Rehydration parity (mapping table, unbroken ≡ rehydrated) | A.2 |
| Transcript round-trip + pagination + owner-scoped 404 | A.2 |
| Migration up/down against populated DB | A.1 |
| Emitter separate-connection visibility (tail sees events mid-component) | B.1 |
| Streamed-section replay idempotence (reconnect mid-synthesis) | B.1 |
| Terminal honesty after failure/interruption with partial sections | B.1 + E.3 |
| Reducer extension incl. new-run reset (unit) | D.1 |
| Server-side filter correctness (collection-true counts) | C.2 |
| Findings union narrows on kind (drift-checked types) | C.1 |
| Scrub on streamed prose + ICF fields (adversarial strings in fixtures) | D.1/E.3 |
| Mock journey updated (new surfaces incl. streaming + rail) | F.2 |
| fe-api-smoke green (accessible names updated in same commit) | F.2 |
| Reduced-motion zero-error e2e | F.2 |
| Hygiene: badge/title/404/error-boundary/toast component tests | F.1 |

## Tasks

### Phase 0 — baseline + brand (½ day)
- T0.1 `lead` inline: `make verify` green on branch base. **[FULL — mandatory]**
- T0.2 `lead`: brand reconciliation pass per pin 11 (owner-assisted; fallback
  rule applies). *Taste-bearing.*

### Phase A — backend: transcript (1½ days)
- A.1 `lead` designs migration + endpoint shapes (thin — pins 2 and the
  mapping annex are the design); `codex` implements: migration (+ downgrade
  = drop table; up/down tested populated), two-phase writes,
  `_sessions` deletion, rehydration from rows, transcript GET (paginated,
  owner-scoped), staleness rule. *Machine-verifiable done: the A-row tests.*
- A.2 `codex`: the A-phase test set per matrix. **[FULL — schema]**

### Phase B — backend: artefact events (1 day)
- B.1 `codex` (brief carries pins 3–4 verbatim): `ProgressEmitter` seam +
  synthesise wiring (skeleton after sectioning; started/completed around
  `_write_section`) + SSE router forwarding + tests per matrix.
  **[verify-fast — event-log additive, no schema]**

### Phase C — backend: read-model enrichment + filters (1½–2 days)
- C.1 `codex`: the [read-model-additions.md](read-model-additions.md) §2 list
  — `FindingOut` union, dossier endpoint, coverage/evidence/chunk-context/
  claim additions, `gaps` population, decisions `_EVENT_KINDS` widening, the
  two bug fixes (evidence `url` ladder · approved-plan step labels/StageKey
  collapse) and the coverage-sentence copy map — exactly as annexed; OpenAPI
  + `pnpm gen` regenerate; drift-check green.
- C.2 `fast-worker`: server-side filter params + collection-true count tests
  (mechanical against C.1's shapes). **[FULL — read models, 025 precedent]**

### Phase D — frontend substrate (1½ days)
- D.1 `codex`: reducer + `narrowSseFrame` + `liveSections` + transcript-backed
  thread state (TanStack query for the transcript read; local optimistic
  append for in-flight turns) + unit tests per matrix.
- D.2 `lead`: motion utilities + `CountUp` (pin 10) + the rail
  (collapse/resize, keyboard-operable per contract) — *brand/taste-bearing.*
  **[verify-fast]**

### Phase E — views (4–5 days; lead-bound per the 025 owner-routing precedent)
- E.1 `lead`: plan pane + planning thread polish (strands 2–3) over D.1's
  substrate — includes composer states, suggestion chips, incomplete-turn
  render.
- E.2 `lead`: journey pane (strand 1) — composition + taste; the individual
  cards (timeline/funnel/coverage/search/activity/groups/complete) are
  transcribed from the demo per pin 8 with `codex` doing the first
  transcription pass of the card set against a per-card brief, lead
  integrating and polishing. *The one split-executor task; the lead owns
  the integrated result.*
- E.3 `lead`: evidence-base page (strand 5) — A4 frame, coverage snapshot,
  claim-type breadth, claim panel + quote-highlight fallbacks, LiveArtefact
  streaming states incl. terminal-partial banner. *Core reading surface.*
- E.4 `lead`: findings both-kinds view (strand 6; ICF row design is
  contract-marked lead) + check-in card uplift (strand 4).
- E.5 `codex`: sources + dossier depth (strand 7) + landing rename/archive +
  stagger (strand 8) + decisions tint/detail (strand 9) + chart token
  hygiene (strand 11) — transcription-shaped per pin 8, per-view briefs.
  **[FULL — views complete]**

### Phase F — hygiene + e2e (1–1½ days)
- F.1 `fast-worker`: strand 14 mechanics — titles/favicon · 404 + error
  boundary · toasts wired + dead exports deleted · signed-in identity ·
  print stylesheet · landing refetch-while-active · check-in badge + title
  marker (the badge reads the existing pending-check-in query) — with
  component tests.
- F.2 `fast-worker`: mock fixtures extension (streaming pause + partial-failure
  states, sanitized) · journey spec update · fe-api-smoke name sync · the CI
  e2e lane (the one approved CI change). **[verify-fast]**

### Phase G — acceptance (1–1½ days)
- G.1 `lead`: the pinned live check (contract § Acceptance, incl. both
  restart legs + hygiene spot-checks; overall timeout 45 min, abort +
  report beyond it). *Live evidence adjudication.*
- G.2 `lead`: verification.md · deferred.md updates (025 transcript seam
  discharged; co-pilot UI + workspace-cluster IA + share/export untouched
  seams recorded) · ADR 0027 (transcript durability + artefact SSE
  vocabulary) status→Accepted at owner sign-off · AGENTS.md phase note.
  **[FULL — step-6 exit]**

## Executor routing note

The 025 plan-gate precedent (owner, 2026-07-21) routes frontend product
surfaces to the lead on taste grounds; this slice is *about* taste, so
E.1–E.4 and D.2 are lead-marked with that standing justification. Delegated:
all backend phases (A–C: machine-verifiable dones — the contract pins +
annexes are the briefs), D.1 substrate plumbing, E.5's transcription-shaped
views, F entirely. E.2 splits: codex transcribes the card set, lead owns the
integrated journey. Consequence: Phase E is lead-bound 4–5 days; wall-clock
grows for product-surface quality, accepted (025 precedent).

## Sizing

0.5 + 1.5 + 1 + 1.5 + 1.5 + 4.5 + 1.5 + 1.5 ≈ **13–15 executor-days**, plus
~20% integration contingency → **~16–18**. Review stack: Tier 3 at
review-economy pins (medium /code-review · one security lane) — but note the
standing retro flag (review pins ran ~3× on four consecutive slices); the
review gate should budget for that reality, not the pin.

## Gate consolidation summary

FULL `make verify`: T0.1 (baseline) · A.2 (schema) · C.2 (read models — 025
E.2 precedent) · E.5 (views complete) · G.2 (step-6 exit).
verify-fast: B.1 (event-log additive), D.2, F.2 (frontend-only, no
schema/ingest contact). B.1's artefact events are runner-adjacent but
zero-schema and additive; the full C.2 gate immediately follows it.

## De-scope levers (pre-authorised order)

1. Dossier `cited_in` join (the one non-trivial dossier query) · 2. Print
stylesheet · 3. Live search card (cheap now per annex D‑1, but presentation-
only) · 4. Groups-by-facet card · 5. E.2 card-set breadth (keep
timeline/funnel/coverage; drop mini-nav).
**Never:** transcript correctness (two-phase/idempotency/rehydration) ·
streaming honesty (replay + terminal states) · scrub/a11y floors · the
kind-aware findings view · substrate invariants.

## Rollback (Tier 3)

One squash; frontend + API changes additive; the migration downgrade drops
`planning_transcript` (tested); `artefact.*` events are inert to old clients
(unknown types dropped by the narrow seam by construction); CI lane removal
is one workflow hunk. No production deploy in-slice.

## Review-stack sizing (conversation C)

Tier 3: contract-verifier · /code-review medium (angles: transcript
two-phase/idempotency · emitter/SSE/reducer · read-model union + filters ·
views a11y/vocabulary · scrub coverage on new render paths) · one
security-auditor lane (transcript endpoints' owner scoping + streamed-prose
injection surface) · codex adversarial · human deep review. Exclude generated
client + lockfiles from review diffs; per-angle diff scoping per
review-economy pins.
