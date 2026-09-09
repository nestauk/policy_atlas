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
of the same suite was fully green (2526 passed — the full count including
ingest; an earlier draft of this note wrongly said "minus ingest"). The
review stack re-ran the full suite on a freshly reset test database with no
concurrent lane: 2526 passed, zero failures, confirming the interference
attribution. No failure implicates this slice's changes.

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
- All new author/institution DOM render paths pass through `scrub()`. The
  markdown download interpolates author names unscrubbed — deliberately the
  same treatment `reference.title`/`venue` already get there (the sink is a
  file save, never rendered as HTML); contract's "same as titles" holds.
- Review stack (step 7): ran 2026-09-08 in a fresh conversation — see
  § Review findings below.

## Review findings (step 7, adjudicated 2026-09-08)

Stack as adjudicated at the contract gate: contract verifier · `/code-review`
medium · security lane · `/simplify` justification; adversarial waived
(owner). Review diff scoped to this slice's commits (`29bea87..HEAD`) —
the branch stacks on task 040 (PR #68), which ran its own stack.

**Self-verify gate:** the full `make verify` composition re-ran green in the
review conversation via component commands (same DB plumbing constraint):
okf-validate 138/0 · backend 2526 passed on a freshly reset test DB ·
mypy/ruff clean · `uv build` OK (the one component the build's step-6 row
had omitted — closed here) · infra 46 · guards · drift-check OK ·
frontend-verify · e2e 11/11.

**Security lane (unique value: end-to-end taint trace): clean.** Provider
author strings traced acquire → JSONB → `_authorships` → wire → render;
every DOM path scrubbed; the markdown download is a file-save sink treating
authors exactly as titles; no new attack surface, no data exposure.

**Contract verifier:** all contract items 1–6 and D1–D5 hold in code;
OpenAPI diff additive-only re-confirmed independently. Findings adjudicated:

- **Adopted — close-button change had no test** (contract claimed existing
  Sheet tests covered it; none asserted the close control): class assertion
  added to `primitives.test.tsx`.
- **Adopted — no component test for the on-screen reference render** and the
  live check never showed an Overton corporate-author reference:
  `ReferencesSection` exported and tested (named authors · corporate author ·
  honest absence, names-only/no superscripts).
- **Adopted — doc corrections:** scrub-coverage claim scoped to DOM paths;
  flake-note "minus ingest" wording fixed; `plan.md` Phase 3 executor mark
  annotated with the codex→lead reroute.
- **Recorded, no change** — `_authorships` rung 2 (bare `authors`) is not
  backend-gated: unreachable for OpenAlex today (which writes rung-1
  `authorships`); matches plan S2, not a D2 leak.
- **Declined — `<sup>` markers lack accessible text** (screen readers say
  "one comma two"): out of contract scope; standard reference-display noise.

**`/code-review` medium (Claude half of the pair):**

- **Adopted (CONFIRMED, medium)** — `numberedAuthorships` didn't dedupe a
  repeated institution within one author (OpenAlex duplicate affiliation
  records → "Name¹,¹"): per-author Set-dedupe added + unit test.
- **Adopted (PLAUSIBLE, low)** — a string `institutions` value iterated per
  character in `_authorships`: extracted `_institution_names` with an
  isinstance-list guard + unit test.
- **Adopted (cleanup)** — the two-author mock literal was pasted five times:
  four mock copies collapsed into one exported `mockAuthorships`; the test
  literal kept deliberately (explicit test inputs).
- Refuted/cut by its verifiers: uncapped author lists (D4/D5 pinned full
  lists), whitespace-name triggers, double-computation micro-optimisation.

**Flagged deviations — all four confirmed:** mock-mode live check (API side
covered by `test_read_model_goldens_and_owner_scope`, verified to assert
what it claims; the seeded-app eyeball stays with the owner); codex→lead
reroute (recorded, plan mark now annotated); component-command substitution
(complete after the `uv build` close); the 25-failure flake (attribution
confirmed: this stack's isolated full-suite rerun was 100% green; no
migration-adjacent file in the diff).

**`/simplify`: not run** — `/code-review` medium already carried the
reuse/simplification/efficiency angles and its cleanup findings were
applied; a second same-family pass would duplicate it.

**Heterogeneity note for the owner:** with the codex build lane stalled
(phase 3 rerouted to lead) and adversarial waived at the gate, no non-Claude
reviewer has read this slice's shipping code. The waiver predates the
reroute; flagged as a residual, not re-decided here.

**Knowledge candidates (step 8):** one lesson worth keeping — substituting
component commands for a Make target must enumerate the target's full recipe
(the build's substitution silently dropped `uv build`); folded into this
section rather than a new `docs/knowledge/` concept (single occurrence, no
durable seam). No other candidates; the build flagged no anomalies beyond
the four deviations above.

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
