# Plan: 029-copilot-chat

> **Status:** rev 2, 2026-08-10 — plan-stage adversarial lane DONE (codex-rescue job
> task-msnlek0m-p568f1; 22 findings, 19 MAJOR, all adjudicated in; contract rev 3.2
> carries the four plan-stage pins it surfaced — cancel endpoint, title mechanics,
> successor-creation mechanics, hydration-wording fix — ratified with this plan).
> Plan approved: _pending · owner_. Build runs in a fresh conversation
> (task-cycle-build), phases in order, one commit per phase on green gate. Executor
> marks per harness.md § routing; every `lead` mark carries its justification.
> Codex-exhaustion fallback: re-route down the ladder, log in verification.md.

## Plan-time constants (reviewable pins)

- Context window = **the whole conversation, ceiling-bounded** (rev 2.1, owner:
  fixed small-K is an API-app cost pattern, not what flagship chat products do —
  they carry the full thread to the context limit): all turns up to **32 000 chars**,
  truncating oldest-first only when exceeded. Chats are many-and-short by design, so
  this is full memory for virtually every real thread; the summarization/recall seam
  is unchanged.
- Frame artefact budget **40 000 chars** = the **degradation threshold for non-entry
  artefacts** (the entry-context artefact always keeps its full body — contract §5).
- Output ceiling **4 096 tokens** per answer (new chat-adapter cap; synthesis calls
  stay uncapped). Per-owner in-flight chat-turn cap **2** (429-class `chat_capacity`).
- Stale-pending expiry 10 min (= planning `_PENDING_TTL` parity, verified).
- Judge enrichment timeout **45 s**, one retry, then "unchecked" stands.
- Enrichment refetch (frontend): poll the turn read model every **3 s, ≤60 s**, stop
  on enriched · terminal-unchecked (server says judge gave up) · conversation
  switched/unmounted/archived. Fake-timer store tests.
- Tool loop: synthesis constants inherited (turn cap 6; 6 executed reads/turn).

## Backfill truth table (contract §1 requires it AT this gate)

One legacy planning conversation per project **with ≥1 planning turn**; zero-turn
projects get nothing. Status derives from plan/run state at migration time:

| Project state at migration | Legacy conversation status |
|---|---|
| Turns exist, no run ever dispatched | `active` |
| Latest run `running` / `paused` | `active` (fence semantics unchanged mid-walk) |
| Latest run `succeeded` / `degraded`, no completed planning turn after `ended_at` | `closed` (closed_at = run `ended_at`) |
| Latest run `succeeded` / `degraded`, ≥1 completed planning turn after `ended_at` (mid-replan) | `closed` **+ a second `active` successor owning the post-run turns** (turn ownership splits at the first post-completion turn) |
| Latest run `failed` / `aborted` / `interrupted` | `active` (replanning within lineage) — except an `abandoned` plan with no later draft → `closed` |
| Archived project | same rules; conversation archived-state untouched (kind=planning is never `archived`) |

Every row is an A4 fixture case. Rubric 14 aligned to this table.

## Reader-scope matrix (contract §4 requires the plan to verify it)

| Tool / lookup kind | As-built scope key | 029 strategy |
|---|---|---|
| `search_chunks` | corpus / evidence scope | **scope-wide by design** (contract: chunk search spans the shared corpus) |
| `query_findings` | `extraction_run_id` | resolver-bound (safe) |
| `selection_rationale` | scope + `selection_run_id` | resolver-bound (safe) |
| `characterisation_summary` | `characterisation_run_id` | resolver-bound (safe) |
| `grouping_groups` | `grouping_run_id` | resolver-bound (safe) |
| `appraisal_by_doc` · `classification_by_doc` · `tags_by_doc` · `screening_by_doc` | **scope-wide** (scope_id only) | bind to the resolved run set where result rows carry run keys; else snapshot-bound at turn start — C2 verifies per kind with a leak test (new-run rows must not appear) |
| `coverage_records` | project + scope (**scope-wide**) | same binding treatment as above |
| `docs_by_tag` · `tag_aggregate` | scope-wide | same binding treatment |

## Verify gates (rev 2 — corrected against the real Makefile)

- **FULL `make verify`** at **A · B · C · F · H**. Rationale: A/B schema+runner
  (mandatory classes); **C adds a governed prompt** — `prompt-guard` only runs in
  full verify — and touches synthesis internals; **F changes the public API** —
  OpenAPI/client drift checks only run in full verify.
- **`make verify-fast`** at **D · E**.
- **G** gates on explicit frontend verification (unit + build) **plus the Playwright
  e2e including the new chat leg** — named commands in the phase commit, since root
  verify-fast runs neither and full verify skips Playwright.
- **OpenAPI + TS client regeneration runs in every phase that changes the API
  surface (D and F), not only F** — drift asserted at each.

## Phase A — baseline + schema (FULL verify)

| # | Task | Executor | Notes |
|---|---|---|---|
| A1 | `make verify` green baseline | lead (inline) | one command |
| A2 | Migration: `conversation` (+ partial unique active-planning index, `entry_artefact_id`) · `chat_turn` · `planning_transcript.conversation_id` · `plan.conversation_id` · `artefact.capability_run_id` · legacy backfill per the truth table above | codex | machine-verifiable: A3 + up/down |
| A3 | Migration tests: up/down · one fixture per truth-table row · invariant index | codex (with A2) | |
| A4 | Destructive-downgrade rehearsal (pre-write only) + post-write rollback note | fast-worker | mechanical |

## Phase B — planning re-home + lineage writers (FULL verify)

| # | Task | Executor | Notes |
|---|---|---|---|
| B1 | Executed-plan→`PlanDraftWire` seed mapping (design) | **lead** | seam design — successor semantics |
| B2 | Conversation lifecycle service: create-with-project/first-turn; one-active invariant; **successor created by the first planning turn after closure, seeded per B1, in its reservation transaction** (contract rev 3.2 — the button only navigates); planning rehydration scoped to the active conversation; **planning calls use `conversation_id` as the stable Langfuse session id** (contract strand 7 — fixes the per-turn throwaway session) | codex | parity tests keep planning behaviour otherwise identical |
| B3 | Closure delta in `_finish_run`'s existing terminal transaction (verified as-built: status + `run.finished` already commit in one `engine.begin()`) | **lead** | fragile runner surface; smallest diff; parity tests |
| B4 | **Lineage writer plumbing**: plan creation (`orchestrate.py` insert) + steering plan-version writes inherit `conversation_id`; artefact insert (`synthesise.py`) writes `capability_run_id`; **lineage-walk test on a stub run** (conversation → plan → run → artefact) + legacy-NULL honesty test | codex | rubric 13's home — was silently unowned in rev 1 |
| B5 | Planning endpoints: additive `conversation_id` exposure; lifecycle/closure/seeding/rehydration-scope/session-id tests | codex | crash-between-phases honesty cases |

## Phase C — chat turn engine (FULL verify — prompt-guard + synthesis suite)

| # | Task | Executor | Notes |
|---|---|---|---|
| C0 | **Kernel seam design**: pin the kernel callable/result signatures, the injected final-emitter interface, and the section adapter's preserved behaviour (provider calls, transcripts, error emission, accounting) + characterization assertions to hold C1 to | **lead** | seam design — the plan lane showed "bit-identical" isn't free; C1 delegates only after this pin |
| C1 | Kernel extraction per C0; section adapter passes the characterization assertions; synthesis suite untouched and green | codex | |
| C2 | Terminal-run component-id resolver + **reader-scope binding per the matrix above** (+ per-kind leak tests; replacement/additive re-runs; degraded missing components; resolved once per turn) | codex | |
| C3 | Chat turn service: two-phase rows (reservation sets the title from the first question — contract rev 3.2), conversation-keyed single-flight, 3c transition table incl. the cancel endpoint, idempotency, fences, resource controls, per-call short-lived connections | codex | barrier/race tests per rubric 13/16/21 |
| C4 | `chat_v1` system prompt + wire models (`claims[]`/citations) + context assembler (frame incl. artefact body + budget rule + labels) | **lead** | prompt-bearing end-to-end |
| C5 | Citation floor + compaction (citable set = tool ∪ frame; appraised/citable-kind; orphan strip; warning marker) + floor tests + **tool-allowlist test** (exactly `search_chunks · query_findings · lookup`; `search`/write tools not constructible — rubric 9's home) | codex | |
| C6 | Context-assembler + tracing tests + **injection-boundary matrix test**: every channel into `chat_v1` (current question, each windowed turn, every frame field, every tool-result channel) asserted sanitized + bounded + data-labelled (rubric 17's home) | fast-worker | mechanical from the enumerated matrix |

## Phase D — streaming (verify-fast + API regen/drift)

| # | Task | Executor | Notes |
|---|---|---|---|
| D0 | **Cancel-wire + stream-shape pin**: the `POST .../turns/{turn_id}/cancel` endpoint semantics (contract rev 3.2) and the NDJSON event schemas/field names | **lead** | public-wire design; D1 delegates against it |
| D1 | Stream implementation per D0: event union, exactly-one-terminal semantics, post-header `failed` events, cancel endpoint, disconnect-finishes-server-side, cancelled-partial persistence; OpenAI streaming adapter behind the neutral wire; **owns `POST .../turns`**; OpenAPI/client regen + drift check | codex | stream contract tests per rubric 20; serialized with F on the router (no parallel router edits) |

## Phase E — judge enrichment (verify-fast; **the contract-named cut-line**)

| # | Task | Executor | Notes |
|---|---|---|---|
| E1 | Emission→judge-envelope shaping; async worker; CAS write; unchecked→verdict read-model states; enrichment tests | codex | reuses `grounding_judge` as-is |
| E2 | Judge-prompt adaptation ONLY if E1 shows envelope mis-fit | **lead** | prompt gate |

**Cut honesty:** exercising this cut-line (or any other scope cut) requires an owner-
approved contract + rubric revision before Phase H — rubric 10a currently binds
completion; a cut without the revision leaves the task in progress, not done.

## Phase F — conversations API surface (FULL verify — drift gate)

| # | Task | Executor | Notes |
|---|---|---|---|
| F1 | Endpoints: library list (+`status=archived`), `GET /{cid}`, **`GET /{cid}/turns`** (paginated ascending — G1's rehydration/refetch source; was unowned in rev 1), create (`entry_artefact_id`; title "New chat"), PATCH, archive/unarchive; BOLA + archived-semantics tests; OpenAPI/TS regen + drift | codex | runs after D (router serialization) |

## Phase G — frontend (gate: frontend unit + build + Playwright e2e incl. chat leg)

| # | Task | Executor | Notes |
|---|---|---|---|
| G1 | Store layer: conversation store (reducer parity with `usePlanningTranscript`), NDJSON stream reader, cancel mutation, **bounded enrichment refetch per the pinned polling policy** | codex | fake-timer tests |
| G2 | **Product surface — lead as integrator** (taste-bearing per the ladder; 027/028 precedent): rail composition, tabs/switcher, Chats library, context chip, URL-addressable conversations, composer stream/stop states, message rendering (markers, references, hover quote-in-context, unchecked→verdict upgrade, warning/stopped badges), hand-off card, entry points, **plus the rev-2.2 additions: copy-answer (with references + trust state), date dividers, composer draft persistence, deterministic empty-state starter questions (owner taste cut-line)** — **delegating enumerated component transcription to codex per mockup + design-inputs** (G2a rail/tab/library shells · G2b message/citation components · G2c state plumbing), lead owns composition, copy, and final pass | **lead** (+codex sub-briefs) | spec = contract §6 + mockup + design-inputs |
| G3 | Frontend test sweep + mock-journey e2e chat leg (stub backend) | fast-worker | from G2's enumerated list |

## Phase H — step-6 exit (FULL verify)

| # | Task | Executor | Notes |
|---|---|---|---|
| H1 | `web-api.md` § Conversations rewrite · deferred.md updates (incl. rev-2.2 named seams: conversation search · standing chat instructions · continue-generating) · AGENTS.md pointer | fast-worker | doc transcription |
| H2 | ADR **0029** — unified conversation model + lineage chain + chat fast-path | **lead** | 0028 is taken (task 028) |
| H3 | Scoped live check per contract (local funded key; ≤30 min): migration sanity · chat from artefact (provenance + generative + evidence-not-held/handoff) · stop mid-stream (cancel endpoint) · bare-disconnect completion · restart durability · library round-trip · successor seeding · CI e2e smoke | lead + owner | |
| H4 | verification.md assembly (+ any codex-fallback substitutions) | lead | evidence adjudication |

## Step 7–10 handoff (rubric 8)

The build conversation ends at H. The **Tier-4 review stack runs in a fresh
conversation** (task-cycle-review): contract verifier · `/code-review` medium ·
**one security lane** (injection posture, tool-set boundary, BOLA, idempotency/races,
stream lifecycle) · adversarial code review (codex) · human deep review. Review diffs
exclude generated files (OpenAPI/TS client) and migration fixtures per the
review-economy pins; findings adjudicated by the fresh conversation's lead, evidence
into verification.md; then PR onto `dev`, human merge, close-out.

## Dependency notes

A → B → C → D → E/F → G → H. E after D (enrichment updates streamed rows); **D and F
serialize on the conversations router**; F may otherwise overlap E. C0 blocks C1;
C1 blocks C3/C5. If E is cut (with the owner-approved contract/rubric revision the
cut requires), G ships "unchecked" states and E becomes the fast-follow.

## Risks

1. **C1 kernel extraction** — mitigated by C0's lead-pinned seam + characterization
   assertions + full synthesis suite in the phase gate.
2. **B3 runner delta** — smallest diff, lead-authored, parity tests; grounded:
   `_finish_run` already commits terminally in one transaction.
3. **Backfill on live data** — truth table above; fixtures per row; rehearsed
   downgrade; behaviour-level post-write rollback.
4. **First streaming plumbing** (D) — D0 pins the wire; blast radius one adapter.
5. **Codex quota** — fallback ladder per the standing rule.
