# Verification: 007-acquire

Evidence for the acquire slice. Public-safe — no secrets, no real third-party records,
no credentials.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make okf-validate` | pass | specs bundle conformant after §1 flow-back |
| `make test` | pass | **161 passed** (53 in `test_acquire.py`; 108 pre-existing, all green under the rename) |
| `make typecheck` | pass | mypy, 29 source files |
| `make lint` | pass | ruff |
| `make build` | pass | wheel verified to ship `policy_atlas/data/*.json` (unzip listing) |

## Checks beyond the build

- **Deterministic tests** — all checks are tests; fixture replay only, no LLM, no egress:
  - Table count 16; all **five named check constraints** on `search_coverage_record`
    reject invalid values by name (`ck_scov_stop_condition` — `'saturated'` explicitly
    rejected — `ck_scov_verdict`, `ck_scov_verdict_origin`, `ck_scov_backends_array`,
    `ck_scov_filters_object`); **cross-project composite FK** rejected
    (`fk_scov_scope_project`); `uq_scov_run` rejects a second record per run.
  - `test_reconstruct_abstract_from_committed_fixture` — OpenAlex inverted-index
    reconstruction against the committed structurally real index (multi-position tokens,
    every token position asserted); empty/missing → `None`.
  - Per-backend envelope mapping incl. Overton `snippet` → `llm_document_description`
    fallback, `keyed_other_identifiers.doi[0]` (list) extraction, string-or-list
    `authors`/`topics`, empty-string-as-absent, title → translated-title fallback,
    no-title → `skipped_unusable`.
  - `abstract_source` provenance persisted, all four values asserted on snapshot metadata:
    `publisher_abstract` · `snippet` · `llm_description` · `none`.
  - Round-trip: 12 + 12 fixture records → snapshots `origin="acquired"`, `run_id` set,
    `text_basis="abstract_only"`, one chunk each, `segmentation_policy="metadata_envelope_v1"`,
    content hash over the chunk text, `source_locator` per contracted mapping
    (OpenAlex `id` URL; Overton `document_url` → `overton_url` fallback); retained
    provider fields present (URL/OA block at minimum) under `metadata.provider_fields`.
  - **Three identity guards separately**: `backend_record_id` re-run · normalized DOI
    (prefixed vs bare, mixed case) across backends with deterministic list-order winner ·
    content hash. `test_cross_backend_doi_dedup_deterministic_winner` — OpenAlex wins.
  - Rerun idempotency: second run `acquired == 0`, `already_acquired == 24`, counting
    invariant `acquired + already_acquired + skipped_unusable == results_returned` holds
    per backend and in total on both runs; a **new** coverage record per run.
  - **Cross-project isolation**: project B acquiring the same fixtures gets its own 24
    links, `already_acquired == 0`; project A untouched.
  - `search.executed` per backend per call (payload keys/values as contracted, trust
    classes declared, fixture mode); `source.acquired` per new snapshot only.
  - Adequacy verdict, all four cases: both-ok → `adequate`; raising backend →
    `inadequate` + `stop_condition="error"` + healthy backend's 12 results kept +
    `component.completed` (never `component.failed`); empty-but-successful beside
    productive → `adequate`; zero usable (title-less page) → `inadequate`.
  - Harness round-trip `Plan(component="acquire")` with the fixture-pair default;
    `component.completed` payload carries counts incl. `by_backend`.
  - **Full chain** `test_full_chain_over_both_fixture_corpora`: acquire → screen
    (abstract-less → `title_only` @ 0.7 fail-open, `failed == 0`) → classify (all
    `Unknown / Insufficient information`) → appraise (`skipped_unknown`, nothing scored).
  - Fixture leak guard (`10.99999/` DOIs; URLs only `example.org` or
    `doi.org/10.99999/…`), `_meta` provenance block, per-backend quirk-coverage
    assertions; zero-egress guard (no HTTP-client import anywhere in the package;
    recorder scripts never imported).
  - `delete_project_data` removes coverage records + acquired links (and the FK-unsafe
    runs-before-links ordering is fixed and exercised with acquired rows).
- **Migration roundtrips** — both migrations, both directions, clean
  (`alembic downgrade -2` → `upgrade head`): `e7b4d2a1c8f3` (rename, incl. pkey +
  unique-constraint renames) and `f9c6e3b8d4a2` (`search_coverage_record`).
- **Manual** — skeleton smoke run observed end to end (below): per-backend acquire
  counts, screen-basis distribution (`title_abstract=21`, `title_only=4`), classify
  Unknowns, appraise skips, event log with two `search.executed` entries.

## End-to-end command

```
uv run --env-file .env python -m policy_atlas.skeleton
```

Exit 0. Observed: `component.completed` for acquire with
`acquired=24, by_backend={openalex: 12, overton: 12}, stop_condition=breadth_truncated,
adequacy_verdict=adequate` + `coverage_record_id`; **two `search.executed` events** in the
event log; DB shows the coverage record row
(`breadth_truncated | adequate | model | backends length 2`) and the acquired
`project_source_snapshot` rows (`origin='acquired'`).

## Diff summary

Five commits, rename mechanically separable from the feature:

1. `9e1bfcd` **rename** — `screening_scope` → `evidence_scope` clean and total: table,
   four `screening_scope_id` columns, `uq_…`/pkey constraint names, module code, event
   payload keys, tests; migration 6. No behaviour change.
2. `d5fd4f5` **schema** — `search_coverage_record` (10 columns, composite FKs, five named
   check constraints); migration 7; table-count assertions 15 → 16 (three files).
3. `51f298a` **fixtures** — dev-time stdlib recorders (OpenAlex keyword form, Overton
   semantic `squery` @ 1 req/s, keys from env) + committed sanitized fixtures
   (`_meta` + records; leak-guard markers), `scripts/recordings/` gitignored.
4. `5d33775` **acquire + wiring** — `acquire.py` (protocol, two fixture backends,
   mappings, three-guard dedup, events, coverage record, error isolation); registry
   entry; `run_harness` optional `search_backends` param (gated change 3);
   `_run_acquire` node; skeleton mixed corpus; `delete_project_data` fix.
5. `433cadf` **tests + spec flow-back** — `test_acquire.py` (53 cases); components.md §1
   clarification + specs `log.md` entry.

**One deviation from contract wording, resolved within its own vocabulary:** decision 4
claims missing abstracts flow `_stub_screen`'s fail-open path "with no screen changes".
As-built, `_stub_screen` crashes on an explicit `abstract: null` (its default only covers
a *missing* key), which would have screened abstract-less acquired records as `failed`.
Fixed on the acquire side per the contract's own "None/**absent** where the source has no
such concept": None-valued envelope keys persist as **absent** in snapshot metadata —
screen genuinely unchanged, fail-open path test-covered (`failed == 0`,
`title_only` @ 0.7).

## Review findings

Tier-3 stack, run 2026-07-05 in fresh contexts (none by the implementing conversation):
contract-verifier (pinned agent) · `/code-review` medium (8 finder angles) ·
`security-auditor` subagent (the one security lane) · Codex adversarial pass
(heterogeneous half) — ~470K total incl. the Codex leg. After the fix batch:
`make verify` green (**167 passed**), skeleton exits 0.

- **Contract verifier:** all 19 rubric items verified satisfied (items 7/8 pending by
  design at that point — closed below); every verification.md/contract claim reproduced
  against as-built code; no findings. One observation — unknown-backend records silently
  counted `skipped_unusable` — was independently escalated by Codex (#5) and fixed.
- **`/code-review` (medium):** three confirmed correctness findings, all fixed +
  test-covered: (1) Overton record with no `document_url`/`overton_url` crashed the whole
  run on `source_locator NOT NULL` instead of counting `skipped_unusable`; (2) same for
  an OpenAlex Work missing `id`; (3) `languages=[""]` persisted `language: ""` against
  the absence convention. Cleanups applied: `functools.cache` on fixture loading,
  `functools.partial` for `_run_acquire`, skeleton counts-logging deduped into
  `_log_component_counts`, raw-SQL run-seeding replaced with `tests/helpers.seed_run`.
  Declined: shared sanitizer module across the two recorders (plan explicitly sanctions
  inline-per-script; leak-guard test is parametrized over both), derivable
  `results_returned` (explicit count is honest; invariant is test-enforced).
- **Security lane (`security-auditor`):** 1 Medium — **real funder grant IDs**
  (`awards[].funder_award_id`) had passed through the sanitizer; unique indexed
  identifiers, one API query re-identifies the record. Fixed: sanitizer v2 hashes
  award ids, fixtures re-derived (`--resanitize`), leak-guard test widened to assert
  hashed award ids. 3 Low, all fixed: Overton raw recording could embed the API key via
  echoed pagination URLs (recorder now redacts on write; the existing on-disk raw was
  scrubbed and confirmed key-free); zero-egress test guard made recursive (`rglob`);
  quantitative-fingerprint residual (authentic dates/counts/biblio) documented as an
  accepted risk in each fixture's `_meta.sanitized`. Info: `OPENALEX_EMAIL` wired into
  the recorder as the polite-pool `mailto`; stub-namespace forward note recorded at the
  live-backend seam. Verdicts: runtime egress CLEAN · keys CLEAN (incl. branch history) ·
  untrusted-text CLEAN · cross-project integrity CLEAN · secrets hygiene CLEAN.
- **Adversarial review (Codex):** five findings, adjudicated: (1) **High, adopted** —
  dedup preload read persisted DOIs verbatim, so an uploaded snapshot with a
  prefixed/mixed-case DOI never blocked re-acquisition; preload now normalizes on read
  (+ test). (2) Medium, **deferred** — concurrent acquire runs could double-insert
  (preload race); v3.0 is single-process/serial and a DB-level guard is a gated schema
  change — recorded in deferred.md. (3) Medium — missing-locator crash: same as
  `/code-review` finding 1 (independent cross-family convergence), fixed. (4) Medium —
  raw-recording key echo: same as the security Low, fixed. (5) Low, adopted stronger —
  unknown/duplicate backend names now rejected upfront (`ValueError` → the harness's
  `component.failed` infrastructure-error path) instead of silently skipping records.
- **`ponytail-review` + `/simplify`:** covered by the reuse/simplification/efficiency/
  altitude finder angles of the `/code-review` run, with fixes applied inline (above) —
  a separate same-family pass over the same diff was skipped per the review-stack
  economy (006 adjudication: near-zero marginal findings). Altitude angle confirmed the
  contract-sanctioned shapes (mapping layer as private helpers, quirk patching,
  event-log counts readback) are designed, not bandaids.
- **`make okf-validate`:** pass (runs inside `make verify`).

## Rubric status

All 19 items hold (contract-verifier confirmed 1–6 and 9–19 item-by-item with evidence;
its two pending-by-design items are now closed):

- Item 7 (deferred seams in docs/deferred.md) — closed at step 8, in this PR.
- Item 8 (review stack ran, findings recorded) — closed by this section.

## Intent & assumptions

- Fixture record count: 12 per backend (contract allows 10–20).
- Recorder query `housing affordability policy` (matches the skeleton's scope intent so
  the smoke run reads naturally).
- Quirks the live pages didn't happen to exhibit were patched onto real record structure
  by the sanitizer and are labelled `(patched: …)` in each fixture's
  `_meta.quirk_coverage`; patched values are fabricated anyway, and each patched
  *pattern* is documented (OpenAlex nullability per API docs; Overton shapes
  v2-confirmed/live-observed).
- Envelope keys with no value persist as absent (not `null`) — see Diff summary.
- `search_coverage_record.backends` includes an errored backend (it is part of the
  attempted search-space boundary; its failure is visible in `search.executed` +
  `by_backend`).

## Known unverified items

- The live-backend seam (timeouts, rate limiting, query sanitization, per-provider caps)
  is recorded in `docs/deferred.md`, not built — nothing to verify until that slice.
- Overton semantic-mode internals (whether `squery` is hybrid under the hood) remain
  unverified — recorded at the seam.

## Public safety

- Committed fixtures are **sanitized for both backends**: real structure/nesting/
  nullability, fabricated values (neutral-lexicon text so fabricated strings can never
  collide with real records). Test-enforced markers: every DOI `10.99999/…`, every URL
  `example.org` (or `doi.org/10.99999/…`).
- A dev-time sanitizer audit additionally asserted **no identifying raw string value
  survives** into either committed fixture (titles, authors, affiliations, publishers,
  OAI ids, thumbnails, cites entries all fabricated).
- Raw recordings live only in gitignored `scripts/recordings/` on the recording machine.
- `OVERTON_API_KEY` / `OPENALEX_API_KEY` read from the environment by the dev-time
  recorders only; never committed, never read by package code (test-enforced zero-egress
  guard).

## Fixture provenance (acceptance check: one manual dev-time run per backend)

| | OpenAlex | Overton |
|---|---|---|
| Recorder | `scripts/record_openalex_fixtures.py` | `scripts/record_overton_fixtures.py` |
| Mode | keyword `filter=title_and_abstract.search` | semantic `squery` (1 req/s honoured) |
| Query | housing affordability policy | housing affordability policy |
| Recorded | 2026-07-05 | 2026-07-05 |
| Records | 12 (of 25 fetched) | 12 (of 50 fetched) |
| Quirk coverage | missing abstract (recorded) · missing year (patched) · non-article type (recorded) · non-English (patched) · missing doi (patched) · multi-position inverted index (recorded) | koi DOI (recorded) · no-DOI (recorded) · empty snippet + llm description (recorded) · neither summary (patched) · string/list authors + topics (mixed) · government + IGO publishers (recorded) · translated title (recorded) · multi-PDF grouped (patched) |

Both raw fetches confirmed gitignored; committed files carry the `_meta` provenance block.

## Deferred work

Recorded in [docs/deferred.md](../../deferred.md) at step 8 (after the review stack, in
the PR) per the contract's list: live `SearchBackend` implementations with the v2-lesson
requirements · Arm-B agentic search loop (chosen direction, with R&D pointers) ·
backend-scope selection seam · Overton semantic mode + filters · thin-base re-search ·
cross-project dedup + fuzzy near-dup · injection-screening posture · slice-008 full-text
inputs · downstream seams surfaced by the API exploration.
