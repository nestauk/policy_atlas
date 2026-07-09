# Plan: 016-live-fetch

> **Status:** rev 1 draft — plan-stage adversarial review next, then
> the plan 🛑. Drafted against contract **rev 2.5** (approved 2.2,
> amended 2.3–2.5 at/after the gate). ADR at confirmation (step 4):
> **ADR 0013 — the mandatory EB spine** (acquire(search) → screen →
> classify → appraise → ingest(fetch) → synthesise; all else
> orchestrator-discretionary per depth gradation) — the chain-shape
> rule the orchestrator slice compiles against.
> Contract: [contract.md](contract.md).
>
> "Plan-pinned" constants below are THIS plan's code constants,
> reviewed at the plan 🛑 (see the contract's terminology note).

Executor routing per harness.md § Agent-side model routing: default =
delegate; every `lead` mark carries a justification. The 015
Codex-exhaustion fallback stands: if Codex runs out mid-build,
re-route down the ladder (judgment → deep-reasoner, mechanical →
fast-worker, brief-unwritable → lead), record substitutions in
`verification.md`, never stall.

## Plan-pinned constants

**Fetch transport (contract decisions 1/3/4/5):**
- `fetch_live.py`, class `LiveDocumentFetcher` (`mode="live"`), one
  pooled sync `httpx.Client`, `follow_redirects=False` — redirects
  are followed **manually** so every hop is validated;
  `REDIRECT_HOP_CAP = 5`.
- `FETCH_TIMEOUT_S = 30.0` (`httpx.Timeout(30.0)`, connect+read;
  recorder/015 precedent). `User-Agent: policy-atlas/0.1 (+research;
  contact via repo)` on every request; **no `Authorization`, no
  cookies, ever** (`cookies` disabled on the client; test-asserted).
- `MAX_DOCUMENT_BYTES = 25_000_000` — enforced against
  `Content-Length` AND the streamed body (existing `too_large`
  reason; matches the 008 fixture `oversize` semantics).
- Retry cap 1 per request; retryable = timeout · 429 · 500 · 502 ·
  503 · 504 (the 015 decision-7 set); `RETRY_BACKOFF_S = 2.0`.
- Concurrency + politeness: `FETCH_MAX_CONCURRENCY = 10` (global
  thread pool) · `PER_HOST_MAX_CONCURRENCY = 2` ·
  `PER_HOST_MIN_INTERVAL_S = 1.0` (monotonic clock, injectable for
  tests) · `MAX_INFLIGHT_BYTES = 100_000_000` — a fetch slot is
  granted only while accounted in-flight body bytes are under the
  cap (backpressure, never failure).
- In-run URL cache: `dict[url, FetchResult]` on the fetcher (repeat
  URLs across docs are one fetch); cross-run caching stays deferred.

**SSRF guard set (decision 3 + rev 2.4 blockers):**
- Scheme allowlist `{http, https}`; URLs with userinfo refused;
  fragments stripped.
- Resolution: `socket.getaddrinfo` → EVERY answer (A + AAAA)
  classified with `ipaddress`; IPv4-mapped IPv6 unwrapped before
  classification; refused classes: private · loopback · link-local ·
  multicast · reserved · unspecified (this covers the cloud-metadata
  169.254.0.0/16 range via link-local).
- **Pinned-IP connect** (no check-then-reresolve window): the request
  is issued to the validated IP with the original `Host` header and
  TLS SNI set to the original hostname (httpx request extensions /
  httpcore `sni_hostname`; if httpx cannot express it cleanly, the
  fetch path drops to httpcore directly — httpx's own core, no new
  dependency). Each manual redirect hop repeats the full
  parse→resolve→classify→pin cycle.
- Refusal = `FetchResult(error="blocked")`; `blocked` and
  `blocked_by_host` join `FAILURE_REASONS` (code-enforced, zero
  schema).
- Log hygiene: every log/event line derived from a URL carries
  scheme+host+path only (`_redact_url` helper, test-pinned); the
  verbatim URL persists only in the DB attempts trail +
  `fetched_from`.

**Access-failure ladder (decision 8):**
- Fetcher-side (has status + body, no envelope): 401 → `paywall`;
  402 → `paywall`; 403 → `paywall` if body carries a
  `PAYWALL_MARKERS` hit else `blocked_by_host`; 404/410 →
  `not_found`; 200 + HTML + markers on a document-expected URL →
  `paywall`; empty body → `empty`.
- `PAYWALL_MARKERS` (code constant, case-insensitive substrings over
  the first 5,000 chars of HTML): "purchase this article" ·
  "institutional login" · "access through your institution" ·
  "sign in to read" · "subscribe to read" · "rent this article" ·
  "get access" · "log in via your institution". Starter list —
  growable in code without ceremony.
- Ingest-side OA cross-check (has the envelope): OpenAlex
  `open_access.is_oa == false` upgrades an uncorroborated
  `blocked_by_host` to `paywall`; `is_oa == true` + a
  `paywall`/`blocked_by_host` outcome logs
  `fulltext.oa_inconsistency` (eval signal). Overton envelopes carry
  no OA signal → no-op.

**Recall aids (decision 7):**
- DOI fallback in `candidate_urls`: when envelope `doi` matches
  `^10\.\d{4,9}/\S{1,200}$` (control chars rejected), append
  `https://doi.org/<percent-encoded doi>` as the LAST cascade entry
  if not already present.
- Landing-page discovery: when a fetch returns HTML, extract
  `<meta name="citation_pdf_url">` (lxml, already in tree; fallback
  regex for malformed HTML is NOT built — no meta tag → no
  discovery); at most ONE discovered URL per landing page, appended
  to that doc's cascade (full guard set applies), recorded in the
  attempts trail as `discovered_from=<host+path>`.

**Ingest pipeline shape (decision 5 — plan-designed):** keep the
as-built cascade-round structure; inside each round the fetch step
becomes a **bounded-parallel batch feeding the parse pool as bodies
arrive** (fetch thread pool → parse worker processes already as-built,
`DEFAULT_MAX_WORKERS = 4`, `PARSE_TIMEOUT_SECONDS = 120` unchanged),
with `MAX_INFLIGHT_BYTES` accounting so a round never holds unbounded
bodies. DB writes stay in the parent transaction, in eligible-set
order (as-built determinism preserved; the fixture path is
functionally identical — same results in the same order). Per-link
isolation: the fetcher contract already never raises for per-document
outcomes; a belt-and-braces except at the cascade converts any
escaped raise into a reason-coded `fetch_failed` and logs it.

**Substrate widening (decision 9, rev 2.5 — mechanics):** the
"ingested on the text in hand" substrate for a failed-fetch doc IS
its envelope snapshot — already snapshotted, chunked and embedded at
acquire; no duplicate snapshot rows. Concretely:
- `synthesise.py` chunk loader (the `full_text_status == "ingested" |
  text_basis == "full_text"` WHERE clause, ~`synthesise.py:820`)
  widens to: full-text chunks where ingested, **else the doc's
  envelope chunks** — every loaded chunk carries `text_basis`
  (`full_text` from the winning snapshot, else `abstract_only`).
- `ChunkInfo` gains `text_basis`; `search_chunks` records expose it;
  chunk-claim citation annotation payloads carry it (the label the
  contract requires on citations); the grounding-judge envelope's
  chunk records include it as data.
- Corpus profile: chunk-claim availability
  (`appraised_ingested_docs > 0`) generalises to "appraised docs with
  chunk substrate > 0" (which, post-widening, is every appraised
  screened-in doc); `no_groundable_substrate` then fires only when no
  references resolve AND the screened-in corpus is empty — the
  genuine miscomposition/empty case.
- Stage-2 screen is UNTOUCHED: it still requires real full text and
  counts abstract-only docs `skipped_no_fulltext` (honest).
- M4 unchanged: chunk claims cite only appraised docs.

**Prompt delta (lead-authored, one rule):** `synthesise_section_v1`
gains one instruction line + record field documenting
`text_basis` on search_chunks records ("abstract-basis chunks are the
document's own abstract; cite them as such — claims resting on them
are abstract-grounded"). Wire-compatible text edit; PROMPT_VERSION
bumps to `synthesise_section_v2` as provenance (015 rev-3.6c framing:
provenance, not a gate).

**Fixture-corpus relocation (decision 12):**
- Moves: `src/policy_atlas/data/fulltext/*` +
  `src/policy_atlas/data/fulltext_manifest.json` →
  `tests/data/fulltext/` (+ manifest beside it). The small
  search-fixture JSONs stay in-package (unchanged — they are not the
  24 MB corpus).
- `FixtureFetcher` gains an explicit `root: Path` (manifest + files
  resolved from it); the packaged `importlib.resources` load dies.
  Default resolution: `POLICY_ATLAS_FIXTURE_CORPUS` env var, else a
  repo-relative `tests/data/fulltext` discovered from the package's
  parent (works in the dev/test checkout); **missing corpus at first
  fetch = loud error naming the path** — never a silent empty.
  Suite wiring via one conftest fixture/env set.
- The corpus-budget guard test (008's ≤30 MB licence/size guard) and
  `scripts/record_fulltext_fixtures.py` output path move with it.
- New test: a `live=True` skeleton run constructs
  `LiveDocumentFetcher` — never `FixtureFetcher` (the
  no-silent-replay invariant).
- Wheel check: `make build` artifact no longer contains
  `data/fulltext` (test or build-check).

**Mandatory spine (decision 9):** every skeleton profile's chain
includes the ingest leg (rapid gains it; deep already has it);
fetcher selection rides the one live flag (`skeleton.py:634`
pattern). Spec flow-back: components §4 (as-enacted note on the
failure path) · §9 + the OPENING chain table (mandatory spine) ·
capability.md · spec `log.md`.

**pip-audit CI (rev 2.2):** `make audit` target — `uv export
--format requirements-txt --no-emit-project | pip-audit -r
/dev/stdin --strict`, ignores (if ever needed) as explicit
`--ignore-vuln` args in the Makefile, each with an adjacent
justification comment; new independent job in
`.github/workflows/verify.yml`. pip-audit runs as a `uv tool run`
(dev-time tool, not a project dependency).

## Tasks

**Phase 0 — build-open baseline (full `make verify`)** — operator/lead.

**Phase 1 — relocation + CI (full `make verify` gate — fixture
loading touches every ingest-marked test)**
1. Fixture-corpus relocation per the constants block: file moves,
   `FixtureFetcher` root injection + loud-missing error, conftest/env
   wiring, budget-guard + recorder-script path updates, wheel check,
   no-silent-replay test. — **fast-worker** *(exact enumerated spec;
   mechanical moves + one loader change)*
2. `make audit` + the verify.yml pip-audit job. — **lead inline**
   *(gated CI surface, ~20 lines; delegation costs more than it
   saves — the one-command-mechanical rung)*

**Phase 2 — the live fetcher (verify-fast gate — genuinely new
module, no schema/reader contact)**
3. `fetch_live.py`: guard set (userinfo/scheme/IP-classify-all-
   answers/pinned connect), manual redirect loop, timeout, streaming
   size cap + in-flight accounting, per-host politeness + global
   concurrency, retry set, magic-byte/HTML/charset classification
   (008 parse contract preserved: PDF-as-octet-stream never reaches
   the plain-text parser), the fetcher-side access ladder +
   `PAYWALL_MARKERS`, in-run cache, `_redact_url` log hygiene,
   injectable clock + transport seams for tests. — **codex** *(the
   hardening core; judgment-bearing; machine-verifiable via
   transport-stubbed tests)*
4. Recall aids: `candidate_urls` DOI fallback (validation +
   encoding) + landing-page `citation_pdf_url` extraction helper.
   — **fast-worker** *(small pure functions from an exact spec;
   integration into the cascade is task 5's)*

**Phase 3 — ingest pipeline + wiring (full `make verify` gate —
ingest-adjacent)**
5. `ingest_full_text.py`: bounded-parallel fetch feeding the parse
   pool within cascade rounds + `MAX_INFLIGHT_BYTES` backpressure +
   discovery-hook wiring (≤1 discovered URL joins the doc's cascade)
   + ingest-side OA cross-check refinement + belt-and-braces
   isolation + summary counts growth (per-reason + bytes +
   wall-clock). Write order and fixture-path behaviour unchanged
   (determinism test-pinned). — **codex** *(concurrency surgery in
   the pipeline's core loop; multi-constraint coherence)*
6. Harness/skeleton: `LiveDocumentFetcher` behind the one live flag;
   **every profile gains the ingest leg** (mandatory spine — rapid
   profile chain grows; deep unchanged); live-mode construction
   asserts. — **codex** *(profile-semantics change; the 015 task-9
   lesson: skeleton briefs are not self-sufficient for fast-worker)*

**Phase 4 — substrate widening (full `make verify` gate — synthesise
reader contact)**
7a. `synthesise_section_v2` prompt TEXT delta (the one text_basis
   rule + record-field doc). — **lead** *(prompt-bearing, AGENTS.md —
   never delegated)*
7b. Substrate widening implementation per the constants block:
   loader WHERE widening, `ChunkInfo.text_basis`, search_chunks
   record field, citation annotation label, judge-envelope chunk
   field, corpus-profile gating generalisation +
   `no_groundable_substrate` narrowing. Zero prompt-text authorship.
   — **codex** *(reader-contact surgery against a fully-authored
   spec)*
8. Stage-2 windowing rider: `_load_stage2_docs` prefix hydration
   (fetch chunks in sequence order, stop at
   `STAGE2_WINDOW_CHAR_BUDGET` + split-boundary slack; drop full
   chunk lists once the ≤60k payload is built). Byte-identical
   first-window payload, test-pinned; if non-trivial → back to
   deferred, escalate. — **fast-worker** *(precise, behaviour-
   preserving, provably-equivalent spec)*

**Phase 5 — tests (full `make verify` gate)**
9. Bulk suites from the contract's Acceptance enumeration: the
   fetcher matrix (every guard/cap/ladder/hygiene branch, injected
   clock + stub transport), DOI/discovery helpers, relocation guards
   (loud-missing, wheel check, no-silent-replay), zero-egress guard
   extension (ingest module never imports `fetch_live`).
   — **fast-worker**
10. Judgment/integration suites: cascade streaming memory accounting;
    per-link isolation end-to-end (a raising fetcher → reason-coded
    row, component green); mandatory-spine profile tests (every
    profile's chain includes ingest); substrate-widening end-to-end
    over scripted backends (abstract-labelled citation reaches the
    annotation payload; all-fetch-failed corpus synthesises visibly
    labelled; empty corpus still refuses `no_groundable_substrate`);
    stage-2 prefix-hydration proof (query-count/loaded-chunk
    assertions). — **codex**

**Phase 6 — flow-back + ADR + records + live check (step-6 exit:
full `make verify`)**
11. Spec flow-back (components §4 as-enacted note · §9 + opening
    chain table mandatory spine · capability.md · `log.md`) +
    **ADR 0013** + `deferred.md` updates (discharged: live
    DocumentFetcher · pip-audit pre-registration · fixture-corpus
    relocation · stage-2 windowing; kept + new seams per rubric 15)
    + knowledge updates. — **lead** *(spec flow-back + ADR; per-slice
    precedent)*
12. `verification.md` + the decision-13 live check (script below).
    — **lead** *(live-run adjudication; per-slice precedent)*

## Live-check script (task 12 — decision 13 pin)

Dev DB `alembic upgrade head` first (012 lesson; no new migration —
confirm head unchanged). Then:
(a) live fetch/ingest over a real screened-in scope (~30–60 docs from
a live 015 acquire+screen run): full outcome distribution recorded
(observed counts; demo numbers are a prior, not a target); per-host
spacing visible in logs; `MAX_INFLIGHT_BYTES` accounting logged and
respected; per-link failures reason-coded with the component green;
wall-clock + bytes recorded;
(b) the mandatory-spine chain smoke: acquire → screen → classify →
appraise → ingest → synthesise over the live corpus — synthesise
mints chunk-cited claims over live-fetched full text (discharges the
015 rev-3.14 minus-`ingest` deviation); at least one failed-fetch doc
observed as a labelled abstract-basis substrate entry (rev 2.5);
(c) SSRF guards at test level only (no live probe);
(d) log-hygiene grep over the run's logs: no query strings from
fetched URLs (structural test + live grep);
(e) `make audit` run recorded (any ignores justified);
(f) wall-clock per leg (feeds the depth/time-budget seam and 017).
Cost: mini-class LLM legs over one modest corpus — low single-digit
dollars. No deep-chain e2e (017 owns it).

## Review-stack sizing (for conversation C)

Per [[review-stack-economy]]: /code-review medium, per-angle diff
scoping (exclude the relocated corpus files — content unchanged, path
moves only), ONE security lane (headline: the SSRF guard set +
pinned-IP connect + log hygiene — the slice IS an SSRF surface),
contract-verifier Opus, Codex adversarial, live-trace CONTENT review
lane (the smoke's labelled abstract-basis citations + judge verdicts
over them). ≤ 250K reasoning / ≤ 500K fast-worker.

## Gate consolidation summary

Full `make verify`: Phase 0 baseline · Phase 1 (fixture-loading
surface under every ingest test) · Phase 3 (ingest-adjacent core
loop) · Phase 4 (synthesise reader contact) · Phase 5 · Phase 6 exit.
**Phase 2 alone gates on `make verify-fast`** (a genuinely new module
with no schema or reader contact — the only consolidation this slice
supports; everything else touches readers or the pipeline core).
