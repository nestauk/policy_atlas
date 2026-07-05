# Task contract: 008-full-text

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted — rev 5 (user-steered, 2026-07-05).  
> Rev 2 changes at user direction: parser selection researched properly (parse quality is
> foundational for a RAG tool — no default libraries); **truncation abolished** (full text
> or honest failure, never silent partial); ingestion is a **bounded parallel fan-out**,
> not a serial loop; fixture documents are **real, openly-licensed publications** (Nesta +
> seminal OA academic literature), not generated fakes. Grounded in a fresh v2
> ingestion-code review (§ V2 integration review) and a parser-landscape research pass
> (saved: `~/Documents/Last30Days/best-pdf-parsing-libraries-for-rag-ingestion-raw-v3.md`).  
> Rev 3 (team decision, 2026-07-05): **Policy Atlas is licensed AGPL-3.0** (LICENSE file
> added), removing the copyleft penalty that had ruled out the PyMuPDF family.  
> Rev 4 (user steer): quality-first — docling primary with PyMuPDF4LLM fallback.  
> Rev 5 (user decision, 2026-07-05): ingestion has a **wall-clock target of a couple of
> minutes per ~100-document run** — docling's CPU cost (~5–20 min fanned out) misses it.
> Parser lands as **PyMuPDF4LLM only**; docling moves to the recorded quality-escalation
> seam, joined by a **time-budget-aware parser-selection seam** (user idea: the user's
> stated time horizon picks the parser — tight → fast, long → ML layout). The
> parse-profile-per-snapshot design is the hook both seams plug into (decision 5).  
> Contract approved (before planning): _date · who_ ·
> Plan approved (before implementation): _date · who_ · ADR: expected for the
> snapshot-identity decision (decision 2) and the parser selection (decision 5) if
> approved — both shape every future component.

## Goal

Add **full-text ingestion** — the post-screen Tier-0 step the spec gates behind `screen`
(EB components §4). For every **screened-in acquired** source of a scope, resolve candidate
URLs from the provider fields task 007 retained for exactly this slice, fetch the document
through a new `DocumentFetcher` seam, parse it with a **structure-aware parser** and segment
it under a named policy, and attach the resulting **immutable `full_text` snapshot** to the
corpus document. When full text can't be fetched or parsed (paywall, dead link, scanned-only,
corrupt), the source is **not dropped** — it stays on the text in hand (`abstract_only`),
with the failure **queryable and reason-coded, never silent**.

Parse quality is treated as **foundational, not incidental**: chunks written here are the
permanent content-of-record (spec: one parse, one segmentation per snapshot; no bytes
retained, so re-parse is impossible by construction). A cheap parse now is a permanently
degraded substrate for every downstream component. This is why the slice takes a real
document-understanding parser rather than a default library (decision 5), and why nothing
is ever truncated (decision 6).

**Zero runtime egress.** Fetching is egress; the live fetcher stays behind the runtime-egress
gate. v3.0's `DocumentFetcher` implementation replays **committed real documents** keyed by
the `example.org` URLs already present in the acquired fixtures — same seam pattern as
`SearchBackend` (task 007). The chosen parsers are model-free local code; the runtime never
touches the network (test-enforced).

Per spec, fetch is **mechanical execution of the governed `search`** — telemetry plane +
run-record summary, **not** a per-document audit event. No new governance event type.

## Deliverable

A PR on `task/008-full-text` → `dev` that:
- Adds three columns to `project_source_snapshot` (`full_text_snapshot_id`,
  `full_text_status`, `full_text_error`) + one Alembic migration (gated change 1).
- Ships `ingest_full_text.py` with `DocumentFetcher` (protocol), `FixtureFetcher`,
  URL resolution + fetch cascade, structure-aware PDF parsing (PyMuPDF4LLM) and HTML
  main-content extraction (trafilatura), structure-aware segmentation under named
  policies, and `ingest_full_text_sources()` with **bounded parallel per-document
  fan-out**.
- Adds `pymupdf4llm` (brings `pymupdf`) and `trafilatura` as runtime dependencies
  (gated change 2).
- Registers `"ingest_full_text"` in `COMPONENT_REGISTRY`; wires `_run_ingest_full_text`;
  `run_harness` gains optional `document_fetcher` (gated change 3).
- Ships committed **real, openly-licensed** fixture documents + a provenance manifest,
  and the dev-time `scripts/record_fulltext_fixtures.py` that fetched them.
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
  content-of-record; identity = content hash + governance event + locator;
  **"Segmentation is trust-relevant, not a hidden detail. Structure-aware parse first
  (pages/headings/tables/captions/footnotes)"** — decision 5 exists to honour this line;
  one parse + one segmentation per snapshot)
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  ("ingestion is not a tool" — indirect-injection surface; `search` is the only
  agent-invocable egress verb)
- [docs/deferred.md](../../deferred.md) — "Slice 008 (full-text) inputs retained for it":
  OpenAlex URL/OA block and Overton `document_url`/`pdf_url` + `grouped_pdf_ids_in_result`
  in `metadata.provider_fields`; the snapshot-identity fork deliberately left to this slice
- [007-acquire contract](../007-acquire/contract.md) — seam pattern precedent
  (fixture-backed backend, gated `run_harness` parameter)

**Fixture grounding (checked 2026-07-05):** in the committed acquire fixtures, all 12
Overton records carry `pdf_url` + `document_url` (+ multi-PDF `grouped_pdf_ids_in_result`);
11 of 12 OpenAlex records are landing-page-only (`primary_location.landing_page_url`), one
carries the full pdf/OA URL set. The fetch fixtures therefore must serve **HTML documents
on landing URLs** and PDFs on pdf URLs — the mixed reality the cascade exists for.

**Parser-landscape grounding (researched 2026-07-05; raw file above):** 2026 benchmarks
(opendataloader-bench, 200 PDFs) rank layout-aware parsers docling 0.877 (permissive
licence, CPU-capable) > marker 0.861 (GPL, GPU-leaning, 2 GB install) > MinerU 0.831
(AGPL, GPU-leaning, CJK specialist); PyMuPDF is the fastest classic extractor (~0.01 s/page)
and led plain-text quality in the cross-category arXiv study; pypdf (BSD) is lightest
(91 ms/page) but has **no layout model** — plain-text only, weak on multi-column academic
layouts. All parsers struggle on scanned/image-only PDFs without OCR. For HTML, trafilatura
leads main-content extraction (mean F1 0.937 vs readability-lxml 0.914; Apache-2.0 since
v1.8). Docling caveats, on the record: ~1 GB model load, ~0.5–0.8 s/page on CPU (≈15–25 s
for a 30-page paper), a known memory-accumulation issue on very long documents (docling
issue #2077). **Licence context (rev 3):** Policy Atlas is itself AGPL-3.0, so the PyMuPDF
family's AGPL-3.0 is fully compatible and no longer a selection penalty. **Quality
adjudication (rev 4):** docling's structure comes from trained models (DocLayNet-class
layout detection, TableFormer table structure, a reading-order model); PyMuPDF4LLM's comes
from heuristics (font-size headings, geometric table finding). On layout-messy grey
literature and two-column academic PDFs — our corpus — the ML tier is measurably better,
and the chunks written here are permanent.

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
3. **Fetch/parse outcome is per-document persistent state with a reason vocabulary —
   v2's central failure, fixed by construction.** v2 collapsed every parse failure
   (oversized, timeout, corrupt, scanned/empty, thin HTML) into one unexplained
   `skipped_count`, swallowed fetch errors at debug level, and kept no per-document record
   of loss. Here: `full_text_status` on the link — `not_attempted` (default; includes
   uploads, whose text arrived with them — the column describes the *fetch pipeline*, text
   availability stays `source_snapshot.text_basis`) · `ingested` · `fetch_failed` ·
   `parse_failed` — with a named CHECK, a second CHECK tying `ingested` ⟺
   `full_text_snapshot_id IS NOT NULL`, and `full_text_error` carrying a **closed,
   machine-readable reason**: `paywall` · `not_found` · `too_large` · `timeout` ·
   `corrupt` · `no_text_layer` (scanned/image-only — distinct, because OCR is a deferred
   seam, not a silent hole) · `thin_text` · `empty`. Attempt-level detail (each URL tried,
   per-attempt errors) goes to structured logs — telemetry plane per spec — and the
   `component.completed` payload carries the run-record summary counts by status and
   reason. Queryable per-document outcome + run summary; nothing swallowed.
4. **URL resolution + fetch cascade — v2's pattern, deterministic, explicit URLs only.**
   Candidate list per document from `metadata.provider_fields`, in fixed order —
   OpenAlex: `best_oa_location.pdf_url` → `primary_location.pdf_url` →
   `open_access.oa_url` → `primary_location.landing_page_url` (fetched as HTML);
   Overton: `pdf_url` → `document_url`. The cascade tries candidates in order until one
   fetch+parse succeeds; every failure is logged per attempt. **Landing-page scraping with
   PDF-link discovery and the DOI-URL fallback are live-seam work** — deferred, recorded
   (v2's meta-refresh follow and PDF-link discovery are the port-forward pattern there).
   A document with no candidate URL at all is `skipped_no_url` (visible, counted). Uploads
   are never fetched (their text arrived with them).
5. **Parser selection: PyMuPDF4LLM for PDF, trafilatura for HTML — quality within a
   stated wall-clock budget (user decision, 2026-07-05: a ~100-document run should
   ingest in about a couple of minutes; docling misses that by roughly an order of
   magnitude on CPU).** The quality ordering itself is on the record and unchanged:
   docling's trained models (DocLayNet-class layout detection, TableFormer tables,
   reading order; 0.877 on opendataloader-bench) beat PyMuPDF4LLM's heuristics
   (font-size headings, geometric table finding), most on layout-messy grey literature.
   The rev-5 call is that the gap is not worth ~10× the wall-clock *for v3.0*, and the
   design keeps the upgrade path open rather than foreclosing it:
   - **PyMuPDF4LLM (`pymupdf4llm_v1`):** structure-aware markdown extraction — headings,
     reading order, `find_tables()`-backed tables, per-page output — at ~0.02–0.1 s/page
     on CPU with no ML stack, no model weights, no network, and no long-document memory
     pathology. A ~100-document (~3,000-page) run fans out to **well under two minutes**.
     PyMuPDF led plain-text extraction quality in the cross-category arXiv study, and its
     engine was the one part of v2's pipeline the code review rated "works, keep" — v2's
     failures were truncation, serialism and thrown-away structure, not the engine.
     AGPL-3.0, licence-compatible since rev 3.
   - **Two recorded seams instead of an in-slice second parser** (both plug into the
     parse-profile-per-snapshot design; neither is built now):
     1. **ML-layout escalation** — docling behind a `docling_v1` parse profile, entered
        via parse-quality evals, for document classes where heuristic structure detection
        measurably falls short.
     2. **Time-budget-aware parser selection** (user idea, 2026-07-05) — the user's
        stated time horizon steers parser choice per run: tight deadline → fast parser,
        long horizon → ML-layout parser. Naturally a plan/Config-carried setting (its own
        interface gate, per plan-as-object) feeding the same profile mechanism; possibly
        orchestrator-derived from the intent conversation, like the deferred
        backend-scope selection.
   - **Also considered:** marker (GPL — compatible, but GPU-leaning, 2 GB install),
     MinerU (AGPL — compatible, but GPU-leaning, CJK-specialist strengths we don't
     need), pypdf/stdlib (no layout model — the floor v2's cautionary tale warns
     against), unstructured/LlamaParse (heavy/API-shaped; LlamaParse is egress by
     definition).
   - **trafilatura** (Apache-2.0) for HTML: main-content extraction with boilerplate
     removal is a solved problem (mean F1 0.937 vs readability-lxml 0.914) that v2
     hand-rolled badly (its BS4 fallback swept nav/footer into the corpus; its declared
     `readability-lxml` dependency was never even imported).
   - `text/plain` needs no parser.
   - Parse profile is named and versioned in the full-text snapshot's metadata
     (`pymupdf4llm_v1` · `trafilatura_v1` · `plain_v1`).
6. **No truncation, ever — full text or honest failure (user direction, 2026-07-05).**
   v2 stacked three silent truncations (50 pages at parse → 100 K chars at normalize →
   15 K tokens at extraction) so its retrieval corpus never saw past roughly the first
   30–40 pages of a long report, with no per-document record of the loss. Long policy
   reports are Policy Atlas's core content, and a truncated text labelled `full_text`
   would be a false grounding claim. Here caps are **guards that fail loudly, never
   scissors**: a generous fetch byte cap (100 MB — over it → `fetch_failed`/`too_large`,
   source stays on the envelope) and a **hard per-document parse timeout** (process-based
   and genuinely cancellable — v2's `run_in_executor` + `wait_for` leaked uncancellable
   threads; over it → `parse_failed`/`timeout`). A parsed document is stored **whole**.
   There is no page cap, no char cap, no `truncated` flag — the flag existed in rev 1 of
   this contract and is deliberately gone: a state that mixes "full text" with "some text
   missing" shouldn't be representable.
7. **Segmentation: structure-aware from the parser's document model, under named
   versioned policies.** PDF (`pymupdf4llm_struct_v1`): chunks follow PyMuPDF4LLM's
   markdown structure (heading-bounded sections, paragraphs, tables kept intact as their
   own chunks), each chunk's `locator` carrying page number(s) and the heading path —
   the provenance v2 computed and then threw away (its `page_spans` never reached the DB,
   forcing brittle post-hoc substring matching for quote location). HTML/text
   (`trafilatura_para_v1` / `plain_para_v1`): paragraph chunks, `{paragraph}` locators.
   One parse, one segmentation per snapshot (spec); token-budgeted re-chunking belongs to
   the embed seam. Content hash over the joined chunk text (same convention as
   `ingest_upload`); `source_locator` = the URL actually fetched; `fetched_from`, content
   type and parse profile recorded in snapshot metadata. A **thin-text guard** (parsed
   text below a minimum, threshold a plan detail) → `parse_failed`/`thin_text` — the
   direct fix for v2 reporting thin DOI-landing stubs as `ok` full text.
8. **Ingestion is a bounded parallel fan-out (user direction, 2026-07-05).** v2 parsed
   serially (its throughput bottleneck at ~200 documents) and its concurrency settings
   were dead config (defined, never wired). Here: per-document ingestion (fetch → parse →
   segment) is a **pure function** with no DB access, executed over a **bounded process
   pool** (CPU-bound parsing + genuinely cancellable timeouts, per decision 6); DB writes
   happen in the parent in **deterministic eligible-set order** as results complete, so
   the persisted outcome is independent of completion order and worker count
   (test-enforced: workers=1 and workers=4 produce identical DB state). Worker count is a
   real wired parameter with a modest default (plan detail). Spec cover: "within-step
   data-parallel fan-out is retained, not
   deferred". Per-host politeness/rate limiting matters only when fetches go live —
   recorded at the live-fetcher seam.
9. **Fixture documents are real, openly-licensed publications (user decision,
   2026-07-05 — supersedes the generated-fixtures plan of rev 1 and amends the task-007
   sanitized-fixtures policy for *documents*).** Real documents carry the parse quirks
   (layouts, tables, footers, encodings) that generated fakes cannot; for a slice whose
   entire job is parse quality, fabricated fixtures would test the pipeline against a
   strawman. Composition:
   - **Grey literature: Nesta publications** (the user's organisation — own-org content,
     clearly committable): report PDFs plus at least one Nesta web/HTML report page for
     the HTML path. Nesta's heat-pump work doubles as domain-relevant content.
   - **Academic: seminal open-access papers** in Nesta's domains — early years
     education, heat pump adoption, food environment policies — **selected for open
     licences (CC BY or equivalent)** at recording time.
   - **Provenance manifest, licence-guarded:** `fulltext_manifest.json` maps each
     acquire-fixture URL → outcome (`ok` + file · `403` · `404` · oversize · no-text-layer)
     and, for every committed document, records **title, real source URL, publisher,
     licence, and retrieval date**. A test asserts every committed document carries a
     licence from the allowlist (own-org · CC BY family) — the successor to 007's leak
     guard (fetch-keying URLs stay `example.org`; the *documents* are real and their
     provenance is the safety property).
   - **Failure cases** need no real paywalled content: manifest entries simulate 403/404/
     oversize; the `no_text_layer` case uses an image-only PDF derived dev-time from one
     of the licensed documents (provenance recorded).
   - **Envelope/document mismatch accepted:** the acquire fixtures' envelope metadata
     (titles, abstracts) remains sanitized/fabricated from 007; fetch fixtures map those
     records' URLs to real documents. The join is by URL, and no test asserts
     envelope-title == document-title. Noted so nobody "fixes" it into re-recording 007.
   - **Size discipline:** ~10–15 documents, individual files preferably < 5 MB, total
     committed budget ≈ 25 MB, plus one deliberately long report (100+ pages) for the
     long-document memory/timeout verification. Binary fixtures are excluded from review
     diffs per the 007 retro.
   - `scripts/record_fulltext_fixtures.py` (dev-time, never imported by the package)
     fetches the curated source list and writes documents + manifest. Dev-time network
     use is explicitly not gated.
10. **Idempotency and re-runs.** Re-running the component skips `ingested` links
    (`already_ingested`, counted) and **retries** failed ones (statuses overwrite —
    deterministic against fixtures; live-world transience is why failed is retryable;
    v2 had no retry anywhere). Counting invariant, test-enforced:
    `eligible == ingested + already_ingested + fetch_failed + parse_failed + skipped_no_url`.
    Return shape mirrors acquire: counts by status and failure reason, no per-document
    lists.
11. **Multi-PDF Overton documents: primary `pdf_url` only in v3.0.** Every Overton fixture
    record is a grouped document; assembling `grouped_pdf_ids_in_result` into one corpus
    text (ordering, dedup, joint hashing) is real design work with no v3.0 reader —
    deferred, recorded. The retained field keeps it possible.
12. **Untrusted-text posture carries forward.** Fetched full text is third-party content
    at much larger volume than the envelope; v3.0's deterministic code never interprets it
    (parse/segment only — no execution, no LLM; the parsers extract text and layout, they
    do not follow instructions in content). The injection-screening enforcement point stays
    at the LLM/live seams, recorded in `docs/deferred.md` (007's posture, extended to
    full text). Security review confirms no interpretation path.
13. **Component wiring mirrors 004–007.** `"ingest_full_text"` in `COMPONENT_REGISTRY`
    requiring `evidence_scope_id`; eligible set = the scope's screened-in
    (`is_relevant = true`) links with `origin = "acquired"`. Runs after the cheap envelope
    passes (spec §4: "after screen/classify/appraise"); the registry gate is screen — the
    skeleton demonstrates the full order. "Ingestion is not a tool" holds: this is an
    orchestrator-scheduled plan component (procedure), not an agent-invocable verb.
    Fetcher injection: `run_harness` gains optional
    `document_fetcher: DocumentFetcher | None = None` defaulting to `FixtureFetcher()` —
    the `search_backends`/`provider` precedent, gated change 3.

### V2 integration review — full-text ingestion (subagent review, 2026-07-05)

Read-only review of `../discovery_policy_atlas` (`backend/app/services/analysis/`:
`acquire.py`, `parse.py`, `normalize.py`, `chunking.py`, `extractor_langchain.py`,
`storage.py`, `service.py`). Adjudication:

**Ported:** PyMuPDF-class fetch cascade *shape* (pdf_url → landing → DOI, meta-refresh
follow) → live-fetcher seam; dual success/failure manifest pattern → our per-link status +
run summary; de-hyphenation + whitespace normalization (necessary but not sufficient —
plan-level normalization detail).

**Fixed by construction in this slice (each a specific v2 defect):**
- Three stacked silent truncations capping the retrieval corpus at ~15 K tokens/document
  → decision 6 (no truncation).
- Serial parsing; dead concurrency config (`ACQUISITION_CONCURRENCY`, `DOWNLOAD_TIMEOUT`
  defined, never wired) → decision 8 (real, wired, test-covered fan-out).
- No parse-failure taxonomy (one `skipped_count` for oversized/timeout/corrupt/scanned/
  empty); fetch errors swallowed at debug; paywalls indistinguishable → decision 3.
- Thin DOI-landing text reported `ok` → thin-text guard (decision 7).
- Chunk provenance computed then discarded (`page_spans` never persisted; quote location
  by post-hoc substring search) → decision 7 (page + heading path in every chunk locator).
- No structure awareness (headers/footers repeat inline; tables flattened; reference
  lists chunked as content) → decision 5 (PyMuPDF4LLM structured extraction — the very
  engine v2 already had but called in plain-text mode).
- Scanned/image-only PDFs silently empty → explicit `no_text_layer` status; OCR recorded
  as a deferred seam.
- Uncancellable parse timeouts (`run_in_executor` threads leak) → process-based hard
  timeout (decision 6).
- Chunking gated behind an unrelated storage flag (RAG index silently unpopulated when
  interim storage was off) → segmentation is unconditionally part of ingestion here.
- `encoding="utf-8", errors="ignore"` silent character loss → plan-level: explicit
  encoding handling, no silent-ignore reads.
- Declared-but-never-imported `readability-lxml` → we ship trafilatura and actually call it.

**Deliberately not carried:** word-count×1.3 token estimation (no token-budgeted chunking
in this slice at all; tiktoken-class sizing belongs to the embed seam); the documented-but-
never-implemented "summary chunk" (doc/code drift — we ship no chunk type that code
doesn't emit); embedding-during-ingestion (decision 1).

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

`full_text_error` values (closed vocabulary, enforced in code + tests, not a CHECK — the
reason list may grow at the live seam without a migration): `paywall` · `not_found` ·
`too_large` · `timeout` · `corrupt` · `no_text_layer` · `thin_text` · `empty`.
Downgrade drops the columns. No data migration (existing rows take the default).

### Python

**`ingest_full_text.py`** — new module (public surface carries Google-style docstrings):

```python
@dataclass
class FetchResult:
    status: str                 # "ok" | "error"
    content_type: str | None    # "application/pdf" | "text/html" | "text/plain"
    body: bytes | None
    error: str | None           # reason vocabulary, decision 3

class DocumentFetcher(Protocol):
    mode: str  # "fixture" | "live"
    def fetch(self, url: str) -> FetchResult:
        """Fetch one URL. Never raises for per-document outcomes."""

class FixtureFetcher:
    """Replays committed real documents by URL from the manifest. Zero egress."""
```

Plus: candidate-URL resolution per backend (decision 4); a pure per-document worker
(cascade fetch → parse via PyMuPDF4LLM/trafilatura → segment → chunk list + metadata,
**no DB
access**) dispatched over a bounded process pool (decision 8); parent-side DB writes in
eligible-set order.

`ingest_full_text_sources(conn, *, project_id, run_id, context, fetcher, max_workers=...)
-> dict`: resolve eligible set → fan out workers → per result: create `source_snapshot`
(+ chunks) and set `full_text_snapshot_id`/`full_text_status`, or record the failure on
the link. Always completes with honest counts; `component.failed` reserved for
infrastructure errors (007 precedent).

**`plan.py`** — `"ingest_full_text": {"requires": ["evidence_scope_id"]}`.

**`harness.py`** — `_run_ingest_full_text` node (mirror `_run_acquire`); `document_fetcher`
parameter; conditional-edge wiring.

**`skeleton.py`** — extend the smoke chain with ingest_full_text after appraise; log
per-status/reason counts and the corpus text-basis distribution.

**`tests/helpers.py`** — `delete_project_data` handles the new FK (clear
`full_text_snapshot_id` links / delete in FK-safe order per task-003 precedent).

**Fixture data** — `src/policy_atlas/data/fulltext/` (real licensed documents, decision 9)
+ `fulltext_manifest.json` (`_meta` + URL → outcome map + per-document provenance/licence).
Coverage: multi-page report PDF (long, 100+ pages), academic paper PDFs (incl. multi-column),
HTML report page, paywall 403, dead link 404, oversize (simulated), image-only PDF
(`no_text_layer`), thin HTML page, cascade fallback (first URL fails → second succeeds),
and untouched non-screened-in records.

**`test_ingest_full_text.py`** — new file, covering:
- Migration roundtrip; table count still 16; both named CHECKs reject invalid rows
  (bad status; `ingested` without snapshot id; snapshot id with non-`ingested` status).
- URL resolution order per backend (OpenAlex four-step precedence; Overton two-step);
  no-URL record → `skipped_no_url`.
- Cascade: first candidate fails, second succeeds — attempts logged, outcome `ingested`.
- PDF parse (PyMuPDF4LLM): multi-page report → heading-bounded chunks under
  `pymupdf4llm_struct_v1` with page + heading-path locators, tables intact as chunks,
  sequenced; multi-column academic paper in correct reading order (spot-checked
  assertion, e.g. a known sentence not interleaved).
- **No-truncation proof:** the long-report fixture ingests whole — chunk text jointly
  contains content from the final section/page; no cap code path exists to test.
- Failure reasons, each separately: paywall (403), dead link (404), oversize →
  `fetch_failed` + correct reason; image-only PDF → `parse_failed`/`no_text_layer`;
  thin HTML → `parse_failed`/`thin_text`; parse timeout (in-test slow parser double) →
  `parse_failed`/`timeout` with the worker actually terminated. In every case the
  envelope snapshot and downstream result rows are untouched; source never dropped.
- HTML parse (trafilatura): main content extracted, nav/boilerplate absent (assert a
  known boilerplate string from the fixture page is not in any chunk).
- Success semantics: new snapshot `text_basis="full_text"`, own content hash over joined
  chunks, `source_locator` = fetched URL, parse profile + `fetched_from` in metadata;
  envelope snapshot byte-identical before/after (immutability).
- Fan-out determinism: workers=1 vs workers=4 → identical DB state (snapshots, hashes,
  chunk sequences, statuses).
- Eligibility: only the scope's screened-in acquired links; `not_relevant`,
  `screen_failed`, uploads, and other scopes untouched.
- Idempotency: re-run → `already_ingested`, no new snapshots; failed links retried;
  counting invariant holds per run, both runs.
- Events: `component.started`/`component.completed` with summary counts by status and
  reason; **no** per-document event types emitted (asserted).
- Harness round-trip: `Plan(component="ingest_full_text")` → statuses + snapshots in DB.
- Zero-egress guard: extend 007's import test to `ingest_full_text.py`; recorder script
  outside the package import graph (the parsers are model-free local code — no network
  path exists beyond the import test).
- Licence guard: every committed document's manifest entry carries an allowlisted licence
  (own-org · CC BY family) + source URL + retrieval date; fetch-keying URLs all
  `example.org`; `_meta` present.
- `delete_project_data` clean with full-text snapshots present.
- Downstream unchanged: classify/appraise outputs identical before/after ingest (they read
  the envelope).

Updates to existing tests: `test_compile.py` — `"ingest_full_text"` valid with a scope id,
rejected without.

### Out of scope

- **Live `DocumentFetcher`** — runtime egress, its own gated slice; carries the live-seam
  requirements (timeouts, redirects, politeness/robots + per-host rate limiting,
  content-type sniffing, landing-page scrape + PDF-link discovery with v2's meta-refresh
  follow, DOI-URL fallback, bounded retry/backoff).
- **OCR for scanned documents** — `no_text_layer` is honestly representable; an OCR stage
  (heavy models or an egress service) is its own decision. Deferred, recorded.
- **Vectorisation / embeddings / vector store** — deferred to the first vector reader
  (decision 1); token-budgeted chunk sizing goes with it.
- **Multi-PDF Overton assembly** (decision 11).
- **Re-screen / re-classify / re-appraise on full text** — existing deferred seams
  (`Unknown` resolution, appraisal second pass) — unchanged.
- **Full-text for uploads** — their text arrives with them; nothing to fetch.
- **Cross-project full-text snapshot reuse** — the shared content-addressed substrate stays
  deferred (007); two projects ingesting the same document each get their own snapshot.
- **Injection screening of fetched text** — posture recorded (decision 12); enforcement at
  the LLM/live seams.
- `characterise`+ and everything downstream of appraise — subsequent slices.

## Constraints & approval gates

**Three gated changes (approval needed at this gate):**

1. **Schema** — three columns + two named CHECKs + one FK on `project_source_snapshot`;
   one Alembic migration.
2. **Dependencies:** `pymupdf4llm` (brings `pymupdf` — the compiled MuPDF engine,
   AGPL-3.0, licence-compatible with the project since rev 3; no ML stack, no model
   weights) and `trafilatura` (light: lxml-based, Apache-2.0). Both parse offline by
   construction. The ML-layout upgrade (`docling`, torch + ~1 GB models) lives at the
   recorded seams (decision 5), not in this gate.
3. **Public interface** — `run_harness` optional `document_fetcher` parameter (+ the
   `"ingest_full_text"` registry entry, per 007 precedent).

Plus one spec clarification (components §4 vectorisation deferral, decision 1) and one
**fixture-policy amendment** (decision 9: real openly-licensed documents supersede
generate-don't-record for *document* fixtures; the 007 sanitized policy stands for API
*records*) — both approved with this contract.

**Explicitly not crossed:** no runtime egress (fixture replay; the recorder script is
dev-time only; the parsers are model-free local code), no auth, no CI change, no other
schema or interface change.

## Public / private boundary

- Committed fixture documents are **real publications committed under their own open
  licences** (own-org Nesta · CC BY family), each with provenance (source URL, publisher,
  licence, retrieval date) in the manifest — licence-guard test-enforced. No paywalled or
  all-rights-reserved content is ever committed; failure cases are simulated.
- No credentials involved anywhere in this slice (fixtures need no API).
- Column names, protocol/function names, policy/profile version strings — durable/committable.

## Model route

`n/a` — deterministic fetch-replay + parse + segment. No models of any kind: no LLM call,
no inference provider, no runtime network I/O.

## Disciplines binding this slice

- **Snapshots immutable** — full text is a *new* snapshot attached at the link; the
  envelope snapshot is never touched (test-enforced byte-identity).
- **Never truncate** — a stored `full_text` snapshot is the whole parsed document; caps
  fail loudly (`too_large`, `timeout`) instead of cutting silently (decision 6).
- **Flag, don't drop** — fetch/parse failure keeps the source on the text in hand with a
  queryable status + closed reason; thin text is a failure, never `ok`.
- **Honest absence** — `not_attempted` ≠ `fetch_failed` ≠ `no_text_layer`: coverage claims
  distinguish "never tried", "tried and unavailable", and "exists but needs OCR".
- **Skip is visible, never silent** — every eligible link lands in exactly one counted
  bucket; invariant test-enforced.
- **Segmentation is trust-relevant** — structure-aware chunks with page + heading-path
  locators; named versioned policies + parse profiles on every snapshot; one parse, one
  segmentation.
- **No per-document governance events** for fetch (spec) — run-record summary + telemetry;
  the `search.executed` discipline stays acquire's.
- **Deterministic** — same fixtures + pinned parser versions → same snapshots, hashes,
  chunks, statuses, counts; independent of worker count (test-enforced).

## Stop conditions

- Any gated change (schema · dependencies · public interface) not yet approved, or any
  schema/dep change beyond the gated items.
- Any runtime code path would perform network I/O.
- The snapshot-identity decision (2) proves wrong mid-build — halt, don't improvise a
  fourth shape.
- The chosen parser proves unable to meet the structure requirements on the fixtures
  (headings/tables/reading order materially wrong) — halt and re-open parser selection
  with evidence (the docling seam is the named alternative), rather than quietly
  flattening to plain text.
- Scope would grow past the contract (live fetch, OCR, embeddings, multi-PDF, re-screen).
- `make verify` red with unclear root cause.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green.
- All checks deterministic (fixture replay, pinned parser versions; no LLM, no egress).
  Every check is a test.
- One manual dev-time check: the recorder script was run once and produced the committed
  documents + manifest (dates, licences, coverage recorded in `_meta`); confirmed in
  verification.md.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts.
- Named results from `test_ingest_full_text.py`, including the immutability test, the
  **no-truncation long-report test**, the fan-out determinism test, the zero-egress
  guard, and the failure-reason matrix.
- Long-document evidence: wall-clock and peak memory for the 100+-page fixture on CPU
  with the pinned backend (the #2077 risk, measured, not assumed).
- Migration roundtrip clean; table count still 16.
- End-to-end command: harness with `component="ingest_full_text"` over an
  acquired+screened corpus — statuses, new snapshots and chunk counts visible in DB;
  text-basis distribution logged by the skeleton.
- Fixture provenance: per-document licence/source/date table from the manifest;
  licence-guard pass.
- Public-safety confirmation (openly-licensed documents only; no credentials).
- Deferred seams recorded in `docs/deferred.md` (live fetcher with its requirement list ·
  **ML-layout parse escalation** (docling behind a `docling_v1` parse profile, entered
  via parse-quality evals; torch + ~1 GB models, dev-time-pinned weights + offline mode
  when it lands) · **time-budget-aware parser selection** (user idea, 2026-07-05: the
  user's stated time horizon steers parser choice per run — tight → fast parser, long →
  ML layout; a plan/Config-carried setting behind its own interface gate, feeding the
  parse-profile mechanism) ·
  **chunk-volume bias at the retrieve seam** (user flag, 2026-07-05: long documents
  contribute proportionally many more chunks, so naive top-k over chunks over-represents
  them — the retrieval slice must carry document-diversity controls: per-document caps /
  MMR / document-grain grouping; the ingestion-side "fix", length normalisation by
  truncation, is rejected — decision 6) · OCR for `no_text_layer` documents ·
  vectorisation-at-first-reader with the
  eager-uniform discipline · multi-PDF assembly · injection screening extended to full
  text · cross-project full-text reuse).
- Diff summary (binary fixture files excluded from review diffs per the 007 retro).

## Risk tier & review focus

**Tier 3** — a schema change, the heaviest dependency addition since scaffold, a
public-interface addition, and the slice builds the seam through which bulk untrusted
third-party documents will eventually enter the product.

Review focus:
- **Correctness:** cascade order; failure-reason mapping; thin-text guard; status/FK
  consistency; counting invariant; idempotent re-run; envelope immutability; **absence of
  any truncation path**; fan-out determinism and real timeout cancellation.
- **Provenance:** page + heading-path locators on every chunk; per-snapshot parse profile
  + segmentation policy; `source_locator` = fetched URL; honest `text_basis`;
  `not_attempted` vs `fetch_failed` vs `no_text_layer`.
- **Security:** zero runtime egress; parsers operate on fixture bytes only; no
  execution/interpretation of fetched content; recorder script outside the import graph;
  licence guard on committed documents.
- **Schema:** migration roundtrip; named constraints; downstream FKs untouched.
- **Scope:** no live fetch, no OCR, no embeddings, no multi-PDF, no re-screening.
