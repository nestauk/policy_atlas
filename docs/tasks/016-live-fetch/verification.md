# Verification: 016-live-fetch

Evidence for the live full-text fetch/ingest slice (contract rev 2.2 approved
2026-07-09, amended 2.3–2.6; plan rev 2). Build executed 2026-07-09/10 per the
plan's six phases; every phase committed on its gate (`ca7db04` → `7d8958b` →
`a861a70` → `ac75a33` → `fa6e2c6` → `ad93638` → this phase). Public-safe.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (okf-validate · test · typecheck · lint · build) | pass | step-6 exit run; 893 tests green, deterministic, zero-egress |
| `make test` | pass | full suite incl. the ingest integration file |
| `make typecheck` | pass | mypy, 95 source files |
| `make lint` | pass | ruff |
| `make build` | pass | wheel verified free of `data/fulltext` (test-pinned) |
| `make audit` | pass | **No known vulnerabilities found**; one expected skip (`policy-atlas`, editable first-party); zero `--ignore-vuln` entries |

Gate history: full `make verify` green at the build-open baseline (807 tests),
Phase 1 (818), Phase 3 (886 — after one red run whose 3 failures were
root-caused to the stage-2 rider's connection-level `yield_per`, fixed, gate
re-run), Phase 4 (890), Phase 5 (893 + a post-suite type-narrowing fix re-run
green), step-6 exit (893). Phase 2 gated on `make verify-fast` per the plan's
gate map (836).

## Checks beyond the build

- **Fetcher matrix** (`tests/test_fetch_live.py`, 38 tests, zero-egress stub
  transport + injected resolver/clock): SSRF refusals (scheme · userinfo ·
  private/loopback/link-local/metadata across ALL A/AAAA answers ·
  IPv4-mapped-IPv6 unwrap · 169.254.169.254 · mixed answer sets · per-hop
  redirect · hop cap), size caps (Content-Length AND streamed), magic-byte
  classification branches (PDF-as-octet-stream never reaches the plain-text
  parser), the decision-8 ladder (401/402/403±markers/404/200+markers/empty),
  retry-once semantics, politeness spacing (injected clock), reject-all
  cookie policy + no-Authorization, `_redact_url` + log-capture hygiene,
  error-cache/in-flight dedup, byte accounting until `release_body`,
  NetworkBackend classification unit tests (monkeypatched getaddrinfo).
- **Recall aids** (`tests/test_recall_aids.py`, 29): DOI validation/encoding/
  dedup shapes; discovery meta-vs-anchor priority, same-host preference,
  scheme filtering.
- **Pipeline** (`tests/test_ingest_full_text.py` additions): reason-priority
  helper, escaped-raise isolation (raising fetcher → reason-coded row,
  component green), discovery-extends-cascade, release_body on parse and
  pre-parse-reject paths, OA cross-check both directions, summary keys,
  ingest log hygiene (tokened URL's query string absent from all log lines,
  verbatim URL retained in `fetched_from`), parallel-vs-serial determinism
  (fetch_workers 4 ≡ 1 per-URL outcomes), no-silent-replay
  (`select_document_fetcher(True)` is `LiveDocumentFetcher`, never
  `FixtureFetcher`), relocation guards (loud-missing at fetch not construct;
  corpus absent from the package tree), licence/budget guard at the new home.
- **Substrate widening** (`tests/test_synthesise*`, `test_synthesis_tools`):
  `text_basis` on ChunkInfo/ChunkSearchResult/search_chunks records/citation
  annotations/judge-envelope chunk records; all-fetch-failed corpus
  synthesises visibly abstract-labelled; empty corpus + no refs still refuses
  `no_groundable_substrate`.
- **Stage-2 rider** (`tests/test_screen.py`): byte-identical first-window
  payload (large/oversize-split/small cases) + the rev-2.4 prefix-hydration
  proof (loaded chunks < DB chunks; loaded chars ≤ budget + crossing chunk).
- **Zero-egress guards**: import guard sanctions `search_live.py` +
  `fetch_live.py` only and pins `ingest_full_text.py` never imports
  `fetch_live`; the socket-deny worker guard unchanged.

## End-to-end command

Live-check driver (scratchpad, not committed; keys via `load_dotenv(<repo>/.env)`;
dev DB confirmed at alembic head `c9e4b7f2d1a8` — no new migration this slice):

```
LOG_FORMAT=json uv run python <scratchpad>/live_check_016.py > live_check_016.log 2>&1
```

One project (`3679fc3f-0187-43c1-87f8-f3424fb55c30`, scope
`26cfa735-57d3-4268-8ecb-f88fb918e7de`, persisted in the dev DB) running the
mandatory spine acquire → screen → classify → appraise → ingest(live fetch) →
synthesise over the intent "What policies are effective at accelerating
household heat pump adoption?". Estimated LLM spend: low single-digit dollars
(mini-class legs; usage in Langfuse dev traces).

## Live-check evidence (decision-13 pin, all steps)

- **(a) live fetch/ingest over a real screened-in scope** (32 docs — the pinned
  ~30–60 window): **21 ingested · 7 fetch_failed · 4 parse_failed**; by_reason
  `blocked_by_host: 5 · empty: 4 · timeout: 2` (observed counts, never pinned
  values); 48 live requests across 22 hosts; **29,680,294 bytes fetched**;
  ingest wall-clock 134.8 s. Per-link failures reason-coded with the
  **component green** throughout — no component failure from any document.
  The decision-8 honesty ladder visible live: 5 refused-client outcomes
  recorded as `blocked_by_host`, none miscounted as paywall.
- **(a) politeness**: per-host request spacing from the run's log timestamps —
  21 of 22 hosts show min same-host gap ≥ 1.0 s (largest fan-outs: nesta.org.uk
  n=7, doi.org n=5, assets.publishing.service.gov.uk n=4); one host shows a
  0.84 s log-timestamp gap, which is log-emission jitter over the
  lock-serialised interval gate (starts are spaced on the fetcher's internal
  monotonic clock; the property itself is test-pinned with an injected clock).
- **(a) bounded memory**: peak in-flight accounted bytes **74,511,672 ≤ the
  100,000,000 cap** — backpressure never breached the budget.
- **(b) mandatory-spine chain smoke**: the full spine ran green over the live
  corpus; synthesise **minted the artefact** (`14d27a25-f56a-4e17-b624-80955dc653c5`):
  8 sections, 47 claims (32 chunk · 8 gap · 7 reasoning), **39/39 chunk
  citations verified over live-fetched full text**, grounding judge active
  (tier lanes 31/1/7), honest flags raised (`uncited_sections`,
  `repair_path_taken`, one chunk claim rejected). **Discharges the 015
  rev-3.14 minus-`ingest` smoke deviation.**
- **(c) SSRF guards**: test-level only per the pin (no live probe) — the
  fetcher matrix above; zero `blocked` outcomes occurred live (no provider URL
  resolved to a refused class this run).
- **(d) labelled abstract-basis substrate observed**: 11 failed-fetch docs in
  the smoke's corpus; the synthesise run's retrieval substrate carried
  **727 `full_text` + 11 `abstract_only` chunks** — the failed-fetch documents
  present as labelled substrate exactly as decision 9/rev 2.5 requires. The
  labelled-**citation** path (a claim citing an abstract-basis chunk, label on
  the annotation payload) is evidenced by the scripted-backend end-to-end test
  (the rev-2 finding-12 approved fallback; this live run's claims happened to
  cite full-text chunks).
- **(e) `make audit`**: green, zero advisories, zero ignores (table above).
- **(f) wall-clock per leg** (feeds the depth/time-budget seam and 017):
  acquire 24.0 s · screen 35.9 s · classify 45.1 s · appraise 0.2 s ·
  ingest 134.8 s · synthesise 589.9 s.
- **Log hygiene over the live run** (decision 13d): 125 fetch/fulltext log
  lines, **zero carrying a query string** (structural tests + live grep).
- No deep-chain e2e (per the pin; 017 owns the dress rehearsal).

## Diff summary

Live full-text ingestion behind the unchanged 008 seam. New module
`fetch_live.py` (`LiveDocumentFetcher`, sync httpx, one pooled client): the
full plan-pinned guard set — scheme/userinfo/fragment hygiene, every-answer DNS
classification with pinned-IP connect at a custom httpcore `NetworkBackend`
(hostname-keyed pooling and SNI preserved; the plan's primary design, no
fallback needed), manual per-hop-validated redirects (cap 5), 30 s timeouts,
25 MB streamed size cap, reservation-based 100 MB in-flight byte accounting
with lease-counted `release_body`, per-host politeness (2 × 1.0 s) + global
concurrency 10, retry-once on the 015 set, reject-all cookies,
`trust_env=False`, magic-byte classification, the decision-8 access ladder,
error-cache + in-flight dedup, `_redact_url` on every log line.

`ingest_full_text.py`: DOI-URL fallback + landing-page discovery
(`citation_pdf_url` meta, bounded PDF-anchor scan; ≤1 per landing page,
cascade-extending); bounded-parallel fetch feeding the as-built parse fan-out
(fixture replay stays serial + byte-deterministic); per-link isolation belt
(`fetch_error`); FAILURE_REASONS + `blocked`/`blocked_by_host`/`fetch_error`
(code-enforced, zero schema); failure-reason priority across the cascade;
ingest-side OA cross-check; `_parse_html` passes bytes to trafilatura
(decision-6 charset fix); URL-redacted ingest logs; summary gains
attempted/bytes_fetched/wall_clock_s. Skeleton: live flag →
`LiveDocumentFetcher` with construction assert (no silent fixture replay).
Substrate widening (decision 9/rev 2.5): both synthesise loaders widen to
labelled envelope chunks; `text_basis` carried through retrieval records,
citations and the judge envelope; `synthesise_section_v1 → v2` (one
lead-authored text_basis rule); `no_groundable_substrate` narrowed to the
genuinely empty case. Stage-2 prefix-hydration rider (decision 11). Fixture
corpus relocated to `tests/data/` (decision 12), wheel slimmed. Spec
flow-back: components opening chain + §4 as-enacted + §9, capability.md,
`log.md`; ADR 0013 (written at design, Accepted); deferred.md discharges +
kept/new seams. `make audit` + independent CI job (rev 2.2).

**Flagged deviations (visible, not silent):**

1. **`make audit` command shape** — the plan pinned `uv export | pip-audit -r
   /dev/stdin --strict`; pip-audit's `-r` mode unconditionally builds a
   throwaway venv via ensurepip, which SIGABRTs under uv-managed CPython on
   macOS (CI-parity violation). Shipped as environment-mode audit
   (`uv run --with pip-audit pip-audit --skip-editable`) over the synced
   uv.lock closure — identical pinned set, identical local/CI behaviour; the
   editable first-party project is the one visible skip (`--strict` treats
   that skip as fatal, so it is dropped; rationale in the Makefile comment).
2. **In-flight byte accounting redesigned from per-chunk to up-front
   reservation** (lead fix during Phase 3 review): per-chunk mid-stream
   accounting could deadlock the pool (all streams blocked on releases only
   other streams could produce; reachable at 10 × 25 MB > 100 MB). The
   fetcher now reserves the full document cap before streaming — blocking
   only while holding nothing — and shrinks the reservation to the actual
   body size on completion. Strictly matches the plan's "a fetch slot is
   granted only while accounted in-flight body bytes are under the cap";
   observable semantics (post-fetch accounted = body size until
   `release_body`) unchanged and test-pinned.
3. **Phase 5 executor consolidation** — the plan's task-9/10 test enumeration
   was largely absorbed into the implementation phases (each executor shipped
   its suite with its code). The residual (three tests: no-silent-replay,
   ingest log hygiene, parallel-fetch determinism) landed lead-inline: the
   leftover volume was smaller than a delegation brief. The no-silent-replay
   test also moved from task 1 (plan) to Phase 5 by necessity — it needs the
   live fetcher, which did not exist in Phase 1.
4. **`httpcore>=1,<2` declaration-only promotion** — required by the
   plan-approved NetworkBackend seam (direct import of httpx's own pinned
   transitive; the 015 rev-3.13 precedent, justification comment in
   pyproject). Lockfile delta: 2 lines (dependency edge only, no new package,
   no version change). Flagged for the review stack as the dependency-gate
   item riding the approved plan design.
5. **Codex sandbox could not reach Postgres** for tasks 5/6/7b — its DB-backed
   test runs errored environmentally; every such suite was re-run green by the
   lead at the phase gates (the gate runs above are the verification of
   record). Codex quota never exhausted; no executor substitutions needed.

## Public / private safety

No document bytes committed (live-check evidence records counts, hosts,
reasons, timings only — no URLs with query strings, no body text). The
committed fixture corpus is unchanged in content, only relocated. No secrets
in code, tests, logs recorded here, or this file.

## Review handoff — knowledge candidates (014-retro discipline)

- **SQLAlchemy `execution_options` on a Connection is sticky** — it mutates
  the connection's defaults for every later statement in the transaction;
  `yield_per` on a Connection wrapped subsequent INSERTs in server-side
  cursors (`DECLARE … CURSOR FOR INSERT` syntax error, 3 stage-2 tests).
  Statement-level `.execution_options(yield_per=…)` is the correct idiom.
- **Per-chunk byte accounting + bounded concurrency deadlocks** — any budget
  where in-flight holders can block mid-stream on releases only other
  holders produce is a deadlock; reserve-then-shrink (block only while
  holding nothing) is the composable shape. Found by lead review of the
  composed pipeline, not by any single component's tests.
- **pip-audit `-r` mode is unusable under uv-managed CPython on macOS**
  (ensurepip SIGABRT in its throwaway venv); environment-mode audit over the
  synced lockfile closure is the equivalent-coverage, CI-parity-safe form.
- **httpcore pools by URL origin; SNI comes from the origin, not the dial** —
  pinning an IP at `connect_tcp` while the URL keeps its hostname preserves
  pooling and TLS verification for free (the plan-review finding, confirmed
  in build: the primary design worked without the non-pooled fallback).
- **Politeness log evidence carries emission jitter** — spacing enforced on
  an internal monotonic clock can show sub-interval gaps between log-line
  timestamps under thread scheduling; assert politeness with injected clocks,
  read live logs as corroboration only.
- **403-as-bot-block is real and common** (5 of 7 live fetch failures were
  `blocked_by_host`, zero corroborated paywalls in this corpus) — the
  decision-8 ladder's refusal to equate 403 with paywall is doing visible
  coverage-honesty work on real traffic.
- **Executors shipping tests with code collapses a planned test phase** —
  plan-time test-task enumeration should expect absorption and pin only the
  cross-cutting residue (integration/e2e/property tests no single executor
  owns).
- `docs/knowledge/` authoring deliberately deferred to step 8 per the
  task-cycle spine (this list + review findings are its input, against final
  code).

## Rubric status / review findings

To be completed by the review stack (step 7, fresh conversation) — this build
conversation must not adjudicate its own work. Review-stack sizing pinned in
plan.md § Review-stack sizing (medium /code-review, one security lane headlined
by the SSRF surface, contract-verifier, Codex adversarial, live-trace content
lane over the smoke's labelled substrate).

## Known unverified items

- The labelled-citation path live (a real claim citing an abstract-basis
  chunk) — deterministically evidenced by the scripted-backend e2e test; this
  live run's 39 verified citations all landed on full-text chunks.
- CI's `audit` job first runs on this branch's PR (local `make audit` green;
  the job is command-identical by construction).
- OS-level CI egress guard — explicitly deferred with rationale
  (deferred.md; contract rev 2.4 finding 8).
- Live-mode fetch concurrency beyond this corpus's shape (10-way pool over
  22 hosts behaved; sustained large-corpus behaviour is 017+/eval territory).
