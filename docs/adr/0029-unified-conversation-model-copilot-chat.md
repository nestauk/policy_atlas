# ADR 0029 — Unified conversation model and the co-pilot chat fast path

- **Status:** Accepted — 2026-08-10 (owner, with the 029 plan approval)
- **Date:** 2026-08-10
- **Task:** 029-copilot-chat · contract approved 2026-08-10 (rev 2.8; adversarial
  rev 3; re-approved rev 3.1; plan-stage pins ratified rev 3.2/3.3)
- **Binding design records:** `docs/tasks/029-copilot-chat/contract.md` (rev 3.3),
  `plan.md` (rev 2.2), `mockup/chat-mockup.html`, `research-notes.md` (4-lane
  2025–26 practice survey), `v2-chat-review.md`, `design-inputs.md` (PR #35
  adjudication)

## Context

After an analysis completes, users follow through on the artefact with questions —
the co-pilot surface the architecture always specified (execution-orchestration
§ Orchestrator: same agent pointed at chat, ephemeral answers, read-only tool scope,
🟡 fast-path discipline open). 027 shipped a single rolling `planning_transcript`
per project, explicitly deferring the thread model to this slice; its full-replay
rehydration grows without bound. The owner's product model (interview, 2026-08-06):
a project holds many conversations, Claude-Projects-style — one rolling transcript
buries parallel lines of questioning. Design inputs: a 2025–26 practice survey,
a review of V2's chat (agentic RAG done well, undermined by localStorage-only
transcripts and chat-side live egress), and the colleague's PR #35 mockup.

## Decisions

1. **A project holds many conversations, in one model.** `conversation`
   (`kind ∈ planning | chat`) + per-kind turn tables. **Chats** are read-only
   follow-through: project-scoped, answering across artefacts (the entry artefact is
   a context chip and provenance fact, never a scope fence), never mutating —
   evidence needs hand off to planning via a typed `handoff` field. **Planning
   conversations** are one per plan lineage: a `succeeded | degraded` run closes its
   conversation *inside the run's terminal transaction*; "Run the analysis again"
   navigates, and the next planning turn creates the successor seeded by a
   deterministic executed-plan→draft mapping. Rehydration scopes to one
   conversation, bounding planner context by construction. At most one active
   planning conversation per project (partial unique index) preserves the
   plan-as-object invariant. *Rejected:* keeping the rolling thread (unbounded
   rehydration; buries follow-through; 027 itself named this slice as its end);
   splitting planning transcripts per run presentationally (plans are already
   per-run via `plan_id + plan_version`); chats that replan or start runs (the
   PR #35 mockup direction — collides with the single gated plan).

2. **The transcript store is ours, turn-pair grain.** Postgres companion store;
   provider-side conversation state stays forbidden (018 — audit/FOI/portability;
   the practice survey confirms owned stores are the recommended regulated-deployment
   pattern, and V2's localStorage-only chat is the counter-example). One row per
   turn-pair with `client_turn_id` idempotency, monotonic `turn_index`, status
   machine `pending | completed | failed | cancelled`. *Rejected:* per-message rows
   now (production norm, but it buys regenerate/branching/tool-rows — all out of
   scope; the pair→per-message split is the named migration seam); V2's
   localStorage.

3. **The chat fast path (resolves the spec's 🟡): deterministic floors + async
   claim-grain judge, no inline verify.** Stage 1 at the terminal payload:
   `claims[]` mapping to durable-id citations; citable set = tool-returned ∪
   hydrated-artefact frame ids; appraised/citable-kind required; orphan markers
   stripped; compaction; zero surviving citations → a "not evidence-checked"
   *warning* (never a tier — Tier 4 is not a safe harbour), with the prompt rule
   *evidential claims about the corpus cite or abstain*. Stage 2: the grounding
   judge runs post-stream in its existing envelope, attaching per-claim
   `{verdict, weakly_grounded, rationale}` — the only tier display on cited
   answers; failure leaves honest "unchecked"; enrichment never blocks and writes
   compare-and-set. *Rejected:* answer-wide self-reported tier (flattens mixed
   answers; self-grades in the judge's vocabulary); V2's server-pre-assigned
   citation register (free-prose-era mechanism; invariants ported instead);
   a deterministic quote-presence floor (binds the block discipline chat explicitly
   doesn't carry; claim support is the judge's job); blocking the answer on the
   judge.

4. **Streaming is first-class, provider-neutral.** The turn POST returns an NDJSON
   union `progress | delta | completed | failed | cancelled` — typed tool-step
   progress, text deltas, exactly one terminal validated payload; explicit cancel
   endpoint (`…/turns/{turn_id}/cancel`) persists the partial as `cancelled` with
   inert markers; bare disconnect finishes server-side. The wire pin (deltas + one
   terminal payload, never provider partial-JSON) means the Bedrock move re-ports
   only the provider adapter. *Rejected:* blocking answers (the one pin the practice
   survey showed as genuinely non-mainstream); new project-SSE frames (028 froze
   that vocabulary); waiting for Bedrock.

5. **Context = grounded frame + ceiling-only window.** The fresh-chat frame carries
   project identity, the coverage sentence, funnel counts, and **each artefact's
   grounded body with its citation keys** (the verified content of record — never
   the persisted summary, whose not-load-bearing spec rule stands; budget rule:
   entry-context artefact full, others degrade to key findings + titles). History:
   the whole thread under a char ceiling, oldest-first on overflow. *Rejected:*
   summary hydration (spec conflict, caught by the adversarial lane); fixed small-K
   windows (API-app cost pattern; flagship products carry the full thread);
   front-loading raw chunks (retrieval is the loop's job).

6. **The agentic core is reuse via kernel extraction.** A bounded tool-loop kernel
   (extracted from `run_section_loop` behind a lead-pinned seam) over the three
   read executors, scoped by a per-turn terminal-run component-id resolver; the
   tool set — `search_chunks · query_findings · lookup`, no `search`, no writes —
   is the security boundary (egress must not originate outside the audit record;
   V2's chat-side Parliament egress is the counter-example). Answers render as
   plain prose with inline markers — no markdown, which is both copy diet and an
   EchoLeak-class exfiltration control.

7. **Lineage lands at row grain.** `plan.conversation_id` +
   `artefact.capability_run_id` (closing the named 025/027 gap) make
   *conversation → plan → run → artefact* walkable; field-level turn provenance
   remains the deferred plan-as-object seam.

## Consequences

- **Tier 4:** the legacy backfill is a data migration on live production data —
  truth table in the plan, per-row fixtures, rehearsed pre-write downgrade;
  post-write rollback is behaviour-level with schema/data retained.
- The planning surface is re-homed under parity tests; the planning wart of a
  throwaway Langfuse session per turn is fixed by session-per-conversation.
- The backend gains its first token-streaming plumbing, contained behind the
  neutral wire.
- The eval slice inherits: judge quality on chat-shaped claims, the unenriched
  window, and the thumbs-feedback → Langfuse-scores gold-set seam.
- Deferred, named: promotion-to-block · shared-search conversion · recall +
  cross-conversation rationale carry · resumable streams · per-message row split
  (regenerate/branching) · conversation search · standing chat instructions ·
  continue-generating · multi-artefact structured reads (workspace-cluster).
