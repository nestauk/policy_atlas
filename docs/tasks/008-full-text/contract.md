# Task contract: 008-full-text

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted.  
> Contract approved (before planning): _date · who_ ·
> Plan approved (before implementation): _date · who_ · ADR: expected for the
> snapshot-identity decision (decision 2) if approved — it shapes how every future
> component reads the corpus.

## Goal

Add **full-text ingestion** — the post-screen Tier-0 step the spec gates behind `screen`
(EB components §4). For every **screened-in acquired** source of a scope, resolve candidate
URLs from the provider fields task 007 retained for exactly this slice, fetch the document
through a new `DocumentFetcher` seam, parse and segment it under a named policy, and attach
the resulting **immutable `full_text` snapshot** to the corpus document. When full text
can't be fetched (paywall, dead link, unparseable), the source is **not dropped** — it
stays on the text in hand (`abstract_only`), with the failure **queryable, never silent**
(fixing v2's fragility of fetch errors swallowed at debug level and thin landing-page text
reported `ok`).

**Zero runtime egress.** Fetching is egress; the live fetcher stays behind the runtime-egress
gate. v3.0's `DocumentFetcher` implementation replays **committed, wholly fabricated fixture
documents** keyed by the `example.org` URLs already present in the acquired fixtures — same
seam pattern as `SearchBackend` (task 007). No sanitization step is needed here: unlike API
recordings, the documents are *generated*, never recorded, so no real third-party content
ever exists in the pipeline.

Per spec, fetch is **mechanical execution of the governed `search`** — telemetry plane +
run-record summary, **not** a per-document audit event. No new governance event type.

## Deliverable

A PR on `task/008-full-text` → `dev` that:
- Adds three columns to `project_source_snapshot` (`full_text_snapshot_id`,
  `full_text_status`, `full_text_error`) + one Alembic migration (gated change 1).
- Ships `ingest_full_text.py` with `DocumentFetcher` (protocol), `FixtureFetcher`,
  URL resolution + fetch cascade, PDF/HTML/text parsing under v2's caps, segmentation
  under named policies, and `ingest_full_text_sources()`.
- Adds `pypdf` as a runtime dependency (gated change 2).
- Registers `"ingest_full_text"` in `COMPONENT_REGISTRY`; wires `_run_ingest_full_text`;
  `run_harness` gains optional `document_fetcher` (gated change 3).
- Ships committed fabricated fixture documents + manifest, and the dev-time
  `scripts/generate_fulltext_fixtures.py` that produced them.
- Updates `skeleton.py`: acquire → screen → classify → appraise → **ingest_full_text**,
  logging the text-basis distribution before/after.
- Spec clarification in EB components §4 (vectorisation deferral — decision 1) + `log.md`.
- Records the deferred seams in `docs/deferred.md`.
- Passes `make verify` — all green.

## Read first

- [EB components §4 — full-text ingestion](../../specs/capabilities/evidence-base/components.md)
  (gated by screen, built for all screened-in; can't-fetch → text-in-hand, `text_basis`;
  fetch is mechanical execution of governed `search`, not a per-document audit event;
  vectorisation eager-and-uniform — see decision 1)
- [System data-model — § Corpus & source snapshots](../../specs/system/data-model.md)
  (immutable snapshots, no original bytes retained; frozen parsed chunks are the
  content-of-record; identity = content hash + governance event + locator; segmentation is
  trust-relevant — named versioned policy, one parse + one segmentation per snapshot)
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  ("ingestion is not a tool" — indirect-injection surface; `search` is the only
  agent-invocable egress verb)
- [docs/deferred.md](../../deferred.md) — "Slice 008 (full-text) inputs retained for it":
  OpenAlex URL/OA block and Overton `document_url`/`pdf_url` + `grouped_pdf_ids_in_result`
  in `metadata.provider_fields`; v2 patterns to carry (OA-location precedence, fetch
  cascade, parse caps 50 MB / 50 pages / 100 K chars, failure manifest) and fragilities to
  avoid; the snapshot-identity fork deliberately left to this slice
- [007-acquire contract](../007-acquire/contract.md) — seam pattern precedent
  (fixture-backed backend, gated `run_harness` parameter, leak guard)

**Fixture grounding (checked 2026-07-05):** in the committed acquire fixtures, all 12
Overton records carry `pdf_url` + `document_url` (+ multi-PDF `grouped_pdf_ids_in_result`);
11 of 12 OpenAlex records are landing-page-only (`primary_location.landing_page_url`), one
carries the full pdf/OA URL set. The fetch fixtures therefore must serve **HTML documents
on landing URLs** and PDFs on pdf URLs — the mixed reality the cascade exists for.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **Tier-0 in this slice = fetch → parse → segment. Vectorisation is deferred** to the
   slice where vectors are first read (retrieval / characterise clustering). Nothing in
   v3.0 reads an embedding; shipping one would need an embedding model (inference/egress
   gate) plus a vector store (dependency + schema gates) that nothing exercises — "model
   only what behaves". The spec's **eager-and-uniform discipline is kept, restated, not
   weakened**: when the embed seam lands, it vectorises eagerly and uniformly over all
   ingested snapshots — lazy/on-demand stays rejected. Spec flow-back: one clarifying line
   in components §4 + `log.md` entry, approved with this contract.
2. **Snapshot identity — the fork 007 deliberately left open. Recommendation:
   link-level attachment.** Full text arrives for a document that already has an immutable
   `abstract_only` envelope snapshot. Options considered:
   - **(a) Attach chunks to the existing snapshot** and flip its `text_basis` — mutates a
     snapshot; breaks content-hash identity and the immutability rule. **Rejected.**
   - **(b) New snapshot + a second `project_source_snapshot` link** — the document appears
     in the corpus twice; "acquired sources always screen" would re-screen the full-text
     link; classify/appraise double-process; requires superseded-link semantics everywhere
     downstream. Heavy, and the duplication is a modelling artefact, not a fact.
   - **(c) New immutable snapshot + `full_text_snapshot_id` on the link (recommended)** —
     the corpus document (the `project_source_snapshot` row) keeps its envelope snapshot
     and gains a nullable FK to its full-text snapshot once ingested. Both snapshots stay
     immutable, each with its own honest `text_basis` and content hash. Corpus membership
     stays one-row-per-document, so screen/classify/appraise results and their FKs are
     untouched and never re-run. Future readers (extract, grounding, retrieval) take the
     full-text snapshot's chunks when present, else the envelope's — exactly the spec's
     "grounding and coverage see which a finding rests on".
   The spec's `supersedes` edge stays what it is — a *human-asserted* corrected-re-upload
   pointer, deferred; this system-made attachment is a different relation and does not
   reuse it. If approved, record as an ADR (it shapes every future corpus reader).
3. **Fetch outcome is per-document persistent state, not just a log line.**
   `full_text_status` on the link: `not_attempted` (default — includes uploads, whose text
   arrived with them; the column describes the *fetch pipeline*, text availability stays
   `source_snapshot.text_basis`) · `ingested` · `fetch_failed` · `parse_failed`. A named
   CHECK constrains values; a second CHECK ties `ingested` ⟺ `full_text_snapshot_id IS NOT
   NULL`. `full_text_error` holds a compact machine-readable reason (`paywall`, `not_found`,
   `too_large`, `thin_text`, …); attempt-level detail (each URL tried, per-attempt errors)
   goes to structured logs — telemetry plane per spec, and the `component.completed` payload
   carries the run-record summary counts. This is the v3.0 failure manifest: queryable
   per-document outcome + run summary, nothing swallowed.
4. **URL resolution + fetch cascade — v2's pattern, deterministic, explicit URLs only.**
   Candidate list per document from `metadata.provider_fields`, in fixed order —
   OpenAlex: `best_oa_location.pdf_url` → `primary_location.pdf_url` →
   `open_access.oa_url` → `primary_location.landing_page_url` (fetched as HTML);
   Overton: `pdf_url` → `document_url`. The cascade tries candidates in order until one
   fetch+parse succeeds; every failure is counted into the attempt log. **Landing-page
   scraping with PDF-link discovery and the DOI-URL fallback are live-seam work** (they
   need real HTML in the wild) — deferred, recorded. A document with no candidate URL at
   all is `skipped_no_url` (visible, counted; constructible in tests though current
   fixtures always carry at least one URL). Uploads are never fetched (their text arrived
   with them).
5. **Parse: `pypdf` for PDF (gated new dependency), stdlib for HTML/text; v2's caps; a
   thin-text guard v2 lacked.** `pypdf` is pure-Python (no binary deps), maintained, and
   parsing is exactly what it's for — hand-rolling PDF extraction fails rung 6 of the
   ladder in the other direction. HTML via stdlib `html.parser` (tag-strip + block
   elements → paragraphs); `text/plain` as-is. Caps carried from v2: 50 MB fetched bytes ·
   50 pages · 100 K chars — over-cap on bytes fails the fetch (`too_large`); page/char caps
   **truncate at the boundary and flag it** in snapshot metadata (`truncated`), never
   silently. **Thin-text guard:** parsed text below a minimum (threshold a plan detail,
   order-of-hundreds of chars) → `parse_failed` / `thin_text`, *not* success — the direct
   fix for v2 reporting thin DOI-landing text as `ok`. Parse profile is named and versioned
   in the full-text snapshot's metadata (e.g. `pypdf_v1` · `stdlib_html_v1` · `plain_v1`).
6. **Segmentation: named versioned policies, structure-aware light.** PDF:
   `page_paragraph_v1` — pages, then blank-line paragraphs; chunk `locator` carries
   `{page, paragraph}`. HTML/text: `paragraph_v1` — `{paragraph}`. One parse, one
   segmentation per snapshot (spec); semantic splitting is a later layer, not this slice.
   Content hash over the joined chunk text (same convention as `ingest_upload`);
   `source_locator` = the URL actually fetched; `fetched_from` + content type recorded in
   snapshot metadata.
7. **Component wiring mirrors 004–007.** `"ingest_full_text"` in `COMPONENT_REGISTRY`
   requiring `evidence_scope_id`; eligible set = the scope's screened-in
   (`is_relevant = true`) links with `origin = "acquired"`. Runs after the cheap envelope
   passes (spec §4: "after screen/classify/appraise"); the registry gate is screen — the
   skeleton demonstrates the full order. "Ingestion is not a tool" holds: this is an
   orchestrator-scheduled plan component (procedure), not an agent-invocable verb, same
   realisation class as acquire. Fetcher injection: `run_harness` gains optional
   `document_fetcher: DocumentFetcher | None = None` defaulting to `FixtureFetcher()` —
   the `search_backends`/`provider` precedent, gated change 3.
8. **Idempotency and re-runs.** Re-running the component skips `ingested` links
   (`already_ingested`, counted) and **retries** failed ones (statuses overwrite —
   deterministic against fixtures; live-world transience is exactly why failed is
   retryable). Counting invariant, test-enforced:
   `eligible == ingested + already_ingested + fetch_failed + parse_failed + skipped_no_url`.
   Return shape mirrors acquire: counts + `coverage`-style summary, no per-document lists.
9. **Multi-PDF Overton documents: primary `pdf_url` only in v3.0.** Every Overton fixture
   record is a grouped document; assembling `grouped_pdf_ids_in_result` into one corpus
   text (ordering, dedup, joint hashing) is real design work with no v3.0 reader —
   deferred, recorded. The retained field keeps it possible.
10. **Untrusted-text posture carries forward.** Fetched full text is third-party content at
    much larger volume than the envelope; v3.0's deterministic code never interprets it
    (parse/segment only — no execution, no LLM). The injection-screening enforcement point
    stays at the LLM/live seams, recorded in `docs/deferred.md` (007's posture, extended to
    full text). Security review confirms no interpretation path.
11. **Fixture documents are generated, not recorded.** `scripts/generate_fulltext_fixtures.py`
    (dev-time, never imported by the package) writes small fabricated documents — multi-page
    PDFs with text streams, HTML pages, a thin page, plus a manifest JSON mapping each
    acquire-fixture URL → outcome (`ok` + file · `403` · `404` · oversize). Structural
    authenticity matters less than in 007: the parser is a third-party library; fixtures
    exercise **our** cascade/caps/segmentation logic. Leak guard extends: every manifest URL
    is `example.org` (test-enforced); document text is fabricated by construction.

### Schema

**Gated change 1 — three columns on `project_source_snapshot`** (one migration; table
count stays 16):

```
full_text_snapshot_id   UUID   NULL  REFERENCES source_snapshot(source_snapshot_id)
                                     (fk_pss_full_text_snapshot)
full_text_status        TEXT   NOT NULL  DEFAULT 'not_attempted'
full_text_error         TEXT   NULL
CheckConstraint(full_text_status IN ('not_attempted','ingested','fetch_failed','parse_failed'),
                name="ck_pss_full_text_status")
CheckConstraint((full_text_status = 'ingested') = (full_text_snapshot_id IS NOT NULL),
                name="ck_pss_full_text_consistent")
```

Downgrade drops the columns. No data migration (existing rows take the default).

### Python

**`ingest_full_text.py`** — new module (public surface carries Google-style docstrings):

```python
@dataclass
class FetchResult:
    status: str                 # "ok" | "error"
    content_type: str | None    # "application/pdf" | "text/html" | "text/plain"
    body: bytes | None
    error: str | None           # "paywall" | "not_found" | "too_large" | ...

class DocumentFetcher(Protocol):
    mode: str  # "fixture" | "live"
    def fetch(self, url: str) -> FetchResult:
        """Fetch one URL. Never raises for per-document outcomes."""

class FixtureFetcher:
    """Replays committed fabricated documents by URL. Zero egress."""
```

Plus private helpers: candidate-URL resolution per backend (decision 4), parse dispatch by
content type (decision 5), segmentation (decision 6).

`ingest_full_text_sources(conn, *, project_id, run_id, context, fetcher) -> dict`:
resolve eligible set → per link: cascade fetch → parse → segment → create `source_snapshot`
(+ chunks) → set `full_text_snapshot_id` / `full_text_status` — or record the failure on
the link. Always completes with honest counts; `component.failed` reserved for
infrastructure errors (per 007 precedent).

**`plan.py`** — `"ingest_full_text": {"requires": ["evidence_scope_id"]}`.

**`harness.py`** — `_run_ingest_full_text` node (mirror `_run_acquire`); `document_fetcher`
parameter; conditional-edge wiring.

**`skeleton.py`** — extend the smoke chain with ingest_full_text after appraise; log
per-outcome counts and the corpus text-basis distribution.

**`tests/helpers.py`** — `delete_project_data` handles the new FK (clear
`full_text_snapshot_id` links / delete in FK-safe order per task-003 precedent).

**Fixture data** — `src/policy_atlas/data/fulltext/` (fabricated PDFs/HTML) +
`fulltext_manifest.json` (`_meta` + URL → outcome map, 007's fixture-format precedent).
Coverage across the acquire fixtures: PDF success (multi-page), HTML landing success,
paywall 403, dead link 404, thin HTML page, oversize document, cascade fallback (first
URL fails → second succeeds), and untouched non-screened-in records.

**`test_ingest_full_text.py`** — new file, covering:
- Migration roundtrip; table count still 16; both named CHECKs reject invalid rows
  (bad status; `ingested` without snapshot id; snapshot id with non-`ingested` status).
- URL resolution order per backend (OpenAlex four-step precedence; Overton two-step);
  no-URL record → `skipped_no_url`.
- Cascade: first candidate fails, second succeeds — attempt visible in logs, outcome `ingested`.
- PDF parse: multi-page → `page_paragraph_v1` chunks with `{page, paragraph}` locators,
  sequenced; page/char caps truncate + set `truncated`; oversize bytes → `fetch_failed` /
  `too_large`.
- HTML parse: tags stripped, paragraph chunks under `paragraph_v1`; thin page →
  `parse_failed` / `thin_text` and the source stays on the envelope (v2-fragility test).
- Failure semantics: paywall / dead link → `fetch_failed` + compact `full_text_error`; the
  envelope snapshot and all downstream result rows untouched; source never dropped.
- Success semantics: new snapshot `text_basis="full_text"`, own content hash over joined
  chunks, `source_locator` = fetched URL, `parse_profile` + `fetched_from` in metadata;
  envelope snapshot byte-identical before/after (immutability).
- Eligibility: only the scope's screened-in acquired links; `not_relevant`, `screen_failed`,
  uploads, and other scopes untouched.
- Idempotency: re-run → `already_ingested`, no new snapshots; failed links retried;
  counting invariant holds per run, both runs.
- Events: `component.started`/`component.completed` with summary counts; **no**
  per-document event types emitted (asserted).
- Harness round-trip: `Plan(component="ingest_full_text")` → statuses + snapshots in DB.
- Zero-egress guard: extend 007's import test to `ingest_full_text.py` (no HTTP client
  usage; generator script never imported by the package).
- Leak guard: every manifest URL on `example.org`; `_meta` present.
- `delete_project_data` clean with full-text snapshots present.
- Downstream unchanged: classify/appraise outputs identical before/after ingest (they read
  the envelope).

Updates to existing tests: `test_compile.py` — `"ingest_full_text"` valid with a scope id,
rejected without.

### Out of scope

- **Live `DocumentFetcher`** — runtime egress, its own gated slice; carries the live-seam
  requirements (timeouts, redirects, politeness/robots, content-type sniffing,
  landing-page scrape + PDF-link discovery, DOI-URL fallback, per-provider fetch pacing).
- **Vectorisation / embeddings / vector store** — deferred to the first vector reader
  (decision 1); eager-and-uniform discipline restated in the spec clarification.
- **Multi-PDF Overton assembly** (decision 9).
- **Re-screen / re-classify / re-appraise on full text** — existing deferred seams
  (`Unknown` resolution, appraisal second pass) — unchanged.
- **Full-text for uploads** — their text arrives with them; nothing to fetch.
- **Cross-project full-text snapshot reuse** — the shared content-addressed substrate stays
  deferred (007); two projects ingesting the same document each get their own snapshot.
- **Injection screening of fetched text** — posture recorded (decision 10); enforcement at
  the LLM/live seams.
- `characterise`+ and everything downstream of appraise — subsequent slices.

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — three columns + two named CHECKs + one FK on `project_source_snapshot`;
   one Alembic migration.
2. **Dependency** — `pypdf` (runtime). First new runtime dependency since scaffold;
   pure-Python, no transitive binary deps.
3. **Public interface** — `run_harness` optional `document_fetcher` parameter (+ the
   `"ingest_full_text"` registry entry, per 007 precedent).

Plus one spec clarification (components §4 vectorisation deferral, decision 1) — approved
with this contract per the spec-refinement flow.

**Explicitly not crossed:** no runtime egress (fixture replay; generator script dev-time
only), no auth, no CI change, no other schema or interface change.

## Public / private boundary

- Committed fixture documents are **wholly fabricated** (generated, never recorded) — no
  real third-party content can exist in them; manifest URLs are `example.org` only
  (test-enforced).
- No credentials involved anywhere in this slice (fixtures need no API).
- Column names, protocol/function names, policy/profile version strings — durable/committable.

## Model route

`n/a` — deterministic fetch-replay + parse + segment. No LLM call, no inference provider,
no runtime network I/O.

## Disciplines binding this slice

- **Snapshots immutable** — full text is a *new* snapshot attached at the link; the
  envelope snapshot is never touched (test-enforced byte-identity).
- **Flag, don't drop** — fetch/parse failure keeps the source on the text in hand with a
  queryable status + reason; truncation is flagged, thin text is a failure, never `ok`.
- **Honest absence** — `not_attempted` ≠ `fetch_failed`: coverage claims can distinguish
  "never tried" from "tried and unavailable".
- **Skip is visible, never silent** — every eligible link lands in exactly one counted
  bucket; invariant test-enforced.
- **Segmentation is trust-relevant** — named versioned policies + parse profiles on every
  snapshot; one parse, one segmentation.
- **No per-document governance events** for fetch (spec) — run-record summary + telemetry;
  the `search.executed` discipline stays acquire's.
- **Deterministic** — same fixtures → same snapshots, hashes, statuses, counts.

## Stop conditions

- Any gated change (schema · dependency · public interface) not yet approved, or any
  schema/dep change beyond the three gated items.
- Any code path would perform runtime network I/O.
- The snapshot-identity decision (2) proves wrong mid-build (e.g. a constraint forces
  double corpus membership) — halt, don't improvise a fourth shape.
- Scope would grow past the contract (live fetch, embeddings, multi-PDF, re-screen).
- `make verify` red with unclear root cause.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green.
- All checks deterministic (fixture replay; no LLM, no egress). Every check is a test.
- One manual dev-time check: the generator script was run once and produced the committed
  fixture documents + manifest (date + coverage recorded in `_meta`).

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts.
- Named results from `test_ingest_full_text.py`, including the immutability test, the
  thin-text (v2-fragility) test, and the cascade-fallback test.
- Migration roundtrip clean; table count still 16.
- End-to-end command: harness with `component="ingest_full_text"` over an
  acquired+screened corpus — statuses, new snapshots and chunk counts visible in DB;
  text-basis distribution logged by the skeleton.
- Fixture provenance: generator run date, document/outcome coverage list, leak-guard pass.
- Public-safety confirmation (fabricated documents only; no credentials).
- Deferred seams recorded in `docs/deferred.md` (live fetcher with its requirement list ·
  vectorisation-at-first-reader with the eager-uniform discipline · multi-PDF assembly ·
  injection screening extended to full text · cross-project full-text reuse).
- Diff summary.

## Risk tier & review focus

**Tier 3** — a schema change, the first new runtime dependency since scaffold, a
public-interface addition, and the slice builds the seam through which bulk untrusted
third-party documents will eventually enter the product.

Review focus:
- **Correctness:** cascade order; caps + truncation flags; thin-text guard; status/FK
  consistency; counting invariant; idempotent re-run; envelope immutability.
- **Provenance:** per-snapshot parse profile + segmentation policy; `source_locator` =
  fetched URL; honest `text_basis` on both snapshots; `not_attempted` vs `fetch_failed`.
- **Security:** zero runtime egress; `pypdf` operates on fixture bytes only; no
  execution/interpretation of fetched content; generator script outside the import graph;
  no real content in fixtures.
- **Schema:** migration roundtrip; named constraints; downstream FKs untouched.
- **Scope:** no live fetch, no embeddings, no multi-PDF, no re-screening.
