# Spec-prep guidance (current phase)

The current phase is **pre-implementation specification preparation**, not application build.
This file is the playbook for distilling the canonical sources into specs, contracts and
capability specs. It governs *how* spec-prep work is done; it is not itself a contract.

## What we are doing

Turning the canonical sources in [../specs/sources/](../specs/sources/) into a small set of
**distilled, consumable specs** — system contracts + the Evidence Base capability spec — that
implementation task contracts can later reference. **Distil, don't duplicate**: a spec is a
declarative, status-tagged compression that points back to its source section. On any conflict,
**the source wins and the spec is corrected** — never the reverse.

## Canonical source & conflict-resolution order

The numbered order in [../specs/index.md](../specs/index.md) is canonical (ratified from the EB
handoff §2). Lower number wins. Backend architecture + EB capability design outrank visual
shorthand in the wireframe.

## Disciplines (carry these into every spec)

- **Preserve decision-level status.** Every settled/provisional/open/deferred decision keeps its
  marker: settled · 🟡 leaning · ❓ open · ⏸ deferred seam. Do not flatten a 🟡 or ❓ into a settled
  — provisional and open decisions must read as provisional and open.
- **Model only what behaves** (Principle 10). Do not introduce a label, object type or flag in a
  spec unless it changes v3.0 system behaviour. No inert sensitivity flag, no source-class
  lifecycle, no `Library` class, no strand entity.
- **Framework vs instance (the flow-back rule).** Cross-cutting decisions live in the **system
  contracts**; a capability spec holds only what is **specific to that capability** and
  *references* the framework. When reasoning about a capability surfaces a decision that changes
  the framework, record it in the architecture/system layer, not the capability spec. (EB already
  flowed back `screen`/`classify`/`select`, the `intervention_outcome_finding` schema, the
  steerable appraisal rubric, etc.)
- **Honest absence.** A gap/coverage claim must carry its base; never present a pipeline artefact
  as a corpus fact. (See [../specs/capabilities/evidence-base/provenance.md](../specs/capabilities/evidence-base/provenance.md).)
- **Build light, leave seams.** Record deferred seams as seams (in [../deferred.md](../deferred.md)),
  not as silent omissions or inert stubs.
- **Read the source in depth before drafting** a contract that depends on it — not headings or
  summaries.

## What is in / out of scope for this phase

**In scope (this pass):** [../specs/index.md](../specs/index.md), [../specs/product.md](../specs/product.md),
the four system contracts under [../specs/system/](../specs/system/), the Evidence Base capability
spec under [../specs/capabilities/evidence-base/](../specs/capabilities/evidence-base/),
[../deferred.md](../deferred.md), and this file.

**Explicitly out of scope (do not do in this phase):**
- No Makefile / package files / CI / Next.js scaffold / dependencies / implementation code /
  hooks / skills.
- No contracts for deferred capabilities (Options Assessment, Impact, Transferability, VfM, etc.).
- No OKF knowledge seeding ([../knowledge/index.md](../knowledge/index.md) says wait until the
  specs are reviewed).
- No filling of [environment.md](environment.md) until the stack is approved.
- The follow-on system contracts (collaboration/audit, persistence-runtime, observability/eval,
  security/egress) are **named but not drafted** — draft each when its first implementation task
  lands.

## Tooling posture

- **Spec Kit is dormant / non-canonical.** The `.specify/` machinery has been removed for now; the
  manual `docs/specs` + `docs/tasks` flow is what we use. Spec Kit can be re-added later
  (`specify init`) if standardised constitution/specify/plan/tasks artefacts become worth the
  overhead. *(The `.claude/skills/speckit-*` skills were removed on 2026-06-22; re-add via the
  plugin if Spec Kit is reinstated at implementation.)*
- The advanced agentic engineering workflow itself is referenced under
  [references/](references/); read it for how task contracts, rubrics and verification evidence
  work once implementation begins.

## Open decisions that gate implementation

See the review/approval list in the session summary; the load-bearing ones are the **Spec Kit vs
manual flow** (now leaning manual) and the **stack confirmation** (Postgres/Aurora + LangGraph +
inference route, all architecture-implied but not yet committed).
