# ADR 0005 — First product egress: embedding + grouping seams, injection posture, Langfuse full-I/O tracing

- **Status:** Accepted — 2026-07-06 (Shabeer Rauf, task-009 contract + plan gates).
- **Date:** 2026-07-06
- **Context doc:** [task 009 contract, decisions 1–6, 13](../tasks/009-characterise/contract.md) ·
  clustering + chunking research 2026-07-05/06 (raw files referenced there) ·
  [execution-orchestration — tool registry, egress rules](../specs/system/execution-orchestration.md) ·
  [engineering-considerations — Langfuse, security, observability](../agentic-ops/engineering-considerations.md).

## Context

Tasks 001–008 built every pipeline component behind deterministic stubs and fixture
replay — zero runtime egress by build-stage discipline, while the specs are explicit
that v3.0 has live egress (inference first pass OpenAI → target Bedrock). Task 009
(characterise) is where two class-1 sequenced capabilities come due at once:
vectorisation (deferred by 008 to "the first vector reader") and generation (the
LLM-based thematic grouping the user chose over algorithmic clustering after two
research rounds — HDBSCAN degenerate at 10s-of-docs scopes, agglomerative
tuning-fiddly, TopicGPT-class grouping best aligned with human topic judgment).
Opening a gate means designing the seams it flows through, the credentials and
budget controls around it, the injection posture for third-party text entering
prompts, and the observability layer — all first-of-kind for this repo.

## Decision

1. **Two dedicated provider seams, mirroring the SearchBackend/DocumentFetcher
   precedent.** `EmbeddingBackend` (`embed_texts`, `mode`) and `GroupingBackend`
   (`discover`, `assign`, `mode`) — each with a live OpenAI implementation and a
   deterministic stub; both injected via `run_harness` optional parameters
   defaulting to stubs. Generation deliberately does **not** ride the existing
   `InferenceProvider.complete(prompt) -> str` (it cannot carry strict structured
   outputs, two models, timeouts and budget caps — contract-review blocker). The
   Bedrock route swaps in at these seams.
2. **Egress is the product; the suite is not.** `make verify` and all library
   defaults are stub-only and egress-free (socket-deny enforced); the skeleton goes
   live when `OPENAI_API_KEY` is configured — a configured key on the operator
   entrypoint *is* live intent (an extra opt-in flag was adopted from adversarial
   review and reversed at user direction). Keys are env-only, never defaults,
   never logged; per-run budget guards on both paths (embed `max_chunks`; grouping
   baseline `1 + ceil(n/batch)` with an enforced retry-capped maximum checked
   before any live call).
3. **Neither egress path is agent-invocable.** `search` remains the only
   agent-invocable egress verb; embedding and grouping calls are mechanical
   execution under the governed run — telemetry + run-record summary counts, no
   per-item governance events (008's fetch posture extended).
4. **Injection posture (first corpus text into an LLM prompt).** Structural
   mitigations over prompt-hope: document content enters prompts as id-keyed data
   records under explicit data/instructions separation; output channels are
   schema-constrained to themes + id assignments (no tools, no free text acting on
   the world); exhaustiveness and id validity enforced in code after every call;
   theme names/descriptions are themselves treated as untrusted model output
   (length/charset constraints, stored and rendered as data); standing rule: tags
   and summaries re-enter prompts only as data. Embeddings interpret nothing.
5. **Prompts are repo-first, versioned, lead-authored.** The
   `characterise_grouping_v1` discovery+assignment pair is the repo's first product
   prompt surface; version recorded on every characterisation row and event
   (the `rubric_version` discipline applied to prompts). Langfuse remains the
   runtime *registry* seam — not adopted in this slice.
6. **Langfuse is the trace backbone from the first LLM call — full I/O,
   eval-ready.** Tracing wraps the two live backends only: one trace per run, spans
   per component/call carrying ids, profile/prompt versions, models, tokens,
   latency, cost; full prompt/output payloads (user-settled, resolving the
   engineering-considerations sensitive-tracing item — instances are
   user-operated); validation outcomes as scores so trace → eval-dataset promotion
   has substrate from day one. Env-driven, no-op without keys; stubs never traced.
   Retention/sampling/masking/access are the observability seam's recorded open
   items.

## Consequences

- The egress gate is one-way for the product: from 009 onward the live path is the
  intended operating mode, and later live slices (search backends, document
  fetcher, LLM screen/classify, grounding tier) reuse these control patterns
  (seam + stub default + env keys + budget guard + posture) rather than
  re-deriving them.
- Every future LLM-bearing slice inherits the injection posture and the
  tags/summaries-as-data rule as standing constraints, and the trace backbone as
  its default observability surface.
- The stub/live split keeps CI deterministic forever; live behaviour is verified
  by manual evidence + the eval workstream, never by the suite.
- Costs are bounded by construction (budget maxima known pre-call), and every
  grouping is attributable (`grouping_provenance`) even though it is
  interpretive and non-reproducible by design.

## Alternatives considered

- **Extend `InferenceProvider` for generation** — rejected: the grounding stub's
  contract is a different shape; overloading it would blur two seams (blocker
  finding at contract review).
- **Local embedding model / algorithmic clustering** — rejected at user gates:
  gate-excluded ML dependency tier; degenerate or tuning-fiddly at real corpus
  sizes; superseded by the provider route regardless.
- **Explicit live flag on top of the key** — adopted from adversarial review,
  reversed at user pushback: egress is the product; the discipline lives in the
  suite/library defaults, not in operator friction.
- **Metadata-only tracing** — declined: full I/O is the trace backbone's value for
  the eval surface; the instances are user-operated and the open policy items are
  recorded, not silently defaulted.
