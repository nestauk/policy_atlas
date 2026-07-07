# Verification: 010-select

Evidence for the select slice (EB component 6 — coverage-aware stratified selection,
the selection directive, the `RankingBackend` seam and the repo's second product
prompt). Build sections filled at step 6; **Review findings** + **Rubric status** to be
added by the step-7 review stack (fresh conversation).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | **313 passed** (285 pre-Phase-5 + 19 new in `test_select.py` (9 → 28) + 9 in `test_select_rerank.py`; earlier phases added `test_ranking.py` (4) and 5 registry cases in `test_compile.py`); stub/double backends throughout — deterministic, zero egress |
| `make typecheck` | pass | mypy strict, 43 source files |
| `make lint` | pass | ruff |
| `make build` | pass | sdist + wheel |
| `make okf-validate` | pass | 23 concepts, 0 violations (one spec flow-back this slice) |
| migration roundtrip | pass | `alembic upgrade head` → 20 tables (inspector) → `downgrade -1` → 19 → `upgrade head` → 20, clean (revision `c8d4f2e7a3b1`); downgrade drops `selection_result` only |
| `make verify` (step-7 re-run) | pass | **321 passed** after review-stack fixes (8 covering tests added); typecheck/lint/build/okf green |

Composite-FK note (plan Task 1): both referenced composite uniques
(`uq_evidence_scope_id_project`, `uq_runs_run_project`) pre-existed from the
screening-result precedent — verified, no new unique constraints needed. No
dependency changes (`openai` + `langfuse` already present — asserted, not added).

## Checks beyond the build

All suite checks are deterministic (stub ranker + misbehaving/counting/raising/subset
doubles for the judgment paths). Named results, per the contract's evidence list:

- **Stratified-allocation math** — `test_allocation_math_matches_hand_computed_fixture`
  (strata 10/6/2 + 2 unclustered, budget 8: floors 4, largest-remainder 4 —
  hand-computed per-stratum allocations, reasons and exclusion classes asserted);
  `test_budget_below_strata_grants_floors_in_stratum_order` (budget 2 over 4 strata +
  empty unclustered: floors granted count-desc/name-asc, unfloored strata end
  zero-selected); `test_exhausted_stratum_surplus_redistributes` (capped stratum's
  surplus re-enters; total selected == budget).
- **Breadth-floor anti-top-k** — the dominant stratum cannot starve the rest: every
  non-empty stratum is floored before any proportional slot is granted (asserted in
  the allocation fixtures above).
- **Must-includes** — `test_must_include_bypasses_budget_and_conflict_is_notable`:
  selected outside the budget (`selected_count == budget + n_must`), a must-include
  satisfies its stratum's floor, an out-of-scope id is a flagged notable entry
  (`must_include_not_in_scope`) + the `must_include_conflict` trigger, run completes.
- **Non-evidence exclusion** — `test_eligibility_base_ladder_by_evidence_type`:
  `"Other (Non-evidence documents)"` excluded and counted; `"Unknown / Insufficient
  information"` and unclassified (NULL) stay eligible.
- **Counting invariants** — `test_counting_invariants_on_mixed_fixture` (eligible-set
  based: `screened_in == non_evidence + eligible`; `eligible == selected +
  not_selected`; `selected == must_include + breadth_floor + ranked`; every selected
  doc in exactly one stratum bucket); invariants are also asserted in code before the
  row write (`SelectError` on violation).
- **Determinism** — `test_deterministic_runs_write_identical_payload_columns`: two
  runs, same corpus + characterisation → byte-identical payload columns (`strategy`,
  `budget`, `selection_provenance`, `selected`, `excluded`, `flags`; PK/timestamp
  excluded per the contract).
- **Edge scopes** — `test_missing_characterisation_empty_scope_and_unclustered_select_all`:
  n = 0 → completed summary with `empty_scope` flag and **no selection row**; missing
  characterisation row → structural `SelectError` (harness: `component.failed`, no
  row — `test_harness_select_component_missing_characterisation_fails`); budget ≥ n →
  select-all with reasons; unclustered-only (zero themes) → one stratum, still
  stratified formally.
- **Missing-signal flag-not-block** — `test_missing_signals_flag_not_block`: missing
  year/appraisal/confidence read neutral 0.5, land in `missing_signals` and
  `signal_availability`, doc stays selectable. (The NULL-screen-confidence leg runs
  at the pure `select_documents` layer: `ck_ssr_non_null_when_decided` makes a
  relevant-with-NULL-confidence DB fixture impossible by construction.)
- **Text-basis tilt (soft)** —
  `test_text_basis_soft_tilt_ranks_full_text_above_but_never_excludes`: hand-computed
  0.15 composite gap (weight 0.20 × (1.0 − 0.25)); the abstract-only doc is still
  selected.
- **Trigger flags** — dedicated fixtures with detail payloads for
  `large_stratum_excluded`, `thin_base`, `thin_full_text`, `must_include_conflict`,
  plus the negative case (`flags == {}`); `priority_stratum_excluded` under rerank
  tests below.
- **Rationale bidirectionality** —
  `test_rationale_bidirectional_with_hand_computed_full_text_shares`: selected list +
  excluded aggregates present and summing; per-stratum full-text shares (candidates
  vs selected) hand-computed; `test_summary_payload_shape_is_frozen` freezes the
  exact summary keys.
- **Directive semantics** — tag and column boosts deterministically reorder a stratum
  (hand-computed composite effects); a year `{gte, lte}` boost matches only in-range
  docs; a boost can never exclude (the boosted-against doc still selected); a
  zero-match boost → `unmatched_boosts` in provenance, non-fatal; empty directive
  `{}` ≡ absent directive (byte-identical payloads); malformed directives
  (unknown key, out-of-range weight, bad uuid, wrong types) → `DirectiveError`, fail
  closed; the executed directive + `directive_source` recorded whole in
  `selection_provenance`; priority-strata casefold matching (name substring + member
  tag equality) with `priority_stratum_excluded` fired for a zero-selected matched
  stratum and unmatched patterns flagged non-fatally
  (`test_priority_strata_flags_are_soft_and_match_names_or_tags` — allocation
  asserted identical with and without the priority field: soft for selection, hard
  for escalation).
- **Rerank semantics** (`test_select_rerank.py`, all against protocol doubles — zero
  egress): contested-strata-only calls asserted with a counting double (union of
  batched ids == exactly the contested rankable candidates; must-includes and
  wholly-selected strata never sent; zero calls when budget ≥ eligible); call-budget
  maximum `ceil(contested/25) × (1 + 1)` enforced (an always-raising double is called
  exactly `maximum` times, every contested doc falls back, and the selected-id set
  equals the deterministic run's — whole-stratum fallback ≡ `coverage_stratified_v1`);
  scored-before-fallback ordering with both scores recorded and composite tie-breaks;
  a misbehaving double (out-of-range/bool scores, conflicting duplicates, invented
  ids, missing docs) → per-doc fallback, flagged `rank_fallback`, never dropped or
  excluded; LLM scores order but never exclude.
- **Injection posture / reasons as untrusted data** — an injection-shaped but
  length/charset-valid reason is stored verbatim as inert data on the selected record
  and changes nothing else; control-character or >240-char reasons make that doc fall
  back; `test_rerank_prompt_hygiene_is_structural` asserts on the built prompt that
  corpus text enters only as id-keyed JSON data records under the
  data/instructions-separation marker and never reaches the instruction half.
- **Zero-egress / socket-deny** — `test_socket_deny_select_harness_round_trip`: a
  full select harness round-trip (llm_rerank_v1 path on the stub backend) completes
  green with `socket.socket` patched to raise (scoped after the DB connection, the
  008 pattern).
- **Key hygiene** — `test_openai_key_hygiene_for_select_rerank`: a canary
  `OPENAI_API_KEY` appears in no event payload, not in the persisted
  `selection_result` row JSON, and not in captured output;
  `test_openai_ranking_backend_requires_api_key`: the live backend without a key
  fails loudly at construction.
- **Provenance keys** — asserted on row and event payload: `strategy_version`,
  `characterisation_run_id`, executed directive + source, `effective_weights`,
  `signal_availability`; under `llm_rerank_v1` additionally `prompt_version`,
  `model`, `batch_size`, `call_budget {baseline, maximum, used}`, `retry_count`,
  `fallback_count`.
- **Schema constraints** — `test_schema_constraints_reject_bad_rows`: strategy CHECK,
  `budget > 0` CHECK, `UNIQUE (evidence_scope_id, run_id)` (same-run rewrite is a
  loud IntegrityError), cross-project composite-FK guard; `delete_project_data`
  removes `selection_result` FK-safely; select writes no artefact/block rows and
  leaves screening rows untouched (`test_select_writes_no_artefact_or_block_and_leaves_screening_untouched`).

## Live-run evidence (contract's one manual check)

Skeleton end-to-end against the live corpus with `OPENAI_API_KEY` +
`LANGFUSE_*` (dev instance), 2026-07-06 23:39–23:42 UTC — exit 0, `skeleton.done`:

- `skeleton.backends mode=live ranking=llm_rerank_v1 traced=True`; chain acquire →
  screen → classify → appraise → ingest_full_text → characterise → **select** (select
  as its own run, `run_id 9ce28552-33e8-481c-b803-68c4c42fb2db`, stratifying over the
  explicitly referenced `characterisation_run_id b7743030-b312-430a-a578-e54b920e00fd`
  — recorded in provenance and the summary).
- **Demo directive** (plan finding 5): budget 8 + one tag boost
  (`topic_theme = "SDG 11: Sustainable Cities and Communities"`, weight 3.0, chosen
  from live provider tags) — `directive_source=scope_context`, recorded whole in
  provenance. **Visible directive effect**: boosted docs carry composites ≈ 2.3
  (× 3.0 multiplier) vs ≈ 0.6 unboosted, and the boost reordered the affected
  strata's picks.
- **Selection**: 25 screened-in / 0 non-evidence / 25 eligible over 6 strata +
  `unclustered`; floors 5 + ranked 3 = 8 selected; exclusion aggregates
  (`ranked_below_cut` 16, `budget_exhausted` 1) rendered per stratum; per-stratum
  full-text shares rendered (selected-set share 7/8 = 0.875 → no `thin_full_text`);
  `flags={}` (correct for this corpus); the selection row present and rendered
  per-doc.
- **Real rerank calls on contested strata**: 24 contested docs → baseline 1 /
  maximum 2, **used 1**, `retry_count 0`, `fallback_count 0`
  (`select.rerank_fired used=1` — the finding-5 assert-and-log). Every contested
  selected doc carries `llm_score` + `llm_reason`; the wholly-selected stratum's doc
  carries neither (no calls spent on it). The judge's scores were honestly 0 with
  reasons like "no content addressing housing affordability" — the fixture corpus is
  synthetic wordlists against a housing intent; purpose-fit judgment working as
  designed (ranking *quality* remains the recorded eval seam).
- **Langfuse (dev instance)**: trace root `run:9ce28552-…` (id
  `8a2904e8845a7789bf580837fa875b52`) with the `component:select` span; the
  `rank:batch1` **generation** observation recorded with `model=gpt-5-mini`,
  `prompt_version=select_rerank_v1`, `batch_size=24`, token usage, full I/O, and the
  `rank_batch_valid = 1.0` score — verified via the Langfuse API, names/usage only.
  The batch span lands as a **detached trace root** (the ranking call runs on an
  executor thread; OTel context does not cross threads) — the same recorded 009
  detached-trace wart, already named in the plan as a capability-run-seam symptom;
  not new to this slice.
- **Cost note (honest)**: one `gpt-5-mini` rerank call — 4,723 prompt + 2,653
  completion = 7,376 tokens ≈ **$0.007**. Whole live skeleton run (embeddings +
  grouping + rerank) remains of 009's order, ≈ $0.10.
- **Key hygiene audit**: captured live output greps clean for key-shaped strings
  (`sk-…`, `*-lf-…`, `OPENAI_API_KEY=`) — 0 hits.

## End-to-end command

```
uv run --env-file .env python -m policy_atlas.skeleton
# .env: OPENAI_API_KEY + LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST + DATABASE_URL (dev DB at migration head)
```

## Diff summary

One slice on `task/010-select`, five phase commits + this one:

1. **Schema** (`55696d5`): `selection_result` + migration 10 (tables 19 → 20);
   six existing table-count assertions 19 → 20.
2. **Ranking layer** (`e555b67`): `ranking.py` — `RankingBackend` protocol,
   `OpenAIRankingBackend` (strict structured outputs, 0–10 integer score schema,
   `rank:batch{i}` generation spans opened inside the backend where `response.usage`
   lives, `rank_batch_valid` score), deterministic `StubRankingBackend`,
   caller-owned `validate_ranked`; the lead-authored `select_rerank_v1` prompt (the
   slice's only prompt-bearing surface).
3. **Component** (`dd91ee3`): `select.py` — directive → signals → strata →
   allocation → strategies → rationale → flags → row-written-last;
   `screened_sources` promoted public in `characterise.py` (rename only).
4. **Wiring** (`c26933b`): registry entry (+ `characterisation_run_id` on
   `Plan`/`Config`, required for select at compile), `run_harness ranking_backend`,
   `_run_select`, skeleton chain + demo directive + summary rendering, FK-safe
   deletes, compile tests.
5. **Tests** (`e534f5c`): contract bulk (28 in `test_select.py`) + judgment cases
   (9 in `test_select_rerank.py`).
6. This commit: components §6 spec flow-back (approved rev 3) + `log.md` entry +
   this file.

**Minor deviations, flagged (resolved within the contract's vocabulary — the 007
precedent; none change the design):**

- **Empty directive `{}` → `directive_source="default"`**: the contract's acceptance
  check requires `{}` to be byte-identical to the absent-directive path, and the
  contract's own words are "an empty directive *is* the default"; recording
  `scope_context` for `{}` would break the byte-identity it mandates.
- **`run_harness` passes `ranking_backend=None` through** rather than resolving a
  stub inside (plan wording said "stub resolved inside, the 009 pattern"): `None`
  *is* the strategy routing — `coverage_stratified_v1`, touching no backend; a
  passed backend selects `llm_rerank_v1`. `StubRankingBackend` exists and is what
  the suite injects to exercise the llm path egress-free. An eagerly-resolved stub
  would have erased the routing signal.
- **Contested-strata definition tightened at lead review** (vs the build brief, in
  the contract's favour): contested = `0 < allocation < stratum size` *including*
  floor-only strata (decision 10's "allocation < stratum size") — a breadth-floor
  pick from several candidates is a real choice the ranker must order; only
  wholly-selected and zero-slot strata are skipped.
- **Must-include validation set**: validated against the *selectable* set (eligible ∩
  referenced characterisation) — an eligible doc absent from the referenced
  characterisation cannot be placed in a stratum, so it flags
  `must_include_not_in_scope` rather than being silently unselected (decision 4's
  never-silent rule; the eligible-set narrowing is adversarial finding 1's).
- **Skeleton demo directive on a tagless corpus** degrades to budget-only (a `None`
  boost tag would fail the directive closed — fail-closed validation working as
  designed; live corpora always have provider tags).
- **`test_missing_signals_flag_not_block`'s NULL-confidence leg** runs at the pure
  layer — `ck_ssr_non_null_when_decided` makes the DB fixture impossible (the
  constraint, not the test, is the authority on what a relevant row can look like).

Data files: none added this slice (no fixture/recording changes; the 007-retro
exclusion list is empty for this diff).

## Review findings

Step-7 stack (fresh conversation, 2026-07-07): contract-verifier (pinned Opus, read-only) ·
`agent-skills:security-auditor` · Codex adversarial (read-only rescue brief) ·
`/code-review medium` (8 lens-scoped finder angles + 1-vote verify). Lead adjudicated;
fixes applied on-branch; `make verify` re-run green (**321 passed** — 313 + 8 covering
tests added with the fixes).

- **Contract verifier:** every rubric item HOLDS (7 and 8 pending by schedule); no
  unapproved gated change; one MAJOR — unknown boost **column** failed closed
  (`DirectiveError`) against decision 4's "unknown columns/tags … flagged, never
  fatal" and the matching acceptance-evidence bullet, with no test either way.
  **Adopted** (convergent with Codex finding 1 — high-confidence): unknown columns
  now parse, match nothing, and surface via `unmatched_boosts` exactly like unknown
  tags; structural malformation still fails closed. Covering test added
  (`test_unknown_column_boost_is_flagged_non_fatal`).
- **`/code-review medium`** (Claude half of the heterogeneous pair): 11 candidates
  → 10 verified (1 refuted by the adjudicator: "breadth_floor mislabeling" flags
  exactly decision 3's mandated reason precedence). Adopted: **live-path KeyError**
  — `_empty_summary` omitted `call_budget` under `llm_rerank_v1`, crashing the
  skeleton's rerank-fired check on an empty/all-non-evidence scope (CONFIRMED;
  fixed — empty summaries now carry the full zeroed rerank provenance;
  `test_empty_scope_rerank_provenance_carries_call_budget`); **future-year recency
  reward** — implausibly-future `year` metadata read as maximally recent unflagged
  (CONFIRMED; fixed — beyond a one-year ahead-of-print grace it reads as a missing
  signal, flag-not-block; `test_future_year_reads_as_missing_signal`); three
  confirmed simplifications (`_log_usage` now reuses `_usage_metadata`; skeleton's
  demo tag query built once with a conditional filter; dead `run_id` parameter
  dropped from `_selection_payload`); three confirmed test-helper duplications
  hoisted to `tests/helpers.py` (`seed_select_doc` · `seed_characterisation` ·
  `run_select`, the established helper precedent). Declined: `_share`/`_batches`
  duplication (2–3-line private pure helpers; a shared util module costs more than
  the duplication — revisit via `itertools.batched` if a third copy appears).
- **Security lane** (`agent-skills:security-auditor`): 0 critical/high/medium; all
  five focus lanes (prompt-injection posture, key hygiene, egress bounds, data
  layer, untrusted directive) verified clean except two LOW directive-hardening
  gaps, **both adopted**: directive strings now screened for control characters and
  length (`DIRECTIVE_STRING_MAX`), and `budget`/list sizes capped
  (`DIRECTIVE_BUDGET_MAX`, `DIRECTIVE_LIST_MAX`) — fail-closed at parse, static
  messages; four covering cases in `test_malformed_directive_shapes_raise`.
  Info items declined with reasons: harness `assert` (traced fallback is already
  fail-closed via `SelectError`), f-string CHECK-constraint SQL (code constants),
  locator-as-title fallback (matches the 009 grouping pattern); suite-wide
  `pytest-socket` recorded as a deferred hardening note.
- **Adversarial review** (Codex, read-only; Tier 3 heterogeneous partner):
  6 findings — allocation arithmetic and scored-before-fallback ordering pressed
  and **clean**. Adopted: finding 1 (unknown column, convergent — above); finding 6
  (title-only rerank degradation was unflagged against decision 10's "flagged" —
  fixed: `title_only_count` recorded in rerank provenance;
  `test_rerank_title_only_docs_are_counted`); finding 2 **in-part** (wall-clock
  recency: byte-identity holds per the contract's same-inputs claim, but the
  reference year is now pinned once per run and recorded as
  `recency_reference_year` in provenance, so every recency score is attributable).
  Declined with reasons: finding 3 (identical-duplicate rerank rows are deduped,
  not fallen back — an identical duplicate is unambiguous; discarding a valid
  judgment would be strictly worse; conflicting duplicates do fall back, per the
  recorded deviation); finding 4 (SDK transport retries sit beneath the logical
  call budget — `max_retries=2` already recorded in Known unverified items; egress
  stays bounded by a known constant multiplier); finding 5 (per-doc scores for
  excluded docs — the contract's own schema makes `excluded` aggregate-per-stratum
  by design; per-doc attribution is for selected docs).
- **`/simplify`:** skipped with justification — the `/code-review` pass ran the
  reuse/simplification/efficiency/altitude finder angles and their confirmed fixes
  were applied above; a separate same-family cleanup pass would duplicate it
  (efficiency, altitude and conventions angles each returned zero findings).
- **`/okf validate`** (specs changed): pass at build time and in the post-fix
  `make verify` re-run (23 concepts, 0 violations).

Convergence note: the one finding found independently by both review families
(unknown-column fail-closed) was also the stack's most substantive; the
single-family uniques (live-path KeyError — Claude line-by-line; title-only flag —
Codex; directive input caps — security lane) each justify their lane.

Token economy (actuals, for the retro): reasoning-class ≈ 239K (contract-verifier
149K + security 90K; Codex external) — within the ≤250K target. Fast-worker ≈ 725K
review-side (8 lens-scoped finders 608K + 3 grouped verifiers 117K) — **over the
≤500K target** despite per-angle pathspec scoping; the 6.4K-line diff dominates
finder cost even scoped (fix-implementation delegation, 176K, was build work, not
review). Retro seam: on diffs this size, drop to ~5 finder angles or scope
correctness angles to `src` subsets.

## Rubric status

Completed by the step-7 review stack (2026-07-07). Items 1–6, 9–15 (incl. 11a):
**hold** — per-item evidence in the contract-verifier report summarized above;
post-fix `make verify` green (321 passed). Item 7: deferred.md entries ride step 8
in this PR (the 009 vectorisation entry verified unchanged and uncontradicted).
Item 8: this review stack — three lanes + heterogeneous pair, sized per the 009
retro note; findings and adjudications recorded above. Fake-done check on the
review-phase fixes: no tests relaxed or deleted (8 added, 3 helpers hoisted
verbatim); no swallowed errors (all new validation fails closed with static
messages); no stub returns (the empty-summary fix writes honest zeros, not fake
budget figures).

## Intent & assumptions

- Selection is run-local and never canonical: `not_selected` stays derivable
  (screened-in eligible minus selected), no doc-level status column exists, and the
  rationale phrases exclusions as coverage, never absence.
- The directive is the future capability agent's tool-call surface; v3.0 sources it
  from `evidence_scope.context["selection"]` (the skeleton demonstrates one). The
  policy object, when its slice lands, compiles into directive boosts — select's
  code is untouched by construction.
- `DEFAULT_WEIGHTS` are honestly arbitrary pending selection-quality evals (recorded
  in the constant's docstring); `thin_base` is honestly stub-constant until the LLM
  screen tool lands.

## Known unverified items

- **Rerank quality** (are the right docs ranked up?) — out of scope by contract;
  the recorded eval seam needs extract to give selection a downstream consequence.
  This slice's bar is machinery correctness + honest, attributable rationale.
- The `rank:batch{i}` span detachment (threaded OTel context) is observed, recorded
  and accepted as the known 009 wart; the fix belongs to the capability-run seam.
- Rate-limit behaviour under many concurrent batches is untested live (the fixture
  corpus needs only one batch); the backend carries SDK retries (max_retries=2) and
  the code path degrades to whole-batch fallback.

## Public safety

- No credentials in code, logs, tests or this file; the live-output key audit greps
  clean; suite paths are socket-denied.
- What left the machine on the live path: the scope intent string and titles +
  abstracts of contested-strata candidates (the rerank call) — the same text class
  and posture as 009's grouping calls; the fixture corpus is openly licensed /
  synthetic, so only committable text was sent. Full-I/O traces went to the
  user-operated dev Langfuse instance per the settled posture.
- Committed artifacts (strategy names, weights, prompt text, table/column names,
  counts, rationale shapes) are public-safe. Ranker reason strings are
  **potentially source-derived text** (length-capped, stored as data): the
  `selection_result` row inherits the corpus's sensitivity class — public-safe for
  this openly-licensed fixture corpus, private-by-default for arbitrary corpora
  (adversarial finding 8).

## Deferred work

Seams left open ride to `docs/deferred.md` at step 8 (after the review stack, in the
PR — per the plan's step-8 obligations list): steer-point pause reading the flags ·
agent-authored directives (invocation-time) · rerank-quality evals (incl. listwise
ordering) · Cohere-class cross-encoders at the `retrieve` seam · capability-run
entity (with the three-level run model settled at the plan gate) ·
embedding-relevance-for-select (declined, rev 4) · selection-diversity extensions ·
policy soft-prior tilt (compiles into directive boosts) · second strategies · full
appraisal on the selected subset — plus pointer updates where 009 entries exist.
