# Pre-implementation readiness

Checklist for the transition from spec preparation into implementation. Items marked `[x]`
are done as of the spec-prep phase (2026-06-22); `[ ]` items are open gates.

## Source packet

- [x] Canonical architecture reference present (`docs/specs/sources/backend/backend-architecture-reference.md`).
- [x] Architecture briefing present (`docs/specs/sources/backend/backend-architecture-briefing.md`).
- [x] Evidence Base capability design present (`docs/specs/sources/backend/backend-evidence-base-build-spec.md`).
- [x] UX handoff, wireframe and design assets present.
- [x] Conflict-resolution order recorded in `docs/specs/index.md`.
- [x] Font binaries removed from version control; policy noted in `docs/specs/sources/evidence-base-ux/assets.md`.

## Distilled specs

- [x] Four system contracts drafted and reviewed: data-model, provenance-grounding,
  execution-orchestration, plan-as-object.
- [x] Evidence Base capability spec drafted and reviewed: capability, components, provenance.
- [x] Deferred seams registered in `docs/deferred.md`; v3.0 scope is clean.
- [x] Open/provisional decisions marked 🟡 / ❓ throughout; none silently flattened.
- [ ] Tool/component I/O contracts — draft when the first implementation task lands.
- [ ] Task-contract map for first implementation slices.
- [ ] Verification plan for first implementation slices.

## Engineering decisions before scaffold

- [x] Backend stack direction confirmed: Postgres/Aurora + pgvector, LangGraph,
  OpenAI API → Bedrock routing, Langfuse.
- [ ] Frontend scaffold and package manager committed (likely Next.js + pnpm; confirm before
  creating any files or installing dependencies).
- [ ] Local command surface defined (package scripts and/or Makefile wrapper — after scaffold
  exists; see `engineering-considerations.md`).
- [ ] Prompt-management approach confirmed (repo-first governance, Langfuse as runtime
  registry; open decisions listed in `engineering-considerations.md`).
- [ ] Langfuse trace-redaction policy confirmed.
- [ ] CloudWatch / runtime observability approach confirmed.
- [ ] Data/telemetry retention policy decided (Langfuse, CloudWatch; whether uploaded /
  acquired document text may appear in traces).

## Approval gates (require explicit human sign-off before proceeding)

- [x] Backend stack direction confirmed.
- [ ] Schema / data model — canonical entity, annotation and findings-layer tables.
- [ ] Auth / tenancy — cross-tenant boundary model; ownership/driver model.
- [ ] External egress — search backends, inference route, governance-event logging.
- [ ] Dependencies, CI, production config, public interfaces.

## Stop rule

An unchecked item above is a stop signal. Either resolve it, confirm it is out of scope for
the slice being built, or explicitly accept the risk and record that decision. Do not build
around an implicit assumption.
