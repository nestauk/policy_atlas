# Task contract: 043-dossier-hotfix

> **Status:** drafted. Low-risk hotfix; skips rubric/plan/ADR per tier rules.

## Goal

Fix the source dossier when it opens from "Most relevant sources" on the deployed app:
(1) two "Loading the dossier…" lines show at the same time, and (2) for some sources the
sheet shows a stuck loading line plus "This source isn't in the evidence list yet.",
while the same dossier opens fine from the All sources table.

## Root cause

`MostRelevantSources` opened the dossier by **title** (the legacy title-keyed path), even
though each `TopSource` carries the citation's `source_id`. The title is a synthesis-time
snapshot (`citation.source_title`); in deployed data it can drift from the evidence row's
current title, and the lookup scans only one evidence page (`page_size: 200`). A miss
leaves the dossier query disabled forever — and in React Query v5 a disabled query is
`isPending`, so `SourceDossier` rendered a second, permanent "Loading the dossier…" line
next to the not-found message. The All sources table passes `source_id`, so it never hit
either problem.

## Fix

- `MostRelevantSources` now opens the dossier with `source.sourceId` (the by-id path
  citations already use; `?source=<uuid>` deep links were already supported).
- `SourceDossier` renders one loading line, gated on `dossier.isLoading` (not
  `isPending`) so a disabled query cannot show a stuck loading state, and on
  `evidence.isPending` only for the title-keyed path.

## Out of scope

The References list still opens by title: `ReferenceOut` carries no `source_id` on the
wire, so the same drift can in principle still miss there. Fixing that needs a backend
schema change (add `source_id` to `ReferenceOut`) — a separate slice. Recorded in
`docs/deferred.md` § Web app, under the `CitationOut.source_id` entry.

## Verification

`frontend/src/views/ArtefactView.dossier.test.tsx`: single loading line while the
lookup waits, no stuck loading line on a title miss, by-id open independent of the
evidence lookup. `tsc`, `eslint` and the neighbouring ArtefactView suites pass.
