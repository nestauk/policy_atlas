# Spec-authoring disciplines

How to write or refine a spec — the disciplines a distillation must carry, used by the
[task-cycle](../../.claude/skills/task-cycle/SKILL.md)'s *Spec refinement* flow-back. Governs *how*
spec work is done; it is not itself a contract.

A spec is a **declarative, status-tagged compression** of a source section, not a duplicate of it.
Specs + `docs/adr/` are canonical and living; the `sources/` they were distilled from are frozen
historical origin ([ADR 0002](../adr/0002-spec-governance.md)).

## Conflict-resolution order (frozen sources)

The numbered order in [../specs/index.md](../specs/index.md) is the read-order for the **frozen**
sources (ratified from the EB handoff §2): lower number wins; backend architecture + EB capability
design outrank visual shorthand. It governs which source to trust when consulting them for an area
no spec covers yet — *not* whether a source overrides a spec (it doesn't; ADR 0002).

## Disciplines (carry these into every spec)

- **Preserve decision-level status.** Every decision keeps its marker: settled · 🟡 leaning · ❓ open
  · ⏸ deferred seam. Don't flatten a 🟡 or ❓ into settled.
- **Model only what behaves.** No label, object type or flag in a spec unless it changes v3.0
  behaviour (no inert sensitivity flag, no source-class lifecycle, no `Library` class, no strand entity).
- **Framework vs instance (flow-back).** Cross-cutting decisions live in the **system contracts**; a
  capability spec holds only what is specific to it and *references* the framework. A capability-level
  realisation that changes the framework is recorded in the system layer, not the capability spec.
- **Honest absence.** A gap/coverage claim carries its base; never present a pipeline artefact as a
  corpus fact (see [provenance-grounding](../specs/system/provenance-grounding.md)).
- **Build light, leave seams.** Record deferred seams as seams ([../deferred.md](../deferred.md)),
  not silent omissions or inert stubs.
- **Read the source in depth** before drafting a spec that depends on it — not headings or summaries.
