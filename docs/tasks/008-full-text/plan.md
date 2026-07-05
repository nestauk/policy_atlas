# Implementation Plan: 008-full-text

> **Status:** drafted — pending plan-phase adversarial review + human confirmation.
> Contract: [contract.md](contract.md) (approved 2026-07-05 · Shabeer Rauf; three gated
> changes + spec clarification + fixture-policy amendment signed off; contract-stage
> adversarial findings adjudicated 2026-07-05, 9/9).

## Overview

One feature stage plus its substrate, on `task/008-full-text` (branch already carries the
AGPL LICENSE and the contract/rubric commits):
1. **Schema** — three columns + three named CHECKs on `project_source_snapshot`
   (migration 8). No new table; count stays 16.
2. **Fixture documents** — real, openly-licensed publications (Nesta + CC-BY OA papers
   across the three mission domains) + licence-guarded provenance manifest, fetched by a
   dev-time recorder.
3. **`ingest_full_text.py`** — fetch cascade over the fixture fetcher, PyMuPDF4LLM /
   trafilatura parsing, structure-aware segmentation, bounded parallel fan-out,
   per-document status accounting.
4. **Wiring + tests + spec flow-back.**

Unlike 007 (which created corpus rows from metadata), this slice **upgrades** existing
corpus documents in place at the link level; its durable rows are full-text snapshots +
chunks + three new link columns.

## Executor routing (plan-time decision, per harness.md ladder)

| Task | Executor | Why |
|---|---|---|
| 1 (schema + migration) | `lead` | gated surface; migration subtleties stay with the adjudicator |
| 2 (fixture curation: document list) | `lead` | taste + licence judgment + mission-domain knowledge |
| 3 (recorder script + fixture download) | `codex` | judgment-bearing execution, machine-verifiable done (files + manifest + guards), async-friendly |
| 4 (`ingest_full_text.py`) | `lead` | seam-bearing product code; the slice's core logic |
| 5 (wiring: registry/harness/skeleton/helpers) | `fast-worker` | mechanical from precedent + exact spec below |
| 6 (test suite: contract list bulk) | `fast-worker` | transcription of a precise contract test list |
| 7 (test suite: concurrency/socket-deny/timeout) | `lead` | the judgment-bearing test cases |
| 8 (spec flow-back) | `lead` | one line in a living spec + log entry |

## Architecture decisions (all fixed in the approved contract)

- Statuses on the link: `not_attempted` · `ingested` · `fetch_failed` · `parse_failed`;
  reasons: `no_url` · `paywall` · `not_found` · `too_large` · `timeout` · `corrupt` ·
  `no_text_layer` · `thin_text` · `empty`. Three named CHECKs (status vocabulary;
  `ingested` ⟺ snapshot id; failure ⟺ reason present).
- Counting invariant: `eligible == ingested + already_ingested + fetch_failed +
  parse_failed`; summary also counts by reason. Re-runs skip `ingested`, retry failures.
- **No truncation**: 100 MB fetch byte cap (reject) + hard per-document parse timeout
  (terminate-and-survive) are the only guards; parsed documents store whole.
- Fan-out: fetch in the parent; parse+segment as a pure function in per-document worker
  processes fed primitives only (bytes, content type, caps); results written in
  eligible-set order; DB state identical for workers=1 vs 4.
- Snapshots: new immutable `full_text` snapshot; link gains `full_text_snapshot_id`;
  required snapshot metadata: `parse_profile`, `segmentation_policy`, `fetched_from`,
  content type, `envelope_source_snapshot_id`, `ingested_by_run_id`.
- Segmentation: `pymupdf4llm_struct_v1` (heading-bounded sections, tables intact,
  `{page(s), heading_path}` locators) · `trafilatura_para_v1` / `plain_para_v1`
  (`{paragraph}`).
- URL cascade: OpenAlex `best_oa_location.pdf_url` → `primary_location.pdf_url` →
  `open_access.oa_url` → `primary_location.landing_page_url` (HTML); Overton `pdf_url` →
  `document_url`. No URL → `fetch_failed`/`no_url`.
- Fixtures: real licensed documents under `src/policy_atlas/data/fulltext/` +
  `fulltext_manifest.json` (`_meta` + URL→outcome map + per-document provenance with
  licence-or-permission).
- Events: `component.started`/`completed` only; no per-document event.

## Dependency graph

```
Task 1 (schema + migration 8)         Task 2 (doc list, lead) ─→ Task 3 (recorder + fixtures, codex)
        └──────────────┬────────────────────────┘
                       ▼
             Task 4 (ingest_full_text.py)  ← deps added to pyproject here
                       ├── Task 5 (wiring: plan.py, harness.py, skeleton.py, helpers, test_compile)
                       ├── Task 6 + 7 (test_ingest_full_text.py)
                       └── Task 8 (components.md §4 + log.md)
```

---

## Phase 1 — Schema (separable commit)

### Task 1: Columns + migration 8 — `lead`

**Files:** `src/policy_atlas/schema.py`,
`alembic/versions/<hash>_full_text_columns.py`.

- `project_source_snapshot` gains: `full_text_snapshot_id` UUID NULL FK →
  `source_snapshot.source_snapshot_id` (`fk_pss_full_text_snapshot`);
  `full_text_status` TEXT NOT NULL server_default `'not_attempted'`;
  `full_text_error` TEXT NULL. Named CHECKs per the contract block
  (`ck_pss_full_text_status`, `ck_pss_full_text_consistent`,
  `ck_pss_full_text_error_presence`).
- Migration 8: `op.add_column` ×3 + `op.create_foreign_key` + `op.create_check_constraint`
  ×3; downgrade drops constraints then columns. Existing rows take the server default —
  **verify the server_default is kept or dropped consistently with schema.py's
  column-level default** (the other tables use plain defaults; match precedent).
- `schema.py` module docstring: "sixteen tables, **eight** alembic migrations".
- Table-count assertions stay 16 — **no count bumps this slice** (check
  `test_schema.py` for any column-list assertion over `project_source_snapshot` and
  update it).

**Acceptance:** migration roundtrips (`downgrade -1` / `upgrade head`); `make verify`
green (nothing reads the columns yet). **Commit.**

**Estimated scope:** S (2 files)

---

## Phase 2 — Fixture documents (dev-time network)

### Task 2: Curated document list — `lead`

A source list checked into the recorder script: ~10–15 documents across the three Nesta
mission domains (early-years education/development · heat pumps/home decarbonisation ·
food environment/obesity), each entry carrying `title`, `url`, `publisher`, `licence`
(SPDX-like) **or** `permission`, `kind` (pdf/html), and which coverage case it serves
(long 100+-page report · multi-column academic PDF · HTML report page · thin page ·
image-only derivative). Nesta publications for grey literature (incl. ≥1 HTML report
page); CC-BY OA papers (PLOS/BMC/MDPI-class publishers make licence verification easy)
for academic. Failure cases (`403`/`404`/oversize) are manifest-simulated — no document
needed. User may nominate favourite Nesta reports; not blocking.

### Task 3: Recorder + committed fixtures — `codex`

**Files:** `scripts/record_fulltext_fixtures.py`, `src/policy_atlas/data/fulltext/*`,
`src/policy_atlas/data/fulltext_manifest.json`, `.gitignore` (recordings path if any).

- Stdlib `urllib` download of each source-list entry → verify content type + size →
  write under `data/fulltext/` with stable names; derive the image-only PDF from one
  licensed document (render page→image→PDF; PyMuPDF can do this dev-time); write the
  manifest: `_meta` (record date, coverage list, recorder version) + fixture-URL→outcome
  map (keyed by the **acquire fixtures'** `example.org` URLs — read them from
  `openalex_works.json`/`overton_documents.json` so the mapping can't drift) +
  per-document provenance/licence.
- Map coverage: at least one OpenAlex record resolving via each cascade rung (the one
  pdf-bearing record → PDF; landing-only records → HTML or failure outcomes); Overton
  records → PDF success, incl. the long report; one cascade-fallback case (first URL
  fails, second succeeds); one thin-HTML; one 403; one 404; one oversize; one
  image-only; ≥1 record left `not_attempted`-eligible (not screened-in) untouched.
- **Run once dev-time**; commit documents + manifest; total ≤ ~25 MB (contract budget);
  guard tests (Task 6) enforce licence-or-permission + `example.org` keying.

**Estimated scope:** M (script ~150 lines + data files). **Commit** ("fixture documents +
manifest, dev-time recorded").

---

## Phase 3 — `ingest_full_text.py` — `lead`

### Task 4: Module + dependencies

**Files:** `pyproject.toml` (+`pymupdf4llm`, `trafilatura` — approved gated change 2;
pin minimums; `uv lock`), `src/policy_atlas/ingest_full_text.py`.

Public surface: `FetchResult` (dataclass) · `DocumentFetcher` (Protocol, `mode`,
`fetch(url)`) · `FixtureFetcher` (manifest replay via `importlib.resources`) ·
`ingest_full_text_sources(conn, *, project_id, run_id, context, fetcher,
max_workers=4) -> dict`. Google-style docstrings.

Shape (contract §Python + adversarial adjudications):
1. **Eligible set** (deterministic order): the scope's `source_screening_result`
   `is_relevant=true` rows joined to `project_source_snapshot` `origin='acquired'`,
   ordered by link id; skip `ingested` → `already_ingested`.
2. **Parent-side per document:** resolve candidate URLs from
   `metadata.provider_fields` (cascade order above; none → `fetch_failed`/`no_url`);
   fetch via injected fetcher; enforce 100 MB cap (`too_large`); on all-candidates-failed
   map the *last* failure to its reason (403→`paywall`, 404→`not_found`).
3. **Worker (pure, primitives in/out):** parse by content type — PDF: `pymupdf4llm`
   `to_markdown(page_chunks=True)` → heading-bounded section chunks with
   `{pages, heading_path}` locators, tables intact; no extractable text →
   `no_text_layer`; HTML: `trafilatura.extract` → paragraph chunks; plain text →
   paragraphs. Thin-text guard (< threshold, plan default 200 chars) → `thin_text`.
   Runs in a per-document `multiprocessing.Process` with `join(timeout)` +
   `terminate()` on expiry (**not** `ProcessPoolExecutor` — its `cancel()` can't kill
   running tasks; adversarial finding 6); a bounded semaphore keeps ≤ `max_workers`
   live; results returned over a pipe/queue as primitives.
4. **Parent-side writes, eligible order:** success → `source_snapshot`
   (`text_basis="full_text"`, content hash over joined chunk text — `grounding.content_hash`
   conventions, `source_locator`=fetched URL, required metadata incl. governance
   breadcrumbs + `segmentation_policy`) + `chunk` rows + link update
   (`full_text_snapshot_id`, `ingested`, error NULL); failure → link update (status +
   reason). `component.failed` reserved for infrastructure errors.
5. Return counts: totals + `by_reason` + `by_scope`-free simple dict per contract.

**Estimated scope:** L (~300 lines; the segmentation/locator derivation is most of it)

---

## Phase 4 — Wiring — `fast-worker` (spec below is the brief)

### Task 5: Registry, harness, skeleton, helpers

- `plan.py`: `"ingest_full_text": {"requires": ["evidence_scope_id"]}`.
- `harness.py`: `run_harness` gains `document_fetcher: DocumentFetcher | None = None`
  (approved gated change 3), default `FixtureFetcher()` resolved inside `run_harness`,
  carried in `HarnessState` (the `search_backends` pattern); `_run_ingest_full_text`
  binds it via `functools.partial` → `_run_scope_component` (verified fit: acquire uses
  the same shape); graph node + conditional edge + edge to finish.
- `skeleton.py`: after appraise, run ingest_full_text on the same scope; log counts by
  status/reason + the corpus text-basis distribution (before/after).
- `tests/helpers.py` `delete_project_data`: full-text snapshots are referenced by link
  FK — clear `full_text_snapshot_id` (or delete links first, then orphaned full-text
  snapshots + their chunks per task-003 precedent); verify exact FK-safe order at
  implement time with a seeded-delete test.
- `test_compile.py`: `"ingest_full_text"` valid with scope id; rejected without.

**Estimated scope:** M. **Commit** (module + wiring) after Phase 3+4 verify green.

---

## Phase 5 — Test suite

### Task 6: `test_ingest_full_text.py` bulk — `fast-worker` (contract test list is the brief)

The contract's list minus the concurrency/egress cases: migration roundtrip + three
CHECKs (five rejection cases) · URL resolution order per backend + `no_url` persisted ·
cascade fallback · PDF structure (headings/tables/locators/reading order spot-check) ·
**no-truncation long-report proof** · failure-reason matrix (paywall/not_found/
too_large/no_text_layer/thin_text) · HTML main-content (boilerplate absent) · success
metadata completeness + governance-chain reachability · envelope immutability ·
eligibility boundaries (not_relevant/screen_failed/uploads/other scopes) · idempotency +
retry-failed + invariant both runs · events summary, no per-document events · harness
round-trip · licence guard + `example.org` keying + `_meta` · `delete_project_data` ·
downstream unchanged (classify/appraise identical pre/post ingest).

### Task 7: Concurrency + egress cases — `lead`

Fan-out determinism (workers=1 vs 4 → identical DB state) · timeout with worker actually
terminated and the run completing (slow-parser double; must be a top-level function —
spawn-picklable) · socket-deny end-to-end run (autouse-scoped guard fixture blocking
`socket.socket`) · zero-egress import guard extended (module source has no http client;
recorder not imported).

**Estimated scope:** L combined (~450 lines)

### Task 8: Spec flow-back — `lead`

- `components.md` §4: one line — v3.0 ingestion = fetch → parse → segment; vectorisation
  deferred to the first vector reader; eager-and-uniform discipline restated.
- `docs/specs/log.md` dated entry. `make okf-validate` green.

### Checkpoint — final
- [ ] `make verify` fully green; skeleton exits 0 with ingest counts; migration
      roundtrips; `/verify` drives the end-to-end flow (exact command → verification.md).
      **Commit** (tests + flow-back).

### Step-8 obligations (after the review stack, in the PR)

`docs/deferred.md` per the contract's list: live `DocumentFetcher` (+ paywall-detection
signal ladder & OA-status cross-check) · docling ML-layout escalation (+ GPU/AWS sizing
note) · time-budget-aware parser selection · chunk-volume-bias controls at retrieve ·
OCR (`no_text_layer`) · multi-PDF assembly · injection posture extended to full text ·
cross-project full-text reuse · **update the existing "Slice 008 inputs retained" entry**
(lands now; supersede the v2 OpenAlex URL-precedence order per adversarial finding 4) ·
knowledge entry if any survives review · point-in-time claims sweep.

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `pymupdf4llm` locator granularity (heading path + pages from `page_chunks` output) | Locator derivation fiddly | Verify against the real fixture set early (Task 4 before Task 6); worst case locators carry `{pages}` + nearest heading only — still ≥ contract minimum |
| Table extraction quality varies by document | Tables split/flattened in some fixtures | Assert tables-intact on a chosen fixture with a clean table, not universally |
| Spawn start method on macOS/CI (workers, doubles) | Pickling failures in tests | Workers take primitives; test doubles are top-level functions; run suite locally with `spawn` forced once |
| Committed PDFs bloat the repo | Slow clones, noisy diffs | ≤25 MB budget; binary files excluded from review diffs (007 retro); shallow-clone note if needed |
| Real fixture URLs rot before recording day | Recorder failures | Source list verified at curation (Task 2); recorder re-runnable; any dead entry swapped at record time |
| Licence ambiguity on an academic PDF | Can't commit | CC-BY-only publishers preferred (PLOS/BMC class); drop-and-swap over agonising |
| `pymupdf4llm` version drift changes chunk output | Hash-sensitive tests flake on upgrade | Pin minimum + record version in `_meta`; content-hash assertions computed from produced text, not golden strings |
| Semaphore-bounded `multiprocessing.Process` runner is bespoke (~40 lines) | Concurrency bugs | Deterministic-writes design keeps workers stateless; determinism + termination tests are exactly the guard; `ponytail:` comment names the upgrade path (pebble/pool) if it ever grows |

## Open questions

None blocking — all design decisions fixed in the approved contract. Optional: the user
may nominate specific Nesta reports for the fixture set at Task 2.
