# Verification: 041-policy-live-bugs

Evidence for one slice. Public-safe: no secrets, raw source text, credentials
or unredacted traces.

> **Lightweight cycle.** Low tier: owner-directed live-bug batch, each fix
> requested and accepted piecewise in session on 2026-09-08. No rubric, no
> plan, no ADR. One public-interface change (additive fields on
> `EvidenceItemOut`) passed its gate as an explicit owner request in
> session — see the contract's public-interface-gate note. A Codex review
> of the full diff ran on 2026-09-08; its findings and their outcomes are
> in § Review findings.

## Public interface change

`EvidenceItemOut` gains `abstract: str | None` and
`abstract_source: "provider" | "llm_description" | None` (S3). Moved up
from `SourceDossierOut`, which now inherits them — the dossier's wire shape
is unchanged. Additive on the evidence list; OpenAPI + generated frontend
types regenerated with `make openapi-sync`.

## Commands run

| Command | Result | Notes |
|---|---|---|
| `npx vitest run` (frontend) | **pass** | 591 tests / 78 files, includes new tests for the CSV download (pagination, quoting, formula-injection defusal, filename) and the chat best-claim verdict |
| `npx tsc --noEmit` (frontend) | **pass** | |
| `npx eslint` (touched files) | **pass** | |
| `make typecheck` (backend mypy) | **pass** | 305 files |
| `make lint` (backend ruff) | **pass** | |
| `pytest -k "evidence or dossier or read_model"` vs `policy_atlas_test` | **1388 passed, 2 failed** | The 2 failures are pre-existing — see § Known items |
| `make openapi-sync` | **pass** | openapi.json + `src/api/gen/types.ts` regenerated |
| `evidence_page` called directly against the dev DB | **pass** | Returns populated `abstract`/`abstract_source` for sources that carry one |

## Manual checks

- Judge output for chat turn `5fa774fa-873d-4881-add4-396e0d975d4e`
  (owner's ACARA example) read from the DB: 5 claims cite [1]; c1 is
  tier_1, c2/c3 tier_2, c4/c5 unsupported (meta-claims about the evidence
  base). Confirms S7's premise: the old worst-verdict chip flagged a
  well-supported reference, and the old tooltip paired that label with a
  different claim's rationale. The new chip shows tier and rationale from
  the same best-supported claim.
- CSV values are quoted, quotes doubled, and cells whose first
  non-whitespace character is `= + - @` are prefixed with `'`
  (spreadsheet formula injection — titles/venues arrive from external
  sources). The file starts with a UTF-8 BOM and is served as
  `text/csv;charset=utf-8`.

## Review findings (Codex, 2026-09-08)

| Finding | Severity | Outcome |
|---|---|---|
| CSV export: offset pagination has no snapshot; sources arriving mid-download can shift pages (duplicates/omissions) | medium | **Accepted, not fixed** — owner call: only occurs while a run is actively adding sources during the seconds of a download; cursor logic not worth it |
| Formula defusal missed markers behind leading whitespace (`"\t=SUM(1)"`) | medium | **Fixed** — defusal now matches `/^\s*[=+\-@]/`; test covers the tab-prefixed case |
| CSV Blob lacked a UTF-8 BOM/charset; non-ASCII text could mis-decode in spreadsheet apps | low | **Fixed** — `\uFEFF` BOM prepended, MIME `text/csv;charset=utf-8` |
| `_abstract_fields` could return `abstract_source="llm_description"` with no abstract | low | **Fixed** — a missing abstract now returns `(None, None)` |
| Docs called the slice "no-gate" while shipping a public-interface change | medium | **Fixed** — contract records the gate and its in-session owner approval |

## Known items

- **Two pre-existing conformance failures**, order-dependent, on the
  `/evidence` route: `test_task_scoped_get_routes_hide_ownership_with_byte_identical_404`
  and `test_conditionally_public_gets_hide_private_and_unknown_tasks_and_open_public_ones`
  (both `[/api/v1/tasks/{task_id}/evidence]`). They pass alone and when
  `tests/api/test_api_conformance.py` runs alone; they fail inside the
  `-k "evidence or dossier or read_model"` selection. Verified pre-existing
  by stashing this slice's backend diff and rerunning the identical
  selection on a clean test DB: same 2 failures. Not fixed here; needs its
  own look (cross-module test pollution on `dev`).
- Some sources genuinely have no description (`abstract` absent in
  provider metadata) — their CSV Description cell and title hover are
  empty by design (honest absence).
- The Share tab now renders two primary buttons; the brand guide says one
  per view. Owner-directed (both were asked for as blue buttons).
