# Task contract: 015-live-search

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted rev 2 — awaiting contract approval (material
> rewrite at the gate; the 🛑 was still open).
> Contract approved (before planning): _date · who_ ·
> Plan approved (before implementation): _date · who_ · ADR: _expected:
> one_ (depth-graded agentic search adoption — the Arm-B fold is a
> consequential design decision; drafted at step 4).
>
> **Revision history:**
> - **rev 2** (2026-07-08, user scope call at the gate — MATERIAL):
>   **search becomes a depth-graded capability, not a transport slice.**
>   The user reversed the rev-1 minimal posture ("we've deferred too much
>   to seams for this slice"): **(a) query derivation folded in at BOTH
>   depths** — rapid = LLM multi-query fan-out (the V2-production Arm-A
>   shape), deep = the full Arm-B reformulation loop; depth is a
>   thoroughness gradation (the 014 screen-stage precedent). **(b)
>   Latency requirement recorded** (user diagnosis): the R&D loop's ~6 min
>   is unacceptable for a quick search, and a suspected driver is sending
>   full titles+abstracts of ALL hits into reformulation — deep-loop
>   prompt inputs are token-bounded exemplar records by contract
>   (decision 15). **(c) Breadth folds**: pagination-to-cap,
>   Overton/OpenAlex filters via `scope_filters`, user-selectable backend
>   scope (public-interface gate) — all depth-aware. **(d) Loop folds**:
>   thin-base re-search trigger, citation snowballing (OpenAlex-native),
>   LLM-suggested-paper grounding. **(e) Semantic Scholar stays OUT**
>   (backend pair user-settled; S2 remains the candidate third backend).
>   **(f) Decision 12 (no citation floor) APPROVED** by the user ("that
>   silent recall filter shouldn't be there for v3"). Gates grow: egress
>   (transport + four generation surfaces), schema (`stop_condition`
>   CHECK widening), public interface (backend-scope Plan/Config field).
>   New decisions 13–19; decisions 2/6/11 amended where the depth model
>   supersedes their single-call frame. Components §1 spec flow-back
>   rides this reopened 🛑.
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
>   **New decision 12**: NO citation floor — V2 silently applied
>   `cited_by_count > 5` to every OpenAlex call. **Risk recorded**: the
>   R&D's strongest transport lesson — lexical endpoints starve on long
>   verbatim NL (S2-measured 0-vs-25; OpenAlex same index class,
>   inferred) — *rev 2 note: now mitigated by design (rapid-mode query
>   generation), not merely measured*. **Validated as-built, no action**:
>   abstract-index reconstruction (007), DOI-keyed cross-backend dedup
>   (007), per-backend error isolation, idiom-as-backend-property,
>   fail-closed missing-`results` (a deliberate flip of V2's
>   silent-empty). **Declined**: response caching (*rev 2 note: caching
>   is re-opened as a plan question — the deep loop re-fetches; the
>   R&D's cache-before-throttle pattern is the reference*); V2's
>   silent-swallow raw channel. **Seams recorded**: SR/RCT fanout (*rev 2:
>   now IN-slice, decision 14*) · eval-reuse pointers (PaperFindingBench
>   zero-adapter first run · the parity-tested `metrics.py` recall@k_est
>   port · SYNERGY true-recall · CODEC policy topics · the
>   Campbell/3ie/EPPI "unzip" build · the coverage-vs-recall split,
>   per-backend) — to deferred.md's search-eval seam at step 8.
> - **rev 1.1** (2026-07-08, user gate call): **`OPENALEX_API_KEY` is
>   mandatory in live mode** — the API itself works keyless, but Nesta
>   holds an institutional key with different rate/volume limits and the
>   product should always ride it; an unkeyed live call silently forfeits
>   those limits, exactly the silent-degradation shape the fail-loud rule
>   exists for. Decisions 8 + 9 amended: live mode requires BOTH
>   `OVERTON_API_KEY` and `OPENALEX_API_KEY` (each missing key is a loud
>   startup error naming the variable); OpenAlex key hygiene now matches
>   Overton's (the key rides the query string on both).
> - **rev 1** (2026-07-08): initial draft (minimal transport slice).
>   Sequencing context: third slice of the live-demo path (014 LLM
>   screen+classify MERGED → **015 live search** → 016 live fetch/ingest →
>   017 demo dress-rehearsal → eval slice).

## Goal

Make `acquire` a **live, depth-graded search capability** over OpenAlex +
Overton — the header-class-1 capability v3.0 cannot function without
(user, 2026-07-05). Two layers land together:

1. **Live transport** behind the existing `SearchBackend` seam (007),
   carrying every pre-registered v2-lesson requirement (timeouts, rate
   limiting, sanitizers, caps, key hygiene).
2. **Query-derivation + search-loop capability**, thoroughness-graded
   (user scope call, rev 2): **rapid** = LLM multi-query fan-out, one
   pass; **deep** = the Arm-B agentic loop (reformulation from judged
   exemplars, citation snowballing, suggestion grounding, adaptive
   stopping) — the direction adjudicated 2026-07-05, pulled in-slice
   with a hard latency posture. V2's central search lesson (a single
   query is unstable/low-recall) and the R&D's strongest transport
   lesson (verbatim NL starves lexical indexes) are both answered by
   design rather than deferred.

Everything downstream of the seam already exists and is reused: envelope
mappings, three dedup identity guards, `search.executed` events per call
(already N-call-shaped), one fail-closed `search_coverage_record` per run.

## Deliverable

PR landing:

- Live transport module: `OpenAlexLiveBackend` + `OvertonLiveBackend`
  (`mode="live"`), decisions 1–10.
- The depth directive (`context["search"]["depth"]`, fail-closed) and
  the two search strategies behind it (decisions 13–15).
- Four lead-authored product prompts — `search_queries_v1` ·
  `search_reformulate_v1` · `search_suggest_v1` · `search_judge_v1`
  (11th–14th product prompt surfaces).
- Protocol growth: capability flags + snowball/lookup verbs on
  `SearchBackend` (decision 16).
- Thin-base re-search trigger wiring (decision 17); `stop_condition`
  CHECK migration (short_circuit · budget_exhausted).
- Breadth: pagination-to-cap, `scope_filters` directive vocabulary,
  backend-scope Plan/Config field (decision 18).
- Tests (transport-stubbed, scripted-backend loop tests, seeded-RNG
  sampling tests) + `verification.md` with the pinned live check.
- Components §1 spec flow-back + `log.md` entry; `deferred.md` +
  knowledge updates.

## Read first

- [EB components §1 — acquire](../../specs/capabilities/evidence-base/components.md)
  (`search` is the only egress verb; ingestion is not a tool; the
  thin-base hatch in §2)
- [execution-orchestration](../../specs/system/execution-orchestration.md) —
  configured backends with declared trust classes; every call emits a
  governance event
- [007 contract](../007-acquire/contract.md) — the seam design, the API
  grounding notes, and the Arm-B R&D adjudication this rev pulls in
- [deferred.md](../../deferred.md) § Search / acquisition — the
  live-backend and Arm-B entries (both discharged by this slice)
- As-built: `acquire.py` (protocol, mappers, error isolation),
  `scripts/record_*_fixtures.py` (the exact live call forms), 014's
  stage directive (`screen.py`) as the depth-directive precedent
- [v2-search-autopsy.md](v2-search-autopsy.md) — the rev-1.2 evidence
  base: V2 production search autopsy + PR #184 R&D analysis (file:line
  refs for every V2/R&D claim here; the Arm-B mechanics live in its
  Report 2)
- R&D handover: `../discovery_policy_atlas/backend/testing/r_and_d/
  search_experiments/ONBOARDING.md` + `core/source.py` (the SourceClient
  shape decision 16 grows toward)

## Decisions

### Transport layer (revs 1–1.2 — unchanged by rev 2 except where noted)

1. **Live backends are new implementations behind the unchanged seam.**
   `SearchBackend` (protocol — grown additively per decision 16), the
   mappers, dedup, events and coverage record are all reused. The live
   classes live in a **new module** so `acquire.py` stays free of HTTP
   imports — the 007 zero-egress guard test keeps passing against
   `acquire.py` and extends to assert the live module is never imported
   by it. Transport is **stdlib `urllib` with explicit timeouts** — no
   new dependency; sync HTTP in sync code. A small injectable fetch seam
   (`_get_json`-shaped) makes the backends testable without sockets.

2. **Native query idiom per backend; `min_similarity=0.3`** *(amended
   revs 1.2, 2)*. OpenAlex = keyword
   `filter=title_and_abstract.search:<query>`; Overton = semantic
   `squery` **with `min_similarity=0.3`** — the V2 production threshold
   (V2 `utils/overton.py:26`; rationale undocumented, calibration at the
   eval seam) — sent **only** in semantic mode. The fixtures were
   recorded in exactly these modes, so live results match the mappers'
   structural expectations. *(rev 2)* What each backend is **queried
   with** is now decision 14's business: the verbatim-NL-starves-lexical
   risk (R&D-measured 0-vs-25 on the same index class) is answered by
   generating keyword queries for OpenAlex rather than by measuring the
   starvation; Overton's semantic leg takes verbatim NL (dense endpoints
   want it — R&D-supported). The per-backend result-count probe stays in
   the live check as evidence.

3. **Explicit timeouts everywhere.** Every request carries a connect+read
   timeout (recorder precedent: 30 s; exact constant plan-pinned). No
   call path can hang unbounded — the V2 OpenAlex defect this closes.

4. **A real Overton rate limiter.** Max 1 call/second, enforced in the
   backend with a monotonic-clock minimum interval between requests —
   process-local, sufficient under v3.0's single-process/serial posture.
   *(rev 2)* The limiter gates **every** Overton request including
   pagination page loops and any loop-round re-query — the V2 abuse
   pattern was precisely a delay-free `next_page_url` loop
   (V2 `utils/overton.py:78-99`).
   <!-- ponytail: process-local limiter; distributed limiter if runs ever parallelise -->
   On a 429 the backend does **not** hammer: one backoff-then-retry at
   most, then the backend fails for the run — error isolation turns that
   into `status="error"`, never a crashed run. Conservative because
   Overton key-blocks abusers: losing one run is recoverable, losing the
   key is not.

5. **OpenAlex query sanitizer on the production path** *(amended
   rev 1.2)*. Two 400-vector classes, both sanitized in the live
   `search()` itself (V2's comma sanitizer sat on a method with no
   callers): commas inside quoted phrases, and **wildcards `*`/`?`**
   (the stemmed field 400s on them — R&D-observed). Applied to
   **generated queries too** (rev 2 — the R&D saw the LLM emit `*`
   despite prompt bans; sanitize output, don't trust instructions).
   Title-lookup queries (decision 16) additionally strip the
   punctuation classes that 400 the `title.search` filter
   (commas/colons/parens/dashes — R&D `openalex_client.py:91-95`).
   Unit tests pin every transform.

6. **Per-provider result caps, depth-aware; fields requested explicitly**
   *(amended revs 1.2, 2)*. Caps are per-backend so the verbose provider
   can't crowd out grey literature, and **per-depth** (plan-pinned
   constants; order: rapid ~25–50/backend, deep ~100–200/backend
   across the whole run — the R&D's Arm-A ran 200/variant, our deep cap
   bounds the *run*, not the variant). Pagination lands (decision 18);
   `breadth_truncated` remains the honest stop condition when a cap
   bites. **OpenAlex requests carry a `select=` field list derived from
   the mapper's constants** (envelope-source fields +
   `_OPENALEX_RETAIN_KEYS` + `abstract_inverted_index` + `authorships`):
   OpenAlex is credit-metered and V2 wastefully fetched full works; a
   test asserts the select list is a superset of everything the mapper
   reads.

7. **Retry posture: cap 1, then honest failure** *(amended rev 1.2)*.
   One retry per request on transient failures — timeout and HTTP
   **429 · 500 · 502 · 503 · 504** (502/504 on R&D evidence: OpenAlex
   transiently 504s under load) — then that call counts as errored.
   *(rev 2)* In loop context a failed snowball/lookup call is **counted
   and skipped** (the fan-out isolation pattern), while a failed
   *primary search* call errors the backend for the run as before.

8. **Egress switch: the skeleton's one live flag; missing keys fail loud**
   *(amended rev 1.1)*. A live skeleton run uses live search backends —
   one switch, not per-surface toggles. Live mode requires **both**
   `OVERTON_API_KEY` and `OPENALEX_API_KEY`; each missing key is a loud
   startup error naming the variable, never a silent fixture fallback.
   OpenAlex's key is mandatory *by our policy, not the API's* (rev 1.1):
   Nesta's institutional key carries different rate/volume limits and an
   unkeyed call silently forfeits them. The suite and all library
   defaults stay fixture-backed and egress-free.

9. **Key and query hygiene** *(amended revs 1.1, 1.2)*. Keys are
   env-only — never committed, never logged, never persisted. Both
   providers' keys ride the query string, so the rules apply uniformly:
   the live backend strips/never-persists any response field carrying a
   key (Overton echoes params into `next_page_url`); a test asserts no
   key string survives into snapshots, events or logs. **HTTP errors are
   redacted structurally** (rev 1.2 — V2's concrete leak vector: an
   HTTP-error exception carries the full keyed URL and V2 logged it at
   error level, V2 `references.py:648`): transport errors are caught at
   the fetch seam and re-raised/logged as **status code + host only**,
   test-asserted. Hosts are pinned literals (`api.openalex.org` /
   `app.overton.io`, HTTPS) — no provider-supplied URL is ever fetched
   (016's SSRF surface). A `User-Agent` identifying policy-atlas rides
   every request (V2 sent none to Overton).

10. **Provider JSON stays nested; response shape is validated** *(amended
    rev 1.2)*. Everything provider-controlled stays under
    `provider_fields` — as-built, now load-bearing against live data; a
    test asserts no provider-controlled key lands at the top level of
    snapshot metadata. A response that isn't the expected envelope
    (non-JSON, missing `results` array) is an error (isolation path),
    never a partial parse — a **deliberate flip of V2**, which read a
    malformed response as success-with-zero-results (V2
    `overton.py:81-84`), corrupting the coverage verdict. Tolerance:
    Overton's `next_page_url` can be JSON `false` (live-observed) —
    validation must not choke on it. Unknown-backend loudness is
    as-built (`acquire_sources` raises) — discharged.

11. **Live-check scope pin** (contract-time, per failure-log 2026-07-08)
    *(amended revs 1.2, 2)*: changed surfaces + one cheap smoke —
    (a) a live **rapid** acquire run (both providers, a real scope
    intent): generated queries recorded in events, real records with
    correct envelopes/`abstract_source`, provider tags bounded, coverage
    record `adequate`, `mode="live"`; (b) an immediate re-run showing
    dedup; (c) rate limiter observed + key-hygiene grep clean; (d) the
    **per-backend result-count probe** — now comparative evidence:
    verbatim intent vs generated queries on the OpenAlex leg (the
    decision-2 risk, measured with its mitigation in place); (e) one
    live **deep** run: reformulation rounds visible in events, snowball
    + suggestion-grounded records landing through dedup, stop condition
    + **wall-clock and cost recorded against decision 15's budgets**;
    (f) the **thin-base trigger fired once** (a deliberately narrow
    intent): re-search runs, `re_searched_still_thin` lands when still
    thin; (g) one **rapid-profile chain smoke** over the live-acquired
    corpus (acquire → screen → classify → appraise → characterise, live
    LLM backends — mini-class over ~50 envelopes: cents). **No
    deep-chain e2e** (the 014 lesson; 017 owns the dress rehearsal).
    Live results are non-deterministic — evidence records observed
    counts, not pinned values.

12. **No citation floor — no hidden recall filters** *(new rev 1.2;
    **user-approved 2026-07-08**)*. V2 silently applied
    `cited_by_count > 5` to **every** production OpenAlex call (V2
    `references.py:551`, `config.py:180`) — a hidden filter dropping
    recent, niche and low-cited work before any relevance judgment. v3
    sends **no citation floor**: screen is the relevance filter, and a
    pre-search popularity floor is a silent exclusion (flag-not-drop
    violation) biased against the recent policy work Policy Atlas exists
    to surface. The counter-case (cheap junk control) goes to the eval
    slice as a measured question; the knob's future home is a
    **documented, directive-expressible `scope_filters` entry** — never
    an implicit default. A test asserts the OpenAlex request carries no
    `cited_by_count` filter.

### Search capability (rev 2 — the user's fold)

13. **Depth is a thoroughness gradation, fail-closed** (the 014
    screen-stage precedent exactly). The `"acquire"` component reads
    `context["search"]["depth"]` — `"rapid"` (default) | `"deep"`;
    unknown values are a structural failure (plan-compile fails closed).
    One component, two strategies: a deep run is not a different
    component, it is the same governed `search` verb exercised harder —
    same events, same coverage record, same dedup, same mappers. The
    skeleton's deep profile sets `deep`; the rapid profile (and every
    default) sets `rapid`. Depth is recorded on the coverage record
    (inside `scope_filters`' sibling context or the `backends` array
    entries — exact home plan-pinned) so absence claims know how hard
    the space was searched.

14. **Rapid search: LLM multi-query fan-out (V2's Arm-A shape, made
    honest).** One generation call per run — `search_queries_v1`
    (lead-authored; mini-class default, exact id plan-pinned; V2 used a
    judgment-class model for boolean generation at temp 1.0) — produces
    **n ≈ 5 diverse keyword/boolean queries** from the scope intent
    (intent enters as an id-keyed data record, never instructions — the
    011/012 carried requirement; output queries are sanitized per
    decision 5, schema-constrained, length-capped, count-capped).
    Fan-out: each generated query → OpenAlex **base + systematic-review
    + RCT deterministic clause variants** (V2's production recall
    feature, `_fanout.py` precedent — clauses are code constants, not
    LLM output); **Overton takes the verbatim intent as its one
    semantic `squery`** (dense endpoints want NL; generated keyword
    queries would *hurt* that leg). Per-call `search.executed` events
    carry each executed query verbatim (already the 007 shape — queries
    travel by reference from the coverage record). Failed variants are
    counted and skipped (decision 7); dedup collapses cross-variant
    hits (as-built, in-memory within the call stream). V2's central
    lesson is honoured by construction: **no single LLM query is ever
    load-bearing** — instability averages out across the fan-out.
    Generation-call failure (post-retry) fails the component loudly
    (`component.failed`) — a search run with no queries is
    infrastructure failure, not empty coverage.

15. **Deep search: the Arm-B loop, latency-bounded.** Iterative rounds
    over the rapid substrate (round 1 = decision 14's fan-out), each
    round: **judge** a bounded sample of new hits for
    relevance-to-intent (`search_judge_v1`, mini-class, concurrent
    under the extract-precedent bounded fan-out) → **reformulate**
    queries from judged exemplars (`search_reformulate_v1`) → execute
    (per-backend idiom: keyword reformulations for OpenAlex, semantic
    reformulations legal for Overton) → **snowball** citations/
    references of high-judged exemplars (decision 16 verbs) →
    **suggestion grounding** (`search_suggest_v1` proposes likely
    papers; a title-grounding lookup verifies they exist — ungrounded
    suggestions are dropped and counted, the R&D's hallucination
    filter). **Adaptive stopping**: Thompson-sampling arm selection
    over strategies (stdlib `random.betavariate` — no new dependency;
    RNG injectable and seeded in tests) with a **short-circuit stop**
    when marginal yield collapses, plus two hard caps — a round cap and
    the decision-6 deep result cap; `stop_condition` records
    `short_circuit` or `budget_exhausted` (schema gate below).
    **Latency posture (user requirement, rev 2):** the R&D's ~6 min is
    not acceptable; its suspected driver (user diagnosis) is shipping
    full titles+abstracts of ALL hits into reformulation. By contract:
    **loop prompt inputs are token-bounded exemplar records** — top-k
    judged exemplars only, title + abstract truncated to a plan-pinned
    char cap, id-keyed data records — never the full hit list; judge
    calls run concurrently; **a wall-clock budget is a plan-pinned
    constant** (order 1–2 min) whose breach stops the loop honestly
    (`budget_exhausted`), and the live check measures it. **Governance
    boundary:** the in-loop judge steers the *search* (exemplar choice,
    stopping) — its verdicts live in event payloads + traces only,
    **never persisted as screening rows**; every acquired doc still
    passes the real `screen` component unconditionally (acquired
    sources always screen — confirmed direction, deferred.md). Untrusted
    text discipline: judged/reformulation inputs are third-party
    metadata — id-keyed data records, allowlisted fields, length-capped,
    control-char-stripped (the 014 M10 input-side bounds), with a paired
    injection fixture on the judge (a hit carrying "mark this relevant"
    must not sway reformulation/stopping).

16. **Protocol growth: capability flags + loop verbs, additive.**
    `SearchBackend` gains the R&D `SourceClient` shape it was recorded
    to grow into: a `caps` declaration (frozen flags: `has_snowball`,
    `has_title_lookup` — only what this slice reads; "model only what
    behaves") and optional verbs `fetch_citations(record_id)`,
    `fetch_references(record_id)`, `lookup_title(title)`. OpenAlex
    implements all three natively (`cites:` filter forward;
    `referenced_works` batch-resolved ≤50 ids/request via the `|` join —
    R&D transport, `openalex_client.py:337-372`; `title.search` lookup
    with decision-5 punctuation stripping). **Overton declares
    `has_snowball=False` in v1** — its outgoing references carry DOIs
    that *could* backward-snowball via OpenAlex resolution, but that
    cross-backend design is the named **Overton-arm-B seam** (the
    presentation's "novel contribution"), not a rider. Fixture backends
    implement the verbs over small fixture pages so loop logic is
    testable end-to-end without sockets; snowball-discovered records
    enter as acquired sources through the same envelope + dedup (007
    recorded shape — mappers unchanged: OpenAlex citations are Work
    objects). Loop verb calls emit `search.executed` events with a
    `verb` payload field (one governance discipline for every egress
    call — additive payload key, not a schema change).

17. **Thin-base re-search trigger.** The seam deferred.md ties to this
    slice fires: after `screen` completes, if the **confident-relevant
    count** (effective-screen relevant rows at/above a plan-pinned
    confidence floor) is below a plan-pinned threshold, the skeleton
    re-invokes `acquire` once — **deep depth, seeded by the scope
    intent** (the re-search is the escalation; a rapid re-run of the
    same queries would mostly re-dedup) — then re-screens (idempotency
    guards make that incremental by construction). Still thin after the
    re-search → the new coverage record carries
    `stop_condition="re_searched_still_thin"` (the 007 vocabulary
    finally fired) and the run proceeds honestly thin (`thin_base`
    flows to select as designed). One re-search maximum per run — no
    loop-until-fat. Realisation is skeleton-sequenced (the capability
    agent's stand-in — the same place the chain order already lives);
    the trigger constants ride the skeleton, not the schema.

18. **Breadth: pagination, filters, backend scope.**
    - **Pagination to a cap**: both backends follow pagination up to the
      decision-6 per-depth caps; the Overton page loop is limiter-gated
      (decision 4); OpenAlex pages via `per-page` + cursor/page params.
      `breadth_truncated` when a cap cuts results.
    - **`scope_filters` becomes a real directive vocabulary**
      (fail-closed): `context["search"]["filters"]` admits
      `published_after` / `published_before` (both backends: Overton
      params; OpenAlex `from/to_publication_date`) and `source_type` +
      `source_country` (Overton-only; ignored-with-a-counted-note on
      OpenAlex is WRONG — a filter a backend can't honour is a
      structural failure for that run's directive, fail-closed, so a
      mixed-backend run with Overton-only filters must say so
      explicitly via a `backends`-scoped filter form; exact grammar
      plan-pinned). Executed filters land on the coverage record's
      `scope_filters` (non-`{}` for the first time) and in every
      `search.executed` payload. V2's region-label mapping stays at the
      seam.
    - **User-selectable backend scope** (public-interface gate): a
      `Config`/`Plan` field (`search_backend_scope`:
      `academic_only` | `grey_lit_only` | `both`, default `both`)
      compiled into which backends `run_harness` passes — the 007-built
      `search_backends` parameter is the mechanism; the field is its
      first author. Fail-closed on unknown values.

19. **Budgets and counts — the loop is governed, never open-ended.**
    Hard plan-pinned constants: LLM call budget per run (generation +
    judge + reformulate + suggest), HTTP call budget per backend per
    run, round cap, wall-clock budget (decision 15), per-depth result
    caps (decision 6). Every budget breach is an honest stop
    (`budget_exhausted`), never a silent trim. The component summary
    counts, per depth: queries generated/executed per backend,
    rounds, judged, snowballed, suggestions grounded/dropped, records
    acquired/deduped/skipped per verb, budget consumption. Cost and
    latency land in the live-check evidence. Seeded RNG makes loop
    tests deterministic; live runs use per-run entropy.

## Scope / Out of scope

- **In:** live transport module (decisions 1–10) · depth directive +
  rapid/deep strategies (13–15) · four prompts (`search_queries_v1`,
  `search_reformulate_v1`, `search_suggest_v1`, `search_judge_v1`) ·
  protocol growth + fixture-backed verbs (16) · thin-base trigger
  (17) · pagination + `scope_filters` vocabulary + backend-scope
  Plan/Config field (18) · budgets/counts (19) · one `stop_condition`
  CHECK migration · skeleton wiring (depth profiles, trigger) ·
  components §1 flow-back · tests + `verification.md` · `deferred.md` +
  knowledge updates.
- **Out:** live `DocumentFetcher` (016 — no full text fetched; no
  provider-supplied URL fetched) · **Semantic Scholar third backend**
  (user-settled pair; the R&D's battle-tested S2 client is the fast
  path when that seam opens) · **Overton snowballing via cross-backend
  DOI resolution** (the named Overton-arm-B seam — decision 16) ·
  blend ranking of search hits (0.9·judge + rerank — the R&D's ranking
  layer belongs to the screen/retrieval-rerank seams, not acquire;
  ranking hits is select's job downstream) · saturation stopping as a
  distinct condition (`saturated` stays ⏸ per spec — short_circuit is
  yield-collapse within one run, not corpus saturation) · V2
  region-label mapping for `source_country` · citation-floor /
  quality filters (decision 12 — eval question; future `scope_filters`
  entry) · response caching **decided at plan time** (re-opened rev 2:
  the deep loop re-queries; adopt the R&D cache-before-throttle pattern
  only if the plan shows repeat fetches are real) · multi-scope /
  concurrent-run hardening (single-process posture stands) · recorder
  scripts stay standalone dev tools.

## Constraints & approval gates

Gated changes riding this slice — **all need explicit approval at the
contract 🛑**:

1. **Runtime egress** — two kinds:
   (a) **transport**: search/snowball/lookup queries carrying scope
   intent and record identifiers to OpenAlex + Overton (the product's
   first non-LLM egress);
   (b) **four new generation surfaces**: `search_queries_v1` ·
   `search_reformulate_v1` · `search_suggest_v1` · `search_judge_v1`
   (11th–14th product prompts; all mini-class default, plan-pinned ids;
   all read third-party metadata under the 014 injection posture).
2. **Schema:** one migration widening `ck_scov_stop_condition` to admit
   `'short_circuit'` and `'budget_exhausted'` (existing three values
   stand; `saturated` stays out per spec). No new tables/columns; table
   count stays 25.
3. **Public interface:** the backend-scope `Config`/`Plan` field
   (`search_backend_scope`, default `both` — no behaviour change when
   omitted), compiling into the existing `search_backends` parameter.
4. **Dependencies:** none (stdlib `urllib`; Thompson sampling via
   stdlib `random.betavariate`).

Plus the components §1 spec flow-back (depth-graded search realisation;
the loop as the same governed `search` verb) — approved with this
contract per the spec-refinement flow.

## Public / private boundary

Code, prompts, migration, transport-stubbed tests: committable. Live-run
output contains real third-party records — dev DB + Langfuse dev traces
only, never committed; `verification.md` quotes counts/structure, not
record content. Keys env-only; grep audit before PR.

## Model route

OpenAI via the existing client resolution. **Four prompt surfaces, all
mini-class default, exact ids plan-pinned** (`search_queries_v1` may
argue up to judgment-class at the plan gate — V2 generated boolean
queries with its judgment model; the other three are volume surfaces
where mini is the 009-lesson floor). Prompt-bearing work is
lead-authored. Bedrock swap remains the routing seam.

## Disciplines binding this slice

Template set, plus: failures counted never silent (error isolation +
fail-closed adequacy; loop-verb failures counted-and-skipped) · no
single LLM query load-bearing (fan-out by construction) · judge steers,
never screens (verdicts are events/traces, not rows; everything
acquired still screens) · budgets stop loudly, never trim silently ·
intent and third-party metadata enter prompts as id-keyed data records ·
deferred seams stay seams.

## Stop conditions

Template set. Additionally: any need to fetch a provider-supplied URL
(016's SSRF surface) · any new dependency · Overton returning a shape
the mappers can't consume (halt and re-ground, don't patch ad hoc) ·
loop cost/latency in the live check blowing past budgets with no
in-contract fix (halt and report — don't quietly raise the budgets).

## Acceptance checks

- `make verify` green — deterministic, zero egress (fixture defaults;
  scripted backends + seeded RNG for loop logic; transport stubbed).
- Transport tests (rev 1.2 set): sanitizer transforms (commas, wildcards,
  title-lookup punctuation) · limiter spacing incl. page loops · timeout
  on every request · retry-then-honest-failure (429/5xx/timeout) ·
  response-shape validation (+ `next_page_url: false` tolerance) ·
  redacted-HTTP-error key test (both backends) · `select=` superset
  test · no-citation-floor test · mapper-consumable live records
  (transport stub over a raw fixture page) · zero-egress guard
  extension.
- Capability tests (rev 2): depth directive fail-closed (unknown depth →
  structural failure) · rapid fan-out (n queries × variants, per-call
  events, failed-variant isolation, generation-failure →
  `component.failed`) · deep loop over scripted backends (rounds,
  judge→reformulate→snowball→ground sequence, exemplar bounding —
  inputs never exceed caps, seeded-RNG stopping, short-circuit and
  every budget stop, honest counts) · ungrounded-suggestion drop ·
  judge-verdicts-never-persisted (no screening rows written by
  acquire) · snowball records through dedup · trigger test (thin
  screen result → one deep re-search → re-screen → still-thin lands
  `re_searched_still_thin`; fat result → no re-search) · `scope_filters`
  grammar fail-closed + filters on events/coverage record ·
  backend-scope field compile (three values + unknown rejected) ·
  migration roundtrip on both DBs · injection fixtures (judge steering
  probe; instruction-shaped metadata in reformulation inputs).
- **Live manual check** — exactly the decision-11 pin (rapid run ·
  dedup re-run · limiter + key hygiene · comparative result-count
  probe · deep run with wall-clock/cost vs budgets · trigger fired
  once · rapid-profile chain smoke; no deep-chain e2e).

## Verification evidence expected

`verification.md`: command results; live-run evidence (per-backend
per-depth counts, the comparative probe, loop round/stop evidence,
wall-clock + cost vs budgets, coverage records incl. non-empty
`scope_filters` and the fired `re_searched_still_thin`, envelope
spot-checks, trace ids); diff summary with flagged deviations;
public-safety confirmation; known gaps. `deferred.md` at step 8: live
`SearchBackend` + Arm-B entries **discharged**; new/retained seams
recorded (Overton-arm-B cross-backend snowball · blend ranking pointer ·
S2 third backend · region mapping · caching if declined at plan ·
citation-floor knob · eval-reuse pointers: PaperFindingBench
zero-adapter first run, the parity-tested `metrics.py` recall@k_est
port, SYNERGY true-recall, CODEC policy topics, the Campbell/3ie/EPPI
"unzip" build, the per-backend coverage-vs-recall split).

## Risk tier & review focus

**Tier 3** (runtime egress on five surfaces + schema CHECK + public
interface — the 014 gate shape, one notch wider). Review focus: key
hygiene under the loop's call volume; injection posture on the judge/
reformulation surfaces (third-party metadata steering the search);
budget enforcement actually hard (no silent trims, no unbounded loops);
the judge-never-screens governance boundary; limiter coverage of every
Overton path; trigger can't loop; no scope creep into 016 (no URL
fetching) or into ranking (no blend-rank). **Plan requirement:** the
build is staged with consolidated verify gates (transport → rapid →
breadth/directives → deep loop → trigger), executor-marked per
harness.md — this slice is large enough that the plan's phase
discipline is load-bearing.
