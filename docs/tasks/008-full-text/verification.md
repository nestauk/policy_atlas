# Verification: 008-full-text

Evidence for the full-text ingestion slice. Filled at step 6 (build phase); **Review
findings** + **Rubric status** to be added by the review stack (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | 205 passed (169 pre-slice + 36 in `test_ingest_full_text.py`); suite ~9 min — the ingest tests run ~10 real-document ingests (fetch-replay + spawned parse workers, no mocking) |
| `make typecheck` | pass | mypy strict, 31 source files |
| `make lint` | pass | ruff |
| `make build` | pass | sdist + wheel |
| `make okf-validate` | pass | 20 concepts, 0 violations (specs changed this slice) |
| migration roundtrip | pass | `alembic upgrade head` → `downgrade -1` → `upgrade head` clean (revision `a1d7f3c9e6b2`); table count still 16 |

## Checks beyond the build

All deterministic (fixture replay, pinned parser versions; no LLM, no egress). Named
results from `tests/test_ingest_full_text.py` (36 tests):

- **Outcome distribution / counting invariant** — `test_outcome_distribution`: over the 24
  eligible fixture documents: 10 `ingested`, 11 `fetch_failed` (paywall 4 · not_found 5 ·
  too_large 2), 3 `parse_failed` (thin_text · no_text_layer · corrupt);
  `eligible == ingested + already_ingested + fetch_failed + parse_failed` holds.
- **Per-link statuses** — `test_per_link_statuses` (15 parametrized cases): each specific
  fixture URL lands in its designed bucket; cascade-fallback case (first URL 404 → second
  ingests) and the Overton `pdf_url: "n/a"` sentinel case assert `fetched_from` = the URL
  actually fetched.
- **Envelope immutability** — `test_envelope_immutability`: all envelope `source_snapshot`
  rows captured before ingest are field-identical after; full text is a *new* snapshot
  (ADR 0003).
- **No-truncation long-report proof** — `test_no_truncation_long_report`: the 233-page
  World Bank fixture parses whole — max chunk-locator page ≥ 220, > 200 K chars, a
  back-matter phrase from `doc[-2]` present in the joined chunk text. No cap code path
  exists to test.
- **Fan-out determinism** — `test_fanout_determinism_workers_1_vs_4`: workers=1 vs
  workers=4 produce identical normalized DB state (statuses, hashes, chunk sequences,
  locators, metadata).
- **Timeout terminate-and-survive** — `test_parse_timeout_terminates_worker_and_run_completes`
  (adversarial finding 6): a hung parser double is genuinely `terminate()`d; the run
  completes with reason-coded outcomes and no leaked worker processes.
- **Zero-egress guards** — `test_zero_egress_socket_deny` (finding 5): a full fixture
  ingest with `socket.socket` patched to raise completes green (scoped around the call —
  the suite's own Postgres connection predates the patch, plan finding 2);
  `test_ingest_module_has_no_http_client` + `test_recorder_script_not_imported_by_package`
  extend 007's import guards.
- **Failure-reason matrix** — paywall (403), dead link (404), oversize, image-only
  (`no_text_layer`), thin HTML (`thin_text`), corrupt, timeout — each separately asserted;
  envelope snapshot and downstream rows untouched in every case; source never dropped.
- **Structure-aware segmentation** — `test_pdf_structure_chunks`: heading-bounded chunks
  under `pymupdf4llm_struct_v1` with `{pages, heading_path}` locators; markdown tables kept
  intact as their own chunks (World Bank fixture); a real abstract sentence appears
  contiguously (reading-order spot check). `test_html_main_content`: trafilatura main
  content extracted; a footer boilerplate string from the raw Nesta page appears in no
  chunk.
- **Success metadata completeness** — `test_success_metadata_complete` (findings 3 + 8):
  every full-text snapshot carries `parse_profile`, `segmentation_policy`, `fetched_from`,
  `content_type`, `envelope_source_snapshot_id`, `ingested_by_run_id`; content hash equals
  `content_hash` over the joined chunk text; `source_locator` = fetched URL.
- **Governance chain** — `test_governance_chain`: full-text snapshot → metadata
  breadcrumbs → link → acquiring run → `search.executed` events, asserted end-to-end.
- **Schema CHECKs** — `test_migration_roundtrip_and_checks`: five rejection cases across
  the three named constraints (`ck_pss_full_text_status`, `ck_pss_full_text_consistent`,
  `ck_pss_full_text_error_presence`).
- **URL resolution** — `test_url_resolution_order`: OpenAlex four-rung precedence
  (`best_oa_location.pdf_url` first, per adversarial finding 4's supersession) + dedup;
  Overton two-rung; the exact `pdf_url: "n/a"` fixture record (plan finding 4).
- **`no_url` persistence** — `test_no_url_persisted` (finding 1): a screened-in record
  with no candidate URLs persists `fetch_failed`/`no_url`, queryably distinct from
  `not_attempted`.
- **Eligibility boundaries** — uploads, `not_relevant`, `failed`, and other-scope links
  all stay `not_attempted`.
- **Idempotency / retry** — second run: `already_ingested == 10`, no new snapshots,
  failures retried deterministically to the same outcomes; invariant holds both runs.
- **Events** — `test_harness_roundtrip_and_events`: `component.started`/`completed` with
  summary counts; **no per-document event types** (spec: fetch is mechanical execution of
  governed `search`).
- **Licence guard** — `test_licence_guard` (finding 9): every committed document carries
  an allowlisted licence (CC-BY-4.0 · CC-BY-3.0-IGO · CC0-1.0) **or** a recorded
  permission entry (org + who + date); fetch-keying URL domains ⊆ {`example.org`,
  `doi.org/10.99999/…`} (007's sanitized set, plan finding 3); `_meta` present.
- **Helpers** — `test_delete_project_data_with_fulltext` (plan finding 5): union-capture
  removes both envelope and full-text snapshots + chunks.
- **Downstream unchanged** — classify/appraise outputs identical before/after ingest
  (they read the envelope).

**Manual dev-time check (contract acceptance):** `scripts/record_fulltext_fixtures.py`
was run once dev-time (2026-07-05) and produced the 13 committed documents + manifest;
its self-checks (licence-or-permission presence, per-file sizes, World Bank page count
233 ≥ 100, image-only derivative has no text layer, ≤ 26 MB total, manifest round-trip)
all passed. Recorded in `_meta` (recorder v1, pymupdf4llm 0.3.4, trafilatura 2.1.0).

## Long-document evidence (the docling-#2077 risk, measured)

233-page World Bank PDF, in-process `parse_and_segment` on CPU (Apple Silicon, pinned
`pymupdf4llm` 0.3.4): **wall-clock 27.2 s, peak RSS 132 MB**, parsed whole (max locator
page 233, 63 chunks, 505,730 chars). No memory pathology; comfortably inside the 60 s
per-document timeout. The full 24-document skeleton ingest (4 workers) completes in
**~51 s** — consistent with the contract's couple-of-minutes wall-clock target for a
~100-document run.

## End-to-end command

```
DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas" \
  uv run python -m policy_atlas.skeleton
```

Drives acquire → screen → classify → appraise → **ingest_full_text** over one scope.
Observed (project `7e7c0428-7141-438d-8ce2-b2c9571eb8dd`, 2026-07-05): text-basis
distribution `{abstract_only: 24, full_text: 1}` → `{abstract_only: 14, full_text: 11}`;
ingest counts `eligible=24 ingested=10 fetch_failed=11 parse_failed=3` with
`by_reason={paywall: 4, not_found: 5, too_large: 2, thin_text: 1, no_text_layer: 1,
corrupt: 1}`; DB shows the 10 full-text snapshots with correct parse profiles /
segmentation policies / `{pages, heading_path}` and `{paragraph}` locators and per-link
statuses exactly matching the manifest's outcome map. Run twice (15:26 and 15:51 UTC),
identical distributions — deterministic replay.

## Fixture provenance (licence-guard test-enforced)

13 committed documents, 24,403,444 bytes total, recorded 2026-07-05:

| File | Publisher | Licence / permission |
|---|---|---|
| bmc_fiscal_policies_review.html | BMC (Springer Nature) | CC-BY-4.0 |
| derived_corrupt.pdf | task-008 recorder (generated) | CC0-1.0 |
| derived_image_only.pdf | derived from Nesta heat-pump PDF | permission: Nesta · Shabeer Rauf · 2026-07-05 |
| derived_thin_stub.html | task-008 recorder (generated) | CC0-1.0 |
| frontiers_ashp_ventilation_2021.pdf | Frontiers Media | CC-BY-4.0 |
| frontiers_getting_ready_2018.pdf | Frontiers Media | CC-BY-4.0 |
| frontiers_school_readiness_2022.pdf | Frontiers Media | CC-BY-4.0 |
| naturecomms_a2a_heat_pumps_2024.pdf | Springer Nature | CC-BY-4.0 |
| nesta_fairer_start_discovery.pdf | Nesta | permission: Nesta · Shabeer Rauf · 2026-07-05 |
| nesta_heat_pump_costs.pdf | Nesta | permission: Nesta · Shabeer Rauf · 2026-07-05 |
| nesta_heat_pumps_report_page.html | Nesta | permission: Nesta · Shabeer Rauf · 2026-07-05 |
| plos_food_environment_review.pdf | PLOS | CC-BY-4.0 |
| worldbank_obesity_flagship.pdf | World Bank | CC-BY-3.0-IGO |

Full titles, source URLs and retrieval dates in `fulltext_manifest.json` (`documents`
map). Coverage spans the three Nesta mission domains (early years · heat pumps/home
decarbonisation · food environment/obesity).

## Diff summary

- **Schema (gated change 1):** three columns + FK + three named CHECKs on
  `project_source_snapshot`; migration 8 (`a1d7f3c9e6b2`); durable
  `server_default='not_attempted'` (plan finding 6). Table count stays 16.
- **Dependencies (gated change 2):** `pymupdf4llm` + `trafilatura`. **Flagged deviation
  (minor, within the approved gate):** `pymupdf4llm` is pinned `>=0.0.27,<1` — the 1.x
  line released after contract approval hard-depends on `pymupdf-layout`/`onnxruntime`,
  i.e. exactly the ML stack the approved gate excludes ("no ML stack, no model weights");
  0.3.4 keeps that tier an optional extra. The ML tier remains the recorded docling seam.
- **`ingest_full_text.py`:** DocumentFetcher seam + FixtureFetcher (lazy manifest);
  four-rung/two-rung URL cascade with sentinel normalization; pymupdf4llm structured
  markdown → heading-bounded sections + intact tables with `{pages, heading_path}`
  locators; trafilatura/plain paragraph policies; thin-text guard; bounded per-document
  spawn workers (drain-before-join transport, plan finding 7; terminate-on-timeout,
  finding 6; primitives only across the process boundary, finding 7); parent-side writes
  in eligible-set order; reason-coded per-link outcomes + run-summary counts.
- **Wiring (gated change 3):** registry entry, `run_harness(document_fetcher=…)`,
  skeleton chain extension with text-basis distribution logging, `delete_project_data`
  union-capture.
- **Fixtures:** 13 real openly-licensed documents + licence-guarded manifest + dev-time
  recorder. **Recorder note:** downloads use `curl` via `subprocess` rather than bare
  `urllib` — nature.com bot-blocks urllib's client fingerprint; still stdlib-only,
  dev-time only, never imported by the package. Binary fixture files are excluded from
  review diffs per the 007 retro.
- **Spec flow-back (approved with contract):** components.md §4 vectorisation-deferral
  clarification + log.md entry.
- Eligible-set predicate uses the as-built `source_screening_result.status = 'relevant'`
  (plan finding 1).

## Intent & assumptions

- The manifest's URL→outcome map is the designed test surface: every eligible fixture
  document lands in a designed bucket, so the outcome distribution doubles as a
  regression oracle.
- Envelope/document mismatch is accepted by contract (fixture envelopes stay sanitized
  007 records; fetch fixtures map their URLs to real documents; the join is by URL).
- `FixtureFetcher` returns `not_found` for unmapped URLs — a dead link is the honest
  fixture-world equivalent.

## Known unverified items / gaps

- **Chunk granularity on heading-light PDFs (observed at /verify, flagged for the parse
  seams):** four academic PDFs (both Nature Comms + Frontiers ASHP + PLOS) yield only
  2–3 very large chunks — pymupdf4llm's font-size heading heuristic misses their internal
  headings, so whole documents collapse into one/two sections. Content is complete
  (no-truncation holds) and locators are honest; reading order and tables are correct
  where detected — so this does not trip the contract's parser stop condition
  ("headings/tables/reading order **materially wrong**"), but it is exactly the
  heuristic-vs-ML-layout gap the recorded **docling escalation seam** (parse-quality
  evals) exists for, and token-budgeted re-chunking at the embed seam will subdivide
  oversized sections regardless.
- Live-fetch behaviours (redirects, politeness, paywall *detection*) are the live-seam's,
  not exercised here by design.
- Suite wall-clock grew from ~4 s to ~9 min (real parses, ~11 full ingest runs — each an
  unmocked 24-document fetch-replay + spawned-worker parse). Accepted for Tier-3 evidence
  quality. Candidate remedies if it bites, both needing their own approval: `pytest-xdist`
  (`-n auto`; the tests are parallel-safe — rollback transactions or unique project ids),
  or a subset filter on `ingest_full_text_sources` (public-interface change). Not slipped
  into this slice.

## Public safety

- All committed documents are real publications under their own open licences or a
  recorded own-org permission — test-enforced; no paywalled or all-rights-reserved
  content; failure cases simulated in the manifest, not committed.
- No credentials anywhere in the slice; fixture fetch keys stay on sanitized domains.
- Logs/evidence above contain no secrets and no raw third-party source text beyond
  attributed openly-licensed titles/phrases.

## Deferred work

Step-8 obligation (after the review stack): record in `docs/deferred.md` — live
`DocumentFetcher` (+ paywall-detection signal ladder & OA-status cross-check) · docling
ML-layout escalation (+ GPU/AWS sizing note) · time-budget-aware parser selection ·
chunk-volume-bias controls at retrieve · OCR for `no_text_layer` · multi-PDF assembly ·
injection posture extended to full text · cross-project full-text reuse · update the
"Slice 008 inputs retained" entry (OpenAlex URL-precedence supersession, finding 4).
The /verify chunk-granularity observation above feeds the docling-seam entry.
