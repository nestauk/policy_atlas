# Verification: 043-dossier-hotfix

Low-tier hotfix; evidence kept short.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `npx vitest run` (frontend) | pass | 79 files, 617 tests |
| `npx tsc --noEmit` | pass | |
| `npx eslint` (changed files) | pass | |

## Checks beyond the build

- `frontend/src/views/ArtefactView.dossier.test.tsx` (new) pins the three dossier
  states: one loading line while the title→id lookup waits on the evidence list; the
  not-found line without a stuck loading line when a title has no match; a by-id open
  that does not wait on the evidence lookup. The second test fails without the fix —
  before it, a disabled dossier query's `isPending` rendered a permanent loading line.
- The reported failure was deployed-only: the citation-time title snapshot drifts from
  the evidence row's title in live data, and the title lookup scans only one evidence
  page (`page_size: 200`). Local seed data has no drift, so the miss never reproduced
  locally. Opening by `source_id` removes the lookup entirely, so no live reproduction
  is needed to close the failure mode.

## Diff summary

`frontend/src/views/ArtefactView.tsx`: `MostRelevantSources` opens the dossier with
`source.sourceId` instead of the title; `SourceDossier` renders a single loading line
gated on `dossier.isLoading` (not `isPending`). Plus the new test file and this task's
docs. References stay title-keyed — recorded in `docs/deferred.md` § Web app
(`CitationOut.source_id` entry).
