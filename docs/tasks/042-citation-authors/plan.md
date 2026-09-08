# Plan: 042-citation-authors

Items 1–6, decisions D1–D5, terms and the surface map are defined in
[contract.md](contract.md). This plan cites them and adds nothing to scope.

> Plan approved (before implementation): _pending_.
> Plan-stage adversarial review: waived per the contract-gate ruling
> (owner, 2026-09-08 — adversarial reviews waived for this slice).

Executor marks per AGENTS.md § Agent-side model routing; every `lead` mark
carries its reason. The family flip happens at step 7 when Codex reviews the
diff.

**Verify gates (consolidation argued here):** full `make verify` at Phase 0
(build-open baseline) and Phase 5 (step-6 exit). Phase 1 is backend-only and
gates on `make verify-fast` plus `make drift-check` after the sync; Phases
3–4 are frontend-only and gate on `make frontend-verify`. No schema/ingest
contact anywhere — no extra full-verify class fires.

## Decisions fixed here (lead seam design)

S1. **Wire shape.** `AuthorshipOut {name: str, institutions: list[str] = []}`
in `read_models.py`; `authorships: list[AuthorshipOut] = []` on
`ReferenceOut`, `SourceDossierOut`, `ChunkContextOut`. Names, not people ids
— display data only.

S2. **One backend ladder.** `_authorships(metadata)` in `repository.py`, next
to `_venue`. Rungs, first non-empty wins:
1. `provider_fields.authorships` entries with a non-empty string
   `author_name` → `{name, institutions}` (institutions filtered to
   non-empty strings).
2. `provider_fields.authors` (D3 retention; string or list of strings) →
   names with no institutions.
3. Envelope `backend == "overton"` and `publisher_org` present → one
   corporate author `{name: publisher_org, institutions: []}` (D2).
4. `[]` (D1 — honest absence; uploaded sources land here).
Malformed shapes (non-mapping entries, non-string names) are skipped, never
raised.

S3. **Frontend numbering is one pure helper.** In `artefactPresentation.ts`:
- `referenceAuthorsLine(authorships)` → names joined, >3 becomes first three
  + " et al." (D4).
- `numberedAuthorships(authorships)` → authors with per-author marker
  indices + the deduped institution list ordered by first appearance (D5).
Both unit-tested; the three surfaces render from these, never re-derive.

S4. **Chat needs no chat-side change.** Chat's citation sheet renders
`CitationProvenanceBlock` fed by the same chunk-context query; once the block
renders `context.data.authorships`, both routes (item 2) are covered.

S5. **Chunk-context metadata is read once.** `_chunk_year` and `_chunk_venue`
each run their own `_chunk_metadata` query today; adding a third lookup makes
it one `_chunk_metadata` call at the `_clamped_quote_window` call site feeding
year, venue and authorships. Same output, one query fewer — in scope as the
mechanical consequence of touching the site.

## Phase 0 — Build-open baseline — `lead` (inline)

One command, nothing to brief: full `make verify` on the branch (never build
on a red base).

## Phase 1 — Backend: S1 · S2 · S5 · D3 retention — `fast-worker`

Mechanical transcription of the exact spec above:

1. `read_models.py`: `AuthorshipOut` + the three `authorships` fields (S1),
   Google-style docstrings.
2. `repository.py`: `_authorships` (S2); populate the reference build
   (`refs_out` loop), the dossier build (`SourceDossierOut(...)` site) and
   the chunk-context site (S5 consolidation).
3. `acquire.py`: add `"authors"` to `_OVERTON_RETAIN_KEYS` (D3) — retention
   stays raw; normalisation lives in S2 rung 2.
4. Tests: `_authorships` ladder unit tests (rungs 1–4 + malformed shapes);
   one read-model test each asserting `authorships` lands on a reference,
   a dossier and a chunk context; an acquire test asserting Overton `authors`
   is retained.

Done when `make verify-fast` is green. Then `lead` (inline, one command):
`make openapi-sync`, confirm the OpenAPI diff is additive-only (rubric item
3), `make drift-check`. Commit.

## Phase 2 — (folded into Phase 1 close — openapi sync, see above)

## Phase 3 — Frontend authors render: items 1–3 — `codex`

Judgment-bearing execution (three surfaces, shared helpers, typography in an
established design system) with a machine-verifiable done. Brief carries S3,
the surface map and D1/D4/D5; done when:

1. `artefactPresentation.ts`: the two S3 helpers + unit tests (truncation
   boundary at 3/4 authors; numbering dedupes and orders institutions;
   corporate author gets no marker).
2. `ReferencesSection` (`ArtefactView.tsx`): authors line (D4, names only)
   between the title and `(year)`; absence renders nothing.
3. `CitationProvenanceBlock` (`ArtefactView.tsx`): authors with `<sup>`
   markers between the `[n] Title` row and the year/venue meta line; numbered
   institutions below the meta line. Both from `context.data.authorships`
   (S4 — no chat-side edits).
4. `SourceDossierBody` (`SourcesView.tsx`): same treatment under the title —
   authors line, year line, institutions list, then the existing chips.
5. `artefactMarkdown` (`artefactPresentation.ts`): reference lines carry the
   D4 authors string after the title.
6. Mock fixtures (`src/mock/fixtures.ts`) gain authorships on at least one
   reference/dossier/chunk-context so tests exercise presence and absence.
7. Tests for each surface: with authors+institutions, with authors only,
   with none (no empty separators, no dangling `·`, no marker without an
   institution row — contract § Review focus).

Done when `make frontend-verify` is green. Commit.

## Phase 4 — Removals + close button: items 4–6 — `fast-worker`

Exact edits:

1. Item 5: delete the tagline `<p>` in `ProvenanceSheet`
   (`ArtefactView.tsx`).
2. Item 4: delete the duplicated title `<p>` in `SourceDossierBody`'s header
   (`SourcesView.tsx`); drop `description="Source dossier"` from both
   `SourceDossier` wrappers (`SourcesView.tsx`, `ArtefactView.tsx`) — the
   sheet falls back to its visually-hidden description, keeping the a11y
   contract.
3. Item 6: `ui/radix/Sheet.tsx` close control: larger glyph (`text-lead`
   scale; exact utility judged in build), hit target not smaller than today.
4. Update any test asserting the removed strings ("Source dossier"
   description, the tagline); assertions move to absence where the contract
   demands it.

Done when `make frontend-verify` is green. Commit.

## Phase 5 — Live check, evidence, step-6 exit — `lead`

Reason for `lead`: browser-driving the pinned live check and writing the
evidence — adjudication-adjacent, not delegable.

1. The contract-pinned live check (~3 min): seeded task → References
   (OpenAlex authors, Overton corporate author) → one provenance sheet
   (superscripts, institutions below year, no tagline) → one dossier (no
   duplicate title, no subtitle, institutions, larger ✕). Screenshots.
2. `verification.md`: command tails, the OpenAPI additive-only diff, the
   item 1–6 manual-check table, deferred.md delta (Overton snapshot
   backfill · `TopSource.authors` · institutions in the reference list),
   known gaps.
3. Full `make verify` (step-6 exit).

Gate: **full `make verify`**. Commit.

## Out-of-plan reminders

- Stop conditions (contract § Stop conditions): non-additive OpenAPI diff;
  any surface outside the map.
- No ADR expected.
- Review (steps 7–10) runs in a fresh conversation with `task-cycle-review`;
  adversarial waived, standard stack runs (contract verifier · `/code-review`
  · `/security-review` scoped per contract · `/simplify` · human review).
