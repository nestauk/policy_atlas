# Task contract: 015-live-search

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted rev 3.5 — awaiting contract approval (the 🛑 is
> open; revs 2–3.5 shaped at the gate in user deliberation).
> Contract approved (before planning): _date · who_ ·
> Plan approved (before implementation): _date · who_ · ADR: _expected:
> one_ (depth-graded agentic search adoption — the Arm-B fold is a
> consequential design decision; drafted at step 4).
>
> **Revision history:**
> - **rev 3.5** (2026-07-09, user direction: re-adjudicate source
>   persistence + the tags layer on the now-known live shapes; one
>   OpenAlex select/shape probe added — see the api-filter-research.md
>   addendum). **New decision 20** — retention + tag deltas, all
>   zero-schema: retain Overton `overton_policy_document_series` ·
>   `translated_title` · `pdf_document_id` · `keyed_other_identifiers`
>   and OpenAlex `indexed_in` · `publication_date`; tag Overton
>   `source_tags` (`asserted_by='overton'`, existing bounds). **Declined
>   with evidence**: OpenAlex `keywords` → tags (probe showed
>   wrong-sense disambiguation noise — "Stock (firearms)"); `grants`
>   retention (not a valid `select` field — would force full-work
>   fetches). Newly-understood existing riches noted for consumers:
>   Overton `source.region` carries group memberships (OECD/G7/G20/…,
>   already retained via the `source` block); `sdgcategories` carries
>   target-level labels ("SDG Target 11.1") already flowing to tags.
>   Classify-allowlist widening for the new priors
>   (`overton_policy_document_series` · `indexed_in`) is a recorded
>   seam on the 014 surface — retention now, consumption via its own
>   prompt-version bump.
> - **rev 3.4** (2026-07-09, residual pinning probes run — user:
>   "finish off the live check"; +4 calls, 21 total; record updated in
>   [overton-param-pinning.md](overton-param-pinning.md)). **Zero
>   pinning residuals remain for the build live check.** `source_type`
>   tokens `igo`/`other` confirmed (full set: government · think tank ·
>   igo · other); the derived-SDG-label pattern held on an unobserved
>   label (SDG 13) — all 17 constants safe; and **`publisher_region`
>   is PROMOTED into the grammar**: `source_region` accepts named
>   groups directly (`OECD members` → 50/50 membership-verified; no
>   `_:` code mapping needed) — single-valued, vocabulary pinned
>   (OECD members · G7 · G20 · Europe · North America · APAC ·
>   Oceania · EU27 · EEA · Very high human development). The V2 `_:`
>   negation idiom (exclusion groups) stays at the seam, untested.
> - **rev 3.3** (2026-07-09, **Overton param-pinning session run at the
>   design stage** — user supplied the API key for exactly this; 17
>   rate-limited probes, findings verified against returned records;
>   full record [overton-param-pinning.md](overton-param-pinning.md)).
>   The rev-3.1 pinning contingency is **discharged before build**:
>   every Overton directive key is live and composes with `squery`
>   (combined-filter probe held). Grammar deltas: **Overton keys are
>   single-valued** (no multi-value OR form exists — pipe/comma/
>   repeated-key/array all zero-match or last-one-wins; V2's `safe='|'`
>   assumption is false here); `languages` = three-letter codes
>   (`fre`, `eng`, …); `sdgs` on Overton = full-label constants
>   (`SDG 11: Sustainable Cities and Communities` — bare numbers
>   silently zero-match); `source_type` tokens `government`/`think
>   tank` pinned (`igo`/`other` facet-observed, one live-check
>   confirmation each). Client rules pinned: semantic-mode
>   `total_results` is the PRE-filter pool (never read it as the
>   filtered count — count returned records); the semantic candidate
>   pool caps at 1000; default page size is 50 and `pp` works;
>   `next_page_url` key-echo CONFIRMED (decision 9's redaction now
>   evidence-backed); unknown params silently ignored (the fail-closed
>   grammar rationale, empirically validated). Facet bonus recorded at
>   the seams: hierarchical source types, named region groups
>   (`OECD members`, `G20` — friendlier than V2's `_:` codes), rich
>   cites-family facets.
> - **rev 3.2** (2026-07-09, user design note on the geography-trap
>   finding): **study geography is extraction-owned — recorded as a
>   named seam with the V2 precedent.** Because no search API supplies
>   study geography (OpenAlex = author affiliation; Overton = publishing
>   org), the only honest source is the document text: V2 extracted
>   study geography at the extraction stage, feeding transferability
>   analysis and the evidence landscape. v3's finding schema carries
>   `population`, `study_design` and a `setting` stratum qualifier but
>   no dedicated study-geography field; adding one is an
>   extraction-schema gate for its own slice (joins the 010
>   selection-diversity seam, characterise's post-extraction coverage
>   dimensions, and the Transferability capability's needs — deferred.md
>   entry at step 8). In-slice effect: decision 18's geography keys
>   carry the cross-reference in their directive help ("no search filter
>   expresses study geography; that signal arrives via extraction").
> - **rev 3.1** (2026-07-09, API filter research adjudicated — two
>   parallel deep-reasoner web recons of the official OpenAlex + Overton
>   docs at the user's direction ("maximum functionality for the agent
>   to define the search strategy"); full record + adjudication table in
>   [api-filter-research.md](api-filter-research.md)). **Decision 18's
>   filter vocabulary made concrete**: self-describing directive keys
>   (the geography trap — OpenAlex country filters mean *author
>   affiliation*, Overton's mean *publishing org* — is defused by
>   naming: `author_affiliation_countries` / `publisher_countries`,
>   never a bare "country"); shared block (dates · SDGs 1–17) + validated
>   per-backend blocks (OpenAlex: `types` from the 28-value live-verified
>   enum · `languages` ISO · `exclude_retracted` · `exclude_paratext` ·
>   `oa_status` opt-in with bias warning; Overton: `publisher_types` ·
>   `publisher_countries`). **Structural finding**: Overton's public API
>   doc enumerates almost no filter params — most names are UI-/V2-
>   inferred; a **dev-time operator param-pinning session** (authenticated
>   "Generate API call" exports + a `show_search_facets=true` facet dump)
>   is now a contracted build prerequisite, and every Overton filter key
>   ships *contingent on pinning* (unpinnable keys drop to the seam,
>   loudly). **Corrections**: OpenAlex strips wildcards silently rather
>   than 400-ing (decision 5 rationale fixed — silent term loss is worse
>   than an error; sanitizer unchanged) and the R&D's ">5 boolean
>   operators" throttle is undocumented folklore. **Overton pagination
>   pinned to the documented driver** — the response `next_page_url`,
>   which is a provider-supplied URL carrying the API key: following it
>   is the one guarded exception to "never fetch provider URLs"
>   (host+scheme validated against the pinned literal, key never
>   logged/persisted; decisions 9/18). **Seams from the research**:
>   Overton-arm-B snowball upgraded to a *documented* edge
>   (`plain_dois_cited` + bulk `generate_id_set.php` — cross-backend DOI
>   seeding OpenAlex→Overton is the concrete hook; reverse policy-inbound
>   unevidenced, confirm with support) · OpenAlex topic-hierarchy
>   filters (name→id resolution) · Overton `source_region` (opaque `_:`
>   code mapping table) · COFOG classifications (reference table) ·
>   OpenAlex `sample`+`seed` (eval-set primitive) · `min_similarity`
>   stays a fixed backend constant, never agent-tunable (semantics
>   wholly undocumented).
> - **rev 3** (2026-07-09, user unification call at the gate —
>   **screen-in-the-loop**): the user challenged rev 2's in-loop judge
>   ("is judge-informed cap ordering not basically a screening step?
>   something unifies this judge, screening and select's rerank") and
>   the challenge held: `search_judge_v1`'s judgment (hit relevance to
>   scope intent) IS screen's judgment, and shipping two calibrations of
>   one judgment invites the loop to optimize toward a relevance notion
>   screen then rejects at admission. **Resolved by deletion, not
>   abstraction**: (a) `search_judge_v1` is CUT — the deep loop's
>   steering signal is **real, persisted 3-rep consensus screening**
>   (deep search = skeleton-sequenced acquire↔screen rounds; exemplars
>   read via the 014 effective-screen helper; screen's code needs no
>   change — incremental idempotency, consensus confidence and
>   failure-aware counts are exactly the required consumer contract);
>   egress gate shrinks to THREE new prompts, and rev 2's
>   judge-never-screens boundary strengthens to *the loop's judge IS
>   screen*. (b) **The thin-base re-search trigger dissolves into the
>   loop's stopping condition** — "re-search when thin" and "search
>   until confident-relevant is adequate" are one behavior; a rapid run
>   that screens thin escalates to one deep continuation (decision 17
>   rewritten); components §2's thin-base hatch is the spec warrant.
>   (c) Cap trimming per round is provider order (each API returns
>   relevance-ranked); junk is removed by real screening, not
>   pre-trimmed by a shadow of it — rev 2.1's judge-informed cap
>   ordering is moot. (d) **Select's rerank stays distinct** (purpose-fit
>   ranking under budget ≠ relevance admission); the user's select-as-tool
>   question is recorded as a spec-level seam (trigger: a second
>   purpose-fit consumer, or rerank-quality evals). Cost note: rev 2
>   paid judge + screen; rev 3 pays screen once (mandatory anyway) —
>   steering is free. Deep-run latency now includes in-loop consensus
>   screening (concurrent mini; ~15–45 s per ~50-doc round) — the
>   decision-15 wall-clock budget stands and the live check measures it.
>   A deep run writes one coverage record per acquire round (each round
>   is an acquire run; queries-by-reference already fits) — more audit
>   state, not less.
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
   pass; **deep** = the Arm-B agentic loop realised as
   **acquire↔screen rounds** (rev 3: reformulation from *screened*
   exemplars, citation snowballing, suggestion grounding, adaptive
   stopping on real confident-relevant counts) — the direction
   adjudicated 2026-07-05, pulled in-slice with a hard latency posture.
   V2's central search lesson (a single query is unstable/low-recall)
   and the R&D's strongest transport lesson (verbatim NL starves
   lexical indexes) are both answered by design rather than deferred.

Everything downstream of the seam already exists and is reused: envelope
mappings, three dedup identity guards, `search.executed` events per call
(already N-call-shaped), one fail-closed `search_coverage_record` per run.

## Deliverable

PR landing:

- Live transport module: `OpenAlexLiveBackend` + `OvertonLiveBackend`
  (`mode="live"`), decisions 1–10.
- The depth directive (`context["search"]["depth"]`, fail-closed) and
  the two search strategies behind it (decisions 13–15).
- Three lead-authored product prompts — `search_queries_v1` ·
  `search_reformulate_v1` · `search_suggest_v1` (11th–13th product
  prompt surfaces; rev 3 cut the fourth — the loop's judge is screen).
- Protocol growth: capability flags + snowball/lookup verbs on
  `SearchBackend` (decision 16).
- The deep loop's screen-informed stopping incl. the thin-escalation
  path (decision 17); `stop_condition` CHECK migration (short_circuit ·
  budget_exhausted).
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
- [api-filter-research.md](api-filter-research.md) — the rev-3.1
  evidence base: OpenAlex + Overton filter catalogs (live-verified
  enums, syntax rules, the Overton documentation-gap finding, tiering)
  behind decision 18's grammar
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
   revs 1.2, 3.1)*. Two hazard classes, both sanitized in the live
   `search()` itself (V2's comma sanitizer sat on a method with no
   callers): commas inside quoted phrases, and **wildcards/fuzzy
   `*`/`?`/`~`** — rev 3.1 correction: per current docs OpenAlex
   **strips** these silently rather than 400-ing (the R&D-era
   observation is stale); silent term loss is worse than an error, so
   we strip them ourselves, deterministically and visibly, before the
   provider does it invisibly. Applied to
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
   (016's SSRF surface), with **one guarded exception** *(rev 3.1)*:
   Overton's documented pagination driver is the response
   `next_page_url`, followed only after scheme+host validation against
   the pinned literal (decision 18; anything else → backend error). A
   `User-Agent` identifying policy-atlas rides every request (V2 sent
   none to Overton).

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
    live **deep** run: per-round acquire↔screen visible in events +
    per-round coverage records, exemplar-seeded reformulation, snowball
    + suggestion-grounded records landing through dedup, stop condition
    + **wall-clock and cost recorded against decision 15's budgets**
    (in-loop screening latency named separately); (f) the **rapid-thin
    escalation exercised once** (a deliberately narrow intent): the
    deep continuation resumes incrementally,
    `re_searched_still_thin` lands when still thin; (g) one
    **rapid-profile chain smoke** over the live-acquired
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

15. **Deep search: the Arm-B loop as acquire↔screen rounds,
    latency-bounded** *(rewritten rev 3 — the loop's judge IS screen)*.
    A deep run is **skeleton-sequenced rounds**, each round one acquire
    run + one incremental screen run:
    - **Round 1**: acquire (decision 14's rapid fan-out) → screen (the
      unmodified 014 component — its NOT-EXISTS idempotency makes every
      later round incremental: only newly acquired docs cost anything).
    - **Round k**: read the scope's screening results via the 014
      **effective-screen helper** (the one read rule — real 3-rep
      consensus decisions + confidences, never a shadow judgment) →
      **reformulate** queries from the top screened exemplars
      (`search_reformulate_v1`; per-backend idiom: keyword
      reformulations for OpenAlex, semantic legal for Overton) →
      **snowball** citations/references of high-confidence relevants
      (decision 16 verbs) → **suggestion grounding**
      (`search_suggest_v1` proposes likely papers; a title-grounding
      lookup verifies they exist — ungrounded suggestions dropped and
      counted, the R&D's hallucination filter) → acquire (dedup guards
      collapse re-hits) → screen the new docs.
    - **Stopping** (screen-informed — "adequately-searched" becomes a
      measured property, not a heuristic): the loop stops when the
      **confident-relevant count** (effective relevant rows at/above a
      plan-pinned confidence floor) reaches the plan-pinned target ·
      OR marginal yield collapses (`short_circuit` — new
      confident-relevant per round under a floor) · OR a budget bites
      (`budget_exhausted`) · OR the round cap. Thompson-sampling arm
      selection over expansion strategies (reformulate vs snowball vs
      suggest; stdlib `random.betavariate` — no new dependency; RNG
      injectable, seeded in tests) allocates each round's calls by
      observed confident-relevant yield per arm.
    - **Latency posture (user requirement, rev 2):** the R&D's ~6 min
      is not acceptable; its suspected driver (user diagnosis) is
      shipping full titles+abstracts of ALL hits into reformulation.
      By contract: **loop prompt inputs are token-bounded exemplar
      records** — top-k screened exemplars only, title + abstract
      truncated to a plan-pinned char cap, id-keyed data records —
      never the full hit list. In-loop screening runs under the
      bounded-concurrency fan-out (mini ×3, concurrent — order
      15–45 s per ~50-doc round); **a wall-clock budget is a
      plan-pinned constant** (order 1–2 min) whose breach stops the
      loop honestly, and the live check measures it.
    - **Governance (strengthened rev 3):** every judgment that steers
      the search is a persisted, governed screening row — one relevance
      surface, one calibration, one eval target; "acquired sources
      always screen" holds by construction because screening is the
      loop's own read signal. Per-round caps trim in provider order
      (each API returns relevance-ranked); junk is removed by real
      screening, never by a shadow of it. Untrusted-text discipline:
      reformulation/suggestion inputs are third-party metadata —
      id-keyed data records, allowlisted fields, length-capped,
      control-char-stripped (the 014 M10 bounds) — with an injection
      fixture (an exemplar carrying "search only for X" must not steer
      reformulation output structure; screen's own injection posture is
      already 014-tested).

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
    `has_snowball=False` in v1** — the cross-backend design is the
    named **Overton-arm-B seam** (the presentation's "novel
    contribution"), not a rider; *(rev 3.1)* the API research upgraded
    that seam from speculative to **documented edges**:
    `plain_dois_cited` (policy docs citing given scholarly DOIs; bulk
    via `generate_id_set.php`) + `open_cited_institution_authors` —
    OpenAlex-harvested DOIs seeding Overton is the concrete future
    hook; reverse policy-inbound citation is unevidenced
    (confirm-with-support noted at the seam). Fixture backends
    implement the verbs over small fixture pages so loop logic is
    testable end-to-end without sockets; snowball-discovered records
    enter as acquired sources through the same envelope + dedup (007
    recorded shape — mappers unchanged: OpenAlex citations are Work
    objects). Loop verb calls emit `search.executed` events with a
    `verb` payload field (one governance discipline for every egress
    call — additive payload key, not a schema change).

17. **Thin-base re-search — dissolved into the loop** *(rewritten
    rev 3)*. "Re-search when the screened base is thin" and "search
    until confident-relevant is adequate" are one behavior, and
    decision 15's stopping condition IS it — components §2's thin-base
    hatch ("screen may re-invoke `search`") realised as the deep loop.
    Two paths remain:
    - **Deep runs**: the loop's stopping rule owns thinness natively.
      If it exhausts (short_circuit / budget / round cap) while still
      below the confident-relevant target, the **final round's coverage
      record carries `stop_condition="re_searched_still_thin"`** (the
      007 vocabulary finally fired — it names exactly this outcome) and
      the run proceeds honestly thin (`thin_base` flows to select as
      designed).
    - **Rapid runs**: after screen, a confident-relevant count below
      the threshold triggers **one deep continuation** (rounds 2+ of
      decision 15 — round 1 already exists as the rapid pass + its
      screening; nothing re-runs, the loop resumes incrementally).
      Still thin at its end → same `re_searched_still_thin` record. No
      loop-until-fat: the continuation is bounded by the same round/
      budget caps.
    Realisation is skeleton-sequenced (the capability agent's stand-in —
    where the chain order already lives; the 012 twice-over-facets
    precedent); the thresholds are plan-pinned constants riding the
    skeleton, not the schema.

18. **Breadth: pagination, filters, backend scope.**
    - **Pagination to a cap** *(amended rev 3.1)*: both backends follow
      pagination up to the decision-6 per-depth caps;
      `breadth_truncated` when a cap cuts results. OpenAlex pages via
      `per-page` (≤200, live-verified) + page/cursor params. Overton
      pages via the **documented driver, the response `next_page_url`**
      (page size is server-fixed ~20; V2's `pp` param is unverified —
      not used) — this is a provider-supplied URL carrying the API key,
      so following it is the **one guarded exception** to decision 9's
      no-provider-URL rule: scheme+host validated against the pinned
      literal before the request (anything else → backend error), key
      never logged/persisted, the loop limiter-gated (decision 4),
      account page-caps surfacing as honest `breadth_truncated`.
    - **`scope_filters` becomes a real directive vocabulary**
      *(rewritten rev 3.1 — grammar adjudicated from the API research;
      full catalog + tiering in
      [api-filter-research.md](api-filter-research.md))*.
      `context["search"]["filters"]` is **fail-closed, all-opt-in, no
      defaults** (every admitted filter is agent-authored for a stated
      intent; the base query applies zero narrowing — the silent-recall
      class stays structurally impossible). **Directive keys are ours,
      self-describing, mapped per backend** — the research's highest-risk
      semantic trap (OpenAlex geography = *author affiliation*, Overton
      geography = *publishing org*, neither = study geography) is
      defused by naming, not help-text hope:
      - **shared** (mapped to both): `published_after` /
        `published_before` (ISO dates → OpenAlex
        `from/to_publication_date`; Overton `published_after/before`) ·
        `sdgs` (UN SDG numbers 1–17, the one vocabulary closed on both
        sides → OpenAlex `sustainable_development_goals.id` IRIs;
        Overton `sdgcategories`; help text: ML-tagged relevance hints,
        not ground truth).
      - **openalex**: `types` (allowlist over the 28-value live-verified
        enum, constant re-verified via `group_by=type` at build) ·
        `languages` (ISO 639-1; auto-detected caveat) ·
        `exclude_retracted` / `exclude_paratext` (booleans → the
        near-free integrity guards `is_retracted:false` /
        `is_paratext:false`) · `oa_status` (allowlist over the 6-value
        enum; help text names the OA-venue bias and 016-fetch trade) ·
        `author_affiliation_countries` (ISO codes →
        `authorships.countries`). *(rev 3.2)* The geography keys' help
        text on both backends carries the cross-reference: **no search
        filter expresses study geography** — that signal is
        extraction-owned (the recorded study-geography extraction seam;
        V2 precedent).
      - **overton** (*pinned at the design stage, rev 3.3 —
        [overton-param-pinning.md](overton-param-pinning.md); every key
        verified live against returned records, composing with
        `squery`*): `publisher_type` (**single-valued** →
        `source_type`; pinned tokens `government` · `think tank` ·
        `igo` · `other` — all four record-verified, rev 3.4) ·
        `publisher_country` (**single-valued** → `source_country`;
        country *names* — `UK`, `USA`, … — incl. hierarchical
        sub-national forms and `IGO`) · `publisher_region`
        (**single-valued** → `source_region`, rev 3.4: named groups
        pinned — `OECD members` · `G7` · `G20` · `Europe` ·
        `North America` · `APAC` · `Oceania` · `EU27` · `EEA` ·
        `Very high human development`; exclusion groups — the V2 `_:`
        idiom — stay at the seam) · `language` (**single-valued**;
        three-letter codes — `eng`, `fre`, …) · `sdgs` map to
        full-label constants on this backend (bare numbers silently
        zero-match; the `SDG {n}: {UN name}` derivation pattern
        verified on an unobserved label, rev 3.4).
      Validation is fail-closed at plan compile: unknown keys, unknown
      enum values, or a key in a backend block the run's backend scope
      doesn't include → structural failure. Multi-value keys map to
      OpenAlex's documented `|` OR (≤100 values); **Overton keys are
      single-valued** (rev 3.3: no multi-value OR form exists on the
      wire — pipe/comma/repeated-key/array all zero-match or
      last-one-wins; multi-value-as-fan-out is a plan-time option, not
      grammar). Client rule (rev 3.3): Overton's semantic-mode
      `total_results` is the pre-filter pool — counts come from
      returned records, never from it. Executed wire params
      land per backend on the coverage record's `scope_filters`
      (non-`{}` for the first time) and in every `search.executed`
      payload. **Excluded from the grammar** (research T3): citation
      floors (decision 12) · `min_similarity` (undocumented semantics —
      fixed backend constant) · `sort` (backend-fixed relevance) ·
      Overton `document_type`/`subject_area`/`tags`/`topics`
      (open/unpublished vocabularies that silently zero-match) ·
      OpenAlex topic/keyword/venue/funder ids (name→id resolution
      seam). V2's region-label mapping stays at the seam.
    - **User-selectable backend scope** (public-interface gate): a
      `Config`/`Plan` field (`search_backend_scope`:
      `academic_only` | `grey_lit_only` | `both`, default `both`)
      compiled into which backends `run_harness` passes — the 007-built
      `search_backends` parameter is the mechanism; the field is its
      first author. Fail-closed on unknown values.

19. **Budgets and counts — the loop is governed, never open-ended**
    *(amended rev 3)*. Hard plan-pinned constants: LLM call budget per
    run (query generation + reformulate + suggest + the in-loop screen
    reps — screen's own ≤ docs × 3 × 2 bound composes in), HTTP call
    budget per backend per run, round cap, wall-clock budget
    (decision 15), per-depth result caps (decision 6), the
    confident-relevant target + floor (decisions 15/17). Every budget
    breach is an honest stop (`budget_exhausted`), never a silent trim.
    The loop summary counts, per round: queries executed per backend,
    new docs acquired/deduped/skipped per verb, screened/
    confident-relevant deltas, suggestions grounded/dropped, arm
    allocations, budget consumption. Cost and latency land in the
    live-check evidence. Seeded RNG makes loop tests deterministic;
    live runs use per-run entropy.

20. **Source-persistence + tag-layer deltas, live-shape-informed**
    *(new, rev 3.5 — user direction; zero schema change: JSONB
    retention constants + the existing `source_tag` machinery)*. A
    snapshot is a point-in-time record and live data makes loss
    permanent (the 007 rationale, now sharper), so the retain sets
    grow where the probes showed value:
    - **Overton retains** (added to `_OVERTON_RETAIN_KEYS`):
      `overton_policy_document_series` (document-series/type —
      "Working paper" · "Clinical guidance" · "White paper" — a
      classify prior and landscape axis) · `translated_title`
      (non-English support; already the title fallback, now persisted
      when both titles exist) · `pdf_document_id` (the second half of
      the two-level identity; 016/multi-PDF seam) ·
      `keyed_other_identifiers` (cross-reference identity beyond the
      consumed DOI).
    - **OpenAlex retains** (added to `_OPENALEX_RETAIN_KEYS`, both
      select-probe-verified as `select`-able): `indexed_in`
      (crossref/doaj/pubmed/arxiv — a cheap discipline/OA prior) ·
      `publication_date` (full ISO date; the envelope keeps year-grain,
      recency analysis gets day-grain from provider_fields).
    - **Tags gain Overton `source_tags`** (publisher-curated subject
      headings — "HOUSING POLICY", committee names) via the existing
      `_provider_tags` path, `asserted_by='overton'`, under the
      standing caps and control-character bounds; sanitized fixtures
      already carry the field.
    - **Declined, with evidence**: OpenAlex `keywords` → tags (the
      shape probe surfaced wrong-sense disambiguation noise —
      "Government (linguistics)", "Stock (firearms)" — which would
      pollute the tag layer; retention in provider_fields stands,
      promotion is refused and test-pinned) · `grants` retention (not
      `select`-able — would force full-work fetches against
      decision 6).
    - **Consumption stays gated**: the new priors join classify's
      *retained* substrate, but widening classify's closed input
      allowlist (014 decisions 4/7) is a prompt-surface change on an
      approved egress surface — recorded as a seam riding the next
      `classify_v1` version bump, never silently folded in here.
      Overton `source.region`'s group memberships (OECD/G7/G20 —
      already retained inside the `source` block) are noted for
      characterise's landscape axes the same way.

## Scope / Out of scope

- **In:** live transport module (decisions 1–10) · depth directive +
  rapid/deep strategies (13–15, deep = acquire↔screen rounds; screen's
  code expected unchanged — its incremental idempotency and
  effective-screen helper are the consumer contract) · three prompts
  (`search_queries_v1`, `search_reformulate_v1`, `search_suggest_v1`) ·
  protocol growth + fixture-backed verbs (16) · screen-informed
  stopping + the rapid-thin escalation (17) · pagination +
  `scope_filters` vocabulary + backend-scope Plan/Config field (18) ·
  budgets/counts (19) · retention + tag deltas in the mapping layer
  (20 — retain-key constants, `_provider_tags`, tests incl. the
  keywords-never-tagged pin) · one `stop_condition` CHECK migration · skeleton
  wiring (depth profiles, round sequencing, escalation) · components
  §1 + §2 flow-back · tests + `verification.md` · `deferred.md` +
  knowledge updates.
- **Out:** live `DocumentFetcher` (016 — no full text fetched; no
  provider-supplied URL fetched) · **Semantic Scholar third backend**
  (user-settled pair; the R&D's battle-tested S2 client is the fast
  path when that seam opens) · **Overton snowballing via cross-backend
  DOI resolution** (the named Overton-arm-B seam — decision 16) ·
  blend ranking of search hits (0.9·judge + rerank — moot in rev 3's
  shape: screen confidence IS the doc-level relevance signal, and
  purpose-fit ranking stays select's) · **select-as-tool / shared
  purpose-fit-ranking tool** (rev 3, user question recorded as a
  spec-level seam: the components taxonomy already supports ambient
  tools — `appraise` is both; extract a shared ranking tool when a
  second purpose-fit consumer lands or rerank-quality evals exist to
  adjudicate it; select-the-component keeps its durable
  `selection_result` + steer-point + rationale surface either way) ·
  saturation stopping as a
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
   (b) **three new generation surfaces**: `search_queries_v1` ·
   `search_reformulate_v1` · `search_suggest_v1` (11th–13th product
   prompts; mini-class default, plan-pinned ids; all read third-party
   metadata under the 014 injection posture). *(rev 3)* Plus a **call-
   volume change on an already-approved surface**: `screen_v1` (014)
   now also runs in-loop during deep search — same prompt, same
   component, same per-doc bound, materially more invocations per deep
   run (budgeted, decision 19). Named here so the egress approval
   covers the volume, not just the surfaces.
2. **Schema:** one migration widening `ck_scov_stop_condition` to admit
   `'short_circuit'` and `'budget_exhausted'` (existing three values
   stand; `saturated` stays out per spec). No new tables/columns; table
   count stays 25.
3. **Public interface:** the backend-scope `Config`/`Plan` field
   (`search_backend_scope`, default `both` — no behaviour change when
   omitted), compiling into the existing `search_backends` parameter.
4. **Dependencies:** none (stdlib `urllib`; Thompson sampling via
   stdlib `random.betavariate`).

Plus the components §1 + §2 spec flow-back (depth-graded search
realisation; the deep loop as acquire↔screen rounds — §2's thin-base
hatch realised; the loop as the same governed `search` verb) — approved
with this contract per the spec-refinement flow.

## Public / private boundary

Code, prompts, migration, transport-stubbed tests: committable. Live-run
output contains real third-party records — dev DB + Langfuse dev traces
only, never committed; `verification.md` quotes counts/structure, not
record content. Keys env-only; grep audit before PR.

## Model route

OpenAI via the existing client resolution. **Three new prompt surfaces,
mini-class default, exact ids plan-pinned** (`search_queries_v1` may
argue up to judgment-class at the plan gate — V2 generated boolean
queries with its judgment model; the other two are volume surfaces
where mini is the 009-lesson floor). In-loop screening rides 014's
approved `screen_v1` route unchanged (mini ×3). Prompt-bearing work is
lead-authored. Bedrock swap remains the routing seam.

## Disciplines binding this slice

Template set, plus: failures counted never silent (error isolation +
fail-closed adequacy; loop-verb failures counted-and-skipped) · no
single LLM query load-bearing (fan-out by construction) · **one
relevance surface** (rev 3: the loop's judge IS screen — no shadow
relevance judgment exists anywhere in acquire; steering reads persisted
effective-screen rows) · budgets stop loudly, never trim silently ·
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
  test (covering decision 20's two new OpenAlex keys) ·
  no-citation-floor test · mapper-consumable live records
  (transport stub over a raw fixture page) · retention/tag deltas
  (decision 20: new retain keys present on mapped fixtures; Overton
  `source_tags` materialised within bounds; OpenAlex `keywords` never
  tagged — the deliberate-refusal pin) · zero-egress guard
  extension.
- Capability tests (revs 2–3): depth directive fail-closed (unknown
  depth → structural failure) · rapid fan-out (n queries × variants,
  per-call events, failed-variant isolation, generation-failure →
  `component.failed`) · deep loop over scripted backends + the stub
  screening backend (round sequencing, exemplars read via the
  effective-screen helper — never a raw status join, exemplar bounding —
  prompt inputs never exceed caps, seeded-RNG arm selection, stopping on
  each of: confident-relevant target · short_circuit · budget ·
  round cap, honest per-round counts) · **acquire writes no screening
  rows itself** (screening rows only ever from the screen component;
  steering is read-only) · ungrounded-suggestion drop · snowball records
  through dedup · escalation test (rapid + thin screen → one incremental
  deep continuation → still-thin lands `re_searched_still_thin`; fat
  result → no escalation) · `scope_filters` grammar fail-closed +
  filters on events/coverage record · backend-scope field compile
  (three values + unknown rejected) · migration roundtrip on both DBs ·
  injection fixture (instruction-shaped metadata in reformulation/
  suggestion inputs must not steer output structure; screen's own
  injection posture is 014-tested).
- **Overton param-pinning session — DISCHARGED at the design stage**
  *(rev 3.1 requirement; run rev 3.3, 2026-07-09, user-sanctioned key
  use; record: [overton-param-pinning.md](overton-param-pinning.md))*:
  21 rate-limited probes pinned every decision-18 Overton key's wire
  spelling, value vocabulary and `squery` co-behavior, verified against
  returned records; key redacted from all persisted output. **No
  residual pinning items remain** (rev 3.4: `igo`/`other` tokens,
  the derived-SDG-label pattern and `source_region` named groups all
  record-verified).
- **Live manual check** — exactly the decision-11 pin (rapid run ·
  dedup re-run · limiter + key hygiene · comparative result-count
  probe · deep run with wall-clock/cost vs budgets · escalation
  exercised once · rapid-profile chain smoke; no deep-chain e2e), plus
  *(rev 3.1)* **one filtered rapid run** (a dated + typed directive on
  both backends: wire params visible in `search.executed` payloads +
  the coverage record's `scope_filters`, result counts consistent with
  the narrowing).

## Verification evidence expected

`verification.md`: command results; live-run evidence (per-backend
per-depth counts, the comparative probe, per-round loop/stop evidence
incl. in-loop screening latency, wall-clock + cost vs budgets, coverage
records incl. non-empty `scope_filters` and the fired
`re_searched_still_thin`, envelope spot-checks, trace ids); diff summary
with flagged deviations; public-safety confirmation; known gaps.
`deferred.md` at step 8: live `SearchBackend` + Arm-B + thin-base-trigger
entries **discharged**; new/retained seams recorded (**select-as-tool /
shared purpose-fit-ranking tool** — the rev-3 spec-level seam ·
Overton-arm-B cross-backend snowball (rev 3.1: now carrying the
documented edges — `plain_dois_cited` + `generate_id_set.php` +
`open_cited_institution_authors`; reverse policy-inbound =
confirm-with-support) · S2 third backend · **filter-vocabulary growth
seams** (rev 3.1: OpenAlex topic-hierarchy/keyword/venue/funder
name→id resolution · Overton `source_region` `_:` code mapping table ·
COFOG classifications reference table · Overton open-vocabulary
`topics`/`document_type` once token lists are pinnable) · caching if
declined at plan · citation-floor knob · eval-reuse pointers:
PaperFindingBench zero-adapter first run, the parity-tested
`metrics.py` recall@k_est port, SYNERGY true-recall, CODEC policy
topics, the Campbell/3ie/EPPI "unzip" build, the per-backend
coverage-vs-recall split, and (rev 3.1) OpenAlex `sample`+`seed` as the
eval-set sampling primitive · **study-geography extraction field**
(rev 3.2, user: V2 extracted study geography at the extraction stage
for transferability + the landscape; no search API supplies it — an
extraction-schema gate joining the 010 selection-diversity seam,
characterise's post-extraction coverage dimensions and the
Transferability capability)).

## Risk tier & review focus

**Tier 3** (runtime egress — transport + three new generation surfaces
+ the screen_v1 volume change — plus schema CHECK + public interface;
the 014 gate shape, one notch wider). Review focus: key hygiene under
the loop's call volume; injection posture on the reformulation/
suggestion surfaces (third-party metadata steering the search); budget
enforcement actually hard (no silent trims, no unbounded loops); the
**one-relevance-surface property** (no shadow judgment anywhere in
acquire; steering reads only the effective-screen helper); limiter
coverage of every Overton path; the escalation is bounded (no
loop-until-fat); no scope creep into 016 (no URL fetching) or into
purpose-fit ranking (select's surface untouched). **Plan requirement:**
the build is staged with consolidated verify gates (transport → rapid →
breadth/directives → deep loop → escalation), executor-marked per
harness.md — this slice is large enough that the plan's phase
discipline is load-bearing.
