---
okf_version: "0.1"
---

# Spec index

This index routes implementation work to the relevant Policy Atlas v3.0 specs. It is
always-loaded context: it tells an agent **what to read for a kind of task**, not what the
architecture says. Load full sections on demand.

## Frozen sources (historical origin) — [ADR 0002](../adr/0002-spec-governance.md)

These are the **frozen** documents the specs were distilled from — the original deliberation, **not
updated** going forward. Consult them only for areas no spec covers yet (the routing table below).
When two of them disagree on such an area, the lower number wins (ratified from the EB handoff §2).

1. [backend-architecture-reference.md](sources/backend/backend-architecture-reference.md) — canonical backend model: data model, tools/execution, plan-as-object, steering, collaboration, observability, persistence, security, deferred seams.
2. [backend-architecture-briefing.md](sources/backend/backend-architecture-briefing.md) — compressed shared mental model + commitments/deferred-seams appendix + glossary.
3. [backend-evidence-base-build-spec.md](sources/backend/backend-evidence-base-build-spec.md) — canonical Evidence Base capability behaviour (the doc these EB specs distil).
4. [evidence-base-ux-handoff.md](sources/evidence-base-ux/evidence-base-ux-handoff.md) — locked product decisions + repo-safe constraints; overrides visual shorthand below on those points.
5. [evidence-base-wireframes.html](sources/evidence-base-ux/evidence-base-wireframes.html) — static UX reference; product intent only, never a schema/contract source.
6. [nesta-brand-tokens.md](sources/evidence-base-ux/nesta-brand-tokens.md) + [hifi.css](sources/evidence-base-ux/hifi.css) — visual language / token cues.
7. [task-lifecycle-ux/](sources/task-lifecycle-ux/README.md) — the 2026-08-17 clickable prototype for the task-lifecycle IA (workspace level + the five task stages). Product intent only, never a schema/contract source; it contains outputs the backend deliberately does not produce. Read its README for how to unpack it.

Backend architecture and EB capability design outrank all visual shorthand. On locked product decisions and repo-safe constraints, the UX handoff (#4) overrides the wireframe and visual assets (#5, #6, #7).

## Distilled specs in this repo

These are **distillations** of the sources above — declarative, status-tagged, pointing back to
source sections. **These specs + `docs/adr/` are canonical and living** ([ADR 0002](../adr/0002-spec-governance.md));
where a spec covers a topic it is authoritative, not the frozen source. They are refined as
implementation lands — see the flow-back in [README](README).

- [product.md](product.md) — product boundary and shared mental model.
- System contracts (the cross-cutting framework every capability + the orchestrator honours):
  - [system/data-model.md](system/data-model.md)
  - [system/provenance-grounding.md](system/provenance-grounding.md)
  - [system/execution-orchestration.md](system/execution-orchestration.md)
  - [system/plan-as-object.md](system/plan-as-object.md)
  - [system/prompting.md](system/prompting.md) — doctrine for every prompt surface
    (promoted from the 018 research + loop method; not distilled from the frozen sources).
- Capability specs (instances of the framework):
  - [capabilities/evidence-base/](capabilities/evidence-base/) — the first and only v3.0 capability.

## What to read for a task

| If the task touches… | Read |
|---|---|
| Entities, blocks, addressable units, annotations, columns/tags, corpus, snapshots, findings layer, versioning, staleness | [system/data-model.md](system/data-model.md) → arch §3 |
| Meta-synthesis, cross-artefact derivation/dependencies, inherited-artefact edits | [system/data-model.md](system/data-model.md) → arch §3.4 |
| Claims, citations, grounding tiers, gaps, patterns, `produce-grounded-block`/verify, summaries | [system/provenance-grounding.md](system/provenance-grounding.md) → arch §3.3, §4 |
| Orchestrator/sub-agents, the tool registry + universal core, steering modes, the routing rule, durability | [system/execution-orchestration.md](system/execution-orchestration.md) → arch §4, §6 |
| The plan object, plan→config compile, two-level/progressive planning, source/evidence policy, depth/thoroughness | [system/plan-as-object.md](system/plan-as-object.md) → arch §5 |
| Anything in the Evidence Base run (acquire → … → synthesise) | [capabilities/evidence-base/](capabilities/evidence-base/) → build spec |
| Writing or changing ANY LLM prompt/envelope surface; the refine-replay loop; model swaps | [system/prompting.md](system/prompting.md) — no frozen-source arch section (018 origin) |
| Export/share, version-pinned deep-links, the superseded-version banner | **No contract drafted yet** — read arch §10 directly (a down-weighted v3.0 seam). |
| Collaboration/comments/event log, persistence substrate, observability/eval, security/egress | **No contract drafted yet** — read arch §7, §9, §8, §11 directly; draft the contract when the first task lands. |

## Status legend (used throughout)

🟡 Leaning (provisional) · ❓ Open · ⏸ Deferred seam (out of v3.0 scope, seam left open).
