# ADR 0012 — Depth-graded agentic search with screen-in-the-loop

**Status:** Accepted — 2026-07-09 (Shabeer Rauf; task 015 contract rev 3.12,
amended 3.13–3.14 + plan rev 2). The round-by-round decision trail lives in the
task 015 contract's revision history (revs 1–3.14, shaped across ~18 adjudicated
rounds: seven user gate calls, a V2 search autopsy + PR #184 R&D analysis, an
API-filter research round with a live Overton param-pinning session, a
three-stream external validation round, and two Codex adversarial reviews).

## Context

Task 007 built the `SearchBackend` seam over fixture replay; live search is the
header-class-1 capability v3.0 cannot function without. The V2 lesson (a single
LLM boolean query is unstable/low-recall) and the field's strongest transport
lesson (lexical indexes starve on long verbatim natural language) both argue
that live transport alone would under-recall. The user folded the deferred
search-capability seams into the slice at the contract gate, then unified the
loop's relevance judgment with the production screening component.

## Decisions

1. **Depth is a thoroughness gradation with an extensible vocabulary** — the
   `"acquire"` component reads `context["search"]["depth"]` (`rapid` default |
   `deep`, fail-closed); every depth-dependent constant (result caps,
   wall-clock, round cap, HTTP budgets) lives in a per-depth table, so future
   gradations (really-rapid → long-running report-grade, the recorded
   tool-wide depth/time-budget seam) are a constants row + profile, never a
   new mechanism. Wall-clocks are per-depth, calibrated to Asta's two modes:
   rapid ≈ 30 s (breach → `breadth_truncated`), deep ≈ 2–3 min (breach →
   `budget_exhausted`).
2. **Rapid = LLM multi-query fan-out; no single query is ever load-bearing** —
   one `search_queries_v1` call yields ~5 diverse keyword queries, each fanned
   into base/SR/RCT variants on OpenAlex (keyword-lexical idiom); Overton
   takes the verbatim intent + ≤2 generated NL paraphrases (semantic idiom).
   Every generated query is result-validated (the SIGIR reproduction's
   decisive lever); all-zero falls back to the verbatim intent, loudly.
3. **Deep = acquire↔screen rounds; the loop's judge IS the production
   screen** — no shadow relevance judgment exists anywhere in acquire.
   Steering reads persisted 3-rep consensus rows via the effective-screen
   helper; every judgment that steers the search is also the durable
   admission decision (one calibration, one eval surface — convergent with
   PaperQA2/Undermind practice; MetaSyn measures screening as the field's
   bottleneck). Round cap 3 (measured plateau at 2–3, harm past 3–4);
   reformulation context is graded exemplars (negatives included) anchored to
   the FIXED original intent, strictly per-round non-accumulating; a fixed
   diversity reserve runs un-steered queries each round (the
   screener-self-reinforcement mitigation).
4. **Fixed arm allocation, not a bandit** — reformulate/snowball/suggest/
   diversity run on fixed per-round call caps; Thompson sampling was cut (no
   shipped-system precedent; a ≤3-round loop leaves a 3-arm bandit in
   permanent cold-start) and survives only as an eval-gated seam that must
   beat round-robin.
5. **Stopping is screen-informed with honest vocabulary** — confident-relevant
   target (`target_reached`) · discovery-RATE collapse (`short_circuit`) ·
   budgets incl. round cap (`budget_exhausted`), with the thin overlay: any
   non-target stop below target records `re_searched_still_thin` (the 007
   vocabulary, finally fired). The thin-base re-search trigger dissolved into
   this rule; rapid-thin runs escalate to one bounded deep continuation. The
   coverage verdict is coverage-adequacy, never a recall guarantee (a
   calibrated recall estimate is a recorded seam).
6. **Transport is first-party httpx; no provider SDKs** — sync `httpx.Client`
   per backend (declaration-only dependency promotion from the openai SDK's
   transitive), explicit timeouts, retry cap 1 over {timeout, 429, 5xx},
   Overton 1.2 s limiter on every path incl. the one guarded
   provider-URL exception (host-validated `next_page_url` paging), redacted
   errors (status+host only — V2's key-leak vector closed structurally),
   `select=`-bounded OpenAlex requests, no citation floor (a silent recall
   filter V2 applied implicitly; rejected for a recall-first tool).
7. **The directive grammar is empirically pinned** — `scope_filters` admits
   only wire-verified vocabularies (21-probe Overton pinning session +
   live-verified OpenAlex enums), with self-describing geography keys
   (`author_affiliation_countries` / `publisher_country|region`) because no
   search API expresses study geography (extraction-owned, recorded seam).
   Overton keys are single-valued (no multi-value OR form exists on the
   wire). `search_backend_scope` (Plan+Config) is the field driving the
   007-built `search_backends` parameter.
8. **The tag layer is the uniform label-prior surface** (spec-confirmed:
   provider label signals materialise at acquire as provenance-classed tag
   rows) — classify's label priors read from `source_tag` with
   `{tag, tag_type, asserted_by}` visible; property priors (record_type,
   source typing, `indexed_in`, `title_source`) stay direct M10 fields.
   English-first Overton titles carry `title_source` provenance; the
   publisher's document series materialises as
   `methodological_structural × overton` tag rows beside classify's own.

## Consequences

- Egress grows by transport + three generation surfaces + in-loop `screen_v1`
  volume; one migration widens `ck_scov_stop_condition` by three values; a
  deep run writes one coverage row per acquire round.
- Every run terminates in synthesise regardless of depth (ADR 0009 /
  knowledge: synthesise-is-run-terminus); search depth composes with the
  existing profile axis — deep search rounds run pre-ingest, the stage-2
  screening leg unchanged.
- The mini-class screen's judge quality is the loop's single biggest
  un-eval'd dependency — an eval-slice must-measure gate before loop-steered
  "adequate" is trusted.
