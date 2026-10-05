# Task contract: 042-citation-authors

One implementation slice: show who wrote each source on the three reference
surfaces, and clean four small snags in the two slide-over sheets.

> **Status:** approved. Contract approved (before planning): 2026-09-08 ·
> owner (with D5 amended: institutions render — see D5) · adversarial reviews
> waived at this gate (owner, 2026-09-08) ·
> Plan approved (before implementation): _pending_ · ADR: none expected.

## Goal

Readers ask "who says this?" before they trust a source. Today no surface
shows author names, although the data already stores them for academic
sources. Six numbered changes:

1. **Report reference list shows authors.** Each numbered reference in the
   report (and in the markdown download) shows the source's authors between
   the title and the year.
2. **Citation sidebar shows authors and institutions.** The provenance
   sheet's citation block shows the authors (with superscript affiliation
   markers, D5) between the `[n] Title` row and the year/venue values, and
   the numbered institutions below the year line. Applies to both routes into
   the block: the report's claim panel and chat's citation sheet.
3. **Source dossier shows authors and institutions.** The dossier header
   shows the authors (with superscript markers) between the title and the
   year line, and the numbered institutions below the year line.
4. **Dossier header duplication removed.** The sheet header already shows the
   source title; the dossier body repeats it. Remove the body's title line and
   the "Source dossier" subtitle. The year line (now with authors, item 3) and
   the chips stay, directly under the sheet-header title.
5. **Provenance-sheet tagline removed.** Delete the footer line "Every claim
   links to the exact passage it came from." from the provenance sheet.
6. **Larger close button.** The `✕` close control on the slide-over sheets
   (provenance sheet and source dossier share one `SheetContent`) renders
   larger, with an equal or larger hit target.

## Deliverable

A PR on `task/042-citation-authors`: three additive read-model fields
(`authorships`), one acquisition retention fix, the six frontend changes above,
regenerated OpenAPI artefacts, tests, and `verification.md`.

## Terms

| Term | Meaning |
|---|---|
| **authorships** | The retained slice of an OpenAlex work's author list: `{author_name, institutions, countries}` per author. Lives in `source_snapshot.metadata["provider_fields"]["authorships"]`, written by `_slim_authorships` in `backend/src/policy_atlas/evidence_search/sourcing/acquire.py`. |
| **envelope** | The normalized snapshot metadata (`source_snapshot.metadata`): title, abstract, year, doi, language, backend, record_type, `publisher_org`, plus `provider_fields`. |
| **publisher_org** | Envelope key. For OpenAlex it is the venue/journal display name; for Overton it is the publishing organisation (e.g. "OECD"). |
| **corporate author** | Reference convention for policy documents: the issuing organisation stands in the author position ("OECD (2023) …"). |
| **provenance sheet** | The "Where this comes from" slide-over (`ProvenanceSheet` in `frontend/src/views/ArtefactView.tsx`), opened from a claim span in the report or from chat. |
| **citation block** | One citation's panel inside the provenance sheet (`CitationProvenanceBlock`): `[n] Title`, meta line, chips, quote in context. |
| **source dossier** | The per-source slide-over (`SourceDossier` wrappers in `SourcesView.tsx` and `ArtefactView.tsx`, body `SourceDossierBody` in `SourcesView.tsx`). |

## Where the data lives (authors feasibility)

| Source origin | Author data today | What this slice shows |
|---|---|---|
| OpenAlex (academic) | Author names + institutions retained in `provider_fields.authorships` — present for existing snapshots | Real author names |
| Overton (policy) | Provider sends `authors` (string or list) but `_OVERTON_RETAIN_KEYS` drops it; `publisher_org` is retained | Existing snapshots: `publisher_org` as corporate author. New acquisitions: retained `authors` names when present, else `publisher_org` |
| Uploaded | Whatever the upload envelope carries; usually nothing | Honest absence — no authors line |

Decisions pinned here (owner confirms at the contract gate):

- **D1 — honest absence.** No author data → no authors line. Never a
  placeholder.
- **D2 — corporate-author fallback for Overton.** When a source has no
  retained author names and its envelope backend is `overton`, the
  authorships fall back to one entry: `{name: publisher_org, institutions:
  []}`. The organisation renders in the author position — the reference
  convention for policy documents (see Terms); Overton itself flags
  `authors_are_organizations`. No such fallback for OpenAlex — there
  `publisher_org` is the journal, not an author.
- **D3 — retain Overton authors going forward.** Add `"authors"` to
  `_OVERTON_RETAIN_KEYS` and normalise its string-or-list shape at read time
  (names only — Overton sends no per-author affiliations). Existing
  snapshots are immutable and keep the D2 fallback.
- **D4 — reference-list truncation.** In the report reference list (on-screen
  and markdown), up to three names render in full; more than three render as
  the first three plus "et al.", names only — no superscripts there. One
  shared frontend helper; the API always carries the full list.
- **D5 — institutions render (owner amendment, 2026-09-08).** In the
  citation block and the source dossier, the full author list renders with
  superscript affiliation markers (¹ ²…), and the institutions are listed
  below the publication-year line, numbered by first appearance and deduped —
  the standard paper display. An author without institutions carries no
  superscript; a source with no institutions shows no institutions line. A
  corporate author (D2) is one unmarked name and no institutions line.

## Surface map

| # | Surface | File | Change |
|---|---|---|---|
| 1 | Report references (on-screen) | `frontend/src/views/ArtefactView.tsx` `ReferencesSection` | authors between title and `(year)` |
| 1 | Report references (markdown download) | `frontend/src/views/artefactPresentation.ts` `artefactMarkdown` | authors in each numbered line |
| 2 | Citation block meta line | `frontend/src/views/ArtefactView.tsx` `CitationProvenanceBlock` | authors prepended to the `year · venue` meta line |
| 3, 4 | Dossier header | `frontend/src/views/SourcesView.tsx` `SourceDossierBody` | add authors; delete duplicated title line |
| 4 | Dossier sheet header | `SourceDossier` in `SourcesView.tsx` and `ArtefactView.tsx` | drop `description="Source dossier"` |
| 5 | Provenance sheet footer | `frontend/src/views/ArtefactView.tsx` `ProvenanceSheet` | delete the tagline paragraph |
| 6 | Sheet close button | `frontend/src/ui/radix/Sheet.tsx` | larger `✕`, hit target not smaller |
| 1–3 | Read models | `backend/src/policy_atlas/api/contract/read_models.py` | new `AuthorshipOut {name: str, institutions: list[str] = []}`; `authorships: list[AuthorshipOut]` (default `[]`) on `ReferenceOut`, `SourceDossierOut`, `ChunkContextOut` |
| 1–3 | Read-model build | `backend/src/policy_atlas/api/readmodels/repository.py` | one `_authorships(metadata)` helper next to `_venue`; populate the three build sites |
| D3 | Acquisition | `backend/src/policy_atlas/evidence_search/sourcing/acquire.py` | retain Overton `authors` |
| — | Generated | `frontend/openapi.json`, `frontend/src/api/gen/types.ts` | via `make openapi-sync` only |

Do-not-change rows: `EvidenceItemOut` (the sources list rows stay lean —
authors ride only on the dossier); the mobile bottom-sheet geometry in
`Sheet.tsx` (task 040); `MostRelevantSources` already renders a `TopSource.
authors` slot — populating it is out of scope (nothing feeds it today).

## Read first

- [EB capability](../../specs/capabilities/evidence-base/capability.md) — the
  reference-list and dossier surfaces.
- [provenance-grounding](../../specs/system/provenance-grounding.md) — the
  citation ladder the provenance sheet renders.
- [data-model](../../specs/system/data-model.md) — snapshot envelope
  ownership.

## Scope / Out of scope

- **In:** the surface-map rows above; unit tests for `_authorships`
  (authorships present · overton fallback · uploaded absence · malformed
  shapes); frontend tests for the authors render, the truncation helper, the
  superscript/institution numbering helper (D5), and the four removals.
- **Out:** `EvidenceItemOut`/sources-list rows; populating
  `TopSource.authors`; institutions in the reference list (D4 — names only
  there); any prompt, schema (SQL), auth, or dependency change; backfilling
  existing Overton snapshots.

## Constraints & approval gates

- **Public interface (additive):** one new component schema (`AuthorshipOut`)
  and three new optional fields on existing read models. This is the slice's
  one gated surface — approval is this contract's sign-off. No field is
  removed or renamed; the OpenAPI diff must be additive only.
- Generated files (`frontend/openapi.json`, `frontend/src/api/gen/types.ts`)
  change only via `make openapi-sync`; `make drift-check` stays green.
- No SQL schema change: authors come from existing JSONB metadata.
- No prompt change (`make prompt-guard` untouched).
- Author names are provider-supplied strings: every new render path goes
  through the existing `scrub()` seam, same as titles.

## Public / private boundary

Author names and organisation names are source metadata already treated as
displayable (titles, venues, publishers render today). No raw source text,
credentials or traces are touched. Contract and docs are public-safe.

## Model route

n/a — no inference in this slice.

## Disciplines binding this slice

- **Honest absence** — D1: no fabricated or placeholder author lines.
- **Flag, don't drop** — D2's corporate author is the policy-document
  citation convention, applied only by backend (`overton`) and never for
  OpenAlex, where `publisher_org` is a journal, not an author.
- Leave deferred seams in [docs/deferred.md](../../deferred.md): Overton
  snapshot backfill, `TopSource.authors`, institutions in the reference list.

## Stop conditions

Halt and escalate when: the OpenAPI diff turns out non-additive; a surface
outside the map needs touching; or the turn/token budget is spent.

## Acceptance checks

- `make verify` green (includes `drift-check`).
- Deterministic tests: `_authorships` ladder (backend unit); reference/
  dossier/citation-block render with and without authors and institutions
  (frontend); the tagline,
  duplicated title and "Source dossier" subtitle are gone (frontend); close
  button class change covered by the existing Sheet tests. No AI eval — no
  judge behaviour changes.
- **Live check (pinned scope):** one seeded task in the local app — open the
  report, expand References (authors visible on an OpenAlex and an Overton
  reference), open one claim's provenance sheet (authors with superscripts
  and the institutions below the year, no tagline), open one source dossier
  (authors under the title, institutions below the year, no duplicate title,
  no subtitle, larger ✕). ~3 minutes. No full live e2e.

## Verification evidence expected

Command results; the OpenAPI diff (additive-only confirmation); live-check
notes or screenshots for the six items; deferred.md delta; known gaps.

## Risk tier & review focus

**Tier 3** — the slice touches a hard gate (public interface, additive) and
adds render paths for provider-supplied strings. It is otherwise display-only:
no schema, no auth, no egress, no prompts. Proposal, per the 033 precedent:
run the standard stack (contract verifier · `/code-review` ·
`/security-review` scoped to the new render paths and the additive fields ·
`/simplify` · human review) and **waive the adversarial reviews** — owner
decides at this gate.

Review focus: additive-only OpenAPI diff; `scrub()` on every new
author-string render; D2 never substitutes a journal for an author on
OpenAlex sources; honest absence (no empty "()" or dangling "·" separators
when fields are missing, no superscript without a matching institution row);
the four removals don't break the a11y contract (the sheet keeps a
`Description` for screen readers).
