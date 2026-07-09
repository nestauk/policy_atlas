# Plan: 015-live-search

> **Status:** rev 2 — plan-stage adversarial review adjudicated
> (Codex, 9 findings: 2 blockers · 6 majors · 1 minor, **9/9
> adopted**). Blockers: (1) prompt-text authorship pulled back to the
> lead — task 3 split into 3a (lead: `screen_v2`/`classify_v2` text +
> prior-record contract) / 3b (codex: assembly only); (2) deep
> OpenAlex HTTP arithmetic fixed — per-round per-arm CALL caps pinned
> (reformulate 4 · snowball 6 · suggest 6 · diversity 1 = 17/round),
> deep OA budget 40→50 (15 + 2×17 = 49 ≤ 50). Majors: the
> **deep-thin overlay** (any non-target deep stop while below target →
> final coverage row records `re_searched_still_thin`, task 8 + tests
> + live check) · gate consolidation corrected (Phases 2 and 6 touch
> readers → full verify; only 3 and 5 stay verify-fast) ·
> `search_backend_scope` pinned on **Plan AND Config** with compile
> copy/validation + harness backend resolution from compiled config ·
> `squery` + `min_similarity=0.3` (semantic-mode-only) added to the
> transport wire contract + assertions · **caching decided: NO cache
> in v1** (dedup guards absorb re-hits; reformulated queries are never
> identical; budgets bound repeats — cache-before-throttle stays the
> recorded seam) · task 9 → **codex** with the exact skeleton sequence
> pinned (the existing skeleton "deep profile" already means stage-2
> full-text screening — 015's deep SEARCH rounds run pre-ingest under
> the same profile axis, no naming collision, stage-2 honestly
> `skipped_no_fulltext` on live-acquired docs until 016). Minor: the
> live-check key audit greps the ACTUAL env key values (+ structural
> redaction tests), not just `api_key|sk-` labels.
>
> Rev 1 base drafted against contract **rev 3.14** (approved
> 3.12, amended 3.13–3.14 at the gate). Awaiting the plan 🛑. ADR due
> at plan confirmation (step 4):
> **ADR 0012 — depth-graded agentic search** (screen-in-the-loop as the
> one relevance surface · the depth spectrum's extensible constants
> table · fixed allocation over bandits) — capability-class decisions.
> Contract: [contract.md](contract.md); evidence:
> [v2-search-autopsy.md](v2-search-autopsy.md) ·
> [api-filter-research.md](api-filter-research.md) ·
> [overton-param-pinning.md](overton-param-pinning.md) ·
> [deep-research-validation.md](deep-research-validation.md).

Executor routing per harness.md § Agent-side model routing: default =
delegate; every `lead` mark carries a justification.

**Codex-exhaustion fallback (user, 2026-07-09 — this slice is large
enough that Codex usage may run out mid-build; NOT a blocker, never a
stall):** if Codex becomes unavailable, re-route the remaining
`codex`-marked tasks down the ladder — judgment-bearing implementation
→ **deep-reasoner**, mechanical remainder → **fast-worker**, brief-
unwritable work → **lead** — continue building, and record every
substitution in `verification.md` (the family-flip review Codex would
have provided in-line is then covered by conversation C's adversarial
lane as usual).

## Plan-pinned constants

**Transport (decisions 1/3/4/7/9):**
- `httpx.Client` sync, one per backend, `HTTP_TIMEOUT_S = 30`
  (connect+read via `httpx.Timeout(30.0)`), `User-Agent:
  policy-atlas/0.1`; OpenAlex adds `mailto` param when
  `OPENALEX_EMAIL` set. Hosts: literals `https://api.openalex.org` ·
  `https://app.overton.io`.
- Retry cap 1 per request; retryable = timeout · 429 · 500 · 502 ·
  503 · 504; backoff 2.0 s before the one retry (Overton 429 retry
  additionally waits ≥ `OVERTON_MIN_INTERVAL_S`).
- `OVERTON_MIN_INTERVAL_S = 1.2` monotonic-clock spacing on EVERY
  Overton request incl. `next_page_url` follows (the R&D bumped
  1.1→1.2 after persistent 429s; our 21-probe session ran clean at
  1.2).
- `next_page_url` follow: parse → assert scheme==https AND
  host==app.overton.io else backend error; never logged/persisted
  un-redacted.
- OpenAlex `select=` constant `OA_SELECT`: envelope sources (`id`,
  `display_name`, `abstract_inverted_index`, `publication_year`,
  `publication_date`, `doi`, `language`, `type`) + `primary_location`,
  `best_oa_location`, `open_access`, `topics`, `primary_topic`,
  `keywords`, `cited_by_count`, `fwci`, `is_retracted`, `is_paratext`,
  `ids`, `sustainable_development_goals`, `indexed_in`,
  `authorships` — test-asserted superset of everything the mapper
  reads (grants is NOT select-able; excluded per rev 3.5).
- Overton page size via `pp` (pinned live): rapid `pp=50` single page;
  deep `pp=50` paging via `next_page_url` under the run cap.
- Overton semantic wire contract *(rev 2 — contracted, now owned)*:
  `squery=<NL text>` + `min_similarity=0.3`, the pair sent **only** in
  semantic mode (task 4 wire mapping; task 10 asserts both presence in
  semantic calls and absence anywhere else).
- Keys: `OPENALEX_API_KEY` + `OVERTON_API_KEY` both required live
  (loud startup error naming the variable). Key-redaction applies to
  raised messages, logs, persisted fields (incl. `next_page_url`).

**Depth constants table (decision 13 — the extensible compile
target; one row per depth):**

| constant | rapid | deep |
|---|---|---|
| result cap / backend | 50 | 150 (whole run) |
| wall-clock | `RAPID_WALL_CLOCK_S = 30` (breach → stop remaining calls, `breadth_truncated`) | `DEEP_WALL_CLOCK_S = 150` (breach → `budget_exhausted`, thin-overlay below) |
| rounds | 1 (the fan-out) | `ROUND_CAP = 3` |
| HTTP budget — OpenAlex | 20 | 50 *(rev 2 blocker fix: 15 round-1 fan-out + 2 × 17 per-round arm cap = 49)* |
| HTTP budget — Overton | 5 | 15 (≈18 s at 1.2 s spacing — fits the wall-clock) |
| per-round arm CALL caps (rounds 2–3) | — | reformulate ≤ 4 · snowball ≤ 6 (5 fwd + 1 backward batch) · suggest lookups ≤ 6 · diversity ≥ 1 (= 17 OA-class calls) *(rev 2)* |
| generation-LLM calls | 1 (`search_queries_v1`) | ≤ 8 (1 queries + ≤3 reformulate + ≤3 suggest + escalation reuse) |

**Deep-thin overlay (rev 2, contract decision 17):** any deep stop
other than `target_reached` (short_circuit · budget · round cap) while
confident-relevant < target ⇒ the FINAL round's coverage row records
`stop_condition = 're_searched_still_thin'` (the overlay wins over the
raw stop value); owner task 8, tests task 11, live-check (f).

**Caching (rev 2 — the contract's plan-time decision): NONE in v1.**
Dedup identity guards make re-acquired hits cheap skips; reformulated
queries are never byte-identical; per-arm caps + budgets bound repeat
fetches. Cache-before-throttle (the R&D pattern) stays the recorded
seam.

**Rapid strategy (decision 14):**
- `N_QUERIES = 5` diverse keyword queries from one `search_queries_v1`
  call (mini); OpenAlex fan-out = each × {base, +SR clause, +RCT
  clause} (clause constants from V2's `_fanout.py` shape, code
  constants) ⇒ ≤ 15 OpenAlex search calls; Overton = verbatim intent +
  ≤ 2 generated NL paraphrases (same generation call) ⇒ ≤ 3 Overton
  calls.
- Validation: a generated query returning 0 results is
  counted-and-dropped (`queries_zero_result`); ALL generated
  zero → verbatim-intent fallback + summary note. Sanitizers
  (commas-in-quotes, wildcards `*?~`) run on every generated query;
  title-lookup punctuation strip on lookup queries.
- Generation failure (post-retry) → `component.failed` (a search run
  with no queries is infrastructure failure).

**Deep loop (decision 15):**
- Exemplars per round (non-accumulating, this-round-only):
  `POS_EXEMPLARS = 8` top confident-relevant + `NEG_EXEMPLARS = 4`
  most-confident not_relevant, each `{id, title, abstract[:500],
  screen_confidence}`; the scope-intent record rides every
  reformulation/suggestion prompt as the fixed anchor.
- Arm allocation per round (fixed, rev 3.10): reformulate 40% ·
  snowball 30% · suggest 15% · **diversity reserve 15%**
  (`DIVERSITY_FRACTION = 0.15`, ≥ 1 fresh intent-derived query not
  steered by exemplars) — of the round's HTTP/query budget;
  proportions are plan constants, not learned.
- Snowball: seeds = top `SNOWBALL_SEEDS = 5` confident-relevant with
  OpenAlex ids; forward (`cites:`) + backward (`referenced_works`
  batch ≤ 50 ids via `|` join), cap `SNOWBALL_RESULTS = 40`/round.
- Suggest: `SUGGEST_MAX = 10` proposals/round; grounding = OpenAlex
  `title.search` lookup then **DOI/id match when the suggestion
  carries one** (prefer id resolution, rev 3.10); ungrounded dropped +
  counted; `suggestions_grounded_screened_out` counter.
- Stopping: `TARGET_CONFIDENT_RELEVANT = 20` at
  `CONFIDENT_FLOOR = 0.7` (→ `target_reached`) · discovery-rate floor
  `SHORT_CIRCUIT_RATE = 1/50` new-confident-relevant per
  docs-screened-this-round (→ `short_circuit`) · budgets/round-cap
  (→ `budget_exhausted`) · rapid-thin escalation threshold
  `THIN_CONFIDENT_RELEVANT = 8` (one deep continuation, resumes at
  round 2 semantics).
- In-loop screening: the unmodified 014 component per round
  (incremental via NOT-EXISTS); its own budget composes
  (≤ new-docs × 3 × 2).

**Prompts + models (contract Model route):**
- `SEARCH_QUERIES_MODEL = SEARCH_REFORMULATE_MODEL =
  SEARCH_SUGGEST_MODEL = "gpt-5-mini"` (009 floor; queries-model
  swap-up is an eval-seam question). PROMPT_VERSIONs:
  `search_queries_v1` · `search_reformulate_v1` · `search_suggest_v1`
  (11th–13th product prompts, lead-authored).
- Wire models (pydantic, strict): queries
  `{queries: [str ≤120 chars] ≤5, overton_paraphrases: [str ≤300] ≤2}`;
  reformulate same shape; suggest `{papers: [{title ≤200, year?,
  doi?}] ≤10}`. NUL scrub + M10 sanitization at assembly.
- Prompt-input restructure (revs 3.7/3.8): screen payload gains
  `title_source`; classify property priors = `record_type`,
  `source.type`, `organisation_type`, `indexed_in`, `title_source`,
  `abstract_source` (each ≤500 chars, control-stripped); classify
  label priors = `source_tag` reads (all non-classify asserters,
  `{tag, tag_type, asserted_by}`, ≤ 30 records, tag ≤200 chars) —
  `_topic_labels` retired; keywords provably absent (test). Prompt
  versions bump as provenance: `screen_v2` wire-compat text edit ·
  `classify_v2`.

**scope_filters grammar (decision 18; validated vocabularies from the
research + pinning records):**
- Shape `{shared?, openalex?, overton?}`; fail-closed on unknown
  keys/values/backend-scope mismatch (DirectiveError, 010 grammar
  precedent).
- shared: `published_after/before` (ISO date) · `sdgs` (ints 1–17 →
  OA IRIs / Overton full-label constants).
- openalex: `types` (⊆ 28-value constant, re-verified via
  `group_by=type` at build) · `languages` (ISO 639-1) ·
  `exclude_retracted`/`exclude_paratext` (bool) · `oa_status`
  (⊆ 6-value constant) · `author_affiliation_countries` (ISO).
- overton (single-valued each): `publisher_type`
  (government|think tank|igo|other) · `publisher_country` (name
  string) · `publisher_region` (⊆ 10-group constant) · `language`
  (3-letter code).
- Executed wire params → coverage-record `scope_filters` (per
  backend) + every `search.executed` payload.

**Config/plan surface** *(rev 2 — as-built fit: `Plan` and `Config`
are separate models and `run_harness` currently ignores `Config` for
the backend default, `plan.py:57-75` / `harness.py:631-635`)*:
`search_backend_scope` (`academic_only|grey_lit_only|both`, default
`both`) lives on **both `Plan` and `Config`**; `compile` copies and
validates it (unknown → ValidationError, fail-closed before
execution); `run_harness` resolves the default backend list from the
COMPILED config whenever the `search_backends` parameter is not
explicitly passed. Depth directive `context["search"]["depth"]`
(`rapid` default | `deep`) parsed fail-closed in acquire.

**Migration 15:** `ck_scov_stop_condition` widens to
{breadth_truncated, re_searched_still_thin, error, short_circuit,
budget_exhausted, target_reached}; table count stays 25; roundtrip
both DBs. **pyproject:** `httpx>=0.28,<1` declared (declaration-only
promotion; lock regen must show zero new packages).

**Coverage/counting invariants (per acquire round = one run = one
coverage record):** `acquired + already_acquired + skipped_unusable ==
results_returned` holds per backend per round; Overton semantic-mode
`total_results` is NEVER read into counts (rev 3.3 client rule);
summary adds per-round `cost_per_marginal_confident_relevant`.

## Tasks

**Phase 0 — build-open baseline (full `make verify`)** — operator/lead.

**Phase 1 — gated surfaces (full `make verify` gate)**
1. Migration 15 (stop-condition widen) + `pyproject` httpx promotion +
   lock regen (verify zero new packages) + schema constants.
   — **lead** *(gated schema+deps surfaces; migration authorship lead
   per slice precedent)*

**Phase 2 — prompts + wire models**
2. `search_queries_v1` · `search_reformulate_v1` · `search_suggest_v1`
   prompt surfaces + strict wire models (new `search_prompts.py`).
   Pins: intent as id-keyed data record; diversity instruction for the
   5 queries; graded-exemplar framing for reformulate ("more like /
   never like", anchored to the intent record); suggest asks for
   verifiable identity fields (title/year/DOI). — **lead**
   *(prompt-bearing, AGENTS.md)*
3a. `screen_v2` / `classify_v2` **prompt TEXT + prior-record
   contract** (rev 2 blocker fix — prompt-bearing is lead-ONLY, never
   delegate-then-review): the exact prompt-text deltas for
   `title_source`, the property-prior additions, and the tag-layer
   label-prior record framing (`{tag, tag_type, asserted_by}` as
   data), authored in full before 3b starts. — **lead**
   *(prompt-bearing, AGENTS.md)*
3b. Assembly implementation against 3a's authored text: screen payload
   plumbing, `provider_priors` split (property vs label priors),
   `_topic_labels` retired, batched per-run `source_tag` read, bounds
   at assembly, version strings. Zero prompt-text authorship — any
   needed wording change escalates to lead. — **codex**
   *(judgment-bearing multi-file plumbing against a fully-authored
   spec)*

**Phase 2 gates FULL `make verify`** *(rev 2 fix: task 3b changes
classify/screen prompt-input readers — reader contact mandates the
full gate)*.

**Phase 3 — live transport (verify-fast gate; genuinely new modules,
no schema/reader contact)**
4. `search_live.py`: httpx clients, limiter, retry/redaction
   (status+host-only errors, key-scrub), sanitizers, `OA_SELECT`,
   filters→wire-params mapping, `pp` + validated `next_page_url`
   paging, per-depth caps, no-citation-floor guarantee, injectable
   fetch seam. — **codex** *(the hardening core; machine-verifiable
   via transport-stubbed tests)*
5. Protocol growth: `caps` flags + `fetch_citations` /
   `fetch_references` / `lookup_title` verbs — live impls (OpenAlex
   native; Overton `has_snowball=False`) + fixture-backend verb impls
   over small fixture pages. — **codex** *(protocol seam
   implementation; shape pre-pinned by contract decision 16)*

**Phase 4 — mapping-layer deltas (full `make verify` gate —
ingest-adjacent: snapshot/tag writes change)**
6. Decision-20 retention/tags/title: retain-key additions (both
   backends), English-first title + `title_source` + native-title
   retention, series → `methodological_structural` tags
   (`_provider_tags` grows per-assertion tag_type), `source_tags` →
   tags, keywords-never-tagged pin. — **fast-worker** *(exact
   enumerated spec from the contract)*

**Phase 5 — rapid strategy + directives (verify-fast gate)**
7. `search_loop.py` rapid path: generation call, fan-out builder
   (variants + paraphrases), validation + fallback, wall-clock stop
   (`breadth_truncated`), summary counters; depth directive parse;
   `scope_filters` grammar validation + compile;
   `search_backend_scope` Config field + compile. `acquire_sources`
   grows the strategy call while keeping mapping/dedup/coverage
   machinery untouched. — **codex**

**Phase 6 — deep loop + escalation (full `make verify` gate — rev 2
fix: the loop READS effective screening rows for steering)**
8. `search_loop.py` deep path: graded-exemplar assembly (per-round,
   negatives, intent anchor — read via the effective-screen helper),
   fixed allocation incl. diversity reserve + the per-round arm CALL
   caps (rev 2), reformulate/suggest calls, snowball via task-5 verbs,
   grounding (id-preferred) + counters, stopping (four exits → three
   stop values) **+ the deep-thin overlay** (rev 2: non-target stop
   below target ⇒ final coverage row `re_searched_still_thin`),
   per-round budgets + `DEEP_WALL_CLOCK_S`. — **codex**
9. Skeleton sequencing *(rev 2: re-routed fast-worker → codex — the
   brief is not self-sufficient: the as-built skeleton's "deep
   profile" already means the stage-2 full-text screening leg,
   `skeleton.py:684-766`)*. Pinned sequence: ONE profile axis —
   the deep profile sets search depth=`deep` AND keeps its existing
   stage-2 leg; deep SEARCH rounds (acquire↔screen stage-1) run
   **pre-ingest**; the existing `ingest_full_text` fixture replay +
   stage-2 screen leg follow unchanged (live-acquired docs carry no
   full text until 016 → stage-2 counts them `skipped_no_fulltext`,
   honestly); rapid profile = single rapid acquire + stage-1 screen +
   `THIN_CONFIDENT_RELEVANT` escalation (one deep continuation,
   resuming at round-2 semantics); per-mode wall-clock logging;
   live-mode key checks (both keys, loud). — **codex**

**Phase 7 — tests (full `make verify` gate — step-6 exit adjacent)**
10. Bulk suites from the contract's Acceptance enumeration: transport
    matrix (sanitizers · limiter incl. paging · timeout-on-every-
    request · retry set · shape validation + `next_page_url: false` ·
    redaction · select-superset · no-citation-floor · zero-egress
    extension), mapping deltas, grammar fail-closed matrix, migration
    roundtrip both DBs, escalation, counting invariants per round.
    — **fast-worker**
11. Judgment suites: scripted-backend loop tests (round sequencing,
    exemplar grading/anchoring/non-accumulation, allocation incl.
    reserve, all four stops, per-round coverage rows), prompt-assembly
    tests (both prior kinds, asserter visibility, keywords absent,
    bounds, instruction-shaped tag/series values stay data),
    injection fixtures (reformulation/suggestion steering),
    acquire-writes-no-screening-rows, grounding matrix, **the
    deep-thin overlay cases** (rev 2: each non-target stop below
    target → `re_searched_still_thin`; at/above target → the raw stop
    value) and **`squery`+`min_similarity` wire assertions** (rev 2).
    — **codex**

**Phase 8 — records + live check (step-6 exit: full `make verify`)**
12. `deferred.md` rewrite (discharged: live SearchBackend · Arm-B ·
    thin-base trigger · per-backend query-mode notes; the full rev-3.x
    seam list per contract § Verification) + knowledge concepts +
    components §1+§2 flow-back + `log.md` + `verification.md` + the
    decision-11 live check (script below). — **lead** *(live-run
    adjudication, spec flow-back and records; per-slice precedent)*

## Live-check script (task 12 detail — decision 11 pin)

Dev DB `alembic upgrade head` first (012 lesson). Then:
(a) live rapid run, real intent — generated queries in events, envelope
spot-checks, tags bounded, coverage `adequate`, wall-clock vs 30 s;
(b) immediate re-run — dedup counts, no dup snapshots;
(c) Overton spacing ≥1.2 s observed; key audit against the **actual
env key VALUES** (script reads both keys from env and greps logs, DB
dumps and verification artifacts for the literal values — rev 2: label
greps like `api_key|sk-` miss raw key material) + structural redaction
tests green;
(d) comparative probe: verbatim intent vs generated queries result
counts per backend (the decision-2 risk, measured with mitigation);
(e) live deep run — per-round acquire↔screen in events + per-round
coverage rows, exemplar-seeded reformulation visible in traces,
snowball + grounded suggestions landing through dedup, stop condition +
wall-clock vs 150 s + cost (in-loop screening latency reported
separately) + `cost_per_marginal_confident_relevant`;
(f) escalation exercised once (narrow intent → deep continuation →
`re_searched_still_thin` if still thin);
(g) one filtered rapid run (dated + typed directive both backends —
wire params in events + coverage `scope_filters`, counts consistent);
(h) rapid-profile chain smoke: acquire → screen → classify → appraise →
characterise → synthesise (§9 minus ingest, flow-back-noted) — new tag
rows visible in characterise distributions, classify seeing tag-layer
priors in traces, artefact minted; mini-class over ~50 envelopes +
one rapid synthesise (low single-digit dollars);
(i) residual pins: `source_type=igo/other` already verified (rev 3.4) —
confirm one derived SDG label live in a filtered run; OpenAlex 28-type
enum re-verified via `group_by=type`.

## Review-stack sizing (for conversation C)

Per [[review-stack-economy]]: /code-review medium, per-angle diff
scoping (exclude fixture data + probe scratch), one security lane
(headline: key hygiene under loop volume + the next_page_url exception
+ injection posture on reformulation/suggestion surfaces),
contract-verifier Opus, Codex adversarial, live-trace CONTENT review
lane. ≤ 250K reasoning / ≤ 500K fast-worker.

## Gate consolidation summary (3.11-retro rule; corrected rev 2)

Full `make verify`: Phase 0 baseline · Phase 1 (schema+deps) ·
**Phase 2** (task 3b touches classify/screen prompt-input readers) ·
Phase 4 (ingest-adjacent writes) · **Phase 6** (the loop reads
effective screening rows) · Phase 7 · Phase 8 exit. Phases **3 and 5**
gate on `make verify-fast` (genuinely new modules, no schema or reader
contact).
