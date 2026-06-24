---
type: System contract
title: Execution & orchestration
description: Orchestrator and sub-agents, the tool registry + universal core, steering modes, the routing rule and durability.
tags: [system, orchestration, execution, tools, steering, durability]
timestamp: 2026-06-22
---

# System contract — Execution & orchestration

**Distils** [backend-architecture-reference.md](../sources/backend/backend-architecture-reference.md)
§4 (capabilities, tools, execution model) and §6 (steering & durability). This spec + `docs/adr/` are canonical; the source is frozen origin
([ADR 0002](../../adr/0002-spec-governance.md)).

## Orchestrator + capability sub-agents

- **One user-facing surface: the persistent project orchestrator/co-pilot.** It frames the
  task, owns the **orchestration plan**, decides at *plan time* (reading declared capability
  specs) which capabilities/components meet the directive, delegates to **capability
  sub-agents**, mediates check-ins, records decisions, explains what changed.
- **Sub-agents never address the user directly.** A sub-agent surfaces input/decision requests
  **only** through `clarify` / `escalate`: it **parks** on a durable signal and the orchestrator
  relays the request into the thread, **attributed to the capability**, collects the response,
  resumes the sub-agent. N capabilities, **not** N chatbots.
- **Plan-time authority, not runtime.** Flexibility lives at plan time (cheap, human-gated,
  logged); execution follows the agreed plan. The capability agent's only runtime discretion is
  the bounded **escape hatches** (e.g. evidence thin → extra search, provided it flags/logs).
- **The co-pilot is the same agent pointed at chat** — answers questions, produces **no
  artefact** (answers ephemeral). *Provenance lookup* reads back already-verified grounding;
  *generative synthesis* is a `produce-grounded-block` rendered into chat, not persisted. Runs
  **faster but honestly tiered** (reuses the §3.3 trust-tier taxonomy — a quick answer is
  *visibly* "pure LLM reasoning"). **Promotion to a block re-runs the full bar.** 🟡 fast-path
  discipline (skip verify? re-appraise? latency budget) open.
- **Private Q&A runs a reduced, read-only scope** — the three internal read tools
  (`retrieve`, `lookup`, `query-findings`), **no `search`** (external egress must not originate
  from a surface outside the audit record). Offers to convert an evidence need into a **shared
  search request**.

## How a capability sub-agent is realised

Not a per-plan graph, not one agent handed every tool. A **declared skeleton (subgraph) of
components**, where **each component is realised by the mechanism its nature demands**:
- **Deterministic procedure / fan-out map** for mechanical work (appraise/extract N docs, compute
  the coverage snapshot) — iteration count runtime-determined, per-item logic fixed; the agent
  invokes it as *one* tool (facade principle).
- **Agent-loop over scoped tools** for deliberative work (synthesise, compare) — tool-call
  discretion + bounded escape hatches.

**Rigidity is a per-capability parameter** (how much skeleton + the deterministic-vs-agentic
mix). Extremes are degenerate cases of one construct (pure agent-loop = scrutinise/red-team;
fixed linear pipeline = v2). EB sits toward structured. Substrate: a **fixed LangGraph harness
interpreting the plan-as-data**, not a graph rebuilt per run.

## The vocabulary — tool / component / capability

- **Tool** — a single shared callable operation with declared I/O, in the registry. *What the
  system can do.* May be a thin primitive **or a facade over a substantial internal workflow**
  (`produce-grounded-block`; a corpus-scale `appraise` fan-out). Size/duration is **not** what
  makes a tool — the single declared interface is. "Tool vs workflow" is a category error.
- **Component** — a step in **one** capability's skeleton; **owned by its capability, run by its
  expert sub-agent**.
- **Capability** — an artefact-producing composition of components, run by a dedicated expert
  sub-agent, coordinated by the orchestrator.

One-liner: **tools are the shared verbs; components are a capability's sentences built from
them.**

- **Tools are registry-shared, declaration-scoped — not capability-agnostic.** An agent sees
  only its current component's declared tools + the tiny universal core. The registry can grow
  large without degrading any agent's choice (reuse without exposure).
- **Cross-capability reuse splits by what's reused**: a shared **operation** → reference the
  **tool**; another capability's **analysis** (a component) → the **orchestrator invokes that
  capability's expert sub-agent** to run the component. **A capability never runs another's
  component itself** (a component carries its owner's expertise/context; a tool does not).
- **Gradation vs distinct operation — the I/O test**: only intensity/depth varies (same I/O
  shape) → a **gradation** (a plan parameter; a named bundle = a "mode"); I/O shape differs,
  output consumed inside → a **component**; I/O shape differs, output is a standalone artefact →
  a **capability**. Guards against capability proliferation.

## Tools — the registry, the universal core, hard rules

- **Registry of tools available to be *declared***, not a runtime palette. **Prefer coarse
  facade tools** over granular primitives (one `gather_evidence`, not {search, dedupe, rank,
  fetch}). **Dynamic tool-retrieval only as a fallback** for genuinely open cases.
- **Universal core** (every stateful capability agent carries it; bar = "needed by essentially
  *all*," not "useful"):
  `search` · `retrieve` · `lookup` · `appraise` · `produce-grounded-block` · `escalate` ·
  `clarify`.
  - **`search`** — the **only agent-invocable egress verb in v3.0**; over configured backends
    each carrying a declared **trust class** (v3.0: OpenAlex, Overton). **Every call emits a
    canonical egress governance event** (§9). ⏸ open-web backend is a deferred seam **behind the
    same verb** (declaration-scoped per component; ingests as frozen chunks — no cite-the-live-web
    path).
  - **`retrieve`** — in-corpus hybrid lexical+vector retrieval over the project corpus; **reads
    the derived index, never the canonical layer**. See *Tier-0 retrieval contract* below.
  - **`lookup`** — deterministic, identifier/filter-addressed, side-effect-free access to
    **canonical project state**, including aggregate queries over columns/tags (the queries whose
    re-running *is* metadata-pattern verification). No ranking, no egress, no writes.
  - **`appraise`** — source quality (see [provenance-grounding.md](provenance-grounding.md)).
  - **`produce-grounded-block`** — synthesise → cite → verify → write (cite/verify mandatory).
  - **`escalate`** — hand a *decision* to a human (transfers authority; usually substance;
    blocks the branch). **`clarify`** — request *missing information* (agent stays decider;
    usually method; can be non-blocking).
- **Scoped, not core**: compute/calculation (quantitative capabilities only); **`query-findings`**
  (only capabilities reading the findings layer); any future open-web `search` backend.
- **Hard rules**: *provenance is data, `cite` is the action* (no "attach citation" path).
  Trust is **enforced at grounding** (`produce-grounded-block` requires each cited claim
  generated-from + citing only **appraised** evidence) — so search/retrieve and appraise stay
  separate tools. **Ingestion is not a tool** (closes indirect-injection via "ingest this
  content" — the named primary attack surface). **Transcripts are not a tool target** —
  capability agents see only promoted structured state, never free-form chat.

## Tier-0 retrieval contract

v3.0 retrieval is **hybrid lexical + dense** over the project corpus — **Postgres FTS + pgvector
on Aurora** — with **application-side rank fusion** (e.g. RRF), never assumed from the DB.
**Cross-encoder reranking sits behind the retrieval-profile seam** (Bedrock Rerank keeps it in
the inference trust boundary), used where precision matters, **never always-on** — selection
scans must preserve recall/coverage/diversity (a missed awkward source is worse than a noisy
shortlist; **false negatives are the dangerous failure mode**). Returns a **traceable candidate
set** (queries, filters, lexical+dense candidates, fused ranking, selected passages, near-misses,
coverage) on the telemetry plane; the **gap-coverage profile additionally writes canonical
attempted-search provenance**. **Retrieval profiles** (gradations of one tool): selection scan
(recall/diversity) · grounding/citation (precision; may cross-encode) · gap-coverage (records
coverage) · Q&A lookup (low-latency, scoped). Indexes are **derived, rebuildable** behind the
adapter seam; a dedicated retrieval service is ⏸ deferred unless Aurora-native fails on measured
quality/latency/filtering/scale/operability.

## Steering modes & the routing rule

**Steering mode** = a per-run dial for involvement *frequency* (mutable mid-run; check-ins
suppressible) — **Minimal** (runs to completion; substance still pauses) · **Moderate**
(recommended default; pauses on important decisions) · **Frequent** (every section/block).
*(UX label currently reads "Thorough" — sync; "thoroughness" is the separate depth axis, §5.)*

**The routing rule** — when a run hits something the plan didn't anticipate, route to *pause &
ask* / *flag & continue* / *silently log & continue*, by **kind of decision × mode**:

| Situation | Minimal | Moderate | Frequent |
|---|---|---|---|
| Method — within a declared escape hatch | log + continue | flag + continue | pause |
| Method — outside the hatch envelope | flag + continue | pause | pause |
| **Substance — declared gate *or* conclusion-shaping residual** | **pause** | **pause** | **pause** |

- **Firm principle: substance escalates to a human in *every* mode** — and a substance check-in
  can **never** be silenced by the frequency dial or a suppression rule (hard-constrained).
- **Classification is resolved structurally, not by a from-scratch runtime judgement**: substance
  is pre-declared as **anticipated mandatory checkpoints** (§4 — unconditional gates *or*
  conditional steer-points with explicit escalation triggers); sanctioned method is pre-declared
  as **escape hatches**. The residual = **agent judgement calls** (broader than "would the
  conclusion change?" — covers emphasis/prioritisation/interpretation/downstream use;
  **bias-to-escalate when substance-or-unsure**), each emitting a durable **`agent_judgement_routed`
  governance event** (so even "method, continue" is reviewable/sampleable). ⏸ no first-principles
  runtime classifier and **no pre-enumerated judgement taxonomy** (brittle, falsely complete) —
  the event stream is the evidence base for later gates/hatches. Known residual-of-the-residual:
  **under-emission**, now measurable by sampling traces.
- **Minimal flags are batch-active, passively-live** — no mid-run interrupt; collated into the
  end-of-run review. **Checkpoints are steer-points, not approve/reject** (the user injects
  reasoning, reshapes output, overrides a verdict since rejected alternatives are visible).
- **Human substance enters two ways**: steering at check-ins, and human-authored/amended
  artefact content — both represented honestly in provenance (never paraphrase-laundered into
  agent-attributed text).

## Durability & concurrency

- **Serial execution in v3.0** — one active branch; a check-in **holds the run**. The dependency
  DAG is **persisted** (the orchestration plan *is* this graph) so parallel-eligible sets are
  identifiable at plan time; v3.0 walks a **topological order serially**. ⏸ branch-level
  parallelism deferred (the evidence-parallel / synthesis-centralised split is preserved for
  when it lands — never fan out the *conclusion*).
- **"Serial" ≠ no within-step fan-out** — data-parallel fan-out over a corpus (appraise/extract N
  docs) is **retained**; atomic to the durability engine (block/component boundary = checkpoint),
  needs no durable cross-branch exactly-once.
- **Durable, resumable runs** via **block-boundary commits + tool-result memoisation.**
  Parked-branch freshness: resume on **current** structured state, staleness **flagged** (§3.6),
  never silently consumed. Live steering = a signal applied at the **next block boundary**. Agent
  write-concurrency is trivial under serial v3.0 (single active writer onto the §9 event log).
