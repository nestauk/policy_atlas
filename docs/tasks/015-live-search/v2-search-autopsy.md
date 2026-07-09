# V2 search autopsy — production path + R&D PR #184 (2026-07-08)

Fifth in the V2 autopsy series (014's screen/classify autopsy is the
precedent). Two parallel deep-reasoner recons of
`../discovery_policy_atlas` (branch `search-experiment-pr`, read-only),
briefed on what task 007 already adjudicated so they hunted only new
material. Full agent reports below, verbatim; the lead adjudication is
recorded in [contract.md](contract.md) rev 1.2.

**Adjudication summary** (detail in the contract revision entry):

| # | Finding | Call |
|---|---|---|
| A1/B8 | V2 silently applied `cited_by_count > 5` on every OpenAlex call (agents split: drop it vs adopt it) | **New decision 12: no citation floor** — screen is the relevance filter; a silent floor drops recent/grey/niche work (flag-not-drop). `scope_filters` seam. ⚑ user call at the gate |
| A2 | Real key-leak vector: `raise_for_status()` embeds the keyed URL in the exception, logged at error level (V2 `references.py:648`) | **Adopted** — decision 9 gains the structural fix (redacted HTTP errors: status + host only) + test |
| A4 | pyalex reconstructed abstracts for free; raw HTTP must do it itself | **Already built** — `_reconstruct_abstract` in `acquire.py` (007); fixtures carry the raw inverted index. No action |
| A5 | Overton `next_page_url` can be JSON `false`, not just null | **Adopted** into decision 10 tolerance note |
| A6/B9 | OpenAlex calls are credit-metered; V2 fetched full works (no `select`) | **Adopted** — decision 6 gains a `select=` field list derived from the envelope+retain constants, test-enforced superset |
| A7 | V2 cross-provider ranking tie-broke on OpenAlex-only `relevance_score` | **N/A by construction** — v3 dedup order is fixed backend list order; no cross-provider ranking at acquire |
| A8 | Overton production semantic threshold `min_similarity=0.3` (undocumented rationale); sent even in boolean mode | **Adopted** — decision 2: send 0.3 with `squery` only; calibration at the eval seam |
| A-verdicts | Retry: pyalex had 3 retries; R&D added 502/504 to the retryable set (transient OpenAlex 5xx under load) | **Adopted** — decision 7 retryable set = timeout · 429 · 500/502/503/504; cap stays 1 |
| A-verdicts | V2 treated missing `results` as empty success | **Confirmed flip** — decision 10's fail-closed error is a deliberate change from V2 |
| B1 | Strongest R&D lesson: lexical endpoints starve on long verbatim NL (S2: 0 hits vs 25); OpenAlex's field is the same index class — v3's verbatim-intent OpenAlex leg is unmeasured recall risk | **Measure, don't engineer** — decision 2 records the risk; decision 11's live check gains a per-backend result-count probe; near-zero OpenAlex is a reported finding feeding the Arm-B seam, never a silent pass. ⚑ user call at the gate |
| B2 | No Overton client exists anywhere in the R&D (the "Overton arm-B contribution" was never built); S2 has the complete battle-tested client | Overton transport is **greenfield** — 007 API grounding + recorder are the sources. S2-as-fast-semantic-backend **declined** for v3.0 (backend set is user-settled; S2 stays the candidate third backend at its seam) |
| B3 | Two-backend dedup must key on DOI, not source id | **Already built** — 007's normalized-DOI guard. No action |
| B4 | V2 prod fanned every query into base/SR/RCT variants (a recall feature v1 drops) | **Recorded seam** — joins the Arm-B/multi-query entry in deferred.md |
| B5 | Protocol must not foreclose the keyword/dense idiom split; return shape should stay bindable | **Confirmed as-built** — idiom is a backend property (decision 2); the mapper layer is the normalization; protocol growth verbs stay at the recorded seam |
| B6 | S2 client hardening template (global throttle, cache-before-throttle, backoff) | Throttle/backoff already decisions 4/7; **response caching declined** (2 requests/run — YAGNI) |
| B7 | Eval reuse: PaperFindingBench (zero-adapter), `metrics.py` (parity-tested recall@k_est port), SYNERGY (true recall), CODEC (policy topics), Campbell/3ie/EPPI "unzip", coverage-vs-recall split | **Recorded** — joins the search-eval seam pointers in deferred.md at step 8 |
| B-misc | OpenAlex 400s on wildcards `*`/`?` (stemmed field rejects unexpected syntax) | **Adopted** — decision 5's sanitizer also strips wildcards |

---

## Report 1 — production search autopsy (deep-reasoner)

Scope: production search/acquisition path only (`r_and_d` excluded). Files read in full: `backend/app/services/openalex.py`, `backend/app/services/overton.py`, `backend/app/utils/overton.py`, `backend/app/services/search_wizard.py`, `backend/app/services/analysis/relevance.py`, plus the orchestrator `backend/app/services/analysis/references.py` and `backend/app/core/config.py`.

### Executive summary

- The production query is **heavily transformed, not verbatim**: user intent → LLM-generated boolean query (single OR multi ×5) → **fanned out ×3** (base + systematic-review clause + RCT clause), plus a separately LLM-generated semantic query for Overton. One "run" can fire **up to 15 OpenAlex calls** (`references.py:509-518, 536-556`). This is the deferred Arm-B fan-out; V3's "one call per backend, verbatim" is a deliberate, large simplification.
- **The comma sanitizer is dead code in production.** `sanitize_openalex_query` is only called from `search_minimal` (`openalex.py:311`), which has **no callers anywhere** in the app. The production path `OpenAlexService.search()` (`references.py:548`) never sanitizes. Confirms the 007 adjudication exactly.
- **OpenAlex production search silently applies `cited_by_count > 5`** on every call (`references.py:551` passing `settings.DEFAULT_MIN_CITATIONS=5`, `config.py:180`). This is a recall filter that drops recent/low-citation work — a hidden behavior V3's contract does not mention. **New finding.**
- **Real key-leak vector:** Overton `api_key` rides the query string (`utils/overton.py:51,68,75,115`); on any HTTP error `raise_for_status()` throws an `HTTPError` whose message contains the full URL (with key), and the orchestrator logs that exception object at error level: `logger.error("Reference fetch error (%s): %s", task_kind, g)` (`references.py:648`). Confirms V3 decision 9's concern with a concrete vector.
- **No rate limiting, no 429 handling, no retry on Overton** (confirms 007). Worse: multi-page pagination follows `next_page_url` in a tight `while` loop with **no delay** (`utils/overton.py:78-99`) — precisely the abuse pattern Overton key-blocks for.
- **OpenAlex had no request timeout** (pyalex, unbounded) — confirms 007. Only `check_rate_limit` had `timeout=10.0` (`openalex.py:464`). Overton had `timeout=30` everywhere (`utils/overton.py:69,79,117`).
- **Abstract reconstruction is a pyalex freebie V3 loses.** OpenAlex returns `abstract_inverted_index`; pyalex reconstructs it via the `page["abstract"] = page["abstract"]` trick (`openalex.py:130-131`). V3 recording raw HTTP JSON must reconstruct the inverted index itself — fixtures taken from pyalex dicts would not show this.
- **`next_page_url` can be JSON `false`, not just `null`** — explicit `is False` guard (`utils/overton.py:96`). Fixture recording and mappers must preserve/handle the boolean-false case.
- **Error isolation via `asyncio.gather(return_exceptions=True)`** (`references.py:643-649`) worked well and validates V3's per-backend isolation decision. But malformed responses were treated as **empty success**, not error (`overton.py:81-84`, `.get("results", [])`) — partially contradicts V3 decision 10.
- **Keys asymmetric in V2:** Overton key is **required** (raises if missing, `utils/overton.py:18-20`); OpenAlex key is **optional** (warns, falls back to 100 credits/day, `openalex.py:56-60`). V3's "require both, fail loud" is a deliberate tightening.

### Per-provider findings

#### OpenAlex (`openalex.py`, via pyalex)

Exact request the production path builds (`search()`, `openalex.py:96-127`):
- Query: `Works().search_filter(title_and_abstract=query)` (`:97`) — boolean/keyword mode, matches V3 decision 2.
- Filter: `cited_by_count=">5"` **always** in production (`references.py:551` → `openalex.py:100-101`); plus `from_publication_date`/`to_publication_date` when dates given (`:103-109`). Uses ISO date strings.
- Pagination: `.paginate(per_page=min(200, max_results), n_max=max_results)` (`:124-126`). Default `max_results=limit`=`config.limit` (default `DEFAULT_MAX_RESULTS=50`, `config.py:178`; hard cap `MAX_SEARCH_RESULTS=1000`, `config.py:179`). So per variant: up to 50 records, page size up to 200 — i.e. usually a single page of 50.
- **No `.select()`** in production `search()` — full works fetched (`.select` only in the dead `search_minimal`, `:331`). Full records = more credits/bandwidth.
- Client config (constructor, `:44-60`): `config.email` = `OPENALEX_EMAIL` (the mailto/polite-pool mechanism), `config.max_retries = 3`, `config.retry_backoff_factor = 0.5`, `config.api_key` = `OPENALEX_API_KEY`. **No timeout set** — pyalex requests can hang unbounded.
- `relevance_score` is read from each work (`:210`) and later drives dedup ranking (`references.py:843`).
- Sync pyalex calls inside `async def search` (`:71`) — event-loop blocking (confirms 007).
- Response mapping tolerances: nested null-guarding on `authorships`/`author`/`institutions` (`:141-161`); OA-URL precedence `best_oa_location` → `primary_location` → `open_access.oa_url` (`:188-204`); `type_crossref` → `work_type` (`:213`); DOI via `page.get("doi")` (`:219`).
- `check_rate_limit()` (`:449-487`) hits `GET /rate-limit?api_key=…` after every run (`references.py:667-668`) and logs credits — a useful ops signal, and an extra keyed request.
- `fetch_raw` for OpenAlex is **commented out "to save credits (10 credits per fetch_raw call)"** (`references.py:559-570`) — direct evidence OpenAlex calls are metered and fan-out is cost-sensitive.

#### Overton (`overton.py` service + `utils/overton.py` client)

Exact request (`utils/overton.py:48-64`):
- Base URL pinned: `https://app.overton.io/documents.php` (`:12`).
- Params always sent: `min_similarity` (**0.3**, hardcoded), `format=json`, `api_key`, `pp` (page size = `max_results` if `<50` else `50`, `:55-58`).
- Query param: `squery=<q>` for semantic (production default) OR `query=<q>` for boolean (`:60-63`; service toggles via `semantic_search`, `overton.py:28`).
- Service also always sets `sort="relevance"` and `min_similarity=0.3` (`overton.py:29-31`), plus optional `source_country`/`source_region` (frontend-label mapping incl. `"All but UK" → "_:uxf"`, `overton.py:34-58`), `source_type`, `published_after`/`published_before` (ISO), `topics`, `classifications`.
- **min_similarity=0.3 value has no documented rationale** — it is just the client default (`utils/overton.py:26`) echoed in the service (`overton.py:30`) and `fetch_raw` (`references.py:630`). It is sent even in boolean `query=` mode where it likely does nothing (`overton.py:30` unconditional).
- `urlencode(params, safe='|')` (`:68,75,115`) — pipe char preserved (Overton filter syntax uses `|`).
- Pagination: `fetch_mode="up_to_max"` (`overton.py:73`), loops following `next_page_url` (`utils/overton.py:78-99`) with **no inter-request delay**, stops when `total_results >= max_results` or `next_page_url is False/None`.
- Timeout: `timeout=30` on every `requests.get` (`:69,79,117`). Sync `requests` inside `async def` (blocking).
- **No 429/403/5xx special-casing, no retry, no backoff** — `raise_for_status()` (`:70,80,117`) throws straight through to `gather`.
- `fetch_raw` in the service **swallows all exceptions → `{}`** (`overton.py:200-208`) — silent failure for the debug channel.
- Response mapping tolerances (fixture-relevant): authors string-or-list (`overton.py:90-92`); topics string-or-list (`:95-97`); `source` dict-or-missing (`:108-116`); `keyed_other_identifiers.doi` is a list, `[0]` taken (`:136-142`); `published_on` may be empty, year parsed by `split("-")[0].isdigit()` (`:154-157`); `document_url` `.pdf`-suffix sniffing to split landing vs pdf (`:121-133`); `citation_count` → `cited_by_count` (`:160`); `policy_document_id` → id (`:145`); `is_oa` always `None` for Overton (`:173`).
- **No User-Agent header set** on Overton requests (plain `requests.get`, no headers) — contrast with OpenAlex's mailto.
- `search_documents_raw` (`utils/overton.py:108-118`) and the legacy `search_all_documents` (`:121-128`) also carry the api_key in the URL.

#### search_wizard.py

Not a search-API client. It is four LLM calls (`ChatOpenAI`, `SEARCH_WIZARD_MODEL=gpt-4.1-mini`, temp 0.3, `config.py:130`) that generate population/outcome/inner-setting options and follow-up questions from the research question (`search_wizard.py:41-398`). It feeds the `search_context` that later shapes query generation. No HTTP-backend relevance beyond confirming the query pipeline is LLM-mediated upstream.

#### relevance.py (search-adjacent parts only)

No search-API surface. It reads the `references.csv` produced by the search stage (`relevance.py:109`), screens rows via `batch_check.LLMProcessor` (already autopsied in 014), and adds acquisition/extraction tracking columns (`add_acquisition_tracking_columns`, `:303-339`: `acquisition_status`, `full_text_available`, `file_path`, `extraction_status`, `text_source`). Relevant only as the consumer contract of the search output schema (`doc_id`, `title`, `abstract_or_summary`).

### Verdict table over the 10 V3 decisions

| # | V3 decision | Verdict | Evidence |
|---|---|---|---|
| 1 | New module, stdlib urllib, injectable seam, sync | **Confirm (direction) + caution** | V2 used pyalex + `requests`, async-wrapping-sync (blocking). urllib is simpler, but pyalex did real work V3 now owns: abstract reconstruction (`openalex.py:130`), retries/backoff (`:48-49`), pagination. `OvertonClient` was already injectable via `OvertonService.__init__` (`overton.py:9`). |
| 2 | Query modes; query = scope intent **verbatim**, one call/backend | **Confirm mechanics, Contradict "verbatim"** | Modes match V2 (`title_and_abstract` `openalex.py:97`; `squery` `utils/overton.py:62`). But V2 query was LLM-generated + fanned out ×3 + multi-query ×5 (`references.py:459-518`). "Verbatim, one call" is a deliberate departure (the deferred fan-out). |
| 3 | 30s timeout every request | **Confirm need** | V2 Overton had 30s (`utils/overton.py:69`); OpenAlex had **none** (pyalex unbounded). V3 unifying at 30s fixes the OpenAlex gap. |
| 4 | Overton limiter 1/s + one 429 backoff-retry | **Confirm gap, Refine** | V2 had no limiter, no 429 handling (confirms 007). Refine: the abuse vector is the delay-free `next_page_url` loop (`utils/overton.py:78-99`) — V3's single-call model + limiter closes it. |
| 5 | Sanitizer in live `search()` path | **Confirm** | V2 sanitizer only on the uncalled `search_minimal` (`openalex.py:311`); production `search()` never sanitizes (`references.py:548`). V3 moving it into the live path is correct. Note the sanitizer is narrow (strips commas inside quotes only, `openalex.py:30-38`). |
| 6 | One page/backend, cap ~25 | **Confirm (single-call), Contradict scale** | V2 OpenAlex `n_max=50` page 200 (`openalex.py:124`); Overton `pp≤50` multi-page up_to_max; ×15 variants → hundreds of records/run. V3's 25 is far smaller — fine given fan-out is deferred. |
| 7 | Retry cap 1 on timeout/5xx/429 | **Refine** | V2 OpenAlex used pyalex `max_retries=3` (`openalex.py:48`); Overton had **0** retries. V3's uniform cap-1 is a sane middle ground; note it is *fewer* retries than V2 gave OpenAlex. |
| 8 | Require BOTH keys, fail loud | **Confirm direction, note asymmetry** | V2: Overton key required, raises if missing (`utils/overton.py:18-20`); OpenAlex key **optional** with 100-credits/day fallback (`openalex.py:56-60`). V3 requiring both (institutional key) is a deliberate tightening. |
| 9 | Key hygiene (no key in logs/URLs, strip echoing fields, UA, pinned host) | **Contradict V2 practice → V3 fixes real bugs** | V2 leaked key via `HTTPError` message logged at error level (`references.py:648` + `raise_for_status` `utils/overton.py:70`); followed key-echoing `next_page_url` directly (`:99`); **no User-Agent**. Host was pinned (`:12`). V3 decision is a genuine fix. |
| 10 | Response-shape validation → backend error, no partial parse | **Refine/Contradict** | Non-JSON would raise in `.json()` → caught by gather → dropped (isolation, OK). But **missing `results` key silently returns empty** and is treated as *success with 0 results*, not an error (`overton.py:81-84`). V3 treating missing-array as error is a change from V2 behavior — correct, but note it flips a silent-empty into a fail-closed error. |

### New lessons not previously adjudicated

1. **Hidden `cited_by_count > 5` filter on OpenAlex.** Every production OpenAlex call filters out works with ≤5 citations (`references.py:551`, `config.py:180`). This silently suppresses recent and grey/low-cited work. **Recommendation (in-slice):** decide explicitly — either don't apply a citation floor in 015, or make it a documented, defaulted-off contract parameter. Do not inherit it implicitly.
2. **Key-leak via logged exceptions.** `raise_for_status()` on a keyed URL produces an exception string containing the key, which is logged (`references.py:648`). **Recommendation (in-slice):** in the live search egress, catch HTTP errors and re-raise/log a redacted message (status code + host only); never log the request URL or the raw provider exception. This is the concrete mechanism behind decision 9.
3. **Delay-free `next_page_url` pagination is the Overton abuse pattern** (`utils/overton.py:78-99`). **Recommendation (in-slice):** V3's single-page model already avoids it; if pagination is ever re-added, the 1/s limiter must gate the *page loop*, not just the first call.
4. **Abstract inverted-index reconstruction.** OpenAlex raw JSON gives `abstract_inverted_index`; pyalex reconstructed the abstract for free (`openalex.py:130-131`). **Recommendation (in-slice mapper):** V3's raw-HTTP mapper must reconstruct the abstract from the inverted index itself; verify the recorded fixtures contain `abstract_inverted_index` (raw) not a pre-reconstructed `abstract` (pyalex-shaped).
5. **`next_page_url` can be JSON `false`.** Explicit `is False` guard in V2 (`utils/overton.py:96`). **Recommendation (seam/mapper):** ensure the Overton envelope mapper and any pagination guard treat `false` (not only `null`/absent) as "no more pages," and that fixtures preserve the literal `false`.
6. **OpenAlex calls cost credits; fan-out is expensive.** `fetch_raw` was disabled with the comment "to save credits (10 credits per fetch_raw call)" (`references.py:559`). **Recommendation:** the institutional key (decision 8) is the right mitigation; keep the single-call model and avoid `.select()`-less full fetches only where needed — but this validates why V3 caps at ~25 and one call.
7. **Cross-provider ranking asymmetry.** Dedup sorts by `relevance_score` then variant priority (`references.py:842-845`), but Overton has no `relevance_score` (defaults 0), so Overton records systematically lose tie-breaks to OpenAlex. **Recommendation (seam):** V3's identity/dedup guards should not rank cross-provider on a provider-specific score; use a provider-neutral order or keep provider partitions explicit.
8. **min_similarity=0.3 is the production Overton semantic threshold** (`utils/overton.py:26`, `overton.py:30`), undocumented rationale, and is sent even in boolean mode. **Recommendation (in-slice):** adopt 0.3 as the documented default for `squery`, and omit `min_similarity` when not using `squery`.
9. **`fetch_raw` swallows all errors → `{}`** (`overton.py:200-208`). A debug/export channel that hides failures. **Recommendation:** V3 should not carry a silent-swallow raw channel; fold raw capture into the fixture-recording harness with explicit error propagation.

### What worked well (keep/copy)

- **Per-task error isolation** via `asyncio.gather(return_exceptions=True)` with per-task metadata tagging (`references.py:643-664`) — one backend/variant failing never kills the run. Directly validates V3's per-backend error isolation.
- **Common-schema normalization + `stable_doc_id`** keyed DOI → source_id → title+year (`references.py:795-808`), then dedup on `doc_id` (`:845`). Validates V3's DOI-primary cross-provider identity and dedup guards.
- **Overton `next_page_url is False` guard** (`utils/overton.py:96`) — correct handling of the provider's quirky sentinel.
- **Defensive nested null-checking** on OpenAlex `authorships`/`institutions` (`openalex.py:141-161`) and the OA-URL precedence chain (`:188-204`) — worth mirroring in V3's mapper.
- **Empty-DataFrame short-circuits** on both providers (`openalex.py:248-252`, `overton.py:181-182`) — clean "no results" path distinct from error.
- **`check_rate_limit` ops visibility** for OpenAlex credits (`openalex.py:449-487`) — a cheap, useful signal worth an analogous (redacted) health log in V3.
- **30s Overton timeout** and **pinned HTTPS Overton host** — already match V3's decisions.

### Uncertainties

- No TODO/incident comments beyond two "save credits" markers and commit-history signals (`ff73662 fix: pagination bugs`, `f72b45a fix: overton retrieval bug (#65)`, `2633bc7 fix: handle empty dataframes`). The pagination fix targeted a `page=`-mode path that no longer exists.
- Read-only recon — the exact wire behavior of `min_similarity` in Overton boolean mode is inferred, not observed.

---

## Report 2 — R&D PR #184 search-experiments analysis (deep-reasoner)

Paths abbreviated: `SE/` = `backend/testing/r_and_d/search_experiments/`; production refs under `backend/app/`.

### Executive summary

- **There is NO Overton client in the R&D — at all.** `grep -rin overton` returns 5 hits, all prose ("Overton-adjacent", "OpenAlex↔Overton share DOIs"). The presentation's "Overton arm-B novel open-source contribution" was never built. The R&D's actual third backend is **Semantic Scholar** (Arm C), fully implemented. So V3's Overton client is **greenfield** — no transport code transfers; only the `SourceClient` protocol shape does.
- **The R&D never sends a research intent verbatim as one query to OpenAlex.** Its "single-pass baseline" (Arm A) runs the **v2 LLM boolean generator** (multi-query, n=5) then fans each into base/SR/RCT variants → up to 15 OpenAlex searches per query. V3's v1 (one verbatim call/backend) is *simpler and more naive than their floor*; they have **zero measured evidence** that a lone verbatim keyword query works on OpenAlex.
- **The single strongest transport lesson: keyword/lexical endpoints starve on long verbatim NL.** S2 `/paper/search` returned **0 results** for a long NL sentence vs **25** for a short keyword query (`SE/docs/FINDINGS.md:349-419`). OpenAlex's search field is the same class of stemmed lexical index (`backend/app/services/openalex.py:97`, `title_and_abstract`), so **"verbatim intent → keyword-OpenAlex" is the exact failure mode they hit.** Semantic/dense endpoints (Overton's presumed mode) *do* want verbatim NL — that side of V3's plan is well-supported.
- **OpenAlex has a documented heavy-query governor**: >5 boolean operators → capped at 1 req/s, intermittent 500⇄429 (`SE/retrieval/_openalex_throttle.py:1-45`). Irrelevant to V3 v1 (a verbatim query has ~0 operators) but the *retry/timeout* hygiene around it is directly adoptable.
- **S2 transport hardening is the reusable gold**: global 1 req/s throttle, cache-before-throttle, exponential backoff on 429+5xx, explicit `timeout=40`, sparse-hit batch hydration (`SE/retrieval/s2_client.py`). This is a clean template for any HTTP backend client V3 writes.
- **~25 records/backend = exactly one HTTP request per backend** on both APIs (OpenAlex `per_page=min(200,max_results)`; S2 `/paper/search` page=min(100,limit)). V3's one-call-per-backend is consistent with their pagination code — no contradiction.
- **Two-backend dedup MUST key on DOI, not source id.** The R&D dedups on `paper_id` *only because it was single-source*, and explicitly flags that OpenAlex↔Overton share DOIs but not source ids (`SE/docs/FINDINGS.md:331-345`). V3 with OpenAlex+Overton needs a DOI-normalized dedup key from day one; prod already has `stable_doc_id` (DOI→source_id→title+year hash).
- **Client abstraction to grow into**: `SourceClient` Protocol (`SE/core/source.py:116-187`) with 9 verbs (2 keyword + 2 dense formulation, keyword/dense search, suggest, fetch_citations/references) and a 4-flag `Capabilities` gate (`has_dense/has_influential/has_snippets/native_abstracts`). Retrieval returns a normalized mutable `Candidate` that accretes fields — **not raw records**.
- **Eval reuse is well-scoped**: `SE/docs/report/golden_datasets_catalogue.md` ranks **PaperFindingBench** (run first — S2 CorpusIDs = their `paper_id`, zero adapter, it's literally what `metrics.py` was ported from), **LitSearch/LitQA2**, **SYNERGY** (social-science subset = true recall), **CODEC** (42 policy topics), and the bespoke **Campbell/3ie/EPPI "unzip"** as the highest-value build. `SE/reporting/metrics.py` is a ~100-line parity-tested recall@k_est reimplementation V3 can lift.
- **Free single-pass wins V3 could adopt**: a citation floor (`min_citations=5`, prod default, held constant A/B/C), `select`-ing only needed OpenAlex fields (prod pulls full authorship blobs — heavy), and explicit per-request timeouts.

### Transport-layer lessons for 015

#### In-slice adoptable

**OpenAlex request shape** (`backend/app/services/openalex.py:97-124`, reused verbatim by the R&D):
- Query goes to `Works().search_filter(title_and_abstract=query)` — a **stemmed lexical full-text field**. This is *keyword/lexical*, not semantic. `SE/openalex_client.py:33` shows the intended call: `keyword_search(query, 200)`.
- Citation floor: `.filter(cited_by_count=f">{min_citations}")`, prod default `DEFAULT_MIN_CITATIONS=5` (`backend/app/core/config.py:180`). Held constant across all arms; drops junk but also recent/niche papers.
- Pagination: `paginate(per_page=min(200, max_results), n_max=max_results)`. **At 25 records this is one page = one request.**
- Prod `DEFAULT_MAX_RESULTS=50`; Arm A overrides to 200 (`SE/arms/arm_a.py:57`).

**OpenAlex sanitization gotchas** (both are latent prod bugs the R&D worked around experiment-side):
- Wildcards: gpt emits `agricultur*` despite the prompt forbidding it; OpenAlex's stemmed field **400s on wildcards**. Fix: strip `*`/`?` (`SE/retrieval/openalex_client.py:80-88`, `strip_openalex_wildcards`; `SE/docs/FINDINGS.md:220-239`). *Less relevant to verbatim intent (no wildcards), but shows the field 400s on unexpected syntax.*
- Commas in quoted phrases break OpenAlex; prod `sanitize_openalex_query` strips them (`backend/app/services/openalex.py:14-40`). A verbatim NL intent with commas should be passed through this or an equivalent.
- Title-filter punctuation: commas/colons/parens/dashes 400 the `title.search` filter (`SE/retrieval/openalex_client.py:91-95`). Relevant if V3 ever does title-grounding lookups.

**S2 request hardening** (`SE/retrieval/s2_client.py`) — the reusable HTTP-client template:
- Base `https://api.semanticscholar.org/graph/v1` (line 63); `x-api-key` header, **hard error if key unset** (191-199); **explicit `timeout=40`** (198).
- Retryable set `{429,500,502,503,504}` (66); backoff `delay=2.0 → *1.7 capped 30`, `max_retries=5` (224-241).
- **Global cumulative rate throttle** — one module singleton across all endpoints/instances, serialises to `s2_min_request_interval_s` (86-105). Value **bumped 1.1→1.2s** after 429s persisted at 1.1 (`SE/config.py:203-206`; `SE/docs/FINDINGS.md:243-254`).
- **Cache-before-throttle** so cache hits cost zero rate budget (244-254) — the property that makes reruns affordable.
- `/paper/search` fields requested explicitly (`_PAPER_FIELDS`, 69-72); pagination offset-based, `offset+limit<=1000`, page≤100 (77, 257-281).

**Content-addressed disk cache** (`SE/retrieval/_cache.py`): sha1[:20] of canonical-JSON (namespace,key); stores **JSON dicts, not Candidate objects** (mapper runs after cache). Trivially liftable; makes a demo idempotent/resumable.

**OpenAlex retry config the R&D settled on** (`SE/config.py:216-231`, applied in `SE/_backend.py:42-69`): `max_retries=3, backoff=0.5` (prod values), retry codes **augmented to `(429,500,502,503,504)`** — they add 502/504 because heavy booleans transiently 504-timeout under cluster load (`SE/docs/FINDINGS.md:48-84`). V3 should add 502/504 to any OpenAlex retry list even for simple queries.

#### Seam material (future, when SearchBackend grows the agentic verbs)

- **Per-variant catch-and-skip**: one un-servable boolean must not sink the query — mirror prod's `gather(return_exceptions=True)`, count into `n_search_failures` (`SE/retrieval/openalex_client.py:279-289`, `SE/arms/arm_a.py:184-202`). Only relevant once V3 fans out into multiple queries.
- **Heavy-query 1 req/s governor** patch at the pyalex chokepoint `BaseOpenAlex._get_from_url`, gating only >5-operator URLs (`SE/retrieval/_openalex_throttle.py:43-94`). Only bites LLM-generated booleans; a verbatim intent never trips it.
- **SR/RCT fanout** (`SE/retrieval/_fanout.py`): each boolean → base + `AND {SYSTEMATIC_REVIEW_CLAUSE}` + `AND {RCT_CLAUSE}`, prod-default ON (`backend/app/core/config.py:139`). A cheap recall/evidence-mix breadth feature V3 drops in v1; seam material.
- **Snowball transport** (OpenAlex `cites:` filter forward; `referenced_works` backward, batch-resolved via `openalex_id="|".join(chunk)`, ≤50 ids/request — `SE/retrieval/openalex_client.py:337-372`). S2 equivalent via `/paper/CorpusId:{id}/citations|references`, edge `isInfluential` flag (`SE/retrieval/s2_client.py:312-423`). These are the citation-fetch/reference-fetch verbs the recorded seam names.
- **Dense-hit batch hydration**: S2 `/snippet/search` returns sparse papers; hydrate corpusIds via `/paper/batch` (POST, `CorpusId:` prefix, ≤500/request, skips nulls — `SE/retrieval/s2_client.py:294-310, 358-385`). Pattern V3's Overton client may need if Overton's search returns sparse hits.

### Client abstraction shape V3 must not foreclose

`SE/core/source.py:116-187` — the `SourceClient` Protocol. V3's minimal `search(query)->list[raw records]` must be able to grow into these signatures:

```python
name: str
caps: Capabilities   # frozen dataclass, 4 flags (source.py:30-37)

async def formulate_keyword_queries(content, n) -> list[str]
async def formulate_dense_queries(content, n)   -> list[str]      # has_dense only
async def keyword_search(query, limit)          -> list[Candidate]
async def dense_search(query, limit)            -> list[Candidate] # has_dense only
async def suggest(content, n)                   -> list[Candidate]
async def reformulate_keyword_queries(content, exemplars, n) -> list[str]
async def reformulate_dense_queries(content, exemplars, n)   -> list[str]
async def fetch_references(paper_id)            -> list[Candidate]
async def fetch_citations(paper_id)             -> list[Candidate]
```

`Capabilities` (`source.py:30-37`): `has_dense`, `has_influential`, `has_snippets`, `native_abstracts` — all default False; unsupported verbs may `raise NotImplementedError` and the loop simply never calls them when the flag is off.

**Two protocol facts that should shape V3's day-1 choices:**

1. **There is no single `search()` — retrieval is split into `keyword_search` and `dense_search`** precisely because the two endpoint classes want different query idioms (keyword-ish vs NL). V3's "one `search(query)` per backend" is fine *if* each backend owns its idiom internally: map OpenAlex→keyword, Overton→dense/semantic. But the protocol should let a backend **declare its native idiom** (a capability/mode) so the future loop can formulate per-leg without breaking the signature. Don't bake in an assumption that one query string suits every backend.
2. **Retrieval returns a normalized `Candidate`, not raw records** (`source.py:40-101`). It is a mutable dataclass that accretes fields across retrieve→judge→rank: `paper_id, title, abstract, year, cited_by_count, reference_count, influential_citation_count, num_snippets, doi, text_basis ("abstract"|"title_only"|"tldr"|"snippet"), origins:set`. `merge_from`/`dedupe` union origins and keep best signals (78-113). *(V3 note: the mapper layer after `search()` is the normalization; the envelope carries id/doi/title/abstract/year already.)*

### Single-pass baseline (Arm A) config + numbers

**Config** (`SE/arms/arm_a.py`, `SE/docs/report/methodology_arms.md` Slide 2):
- Formulate: `generate_boolean_queries_multi`, **n=5**, temp=1.0, model **gpt-4.1** (`backend/app/core/config.py:124-127`; mode="multi"). Cached per query (temp>0 non-deterministic).
- Fan out each of the 5 booleans → base/SR/RCT (fanout ON) ⇒ up to **15 OpenAlex searches/query**.
- Search: `OpenAlexService.search`, **max_results=200/variant** (overrides prod's 50), `min_citations=5`, no date filter.
- Dedup on `paper_id`; rank by prod native order = OpenAlex lexical `relevance_score` desc, then `variant_priority` (SR>RCT>base). **No relevance screen.**
- Judge top **250** with the frozen judge.

**Numbers**: the headline recall@k_est / yield plots live **only in the linked Google Slides**, not in the repo (results are gitignored; `SE/docs/FINDINGS.md` is a build-time scratch log, not a results table). What *is* recorded:
- Directionally: **Arm B (loop) leads recall@k_est at the Perfect bar; Arm C (S2 dense) overtakes at Highly+** (`methodology_arms.md` Slides 7-8). The ~2× recall, ~$0.44/query, ~6 min figures V3 already recorded are **Arm B**, not the single-pass baseline.
- `recall@k_est` is **capped at ~1/factor ≈ 0.5 by construction** (silver-standard pooled normalizer) — absolute values are not "fraction of the literature" (`methodology_arms.md` Slide 5).
- Cost model (`SE/reporting/cost.py`): judge = gpt-5.4-mini @ $0.75/$4.50 per 1M; the per-paper judge (n_judged×) dominates. Arm A ≈ 5 gpt-4.1 boolean calls + 250 judge calls/query.

### Eval-reuse pointers (future eval slice)

Primary doc: `SE/docs/report/golden_datasets_catalogue.md` (companion: `golden_datasets_research.md`).

- **Run first — PaperFindingBench** (ASTA-bench, 333 queries): S2 CorpusIDs are **identical to the harness `paper_id`**, and `SE/reporting/metrics.py` was ported *from* it, so scoring is ≈zero-adapter and regression-tests the whole instrument (catalogue:140, 161).
- **`SE/reporting/metrics.py`** — ~100-line reimplementation of recall@k_est + corrected nDCG + k_est inflation factor, **parity-tested** against ASTA-bench (`SE/tests/test_metrics.py`, README:40-53). Directly liftable as V3's search-recall metric core.
- **True-recall near domain — SYNERGY** (ASReview, social-science subset, complete denominators, OpenAlex-mappable) — the one place you can report *actual* recall, not an estimate (catalogue:123, 164).
- **Policy topics fast — CODEC** (42 expert social-science topics, TREC pooling) — reuse the topics as queries (catalogue:106).
- **Highest-value build — Campbell/3ie/EPPI "unzip"**: each systematic review = a policy question + expert-vetted included-studies list with DOIs → the only policy-domain, expert-judged, cleanly-identifiable gold data (catalogue:105, 167).
- **Key eval design principle**: split **coverage** (|R∩corpus|/|R|) from **retrieval recall** so a "60%" tells you whether to fix the *index* (add sources) or the *retriever* (catalogue:59-89). With two backends this is exactly the per-backend coverage question V3 will want. Match on **DOI (best) or normalized title**, never require corpus membership.
- Curated query set: `SE/queries/loader.py` — `query_text` is **PICO-folded NL** (not raw user question), 26 stratified queries (q01/q23 excluded as over-folded), stratified by `literature_density` (dense/medium/sparse) + `use_case`. Data itself is gitignored (regenerate from Supabase). Note: even their "verbatim" query_text was LLM-transformed at build time — V3's true-verbatim-intent is a distinct, untested input distribution.

### Contradictions / refinements to V3's plan

1. **"Verbatim intent → keyword-OpenAlex" carries real recall risk** (strongest finding). OpenAlex `title_and_abstract.search` is a stemmed lexical index; the R&D's directly-analogous result is S2 `/paper/search` returning **0 hits for a long NL sentence vs 25 for short keywords** (`SE/docs/FINDINGS.md:349-419`). Every arm avoided this by generating short/boolean keyword queries. **V3 has no evidence a lone verbatim NL intent retrieves usefully from OpenAlex.** Mitigations to weigh (all deferrable but the risk should be *acknowledged in the contract*): expect the OpenAlex leg to under-recall on long intents and lean on Overton's semantic leg; or cap intent length; or accept low keyword recall as a measured v1 finding. This does **not** contradict semantic-Overton — dense endpoints want verbatim NL.
2. **Semantic-Overton verbatim is well-supported, but no Overton code exists.** Arm C's "semantic third source" is **Semantic Scholar**, not Overton. Consequence: V3's Overton client is greenfield transport work; only the `SourceClient` protocol and the S2 *hardening patterns* transfer. If V3 wants a de-risked semantic backend fast, **S2 is the one with a complete, battle-tested client** — Overton has none.
3. **Two backends ⇒ DOI dedup, not source-id dedup.** The R&D's `paper_id` dedup is a single-source shortcut it explicitly flags as wrong for OpenAlex↔Overton (`SE/docs/FINDINGS.md:331-345`). *(V3 note: already built — 007's normalized-DOI guard.)*
4. **One-call-per-backend and ~25 records are internally consistent** with the R&D's transport code — no contradiction. But the R&D's *baseline* is ~15 OpenAlex requests/query; V3 v1 is deliberately ~30× cheaper and thinner. Record that the SR/RCT fanout (a prod recall feature) is being dropped.
5. **Protocol shape refinement**: don't foreclose the keyword/dense split; keep the return shape bindable for future ranking/snowball/dedup verbs.

**Uncertainties:** headline single-pass recall numbers (external slides only); exact Overton API params (never coded — source from Overton docs); whether OpenAlex `title_and_abstract.search` degrades to few-vs-zero on verbatim intent specifically (proved for S2's endpoint; OpenAlex analogue inferred from the same index class, not directly measured).
