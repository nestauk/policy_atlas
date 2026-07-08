# Task contract: 015-live-search

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted — awaiting contract approval.
> Contract approved (before planning): _date · who_ ·
> Plan approved (before implementation): _date · who_ · ADR: _expected: none_
> (the seam design is ADR-free 007 contract record; the live implementations
> follow it — promote only if a design decision changes at this gate).
>
> **Revision history:**
> - **rev 1** (2026-07-08): initial draft. Sequencing context: third slice of
>   the live-demo path (014 LLM screen+classify MERGED → **015 live search** →
>   016 live fetch/ingest → 017 demo dress-rehearsal → eval slice). The 007
>   seam entry in deferred.md is this contract's requirements list — every
>   carried v2-lesson requirement is restated as a decision below so nothing
>   is rediscovered in production.

## Goal

Wire **live HTTP implementations of the `SearchBackend` seam** for OpenAlex
and Overton, so `acquire` runs on real search results. This is header-class-1
sequenced capability ("the product cannot function without live search" —
user, 2026-07-05; deferred.md). After this slice the only fixture-bound
surface left in the chain is full-text fetch (016).

Everything downstream of the seam already exists and is deliberately
untouched: the per-backend envelope mappings run against authentic recorded
structure, the three dedup identity guards, `search.executed` governance
events, the `search_coverage_record` and the fail-closed adequacy rule all
ship live for free the moment a live backend returns real records.

## Deliverable

PR landing:

- A new module (name plan-pinned, e.g. `search_live.py`) with
  `OpenAlexLiveBackend` + `OvertonLiveBackend`: same `name`/`trust_class` as
  their fixture twins, `mode="live"` (already flows into events + the
  coverage record), returning raw provider records that the **existing,
  unchanged mappers** consume.
- The carried v2-lesson hardening (decisions 3–7): timeouts, Overton rate
  limiter, OpenAlex query sanitizer, per-provider result caps, retry
  posture.
- Skeleton live-mode wiring (fixture backends stay the default everywhere
  else).
- Tests (transport-stubbed; zero egress in the suite) + `verification.md`
  with the pinned live check.
- `deferred.md` updates (seam discharged; follow-on seams recorded).

## Read first

- [EB components §1 — acquire](../../specs/capabilities/evidence-base/components.md)
  (`search` is the only egress verb; ingestion is not a tool)
- [execution-orchestration](../../specs/system/execution-orchestration.md) —
  configured backends with declared trust classes; every call emits a
  governance event
- [007 contract](../007-acquire/contract.md) — the seam design, the API
  grounding notes (call forms, rate limits, response shapes), and the V2
  integration review this slice's requirements come from
- [deferred.md](../../deferred.md) § Search / acquisition — the live-backend
  entry (this contract's requirements list) and the per-backend query-mode
  note
- As-built: `acquire.py` (protocol, mappers, error isolation, unknown-backend
  loudness), `scripts/record_*_fixtures.py` (the exact live call forms,
  recorded working 2026-07-05)

## Decisions

1. **Live backends are new implementations behind the unchanged seam.**
   `SearchBackend` (protocol), the mappers, dedup, events and coverage
   record are all untouched. The live classes live in a **new module** so
   `acquire.py` stays free of HTTP imports — the 007 zero-egress guard test
   keeps passing against `acquire.py` and extends to assert the live module
   is never imported by it. Transport is **stdlib `urllib` with explicit
   timeouts** — no new dependency; sync HTTP in sync code (the "no sync
   HTTP inside async contexts" requirement is satisfied by construction:
   `acquire_sources` is synchronous). A small injectable fetch seam
   (`_get_json`-shaped) makes the backends testable without sockets.

2. **Query modes are the recorded production modes, per backend** (the
   per-backend-query-mode-is-a-backend-property note, user 2026-07-05):
   OpenAlex = keyword `filter=title_and_abstract.search:<query>`; Overton =
   semantic `squery`. Exactly what the recorders ran on 2026-07-05 — the
   fixtures were deliberately recorded "in the mode production would use",
   so live results have the same structural shape the mappers were built
   against. Query = the scope intent verbatim (007 decision 6, unchanged).
   Semantic/keyword mixes, `min_similarity` tuning, Overton filters
   (`scope_filters` stays `{}`) remain at the recorded seam.

3. **Explicit timeouts everywhere.** Every request carries a connect+read
   timeout (recorder precedent: 30 s; exact constant plan-pinned). No call
   path can hang unbounded — the v2 OpenAlex defect this requirement
   exists to close.

4. **A real Overton rate limiter.** Max 1 call/second, enforced in the
   backend with a monotonic-clock minimum interval between requests —
   process-local, which v3.0's single-process/serial posture makes
   sufficient (the recorded 007/014 concurrency stance; multi-process
   limiting joins the concurrent-run hardening seam).
   <!-- ponytail: process-local limiter; distributed limiter if runs ever parallelise -->
   On a 429 the backend does **not** hammer: one backoff-then-retry at
   most, then the backend fails for the run — error isolation already
   turns that into `status="error"` + `inadequate`, never a crashed run.
   429 handling is deliberately conservative because Overton key-blocks
   abusers: losing one run is recoverable, losing the key is not.

5. **OpenAlex query sanitizer on the production path.** Commas inside
   quoted phrases break OpenAlex queries (v2 lesson: its sanitizer existed
   but sat on a non-production method). The live backend sanitizes the
   query in `search()` itself — the path that runs — with a unit test
   pinning the transform.

6. **Per-provider result caps.** Each backend fetches **one page** with an
   explicit page-size cap (constant plan-pinned, order-of-25 per backend;
   same order as the fixture sets so downstream cost stays demo-scale).
   The verbose provider can't crowd out grey literature because the caps
   are per-backend, not shared. `stop_condition="breadth_truncated"` stays
   the honest description. Pagination beyond one page, saturation stopping
   and the Arm-B loop stay at their recorded seams.

7. **Retry posture: cap 1, then honest failure.** One retry per backend
   call on transient failures (timeout, 5xx, and the 429 case in
   decision 4), then the backend counts as errored for the run. Per-backend
   error isolation, the `search.executed` error payload and the fail-closed
   coverage verdict are already built; a live-shaped test asserts an
   exhausted-retries backend lands there.

8. **Egress switch: the skeleton's one live flag; missing key fails loud.**
   The demo entrypoint's existing `live = bool(OPENAI_API_KEY)` pattern
   extends to search: a live skeleton run uses live search backends — the
   operator's live intent is one switch, not per-surface toggles. Because
   OpenAlex works keyless, key-presence cannot gate search by itself; in
   live mode a missing `OVERTON_API_KEY` is a **loud startup error**
   naming the variable, never a silent fixture fallback (silent
   omission ≠ deferral). The suite and all library defaults stay
   fixture-backed and egress-free.

9. **Key and query hygiene.** `OVERTON_API_KEY` (required live),
   `OPENALEX_API_KEY` (optional) and `OPENALEX_EMAIL` (optional polite-pool
   identifier) are env-only — never committed, never logged, never
   persisted. Overton echoes request params into response fields
   (`next_page_url` — recorder precedent redacts): the live backend
   strips/never-persists any response field carrying the key before
   records leave it; a test asserts no key string survives into snapshots,
   events or logs. Request URLs never appear in log lines at error level
   (the key rides the query string). Hosts are pinned literals
   (`api.openalex.org` / `app.overton.io`, HTTPS) — no provider-supplied
   URL is ever fetched in this slice (that SSRF surface belongs to 016).
   A `User-Agent` identifying policy-atlas rides every request.

10. **Provider JSON stays nested; response shape is validated.** The
    security posture from the seam entry: everything provider-controlled
    stays under `provider_fields` — already the as-built mapping shape,
    now load-bearing against live data; a test asserts no
    provider-controlled key lands at the top level of snapshot metadata
    beside the envelope keys. A response that isn't the expected envelope
    (non-JSON, missing `results` array) is a backend error (isolation
    path), never a partial parse. Unknown-backend loudness is already
    as-built (`acquire_sources` raises) — discharged, verified by existing
    tests.

11. **Live-check scope pin** (contract-time, per failure-log 2026-07-08):
    the live manual check covers the **changed surface plus one cheap
    smoke** — (a) a live acquire run against both providers with a real
    scope intent: real records land with correct envelopes/`abstract_source`
    values, provider tags bounded, coverage record `adequate`,
    `mode="live"` in events; (b) an immediate re-run showing dedup
    (`already_acquired`, no duplicate snapshots); (c) rate limiter
    observed (Overton call spacing) and key-hygiene grep clean; (d) one
    **rapid-profile chain smoke** over the live-acquired corpus (acquire →
    screen → classify → appraise → characterise with live LLM backends —
    mini-class over ~50 envelopes: cents). **No deep-chain e2e** — select/
    extract/synthesise gain nothing from this slice's surfaces (the 014
    lesson: ~50 min of live chain to evidence surfaces needing ~2 min);
    017 owns the full dress rehearsal. Live results are non-deterministic
    — evidence records observed counts, not pinned values.

## Scope / Out of scope

- **In:** new live-backend module; skeleton wiring; the decision 3–7
  hardening; transport-stubbed tests + the zero-egress guard extension;
  `deferred.md` + knowledge updates; `verification.md`.
- **Out:** live `DocumentFetcher` (016 — no full text is fetched here; live
  screen stage-2/extract stay honestly `abstract_only`-bound until then) ·
  **thin-base re-search trigger** — deferred.md says it "waits on live
  search"; proposed OUT (a screen-side loop design, not a transport slice;
  the 017 demo doesn't need it — flip at this gate if wanted) · Arm-B
  agentic loop, multi-query derivation, citation snowballing · pagination
  beyond one page / saturation stopping · Overton filters + `min_similarity`
  tuning / semantic-keyword mixes · user-selectable backend scope ·
  Semantic Scholar (third backend) · changes to mappers, dedup, coverage
  schema, events (shared code untouched except where a decision above
  names it) · recorder scripts (stay standalone dev tools; a dozen lines
  of URL-building duplication is cheaper than coupling product code to
  dev scripts).

## Constraints & approval gates

Gated changes riding this slice — **need explicit approval at the contract
🛑**:

1. **Runtime egress:** search queries carrying the scope intent (project
   data) to two external providers — the product's first non-LLM egress
   surface. Inbound: third-party metadata enters the corpus through the
   already-hardened mapping path; the LLM components that read it carry
   the 014 injection posture (allowlisted fields, length caps,
   control-char stripping, paired-fixture invariance) — no new inbound
   surface beyond volume.

**Explicitly not crossed:** no schema change (table count stays 25; no new
columns; stop-condition vocabulary unchanged) · no new dependency (stdlib
`urllib`) · no public-interface change (`run_harness` already takes
`search_backends`; skeleton wiring is internal) · no CI change · no auth
change.

## Public / private boundary

Code and transport-stubbed tests: committable. Live-run output contains
real third-party records (titles/abstracts) — fine in the dev DB and
Langfuse dev traces, never committed to the repo; `verification.md` quotes
counts and structure, not record content. Keys env-only; grep audit before
PR.

## Model route

`n/a` — no new inference surface. (The live chain smoke reuses 014's
approved screen/classify routes unchanged.)

## Disciplines binding this slice

Template set, plus: failures counted never silent (error isolation +
fail-closed adequacy are the as-built shape — live errors must land there,
not raise past it) · skip is visible (`skipped_unusable` on live junk
records) · deferred seams stay seams (no "just one more page" pagination
creep).

## Stop conditions

Template set. Additionally: any need to fetch a provider-supplied URL
(that is 016's SSRF surface, not this slice's) · any schema or dependency
need · Overton returning a shape the mappers can't consume (halt and
re-record/re-ground rather than patching mappers ad hoc past the contract).

## Acceptance checks

- `make verify` green — deterministic, zero egress (fixture defaults;
  socket-deny posture holds; live module transport-stubbed in tests).
- Unit tests: query sanitizer transform · rate-limiter spacing (monotonic
  clock, no real sleeps in the suite where avoidable) · timeout passed on
  every request · retry-then-honest-failure (timeout / 5xx / 429 paths
  landing in error isolation) · response-shape validation failure → backend
  error · key never in snapshots/events/log output · live backends return
  mapper-consumable records (transport stub replaying a raw fixture page) ·
  zero-egress guard extension (acquire.py clean; live module not imported
  by acquire.py).
- **Live manual check** (operator-run, keys env-only) — exactly the
  decision 11 pin: live acquire (both providers) · dedup re-run · rate-limit
  + key-hygiene evidence · one rapid-profile chain smoke. Red only on a
  provider outage is a report-and-rerun, not a silent pass.

## Verification evidence expected

`verification.md`: command results, live-run evidence (per-backend counts,
envelope/abstract_source spot-checks, coverage record, dedup re-run counts,
rate-limit observation, chain-smoke summary), diff summary, public-safety
confirmation (no real records or keys committed), known gaps.

## Risk tier & review focus

**Tier 3** (runtime egress). Review focus: key hygiene (Overton's
param-echo behaviour especially); timeout/rate-limit/retry actually on
every path (not just the happy one); error isolation preserved under live
failure modes; no scope creep into 016 (no URL fetching); the zero-egress
guard still meaningful after the new module lands.
