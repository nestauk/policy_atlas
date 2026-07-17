---
type: System contract
title: Execution & orchestration
description: Orchestrator and sub-agents, the tool registry + universal core, steering modes, the routing rule and durability.
tags: [system, orchestration, execution, tools, steering, durability]
timestamp: 2026-07-05
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
- **Every capability sub-agent composes its own artefact at its run terminus** (task 013
  flow-back): composition is capability expertise, so the orchestrator *shapes* the artefact at
  plan time (sections, facets, depth — compiled parameters) and owns **no runtime content
  machinery**. EB's instance is its `synthesise` terminal component.
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

*(Rewritten by task 024 — ADRs 0020–0023. The organising principle is the **decider dial**:
every decision surfaces in the durable record; the steering mode never changes what is
decided or what is visible — it moves the **decider** between the user and the orchestrator.)*

**Steering mode** = a per-run **delegation posture** (mutable mid-run), answering "when
should I come back to you?". Check-in *stream* ≠ pauses: progress check-ins stream (and
persist as steering events) in every mode; the mode governs only what blocks and who
answers. The four modes, with their user-facing labels:

| Label ("When should I come back to you?") | Plan value | User decides live | Orchestrator decides (recorded + flagged) |
|---|---|---|---|
| "Often — walk me through it" | `frequent` | everything (the watch only *recommends*) | nothing |
| "At the key decisions" *(default)* | `moderate` | P2 + P3 + P4 always (the evidence base · the selection · the synthesis shape); P1 + watch escalations when fired | routine boundary residuals |
| "Only if something needs my judgment" | `minimal` | fired triggers + watch-escalated substance | everything else, within the user's own surface |
| "Never — here are my standing instructions" | `unattended` | nothing live | per the discretion model below |

The pauses hang on the **steer-point lattice** (task 024): **P1** `search_exception`
(after acquire, exception-only — fires on hard coverage triggers in every attended mode) ·
**P2** `evidence_base_coverage` (before select — the full coverage picture, where adequacy
is actually judgeable) · **P3** `deepening_selection` (after select, with a selection
preview) · **P4** `synthesis_shape` (before synthesise, with the proposal). Every pause
presents the canonical floor options + orchestrator-authored run-specific options + free
text through the router; every pause and decision is a durable steering event keyed to the
walk's `capability_run` identity. Named behaviour change (024): **Minimal is now
fired-only at every lattice point** — the as-built 017 behaviour paused unconditionally at
deepening-selection; Minimal's guarantee is the enlarged structural trigger floor, not a
fixed pause. Per-mode approval/recording guarantees — the **audit posture across the
modes** — live in [plan-as-object.md](plan-as-object.md).

**The routing rule** — when a run hits something the plan didn't anticipate, route to *pause &
ask* / *flag & continue* / *silently log & continue*, by **kind of decision × mode**:

| Situation | Unattended | Minimal | Moderate | Frequent |
|---|---|---|---|---|
| Method — within a declared escape hatch | log + continue | log + continue | flag + continue | pause |
| Method — outside the hatch envelope | flag + continue | flag + continue | pause | pause |
| **Substance — declared gate *or* conclusion-shaping residual** | **standing rule, else watch discretion (flagged loudest)** | **pause** | **pause** | **pause** |

- **Firm principle, restated for the decider dial: substance is never silent in any mode.**
  A substance decision always surfaces in the durable record with its decider attributed
  (`decided_by: user | orchestrator | standing_default`); the dial can move the decider,
  never the visibility. The **structural trigger floor is never suppressible** — declared
  triggers fire deterministically regardless of the watch's judgement, which can add
  escalations but never remove one.
- **The orchestrator watch — the decider layer** *(024; discharges this spec's former
  "⏸ no first-principles runtime classifier" deferral — see below)*: one orchestrator
  agent, three moments (the planning conversation · the free-text steering **router** at
  pauses · the boundary **watch**), one prompt family, one shared session. The watch
  observes component boundaries under **structurally gated invocation**: clean boundaries
  are resolved deterministically (a no-LLM `agent_judgement_routed` `clean_boundary`
  event); anomalous check-ins get a mini-class notable-or-not triage (mistakes bias upward
  — substance-or-unsure always promotes to decision-point treatment); decision points get
  a single-shot judgment-class deliberation over a pre-fetched **bundle** built under the
  option-completeness rule, with a capped read-tool fallback (bounded, allowlisted,
  every call + digest evented). Where the mode delegates, the watch decides **in loco
  user, within the user's own surface** — the same options and free-text grammar,
  compiled through the same author-blind fail-closed parsers — attributed, flagged, and
  overridable at any attended pause. **Authority order is fixed regardless of author:
  user > declared rules > orchestrator.** Replacement re-runs bias-to-escalate in
  attended modes (they change what everything downstream sees); additive re-runs are
  self-decidable where the mode delegates. Fail-safe: a watch or router failure degrades
  to the deterministic floor (structural routing, canonical menu) — the run never depends
  on the judgement layer being up.
- **Unattended — discretion is the mode** *(024 revision of the 017 proceed-and-flag
  mechanism)*: choosing Unattended **is** the delegation. Standing instructions are
  pre-declared per steer point as visible plan content (authored in the planning
  conversation: the planner walks the steer points proposing plain-language defaults —
  accepted, edited, or skipped), and a **pinned rule always overrides the watch**; a
  declared hard stop is always honoured — discretion can never override a declared stop.
  A decision no pinned rule covers is taken by the watch under the disciplines above and
  flagged **`unconfigured_default` — the loudest flag class, reviewed first in the
  collation** (retained from the 017 design; what changed is the resolver: watch
  discretion with recorded reasoning replaces the blanket proceed-and-flag, so the FOI
  record carries *why*, not just *that*). Approving the plan is the consent; every
  auto-resolution is flagged, collated into the end-of-run review, and marked on the run
  record.
- **The classifier deferral, discharged honestly** *(the former ⏸)*: classification is
  still resolved structurally first — substance as **anticipated mandatory checkpoints**
  (§4), sanctioned method as **escape hatches**, and the deterministic routing table above
  intact. What 024 adds is an **additive, floor-bounded, non-taxonomic judgement layer**
  over the residual: the watch triages what structure did not resolve, biased to
  escalate, with every verdict emitting a durable **`agent_judgement_routed`** governance
  event (so even "clean boundary, continue" is reviewable). There is still **no
  pre-enumerated judgement taxonomy** — completeness beyond the cheap-and-persisted
  trigger floor is the watch's residual coverage, and the event stream remains the
  evidence base for later gates/hatches. Known residual-of-the-residual: **under-emission**,
  measurable by sampling traces; plus the named LLM→LLM channel — watch-authored text
  entering downstream prompts in delegated modes has no confirm gate; its controls are
  attribution, loudest-first flags, author-blind compilation, and user override at any
  attended pause (an eval measurement, not a silent assumption — ADR 0021).
- **Minimal flags are batch-active, passively-live** — no mid-run interrupt; collated into
  the end-of-run review. **Checkpoints are steer-points, not approve/reject** (the user
  injects reasoning, reshapes output, overrides a verdict since rejected alternatives are
  visible). Every re-run option declares its mode — **additive** (grows the evidence base;
  prior outputs stand) vs **replacement** (redoes and supersedes; rows immutable, the
  walk's reference moves — superseded, never deleted).
- **Human substance enters two ways**: steering at check-ins (verbatim `user_text` on the
  decision event — prose is data, never paraphrase-laundered), and human-authored/amended
  artefact content — both represented honestly in provenance.

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
