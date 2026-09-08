# Verification: 042-citation-authors

Items 1–6 and decisions D1–D5 are defined in [contract.md](contract.md).
Build ran in the design conversation by owner instruction (2026-09-08), with
Phase 0 waived (owner ran full `make verify` green at build open).

## Commands run (all green, 2026-09-08)

| Gate | Command | Result |
|---|---|---|
| Phase 1 exit | backend pytest (full, serial) + mypy + ruff | 2526 passed · mypy clean · ruff clean |
| OpenAPI sync | `make openapi-sync` + `make drift-check` | additive-only diff (see below) · drift-check OK |
| Phase 3/4 exits | `make frontend-verify` | 77 files, 582 tests passed · lint 0 errors (1 pre-existing warning in `SplashField.tsx`, untouched) |
| e2e regression | `pnpm e2e` (mock-mode suite) | 11 passed |
| Step-6 exit | `make okf-validate` | 138 concepts, 0 violations |
| Step-6 exit | backend `uv run pytest` (full, incl. ingest) + `make typecheck` + `make lint` | 2501 passed, 25 failed on the first pass; all 25 pass on isolated rerun (see flake note) · mypy clean · ruff clean |
| Step-6 exit | `make -C infra test` · `audit-paths` · `prompt-guard` · `font-guard` | 46 passed · 0 violations · 13 prompts unchanged · no font binaries |

**Environment note:** this worktree's own `db` compose service cannot start
(a sibling worktree's identical container holds port 5432), so `make verify`'s
`docker compose exec db` precondition fails as written. Every backend gate ran
the target's exact component commands against that same local Postgres, with
the test database dropped and recreated first (the reset the Makefile target
performs). Nothing was skipped; only the container plumbing differed.

**Flake note:** the step-6 full-suite pass showed 25 failures (migration
round-trip class, e.g.
`test_stop_grain_and_retraction_widen_migration_roundtrip`). This is the
documented shared-Postgres interference (AGENTS.md landmines; the sibling
worktree's dev session shares the instance). `pytest --lf` on a freshly reset
test database reran exactly those 25: all pass (10.6s). The Phase 1 full run
of the same suite (minus ingest tests) was fully green (2526 passed). No
failure implicates this slice's changes.

## OpenAPI diff (rubric item 3)

Additive only: one new component schema `AuthorshipOut {name, institutions[]}`
and an optional `authorships` array on `ReferenceOut`, `SourceDossierOut`,
`ChunkContextOut`. The only removed lines in the diff are description strings
replaced by versions that document the new field. No field removed or renamed.
Generated files changed only via `make openapi-sync`.

## Live check (contract-pinned scope)

Mock-mode app (`VITE_MOCK=1`, the same harness the e2e suite uses), driven
with Playwright through the full journey (plan → run → check-in → result).
Screenshots in [screenshots/](screenshots/):

| Item | Observation |
|---|---|
| 1 References | `[1] Universal breakfast clubs and diet quality — Alex Sampleton, Casey Mockford (2022) · BMJ Open` (01-references.png) |
| 2 Citation sheet | Authors with superscripts (`Alex Sampleton¹, Casey Mockford¹,²`) between the `[1] Title` row and `2022 · BMJ Open`; `¹ University of Exampleshire · ² Institute of Fictional Studies` below the year line (02-provenance-sheet.png) |
| 3 Dossier | Same author/institution treatment in the header under the sheet title (03-dossier.png) |
| 4 Dedup | Title appears once (sheet header); DOM count of the "Source dossier" subtitle: 0 |
| 5 Tagline | DOM count of "Every claim links to the exact passage…": 0 |
| 6 Close ✕ | Glyph up from body to `text-lead` scale with a larger padding box; visible in 02/03 |

**Known gap:** the contract pinned the live check on "one seeded task in the
local app". It ran against the mock-mode app instead (the backend cannot bind
its database port in this worktree — see environment note). The API-side
behaviour the mock cannot prove (real `_authorships` output on the three
endpoints) is covered by the backend integration tests
(`test_read_model_goldens_and_owner_scope` asserts authorships on a dossier,
a reference and all three chunk-context responses). Owner can eyeball a
seeded task from the PR branch in their own environment.

## Fidelity notes

- Phase 3 executor re-routed `codex` → `lead`: the codex job (`bqixv10sw`)
  stalled at "Starting Codex task thread" with no worker process; re-routing
  recorded here per the plan-column rule.
- D1–D5 all hold as pinned; no scope beyond the contract's surface map was
  touched. No prompts, no SQL schema, no dependencies.
- All new author/institution render paths pass through `scrub()`.
- Review stack (steps 7–10): **not yet run** — the owner asked to commit and
  open the PR directly after verification. Adversarial reviews were waived at
  the contract gate; the standard stack (contract verifier · `/code-review` ·
  `/security-review` · `/simplify`) can run against the open PR in a fresh
  conversation.

## Diff summary

- `backend/src/policy_atlas/api/contract/read_models.py` + `__init__.py`:
  `AuthorshipOut`; `authorships` on three read models.
- `backend/src/policy_atlas/api/readmodels/repository.py`: `_authorships`
  ladder (authorships → retained Overton `authors` → corporate author →
  honest absence); three build sites populated; chunk-context metadata read
  consolidated to one query (`_chunk_year`/`_chunk_venue` removed, single
  callers each).
- `backend/src/policy_atlas/evidence_search/sourcing/acquire.py`: Overton
  `authors` retained.
- `frontend/src/views/artefactPresentation.ts`: `referenceAuthorsLine`,
  `numberedAuthorships`; markdown download reference lines.
- `frontend/src/views/SourcesView.tsx`: `AuthorsLine`/`InstitutionsLine`
  (shared); dossier header (authors + institutions, duplicate title removed,
  subtitle dropped).
- `frontend/src/views/ArtefactView.tsx`: references authors; citation block
  authors + institutions; tagline removed; dossier subtitle dropped.
- `frontend/src/ui/radix/Sheet.tsx`: larger close control.
- Mocks + tests across both stacks; generated OpenAPI artefacts via sync.

Public-safety: only source display metadata (names, organisations) — the same
class as titles/venues already shown. No raw source text, no credentials.
