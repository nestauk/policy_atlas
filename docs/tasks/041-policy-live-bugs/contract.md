# Task contract: 041-policy-live-bugs

One implementation slice. Keep it reviewable. Boundaries are in
[AGENTS.md](../../../AGENTS.md). Specs are in [docs/specs/](../../specs/index.md).

> **Status:** in progress 2026-09-08 · owner-directed live-bug batch
> (fixes requested and reviewed interactively in session; no separate
> contract gate — the 033-ux-snags lightweight precedent).
>
> **Branching:** `task/041-policy-live-bugs` from `dev`.
>
> **Lightweight cycle:** low tier. No rubric, no plan, no ADR — each fix is
> small, owner-specified, and was accepted piecewise in session.
> `verification.md` records the evidence.
>
> **Public interface gate:** one additive change — `EvidenceItemOut` gains
> `abstract` and `abstract_source` (S3). The owner requested this change
> directly in session on 2026-09-08 ("Is there any 1-sentence summaries of
> the documents that we also generate that we could add here"); that request
> is the gate approval. No other route, schema, or prompt surface changes.

## Goal

Fix a batch of small live bugs and shortcomings the owner found while
using the app, on the Sources, Share and Chat surfaces.

## Deliverable

One PR on `task/041-policy-live-bugs` that:

- **S1** Adds a Download CSV button to Sources → All sources (top right,
  same row as the filters; wraps below them on narrow screens). It
  downloads the complete unfiltered source list — every page, not the
  shown table — as `<task title> - sources.csv`.
- **S2** Includes in that CSV the LLM reasoning shown as hovers in the
  table (screening reason, evidence type reason, status reason) and the
  document description (`abstract` + its provenance, "AI description"
  when provider-LLM-written).
- **S3** Exposes `abstract`/`abstract_source` on `EvidenceItemOut`
  (moved up from `SourceDossierOut`; populated in `evidence_page` from
  metadata already in hand) and shows the description as a clamped hover
  on the source title in the table.
- **S4** Makes "Included" the default status filter on Sources → All
  sources. The All button now writes `status=all` explicitly.
- **S5** Restyles the Share tab: "Share publicly" and "Share with
  organisation" are standard primary blue buttons, left-aligned with the
  page (the old ghost-button padding read as an indent).
- **S6** Changes the Share warning copy to "Anyone on the internet with
  the public link can see this Task's result and sources …".
- **S7** Makes the chat reference chip show the citation's
  best-supported claim (tier and judge rationale from the same claim).
  The backend's worst-verdict stamp on the citation stays; the report
  keeps using it. Inline claim-level markers are unchanged.
- **S8** Renames the "Unsupported — flagged" chip label to "Unsupported"
  app-wide (the shared `TIER_LABEL` constant).

## Non-goals

- No backend change to how the grounding judge scores claims or how
  verdicts propagate onto citations (S7 is display-side only).
- No LLM-generated one-sentence document summaries — the CSV/table
  description is the existing provider abstract/snippet/AI description.
- No fix for the two pre-existing order-dependent conformance test
  failures on the `/evidence` route (see verification.md § Known items).

## Terms

| Term | Meaning |
|---|---|
| **Task** | Screen word for a `project` row (ADR 0031). |
| **Description** | A source's `abstract`: provider abstract, snippet, or provider-LLM description. |
| **Best-supported claim** | Among claims citing a citation, the one with the lowest-severity verdict (tier_1 … unsupported_mis_cited). |
