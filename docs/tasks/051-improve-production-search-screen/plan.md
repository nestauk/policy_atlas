# Plan: 051-improve-production-search-screen

Problems P1–P9, decisions D1–D20, the terms and the surfaces table are defined in
[contract.md](contract.md). This plan cites them and adds nothing to scope. D18 items
have no phase.

> Plan approved (before implementation): 2026-10-09 · owner, after the Codex findings were
> folded in, the tag-and-keep-prompts decision (D11) and the tutorial update (D20).
> Plan-stage adversarial review: ran 2026-10-09 (read-only Codex brief), 18 findings,
> all folded in. The two blockers changed the contract (amendments in its status line):
> filter variants against the fixed OpenAlex budget (S4, S5, D12/D13) and Overton's
> internal paging against the logical-call accounting (S3, D12). The rest changed this
> plan: `results_returned` keeps its raw meaning (S3); an Overton interleave (S1, S3);
> `wire_params` on the semantic verb (S2); Phase 3 split in two; an eval-only
> fixed-repetition runner for majority experiments (S7); the `search_prompts.py` re-pin
> in Phase 3a; the policy replay suite named (Phase 1); the fixture backends named
> (D19); `excluded_ids` on `score_forward` (S1); Phase 0 split into the baseline, the
> probes and the fixture export, with Phase 2 dependent on the probes; the three
> logical-count tests and the D9 no-cross-pool test (Phase 3a); the deleted and
> retained tests enumerated (Phase 3b); the SSE non-change asserted (Phase 3b).

Executor marks follow AGENTS.md § Agent-side model routing. Every `lead` mark carries
its reason.

**Verify gates.** Full `make verify` at Phase 0a (build-open baseline), after Phase 3b
(acquire persists records and the runner changes: ingest-adjacent; Phase 3a gates on
`make verify-fast` and shares 3b's full gate) and at Phase 8 (step-6 exit). Phases 1,
2, 4, 5, 6 and 7 gate on `make verify-fast` plus the named tests; Phases 3a, 4 and 6
also run `make prompt-guard` after their re-pins. Two checkouts share the test database
(memory note): check that no other `pytest` is running before each gate.

**Order.** Phase 0a first. Phases 0b (probes) and 0c (fixture export) are independent of
each other. Phase 1 needs 0c. Phase 2 needs 0b (the accepted filter keys and the
confirmed Overton shapes go into its brief). Phase 3a needs 1 and 2; 3b needs 3a.
Phases 4, 5 and 6 are independent of each other and need 3b. Phase 7 needs everything
but 8.

## Decisions fixed here (lead seam design)

S1. **One pure module for the two pools: `sourcing/pool.py`.** No I/O, no database.
It mirrors the experiment code the contract names, function for function:

- `PaperCandidate` (frozen dataclass): `record` (the raw OpenAlex work), `origin`
  (`QueryOrigin`), `seed_rank` (position in the interleaved seed list, or a large
  sentinel), `inset`, `coupling`, `wcoupling`, `forward_rank`, `cited_by_count`,
  `specificity`. `openalex_id` and `doi` are properties over `record`.
- `interleave(lists: list[list[dict]], key) -> list[dict]` — rank round-robin across
  result lists, first occurrence by `key` wins (the experiment's `interleave_ids` and
  today's `acquire._interleave`, which moves here). Used for the OpenAlex seed lists and
  for the three Overton result lists.
- `count_references(seeds: list[dict]) -> Counter[str]` — how many seeds cite each
  short work id, seeds included (`snowball_recall.count_references`).
- `backward_targets(counts, seed_ids, n) -> list[str]` — the `n` most-cited ids not in
  the seed set, in count order, stable on ties by first appearance.
- `forward_seeds(seeds, counts, *, top, max_cites) -> list[str]` — the `top` seed ids
  with the most in-set citations among seeds with `cited_by_count <= max_cites`.
- `score_forward(citing: list[dict], seed_ids: set[str], counts, *, excluded_ids:
  set[str]) -> list[PaperCandidate]` — coupling and weighted coupling
  (`sum(log2(1 + counts[s]))` over cited seeds) per citing work, ranked by
  `(-wcoupling, -coupling, forward_rank)`, excluding `seed_ids` and `excluded_ids`
  (the backward candidates).
- `paper_candidates(seeds, backward, forward, counts) -> list[PaperCandidate]` and
  `rank_papers(cands) -> list[PaperCandidate]`: `specificity = (inset + coupling) /
  log10(cited_by_count + 10)`, order `(-specificity, -wcoupling, -inset, seed_rank)`
  (`snowball_recall.candidates` and `rank(..., "specific")`).
- `normalised_title(text) -> str` (lower-case, punctuation and whitespace collapsed),
  `policy_key(record) -> str` (the normalised title when non-empty, else
  `policy_document_id`), `dedupe_policy(records) -> list[dict]` keeping the first copy
  in rank order (D8).
- `count_policy_cites(results) -> Counter[str]` over `cites.policy` ids,
  `landmark_targets(counts, result_ids, n) -> list[str]`,
  `rank_policy(results, landmarks, counts) -> list[PolicyCandidate]` with
  `specificity = inset / log10(citation_count + 10)`, ties by the result's position
  (the interleaved order) and landmarks after results at equal specificity
  (`policy_rank.order(..., "specific")`).
- `country_predicate(record, countries) -> bool` over `authorships[].countries` (D13,
  the local check for citation-found papers under a filter variant split).
- Module constants (D3–D5, D8): `SEEDS = 200`, `KEYWORD_PER_CALL = 200`,
  `SEMANTIC_PER_CALL = 50`, `BACKWARD_EXPAND = 200`, `RESOLVE_BATCH = 50`,
  `FORWARD_TOP = 20`, `FORWARD_MAX_CITES = 300`, `FORWARD_IDS_PER_CALL = 100`,
  `FORWARD_PAGES = 10`, `FORWARD_KEEP = 200`, `OVERTON_DOCS = 400`,
  `OVERTON_LANDMARKS = 15`.

S2. **Backend verbs.** `acquire.SearchBackend` (Protocol) and `BackendCaps` gain:
`search_semantic(text, *, wire_params, max_results) -> list[dict]` (flag
`has_semantic`; `wire_params` is the semantic-reduced filter set of S5),
`lookup_ids(ids, *, wire_params) -> list[dict]` (batched by `RESOLVE_BATCH`, same
`select` as `search`, the wire filter parts appended; flag `has_id_lookup`),
`fetch_citing(ids, *, wire_params, max_results) -> list[dict]` (`cites:` filter,
`FORWARD_IDS_PER_CALL` ids per request, one page of 200 per logical call; flag
`has_forward`), and for Overton `fetch_by_id(record_id) -> dict | None`
(`documents.php?policy_document_id=`, flag `has_fetch_by_id`). Backends without a
flag raise `NotImplementedError` as the existing unsupported verbs do.
`OvertonLiveBackend._search` sends `sort=relevance`; `sort` joins
`_PROTECTED_OVERTON_PARAMS`; its internal paging is unchanged and it returns the
number of pages it fetched on the backend (`last_pages`) so the executed call can
record it. The semantic call sends `search.semantic=<text>` with `select=OA_SELECT`,
`per-page=50`, and the accepted filter parts. All through `_request_json` (timeouts,
limiter, retry cap, redaction); `search_semantic` enforces its own 1 s minimum
interval. `CallVerb` gains `search_semantic` and `fetch_by_id`; `QueryOrigin` gains
`semantic` and `landmark`.

S3. **The single pass in `run_search`, and the pool hand-off to acquire.**
`run_search` keeps its signature. Inside: parse the directive; generate queries (one
call); plan and execute, through `execute_call` as today (one logical call each), per
filter variant the 15 keyword calls and the 8 semantic calls (the latter skipped with
`semantic_skipped` when S5 says so), and the 3 Overton searches (each with
`max_results = ceil(OVERTON_DOCS / 3)`, paging inside the backend); OpenAlex seeds =
`interleave` of the keyword and semantic lists, first `SEEDS`; backward:
`count_references`, `backward_targets`, `lookup_ids` in batches of 50 (each batch one
`execute_call`, verb `fetch_references`, origin `snowball_backward`); forward:
`forward_seeds`, `fetch_citing` per page (verb `fetch_citations`, origin
`snowball_forward`), `score_forward` with the backward ids excluded; under a variant
split the resolve and forward calls carry the non-country filters and
`country_predicate` drops citation-found papers outside the plan's countries;
`paper_candidates`, `rank_papers`. Overton: `interleave` of the three result lists,
`dedupe_policy`, `count_policy_cites`, `landmark_targets`, `fetch_by_id` per landmark
(verb `fetch_by_id`, origin `landmark`), the `source_country` post-filter on
landmarks, `rank_policy`. Then
`acquire.acquire_sources(conn, ..., executed_calls=..., pools={"openalex": [...],
"overton": [...]}, caps={"openalex": papers_cap, "overton": policy_cap})`, where each
pool is the ranked list of `(record, origin)` for the unique works followed by every
duplicate raw occurrence of a work already in the list (same id or DOI), so that
`acquire_sources` sees every returned record: it maps, dedups with `is_new` in pool
order (the duplicates count as `already_acquired` as within-stream duplicates do
today), persists and embeds each pool up to its cap, and keeps `results_returned` as
the raw per-call count from `executed_calls`. The `by_backend` sum invariant and the
meaning of every count are unchanged. `_Candidate` gains `origin`; the
`source.acquired` payload gains `query_origin`; `record_cap_per_backend`, the
targeted-verb exemption and `acquire._interleave` go. `count_existing_rounds` keeps
its one remaining caller (`run_search`'s `round_index`).

S4. **`DEPTH_CONSTANTS`** becomes
`{"rapid": {"papers_cap": 100, "policy_cap": 50, "call_budget": {"openalex": 45,
"overton": 30}}, "standard": {200, 100, same}, "deep": {400, 200, same}}` (D1, D12).
The OpenAlex budget is applied per filter variant (`45 × len(variants)`), the Overton
budget as is. `SearchDepth`, `parse_search_directive`, `validate_scope_filters`,
`_filter_variants` and `_with_filter_variants` are unchanged.

S5. **Semantic filters, fail-closed (D13).** A module constant
`SEMANTIC_ACCEPTED_FILTER_KEYS: frozenset[str]` in `search_loop.py`, filled from the
Phase 0b probe. `_semantic_filter_parts(validated) -> (parts, rejected_keys)`: the
accepted keys' wire parts; when `rejected_keys` is non-empty the semantic calls are not
planned and the coverage record's `scope_filters` payload carries
`"semantic_skipped": [keys]`. Under a variant split the semantic calls run per
variant like the keyword calls (the country key is either accepted, and sent per
variant, or rejected, and the semantic leg is skipped).

S6. **Adaptive vote (D10).** In `assess/screen.py`: `decide_stage1(first:
ScreenRepWire | None, second: ScreenRepWire | None) -> Stage1Decision(status,
confidence, flags)` implementing the contract's truth table and confidence formula; a
pure function with a parametrised test over every row. `_run_stage1_reps` becomes
`_run_stage1_calls(docs, *, screening_backend) -> (outcomes_by_doc, retries, usage)`:
batch 1 submits one call per document through the executor with the existing budget
and one-retry rule; batch 2 submits one call for each document whose batch-1 reply is
valid and `not_relevant`; outcomes per document are the one or two attempts in order.
`_run_stage1` calls `decide_stage1` and writes the row and event as today (`reps`
lists the attempts). `SCREEN_REPS` and `SCREEN_QUORUM` are deleted (their only
readers are `screen.py` and the screening eval); `MAX_CONCURRENT_STAGE1` stays; the
budget maximum is `2 × docs × (1 + SCREEN_RETRY_CAP)`. `screen_prompt.py`:
`SCREEN_MODEL = "gpt-5.6-luna"`, `SCREEN_PROMPT_VERSION = "screen_v4"`,
`SCREEN_SYSTEM_PROMPT` = the text of `scripts/evals/screening/prompts/screen_v4.txt`
byte for byte; the module docstring's "consensus over `SCREEN_REPS`" sentence and the
two comments in `acquire.py` and `search_loop.py` that cite `SCREEN_REPS` are
reworded. Stage 2 untouched.

S7. **Screening eval follows (D10).** `scripts/evals/screening/vote.py`: `combine_reps`
keeps the majority rule for `--reps N` experiments with the quorum literal `2` and a
docstring naming it the historical production rule; `combine_adaptive(attempts)`
delegates to `decide_stage1`. `checks/run_screen.py`: `--vote {majority,adaptive}`
(default `adaptive`); `adaptive` runs the production `_run_stage1_calls`; `majority`
runs an eval-only `_run_fixed_reps(docs, *, reps, backend)` in `run_screen.py` that
submits `reps` independent calls per document through the production backend's
`screen_envelope` with the same executor width and retry rule, so `--reps N` keeps
its meaning; `use_settings` stops touching `SCREEN_REPS` and its production-reset
test covers model, prompt and effort only. A test proves two runs in one process
cannot inherit the vote mode. `analyse_runs.py`'s replay rules are unchanged.

S8. **Runner and loop deletion (D11).** Delete the classify-pop gate block and
`_search_round_continues`; delete the `search_loop` imports it used
(`count_existing_rounds` stays imported only where used). In `search_loop.py`:
`finalise_deep_stop`, `evaluate_deep_stop`, `new_confident_relevant_for_run`,
`docs_screened_from_payload`, `StopDecision`, `ArmName`, the arm constants, the
exemplar reader, `_screened_records`, `_exemplar` and the round-2 branch go.
**Kept:** in `search_prompts.py` the `ReformulatePayload` and `SuggestPayload`
dataclasses, `ExemplarRecord`, the reformulate and suggest message builders and wires;
in `search_generation.py` the `reformulate` and `suggest` backend methods;
`SEARCH_REFORMULATE_MODEL` and `SEARCH_SUGGEST_MODEL` set to `gpt-5.6-luna`; their
unit tests in `test_search_wire.py` and the generation tests. `confident_relevant_count`
and `THIN_CONFIDENT_RELEVANT` stay (contingency hook). **Restore point:** Phase 0a tags
its commit `search-round-loop-last`; ADR 0038 and `docs/deferred.md` carry the recipe. `search_coverage_record.stop_condition` is written as
`completed` or `error` only. The frontend's `runProgress.ts` is not edited: a one-pass
run emits one acquire and one screen entry with `round_index` 1 and renders without a
round label; historical multi-round runs keep rendering.

S9. **Eval checks (D17).** `checks/engine.py`: `run_one_query` runs `run_search` once
and, when `screen=True`, `screen_sources` once; the docstring's round paragraph goes;
`_RecordingBackend` proxies the four new verbs and records their calls (the wrapper
change lands in Phase 2 with the verbs; the engine change in Phase 5).
`checks/production_recall.py`: `screen = True` at every depth, metadata keys
`papers_cap`, `policy_cap`, `call_budget`, `screening`; the printed banner likewise.
`history.py` unchanged. A test in `scripts/evals/search/tests/test_measure.py` proves
`_run_depth("rapid")` sets `screening=True`.

S10. **App text (D15).** `planVocabulary.ts`: `SEARCH_SCOPE_RECORD_CAP` becomes
`{rapid: {papers: 100, policy: 50}, standard: {papers: 200, policy: 100}, deep:
{papers: 400, policy: 200}}`; the hint lines read `Focused: up to 100 papers and 50
policy documents`; `planVocabulary.test.ts` and `PlanDocument.test.tsx` updated to the
new strings. `planner_prompt.py` thoroughness section: the three caps sentences and
the three option subs carry the pairs ("up to 100 papers and 50 policy documents");
nothing else in the prompt changes; re-pinned.

S11. **Docs (D16, D11).** ADR 0038 `single-pass-search-and-adaptive-screen.md`:
context (the measurements), decisions (D1–D13 in ADR form), supersedes ADR 0012
decisions 1, 3, 4, 5 and amends ADR 0011 decision 1, consequences (egress volume,
historical stop values, the parked contingency, the `search-round-loop-last` tag and
the restore recipe). `components.md` §1 as-built
paragraph and §2 judge sentence rewritten. `docs/specs/log.md` one line.
`docs/deferred.md`: discharge the record-cap seam, the multi-round runner entry and
the Overton sort bug; add the relevance reserve, similarity damping, the reformulation
contingency (with the +3.9 measurement and the code's commit), seminal-decile scoring,
removed-title records, the `source_country` plan option.

S12. **Test fixtures (Phase 0c).** One script,
`scripts/evals/search/experiments/export_test_fixtures.py`, deterministic, reads the
experiment caches and writes:
- `backend/tests/data/pool_fixture.json`: for one mini-set review (the loneliness
  review), the Luna run's seeds trimmed to the first 60, their `referenced_works`
  trimmed to the 100 most-cited ids, the resolved backward works for those ids, the
  first 80 citing works of the forward cache, each record reduced to the `OA_SELECT`
  fields minus `abstract_inverted_index`, plus `expected_order`: the ids in the order
  the experiment's `rank(candidates(payload), "specific")` gives on that trimmed set
  (computed by the script by calling the experiment functions).
- `backend/tests/data/policy_replay/<slug>.json` for the three task 049 questions
  (obesity, decarbonising heating, early years attainment): the three result lists
  trimmed to 40 documents each with `cites.policy`, `citation_count`, `es_score`,
  `source.country`, titles (two deliberate duplicates by title and one titleless
  record added), the 15 landmark records, and `expected`: the interleaved order, the
  deduplicated list, the landmark ids, the `specific` order, the UK-only post-filter
  result, and the first 50 after the cut, each computed by the experiment's functions.
No abstract, no credential, no full text enters a fixture. The script's docstring
names the source cache paths and the trim rules so the fixtures can be rebuilt.

## Phase 0a — Build-open baseline and the design-phase commit — `lead` (inline)

Full `make verify` on the branch. Then the design-phase commit: the exploration
artefacts named in the contract's § Deliverable (explicit paths, never `-A`), the
housekeeping move (the `git mv` renames and the path updates already staged by the
move), `contract.md`, `rubric.md`, `plan.md`, `notes.md`. Then
`git tag -a search-round-loop-last -m "last commit on which the task 015/029 round loop runs end to end; restore recipe in ADR 0038"`
on that commit (the tag is pushed with the branch; pushing stays the owner's). One
command sequence, nothing to brief.

## Phase 0b — Live probes — `lead`

Needs the keys in `backend/.env` and the judgment of what the responses mean. One
script, `scripts/evals/search/experiments/probe_051.py`, run from the repository root:
(a) OpenAlex `search.semantic` with each filter key `_OPENALEX_FILTER_KEYS` emits, one
request per key with a harmless value, at 1 s intervals, noting 200 or 400 per key;
(b) Overton `documents.php` with `sort=relevance`, confirming `es_score` descends and
the first result differs from the date order; (c) Overton
`documents.php?policy_document_id=<id>` for one id from (b), confirming one record
with `cites.policy`. The script writes sanitised request and response excerpts (no
key, no full text) to `backend/tests/data/probes_051/` and a table of accepted and
rejected keys; the table and the chosen `SEMANTIC_ACCEPTED_FILTER_KEYS` go into
`verification.md` § Probes. Phase 2 is briefed only after this lands.

## Phase 0c — Test fixtures: S12 — `lead`

Reads private caches and decides what enters the repository (public-safety judgment).
Done when the script exists, runs twice to identical files, the fixtures carry their
`expected_*` fields, and a one-line check in the script asserts each expected order
equals the experiment function's output on the trimmed data. Commit.

## Phase 1 — `sourcing/pool.py` and its tests: S1, D4–D6, D8 — `codex`

Pure functions with a machine-verifiable done: the fixtures of Phase 0c are the
oracle. The brief carries S1 verbatim, the two experiment modules as reference, and
the fixture paths and schemas.

Done when:
1. `sourcing/pool.py` exists with the S1 functions and constants, Google-style
   docstrings in plain language, no imports beyond the standard library and the
   `QueryOrigin` type.
2. `backend/tests/evidence_search/sourcing/test_pool.py`: on `pool_fixture.json`,
   `rank_papers` reproduces `expected_order`; `interleave` round-robins by rank and
   keeps the first occurrence; `count_references` counts seeds; `backward_targets`
   excludes seeds and takes the top `n` stably; `forward_seeds` honours `top` and
   `max_cites`; `score_forward` excludes seed ids and `excluded_ids` and orders by
   weighted coupling; `normalised_title` on the contract's cases (absent, blank,
   translated, punctuation-only, collision); `country_predicate` on records with and
   without affiliations.
3. `backend/tests/evidence_search/sourcing/test_policy_replay.py`: for each of the
   three replay files, `interleave` gives `expected.interleaved`, `dedupe_policy`
   gives `expected.deduplicated` (the two title duplicates collapsed, the titleless
   record kept), `landmark_targets` gives `expected.landmarks`, `rank_policy` gives
   `expected.specific`, the UK-only predicate over `source.country` gives
   `expected.uk_only`, and the first 50 equal `expected.cut_50`.
4. `make verify-fast` green. Commit.

## Phase 2 — Backend verbs, Overton sort, fixtures, wrapper: S2, S5, D19, P1 — `codex`

Transport changes against the pinned request shapes of Phase 0b, multi-file coherence,
machine-verifiable through the wire tests. The brief carries S2, S5, the probe table
and excerpts, and the existing wire-test style (`test_search_wire.py`).

Done when:
1. `search_live.py`: `OpenAlexLiveBackend.search_semantic`, `lookup_ids`,
   `fetch_citing`; `OvertonLiveBackend.fetch_by_id` and `last_pages`; `_search` sends
   `sort=relevance` and `sort` is protected; all through `_request_json`; the semantic
   1 s interval; `BackendCaps` flags; the Protocol in `acquire.py` extended;
   unsupported verbs raise as today; `CallVerb` and `QueryOrigin` extended.
2. `OpenAlexFixtureBackend` and `OvertonFixtureBackend` answer the four verbs from
   fixture data with zero egress; `scripts/evals/search/checks/engine.py`
   `_RecordingBackend` proxies and records them.
3. Tests in `test_search_wire.py`: the semantic request carries `search.semantic`,
   `select`, `per-page=50` and only accepted filter keys; `lookup_ids` batches by 50
   with the wire filter appended; `fetch_citing` sends `cites:` with at most 100 ids
   and one page per logical call; `fetch_by_id` sends `policy_document_id`;
   `sort=relevance` is present on every Overton search and a caller-supplied `sort`
   is dropped; a 429 on the semantic call is retried within the cap; errors are
   redacted to status and host; the credential never appears in logs or cache keys.
4. `make verify-fast` green. Commit.

## Phase 3a — The single pass and the pool hand-off: S3, S4, S5, D2, D3, D7, D12–D14, P2, P7, P8 — `codex`

The judgment-bearing core of the search side, in `search_loop.py` and `acquire.py`
only, with the loop code left in place but unreachable (3b deletes it). Machine-
verifiable through the test list below. The brief carries S3, S4, S5, D7's event
vocabulary and the exact `acquire_sources` signature. Lead reviews the diff before
it lands (family-flip).

Done when:
1. `run_search` runs the single pass of S3 at every depth; `DEPTH_CONSTANTS` is S4;
   `SEARCH_QUERIES_MODEL = "gpt-5.6-luna"`; `QUERY_MAX_CHARS = 1300`;
   `SEMANTIC_ACCEPTED_FILTER_KEYS` and `_semantic_filter_parts` exist; the fixture-mode
   branch runs the same pass on the fixture backends.
2. `acquire_sources` takes `pools` and `caps`, persists in pool order up to each cap,
   embeds only kept records, carries `query_origin` on `source.acquired`, keeps
   `results_returned` raw and the sum invariant, and `_interleave` is gone.
3. `search_prompts.py` re-pinned (`SEARCH_QUERIES_MODEL` lives there); the diff
   recorded.
4. Tests, new, in `test_search_single_pass.py` and `test_acquire_pools.py`: the
   planned call list at each depth (15 + 8 + 4 + up to 10 per variant, and 3 + 15)
   and under a two-variant country filter (30 + 16 + 4 + 10); the call budget stopping
   a backend; three logical-count cases (a full page, a retried call, a provider page
   smaller than requested each count one; an Overton search paging three times counts
   one with `pages = 3` on its event); the semantic skip with `semantic_skipped` on
   the coverage record; the two caps cutting the two pools independently with
   `dropped_over_cap` per pool; mixed-origin dedup keeping the best-ranked copy and
   counting within-stream duplicates as `already_acquired`; only kept candidates
   embedded; `source.acquired` and `search.executed` carry the origins;
   `search_backend_scope` with one backend; the fixture-mode single pass; a
   1,400-character query dropped at validation; the OpenAlex non-country wire filters
   present on resolve and forward calls and the country predicate applied to
   citation-found papers under a variant split; an Overton result carrying
   `cites.scholarly` causes no resolve call and no paper-pool candidate (D9).
5. `make verify-fast` and `make prompt-guard` green. Commit.

## Phase 3b — Loop deletion, runner, and the replacing tests: S8, D11, P3 — `codex`

Deletion with judgment about which tests carry invariants forward, verifiable by
`make verify` and the grep rule. The brief carries S8, the deletion list, and the test
list below. Lead reviews the diff before it lands.

Done when:
1. The S8 deletions are done and the S8 kept list is intact and tested; `runner.py` has
   no round gate; `grep` for every deleted name returns nothing outside `docs/`;
   `git tag -l search-round-loop-last` shows the tag.
2. Tests. Deleted by name, from `test_search_loop_deep.py`:
   `test_deep_round_exemplar_payload_is_top_k_anchored_and_bounded`,
   `test_deep_exemplar_payload_re_reads_effective_state_between_rounds`,
   `test_deep_round_fixed_allocation_snowball_suggest_and_diversity`,
   `test_standard_round_two_trims_snowball_and_suggest_arms`,
   `test_suggestion_grounding_matrix_and_screened_out_counter`, the four
   `test_finalise_deep_stop_*`, `test_new_confident_relevant_for_run_counts_only_that_runs_confident_rows`;
   from `test_search_directives.py` the six `test_deep_stop_*`; the whole of
   `test_search_rounds.py`; from `test_acquire_record_cap.py` the three `_interleave`
   tests and `test_cap_is_per_backend` (replaced by the two-pool cap test of 3a).
   Retained and moved into `test_search_single_pass.py`, updated to the new call
   counts: `test_rapid_fanout_events_failed_variant_isolated`,
   `test_generation_failure_raises_and_harness_records_component_failed`,
   `test_zero_result_generated_queries_count_and_openalex_fallback`,
   `test_rapid_result_cap_is_flat_per_call` (renamed to the per-call page size),
   `test_fanout_runs_every_planned_call_with_no_time_budget`, the three
   `test_search_guidance_*`, `test_acquire_search_does_not_write_screening_rows`;
   `test_search_loop_deep.py` is then removed. Retained in place: the rest of
   `test_acquire_record_cap.py` (`results_returned` raw, dedup before trim, best-ranked
   copy). New, in `backend/tests/runtime/test_search_single_pass_runner.py`: one
   acquire run and one screen run at `standard` and `deep` through `run_plan` (the
   row-level evidence `test_search_rounds.py` gave: one coverage record, `completed`,
   `round_index` 1, no second acquire run); a one-pass run's SSE entries carry
   `round_index` 1 and the existing `runProgress` tests are untouched.
3. Full `make verify` green (the shared 3a/3b gate; ingest-adjacent). Commit.

## Phase 4 — Adaptive screening: S6, S7, D10, P4 — `codex` + `lead`

`codex` for the code and tests (pure decision function, the two-batch call loop, the
eval-only fixed-repetition runner, the eval helper): machine-verifiable through the
truth-table test. `lead` inline for the prompt transplant and the model pin
(prompt-bearing: copying `screen_v4.txt` into `screen_prompt.py` verbatim, setting the
version label and model id) and for the re-pin (`python3 scripts/prompt_hash_guard.py
--update`, diff recorded).

Done when:
1. `decide_stage1` exists with a parametrised test over every truth-table row and the
   confidence examples in D10 (including the 0.3 reversal); `_run_stage1_calls` makes
   one call per document, then exactly one more for each valid `not_relevant`; a
   failed second call leaves `not_relevant` with the flag; a failed first call leaves
   `failed`; the `source.screened` event lists one or two attempts in order
   (`test_source_screened_event_payload` updated); `SCREEN_REPS` and `SCREEN_QUORUM`
   are gone and the three comments that cited them reworded; existing stage-1 tests
   updated from three-rep stubs to the new rule
   (`test_screen_sources_unsure_unanimous_relevant_at_half_confidence` becomes the
   one-call `unsure` case); stage-2 tests untouched and green.
2. `screen_prompt.py`: model, version label and text per S6; `make prompt-guard`
   green after the re-pin; the hash diff in `verification.md`.
3. `vote.py` and `run_screen.py` per S7; `scripts/evals/screening/tests/test_screening.py`
   gains the adaptive case, keeps the majority case through `_run_fixed_reps` with the
   stub backend, and proves the vote mode does not leak between runs; `make
   eval-check` green.
4. `make verify-fast` green. Commit.

## Phase 5 — Eval checks follow the pipeline: S9, D17 — `codex`

Mirrors Phase 3a in the eval engine; verifiable by
`scripts/evals/search/tests/test_measure.py`. Done when `run_one_query` is one search
and one screen, `production_recall.py` reads the new constants and screens at every
depth, the `_run_depth("rapid")` test proves it, `make eval-check` green. Commit.

## Phase 6 — App text and planner numbers: S10, D15, P9 — `fast-worker` + `lead`

`fast-worker`: exact strings in S10 for `planVocabulary.ts` and its two tests;
`make frontend-verify` green. `lead` inline: the planner prompt numbers
(prompt-bearing, six sentences) and the re-pin. Done when `make verify-fast`, the
frontend tests and `make prompt-guard` are green. Commit.

## Phase 7 — ADR, spec, deferred, tutorial diagrams: S11, D16, D20 — `lead`

Design record, spec flow-back and the explanatory page are the lead's (adjudication
and taste-bearing writing). Done when ADR 0038 is Accepted with the sign-off date,
`components.md` §1 and §2 describe the single pass and the adaptive vote,
`docs/specs/log.md` has its line, `docs/deferred.md` has the discharges and the six
new entries, and `docs/tutorials/search-and-screen/index.html` is rewritten per D20
with its diagrams and text read from the as-built code (constants, verbs, call counts,
the vote table), the old design reduced to a short "what it replaced" section and the
proposal sections removed; the measured numbers are left as placeholders that Phase 8
fills. Rendered once with headless Chrome and checked by eye, as the page was on
2026-10-09. `make okf-validate` green. Commit.

## Phase 8 — Live check and step-6 exit — `lead`

Needs the keys, spends money against the contract's ceiling, and the reading of the
numbers is judgment.

1. `make verify` full, green.
2. `scripts/evals/search/checks/production_recall.py --dataset retrieval-ground-truth-mini
   --depths rapid standard deep` in the background; watch the Langfuse cost; stop at
   $10 (contract § Constraints). Compare search recall with the thresholds 12.5 / 17.3 /
   24.6 and screen recall with 90% of search recall; record documents, calls, tokens,
   cache share, cost and wall clock per scope; `history.py --since` rows into
   `history.md` with notes naming the experiment run folders they compare with.
3. Owner's go, then `--dataset retrieval-ground-truth-full --depths standard`, same
   recording; or the deferral noted.
4. Manual smoke run in the app at Focused on the task 049 obesity question: completes;
   a landmark visible in the Sources view (origin `landmark` on its event).
5. The tutorial page's number placeholders filled from this phase's measurements
   (recall, cost and wall clock per scope), rendered and checked once more (D20).
6. `verification.md` complete per the contract's § Verification evidence expected,
   including the probe table, the deleted-code list with replacing tests, the
   public-safety line.
7. Commit. Stop. Review runs in a fresh conversation (`task-cycle-review`).
