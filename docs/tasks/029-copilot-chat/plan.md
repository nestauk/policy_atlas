# Plan: 029-copilot-chat

> **Status:** drafted 2026-08-10 against contract rev 3.1 (FINAL FOR PLANNING).
> Plan-stage adversarial review: _pending_ · Plan approved: _pending · owner_.
> Build runs in a fresh conversation (task-cycle-build), phases in order, one commit
> per phase on green gate. Executor marks per harness.md § routing; every `lead` mark
> carries its justification. Codex-exhaustion fallback: re-route down the ladder
> (deep-reasoner → fast-worker → lead), log substitutions in verification.md.

## Plan-time constants (reviewable pins; contract defers these here)

- Context window K = **8 turns**; window char ceiling **16 000 chars** (oldest-first
  truncation). Frame artefact budget **40 000 chars** (budget rule per contract §5).
- Output ceiling **4 096 tokens** per answer. Per-owner in-flight chat-turn cap **2**
  (429-class error `chat_capacity`). Stale-pending expiry 10 min (planning parity).
- Judge enrichment timeout **45 s**; enrichment retries once; then "unchecked" stands.
- Tool loop: turn cap and per-turn read caps inherit the shipped synthesis constants.

## Verify gates (consolidation argued per the 014 lesson)

Full `make verify`: **A** (build-open baseline + schema) · **B** (planning re-home —
runner + schema-adjacent) · **H** (step-6 exit). Phases C–G commit on green
`make verify-fast` (new-file-dominant; the C kernel extraction additionally requires
the full synthesis test module green before its commit).

## Phase A — baseline + schema (FULL verify)

| # | Task | Executor | Notes |
|---|---|---|---|
| A1 | `make verify` green baseline on the branch | lead (inline) | one command — delegation costs more than it saves |
| A2 | Backfill **truth table** finalized (no-run · running/paused · succeeded/degraded · failed/aborted/interrupted · abandoned plan · mid-replan · archived) | **lead** | seam design — the table IS the migration's semantics; contract requires it at this gate |
| A3 | Migration: `conversation` (+ partial unique active-planning index, `entry_artefact_id`) · `chat_turn` · `planning_transcript.conversation_id` · `plan.conversation_id` · `artefact.capability_run_id` · legacy backfill per A2 | codex | machine-verifiable: A4 tests + up/down |
| A4 | Migration tests: up/down · backfill fixture cases (every A2 row) · invariant index | codex (with A3) | |
| A5 | Destructive-downgrade rehearsal evidence (pre-write only) + post-write rollback note | fast-worker | mechanical: run, capture, document |

## Phase B — planning re-home (FULL verify)

| # | Task | Executor | Notes |
|---|---|---|---|
| B1 | Executed-plan→`PlanDraftWire` seed mapping (design) | **lead** | seam design: the mapping defines successor-conversation semantics |
| B2 | Conversation lifecycle service: create-with-project/first-turn, one-active invariant, successor seeding per B1; planning rehydration scoped to the active conversation | codex | parity tests keep planning behaviour identical otherwise |
| B3 | Closure-in-terminal-transaction delta in `_finish_run` | **lead** | fragile runner surface; small diff — the 027 rev-4 runner-delta precedent (lead-authored, parity-tested) |
| B4 | Planning endpoints: additive `conversation_id` exposure; lifecycle + closure + seeding + rehydration-scope tests | codex | includes crash-between-phases honesty cases |

## Phase C — chat turn engine (verify-fast; synthesis test module full-green before commit)

| # | Task | Executor | Notes |
|---|---|---|---|
| C1 | Kernel extraction: bounded tool-loop kernel + injected final emitter; section adapter keeps `run_section_loop` behaviour bit-identical (existing synthesis tests unchanged) | codex | the riskiest refactor — machine-verifiable by the untouched synthesis suite |
| C2 | Terminal-run component-id resolver (+ tests: replacement/additive re-runs, degraded missing components, resolved-once-per-turn) | codex | mirrors the continuation-reducer reduction |
| C3 | Chat turn service: two-phase rows, conversation-keyed single-flight, 3c transition table, idempotency, fences (`no_completed_run`, `run_active`), resource controls, per-call short-lived connections | codex | barrier/race tests per rubric 13/16/21 |
| C4 | `chat_v1` system prompt + wire models (`claims[]`/citations) + context assembler (frame incl. artefact body + budget rule + labels) | **lead** | prompt-bearing surface end-to-end; field descriptions and frame labels are prompt text |
| C5 | Citation floor + compaction (citable set = tool ∪ frame; appraised/citable-kind; orphan stripping; warning marker) + floor tests | codex | deterministic, precisely specced |
| C6 | Context-assembler + tracing tests (frame fields, budget degrade, session-per-conversation, trace id in payload) | fast-worker | mechanical transcription of the contract's enumerated checks |

## Phase D — streaming (verify-fast)

| # | Task | Executor | Notes |
|---|---|---|---|
| D1 | NDJSON turn stream: event union, exactly-one-terminal semantics, post-header `failed` events, stop vs bare-disconnect (server finishes), cancelled-partial persistence; OpenAI streaming adapter behind the provider-neutral wire | codex | first token-streaming plumbing — named risk; stream contract tests per rubric 20 |

## Phase E — judge enrichment (verify-fast; **contract-named cut-line**)

| # | Task | Executor | Notes |
|---|---|---|---|
| E1 | Chat-emission→judge-envelope shaping; async enrichment worker; CAS write; unchecked→verdict read-model states; enrichment tests (attach, failure→unchecked, no-citation skip, retry replay) | codex | reuses `grounding_judge` as-is |
| E2 | Judge-prompt adaptation for chat-shaped claims — ONLY if E1 shows the existing envelope mis-fits | **lead** | prompt gate (contract rev 3); if exercised, version-bumped and named in verification.md |

## Phase F — conversations API surface (verify-fast)

| # | Task | Executor | Notes |
|---|---|---|---|
| F1 | Endpoints: library list (+`status=archived`), `GET /{cid}`, create (`entry_artefact_id`), PATCH, archive/unarchive; BOLA + archived-semantics tests; OpenAPI + TS client regen | codex | fences/BOLA nuance keeps this above fast-worker |

## Phase G — frontend (verify-fast)

| # | Task | Executor | Notes |
|---|---|---|---|
| G1 | Store layer: conversation store (mirrors `usePlanningTranscript` reducer), NDJSON stream reader, enrichment refetch | codex | |
| G2 | Rail + views: tabs/switcher, Chats library, context chip, URL-addressable conversations, composer (stream/stop states), message rendering (markers, references, hover quote-in-context, unchecked→verdict upgrade, warning/stopped badges), hand-off card, entry points | codex | spec = contract §6 + design-inputs.md build details + the committed mockup; component tests per rubric |
| G3 | Frontend test sweep + mock-journey e2e extension (chat leg on the stub backend) | fast-worker | from G2's enumerated test list |

## Phase H — step-6 exit (FULL verify)

| # | Task | Executor | Notes |
|---|---|---|---|
| H1 | `web-api.md` § Conversations rewrite · deferred.md seam updates · AGENTS.md pointer refresh | fast-worker | doc transcription from the final contract |
| H2 | ADR **0028** — unified conversation model + lineage chain + chat fast-path (two-stage floors + async claim-grain judge) | **lead** | decision record; Accepted at plan sign-off date |
| H3 | Scoped live check per contract (local funded key): migration state sanity · chat from artefact (provenance + generative + evidence-not-held w/ handoff) · stop mid-stream · restart durability · library round-trip · "Run the analysis again" successor seeding · full-chain smoke via CI e2e | lead + owner | ≤30 min wall; staging quota still exhausted — local run |
| H4 | verification.md assembly (incl. any codex-fallback substitutions) | lead | evidence adjudication is the lead's |

## Dependency notes

A → B → C → D → F → G ordered; E after D (enrichment updates streamed rows) but
independent of F/G backend-wise (G's upgrade UI depends on E — if E is cut at this
gate, G ships "unchecked" states only and E becomes the fast-follow). C1 blocks C3/C5.
F can run parallel to D/E after C.

## Risks

1. **C1 kernel extraction** regressing synthesis — mitigated by bit-identical section
   adapter + full synthesis module gate before the phase commit.
2. **B3 runner delta** — smallest possible diff, lead-authored, parity tests.
3. **Backfill on live data** — truth table at this gate, fixtures per row, rehearsed
   downgrade, behaviour-level post-write rollback (contract §1).
4. **First streaming plumbing** (D1) — provider-neutral wire keeps the blast radius
   in one adapter; stream tests are contract-enumerated.
5. **Codex quota** — fallback ladder per the standing rule.

## Cut-lines (owner, at this gate or mid-build)

- **Phase E** (judge enrichment) → ship "unchecked" citations, E as fast-follow.
- G2's hover quote-in-context → markers + references footer only.
- Library `status=archived` view → archive works, listing view later.
