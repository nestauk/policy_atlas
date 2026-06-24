# ADR 0002 — Spec governance: sources frozen, specs + ADRs canonical

- **Status:** Accepted — 2026-06-24 (maintainer decision this session).
- **Date:** 2026-06-24
- **Context doc:** [docs/specs/README](../specs/README) (flow-back) · supersedes the "source wins on
  conflict" rule in [spec-authoring.md](../agentic-ops/spec-authoring.md), [specs/index.md](../specs/index.md),
  [specs/README](../specs/README) and the per-spec intros.

## Context

The architecture and Evidence Base specs under `docs/specs/` were distilled from the canonical source
documents in `docs/specs/sources/` during a short, deliberate spec-prep phase, **before** any
implementation. Until now the rule was *"source wins on conflict; the spec is corrected toward the
source"* — a **distillation-fidelity** rule appropriate while specs were being derived.

The specs were reasoned carefully but fast, and parts will be refined as the concept becomes a real
tool. We need a durable canonical order for that evolution, so agents neither treat the specs as
immutable nor silently drift from them. See the "specs are living, not golden" framing in
[specs/README](../specs/README).

## Decision

1. **`docs/specs/sources/` are frozen historical origin** — a point-in-time snapshot of the original
   deliberation. Not updated going forward. Still readable, and they remain the reference for areas
   **no spec covers yet** (the [spec index](../specs/index.md) routes "read arch §X directly" there).
2. **`docs/specs/` + `docs/adr/` are canonical and living.** Where a spec covers a topic, the spec is
   authoritative — not the frozen source.
3. **The "source wins on conflict" rule is retired** going forward. It referred only to original
   distillation fidelity, not ongoing authority. A spec that intentionally diverges from its frozen
   source is an *evolution*, recorded by ADR — not an error to correct back toward the source.
4. **Spec changes follow the flow-back** in [specs/README](../specs/README): propose → human
   decision → update spec + status markers + an ADR when consequential → log. This ADR is itself the
   first instance.

## Consequences

- Per-spec "source/reference wins" wording is superseded by this ADR and updated to point here.
- The conflict-resolution read-order among sources (index.md) is retained only for consulting the
  **frozen** sources on undrafted areas.
- Risk: a distillation error in a spec now becomes canon without the source as a backstop. Mitigated
  by the specs having been reviewed in spec-prep, and by deliberate ADR'd change going forward;
  reconcile a spec against its frozen source if its fidelity is ever in doubt.
