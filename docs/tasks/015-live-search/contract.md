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
> - **rev 1.2** (2026-07-08, V2 search autopsy adjudicated — two parallel
>   deep-reasoner recons of `../discovery_policy_atlas` at the user's
>   direction: production search path + the PR #184 R&D branch; fifth in
>   the autopsy series; full record + adjudication table in
>   [v2-search-autopsy.md](v2-search-autopsy.md)). **Adopted in-slice**:
>   redacted HTTP errors — the concrete V2 key-leak vector closed
>   structurally (decision 9); Overton `min_similarity=0.3` with `squery`
>   only, the undocumented V2 production default (decision 2); sanitizer
>   also strips wildcards `*`/`?` — a second OpenAlex 400-vector
>   (decision 5); retryable set widened to timeout · 429 · 500/502/503/504
>   (R&D-observed transient OpenAlex 5xx; decision 7); OpenAlex `select=`
>   field list derived from the envelope+retain constants, test-enforced
>   superset — credit-responsible on the institutional key (decision 6);
>   Overton `next_page_url: false` (JSON boolean, live-observed) tolerated
>   in shape validation (decision 10); live check gains a per-backend
>   result-count probe for the verbatim-NL recall risk (decision 11).
>   **New decision 12 ⚑**: NO citation floor — V2 silently applied
>   `cited_by_count > 5` to every OpenAlex call (the agents split on
>   adopting it; lead adjudicated recall-first, user confirmation flagged).
>   **Risk recorded ⚑**: the R&D's strongest transport lesson — lexical
>   endpoints starve on long verbatim NL (S2-measured 0-vs-25; OpenAlex
>   same index class, inferred) — v1 measures rather than engineers
>   (decision 2; query derivation stays the Arm-B seam). **Validated
>   as-built, no action**: abstract-index reconstruction (007), DOI-keyed
>   cross-backend dedup (007), per-backend error isolation, idiom-as-
>   backend-property, fail-closed missing-`results` (a deliberate flip of
>   V2's silent-empty). **Declined**: response caching (2 requests/run —
>   YAGNI); Semantic Scholar as fast semantic backend (backend set is
>   user-settled; stays the candidate third backend at its seam); V2's
>   silent-swallow raw channel (nothing like it exists here). **New
>   seams**: SR/RCT variant fanout (V2 prod recall feature, deliberately
>   dropped in v1 — joins the Arm-B/multi-query entry) · eval-reuse
>   pointers (PaperFindingBench zero-adapter first run · the parity-tested
>   `metrics.py` recall@k_est port · SYNERGY true-recall · CODEC policy
>   topics · the Campbell/3ie/EPPI "unzip" build · the coverage-vs-recall
>   split, per-backend) — to deferred.md's search-eval seam at step 8.
> - **rev 1.1** (2026-07-08, user gate call): **`OPENALEX_API_KEY` is
>   mandatory in live mode** — the API itself works keyless, but Nesta
>   holds an institutional key with different rate/volume limits and the
>   product should always ride it; an unkeyed live call silently forfeits
>   those limits, exactly the silent-degradation shape the fail-loud rule
>   exists for. Decisions 8 + 9 amended: live mode requires BOTH
>   `OVERTON_API_KEY` and `OPENALEX_API_KEY` (each missing key is a loud
>   startup error naming the variable); OpenAlex key hygiene now matches
>   Overton's (the key rides the query string on both).
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
- [v2-search-autopsy.md](v2-search-autopsy.md) — the rev-1.2 evidence
  base: V2 production search autopsy + PR #184 R&D analysis, with the
  adjudication table (file:line refs for every V2 claim in this contract)

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
   per-backend-query-mode-is-a-backend-property note, user 2026-07-05)
   *(amended rev 1.2)*. OpenAlex = keyword
   `filter=title_and_abstract.search:<query>`; Overton = semantic
   `squery` **with `min_similarity=0.3`** — the V2 production threshold
   (V2 `utils/overton.py:26`; rationale undocumented, calibration belongs
   to the eval seam) — sent **only** in semantic mode (V2 sent it
   unconditionally, even where it likely did nothing). Exactly what the
   recorders ran on 2026-07-05 — the fixtures were deliberately recorded
   "in the mode production would use", so live results have the same
   structural shape the mappers were built against. Query = the scope
   intent verbatim (007 decision 6, unchanged). **Known recall risk,
   recorded ⚑ (rev 1.2, the R&D's strongest transport lesson):** lexical
   endpoints starve on long verbatim natural language — the R&D measured
   0-vs-25 hits (long NL vs short keywords) on Semantic Scholar's
   endpoint, and OpenAlex's `title_and_abstract.search` is the same class
   of stemmed lexical index (inferred, not directly measured); every V2
   arm avoided the case via LLM-generated boolean queries. v1 **measures
   rather than engineers**: the live check's result-count probe
   (decision 11) turns the risk into evidence; a starving OpenAlex leg is
   a reported finding that feeds the Arm-B query-derivation seam —
   in-slice query shortening/keyword-ifying is declined as seam creep.
   The Overton semantic leg is unaffected (dense endpoints want verbatim
   NL — R&D-supported). Semantic/keyword mixes, `min_similarity` tuning,
   Overton filters (`scope_filters` stays `{}`) remain at the recorded
   seam.

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

5. **OpenAlex query sanitizer on the production path** *(amended
   rev 1.2)*. Two 400-vector classes, both sanitized in the live
   `search()` itself — the path that runs (v2 lesson: its comma sanitizer
   existed but sat on a method with no callers): commas inside quoted
   phrases, and **wildcards `*`/`?`** (the stemmed field 400s on them —
   R&D-observed, worked around experiment-side only). Unit tests pin both
   transforms.

6. **Per-provider result caps; fields requested explicitly** *(amended
   rev 1.2)*. Each backend fetches **one page** with an explicit
   page-size cap (constant plan-pinned, order-of-25 per backend; same
   order as the fixture sets so downstream cost stays demo-scale) — at
   that size one page is exactly one HTTP request on both APIs
   (R&D-confirmed pagination math). The verbose provider can't crowd out
   grey literature because the caps are per-backend, not shared.
   `stop_condition="breadth_truncated"` stays the honest description.
   **OpenAlex requests carry a `select=` field list derived from the
   mapper's constants** (envelope-source fields + `_OPENALEX_RETAIN_KEYS`
   + `abstract_inverted_index` + `authorships`): OpenAlex calls are
   credit-metered (V2 disabled a debug channel "to save credits") and V2
   wastefully fetched full works; a test asserts the select list is a
   superset of everything the mapper reads, so the list can never
   silently starve the envelope. Pagination beyond one page, saturation
   stopping and the Arm-B loop stay at their recorded seams.

7. **Retry posture: cap 1, then honest failure** *(amended rev 1.2)*.
   One retry per backend call on transient failures — timeout and HTTP
   **429 · 500 · 502 · 503 · 504** (502/504 included on R&D evidence:
   OpenAlex transiently 504s under load) — then the backend counts as
   errored for the run. Per-backend error isolation, the
   `search.executed` error payload and the fail-closed coverage verdict
   are already built; a live-shaped test asserts an exhausted-retries
   backend lands there.

8. **Egress switch: the skeleton's one live flag; missing keys fail loud**
   *(amended rev 1.1)*. The demo entrypoint's existing
   `live = bool(OPENAI_API_KEY)` pattern extends to search: a live
   skeleton run uses live search backends — the operator's live intent is
   one switch, not per-surface toggles. Live mode requires **both**
   `OVERTON_API_KEY` and `OPENALEX_API_KEY`; each missing key is a **loud
   startup error** naming the variable, never a silent fixture fallback
   (silent omission ≠ deferral). OpenAlex's key is mandatory *by our
   policy, not the API's* (rev 1.1): the API works keyless, but Nesta's
   institutional key carries different rate/volume limits and an unkeyed
   call would silently forfeit them — the same silent-degradation shape
   the fail-loud rule exists for. The suite and all library defaults stay
   fixture-backed and egress-free.

9. **Key and query hygiene** *(amended rev 1.1)*. `OVERTON_API_KEY`
   (required live), `OPENALEX_API_KEY` (required live, rev 1.1) and
   `OPENALEX_EMAIL` (optional polite-pool identifier) are env-only —
   never committed, never logged, never persisted. **Both providers'
   keys ride the query string**, so the hygiene rules apply uniformly:
   Overton echoes request params into response fields (`next_page_url` —
   recorder precedent redacts), and the live backend strips/never-persists
   any response field carrying a key before records leave it; a test
   asserts no key string survives into snapshots, events or logs (both
   backends). **HTTP errors are redacted structurally** *(rev 1.2 — V2's
   concrete leak vector)*: an HTTP-error exception carries the full
   request URL, key included, and V2 logged exactly that at error level
   (V2 `references.py:648`); the live backends therefore catch transport
   errors at the fetch seam and re-raise/log **status code + host only**
   — the raw provider exception string never propagates, with a test
   asserting the key is absent from the raised message. Hosts are pinned
   literals (`api.openalex.org` / `app.overton.io`, HTTPS) — no
   provider-supplied URL is ever fetched in this slice (that SSRF surface
   belongs to 016). A `User-Agent` identifying policy-atlas rides every
   request (V2 sent none to Overton).

10. **Provider JSON stays nested; response shape is validated** *(amended
    rev 1.2)*. The security posture from the seam entry: everything
    provider-controlled stays under `provider_fields` — already the
    as-built mapping shape, now load-bearing against live data; a test
    asserts no provider-controlled key lands at the top level of snapshot
    metadata beside the envelope keys. A response that isn't the expected
    envelope (non-JSON, missing `results` array) is a backend error
    (isolation path), never a partial parse — a **deliberate flip of V2**,
    which treated a missing `results` key as success-with-zero-results
    (V2 `overton.py:81-84`: a malformed response silently read as "we
    searched, nothing matched", corrupting the coverage verdict).
    Tolerance note: Overton's `next_page_url` can be JSON `false`, not
    just null (V2 live-observed) — shape validation must not choke on it
    (v1 never follows it regardless). Unknown-backend loudness is already
    as-built (`acquire_sources` raises) — discharged, verified by
    existing tests.

11. **Live-check scope pin** (contract-time, per failure-log 2026-07-08)
    *(amended rev 1.2)*: the live manual check covers the **changed
    surface plus one cheap smoke** — (a) a live acquire run against both
    providers with a real scope intent: real records land with correct
    envelopes/`abstract_source` values, provider tags bounded, coverage
    record `adequate`, `mode="live"` in events; (b) an immediate re-run
    showing dedup (`already_acquired`, no duplicate snapshots); (c) rate
    limiter observed (Overton call spacing) and key-hygiene grep clean;
    (d) the **per-backend result-count probe** (rev 1.2, the decision-2
    recall risk made measurable): record each backend's result count for
    the verbatim intent — a starving OpenAlex leg (0 or near-0 against a
    productive Overton leg) is a **reported finding** feeding the Arm-B
    query-derivation seam, never a silent pass and never an in-slice
    prompt-engineering fix; (e) one **rapid-profile chain smoke** over
    the live-acquired corpus (acquire → screen → classify → appraise →
    characterise with live LLM backends — mini-class over ~50 envelopes:
    cents). **No deep-chain e2e** — select/extract/synthesise gain
    nothing from this slice's surfaces (the 014 lesson: ~50 min of live
    chain to evidence surfaces needing ~2 min); 017 owns the full dress
    rehearsal. Live results are non-deterministic — evidence records
    observed counts, not pinned values.

12. **No citation floor — no hidden recall filters ⚑** *(new, rev 1.2;
    user confirmation flagged — the two recon agents split on this)*. V2
    silently applied `cited_by_count > 5` to **every** production
    OpenAlex call (V2 `references.py:551`, `config.py:180`) — a hidden
    filter that drops recent, niche and low-cited work before any
    relevance judgment, unlogged and unflagged. v3 sends **no citation
    floor**: screen is the relevance filter (recall-oriented by design,
    014), and a pre-search popularity floor is a silent exclusion —
    exactly the flag-not-drop violation the disciplines forbid; it also
    biases against the recent policy-relevant work Policy Atlas exists
    to surface. The counter-argument (it drops junk cheaply; the R&D
    held it constant across all arms) is real but belongs to the eval
    slice as a measured question, and the knob's future home is the
    `scope_filters` object (shape reserved since 007) — a documented,
    directive-expressible filter, never an implicit default.

## Scope / Out of scope

- **In:** new live-backend module; skeleton wiring; the decision 3–7
  hardening; transport-stubbed tests + the zero-egress guard extension;
  `deferred.md` + knowledge updates; `verification.md`.
- **Out:** live `DocumentFetcher` (016 — no full text is fetched here; live
  screen stage-2/extract stay honestly `abstract_only`-bound until then) ·
  **thin-base re-search trigger** — deferred.md says it "waits on live
  search"; proposed OUT (a screen-side loop design, not a transport slice;
  the 017 demo doesn't need it — flip at this gate if wanted) · Arm-B
  agentic loop, multi-query derivation, citation snowballing · **SR/RCT
  variant fanout** (rev 1.2 — V2's production recall feature, base +
  systematic-review + RCT clause per query, deliberately dropped in v1;
  joins the Arm-B/multi-query seam) · **in-slice query shortening /
  keyword-ifying** (rev 1.2 — the decision-2 recall risk is measured, not
  engineered; any query transformation beyond decision 5's sanitizers is
  the Arm-B seam) · pagination beyond one page / saturation stopping ·
  **response caching** (rev 1.2 — the R&D's cache-before-throttle is good
  engineering at experiment scale; at 2 requests/run it's YAGNI) ·
  Overton filters + `min_similarity` tuning / semantic-keyword mixes ·
  **citation-floor / quality filters** (decision 12 — the future
  `scope_filters` knob, never an implicit default) · user-selectable
  backend scope · Semantic Scholar (third backend — rev 1.2 note: the R&D
  holds a complete battle-tested S2 client incl. dense/citation/reference
  verbs; the fast path when that seam opens) · changes to mappers, dedup,
  coverage schema, events (shared code untouched except where a decision
  above names it) · recorder scripts (stay standalone dev tools; a dozen
  lines of URL-building duplication is cheaper than coupling product code
  to dev scripts).

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
- Unit tests: query sanitizer transforms (commas-in-quotes AND wildcards,
  rev 1.2) · rate-limiter spacing (monotonic clock, no real sleeps in the
  suite where avoidable) · timeout passed on every request ·
  retry-then-honest-failure (timeout / 429 / 500 / 502 / 503 / 504 paths
  landing in error isolation) · response-shape validation failure → backend
  error (and `next_page_url: false` tolerated) · key never in
  snapshots/events/log output, **including the redacted-HTTP-error test**
  (rev 1.2: key absent from the raised/logged message on a transport
  failure, both backends) · **`select=` superset test** (rev 1.2: the
  OpenAlex select list covers every field the mapper reads) · **no
  citation-floor test** (rev 1.2: the OpenAlex request carries no
  `cited_by_count` filter) · live backends return mapper-consumable
  records (transport stub replaying a raw fixture page) · zero-egress
  guard extension (acquire.py clean; live module not imported by
  acquire.py).
- **Live manual check** (operator-run, keys env-only) — exactly the
  decision 11 pin: live acquire (both providers) · dedup re-run · rate-limit
  + key-hygiene evidence · one rapid-profile chain smoke. Red only on a
  provider outage is a report-and-rerun, not a silent pass.

## Verification evidence expected

`verification.md`: command results, live-run evidence (per-backend counts
incl. the decision-11 result-count probe, envelope/abstract_source
spot-checks, coverage record, dedup re-run counts, rate-limit observation,
chain-smoke summary), diff summary, public-safety confirmation (no real
records or keys committed), known gaps. `deferred.md` at step 8: the
live-`SearchBackend` seam marked discharged; new seams recorded (SR/RCT
fanout at the Arm-B entry · the eval-reuse pointers — PaperFindingBench
zero-adapter first run, the parity-tested `metrics.py` recall@k_est port,
SYNERGY true-recall, CODEC policy topics, the Campbell/3ie/EPPI "unzip"
build, the per-backend coverage-vs-recall split — at the search-eval
seam · the citation-floor knob at `scope_filters`).

## Risk tier & review focus

**Tier 3** (runtime egress). Review focus: key hygiene (Overton's
param-echo behaviour especially); timeout/rate-limit/retry actually on
every path (not just the happy one); error isolation preserved under live
failure modes; no scope creep into 016 (no URL fetching); the zero-egress
guard still meaningful after the new module lands.
