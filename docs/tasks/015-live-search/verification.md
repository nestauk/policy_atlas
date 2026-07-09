# Verification: 015-live-search

Evidence for the slice (steps 5–6). Live-run output quotes counts and structure only —
no record content, no key material. Langfuse dev traces + dev-DB rows are the full
record (project ids below); none of that is committed.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | 804 tests (includes the ingest integration suite) |
| `make typecheck` | pass | mypy strict, 92 source files |
| `make lint` | pass | ruff |
| `make build` | pass | sdist + wheel |
| `make okf-validate` | pass | runs inside `make verify` |

Full `make verify` green at: build-open baseline · phase 1 (schema+deps) · phase 2
(prompt-input readers) · phase 4 (ingest-adjacent) · phase 6 (screening-row readers) ·
phase 7 · step-6 exit. Phases 3 and 5 gated on `make verify-fast` per the plan's gate map.

## Checks beyond the build

- **Deterministic suites** (phase 7, all green):
  - Transport matrix (`test_search_live.py`, 50): sanitizer transforms · Overton limiter
    incl. `next_page_url` follows · explicit timeout · retry set (429/5xx/timeout, cap 1,
    then honest failure) · structural key redaction (keyed URL in an HTTPStatusError never
    survives into the raised message) · shape validation + `next_page_url: false`
    tolerance · pinned-host guard on `next_page_url` · `OA_SELECT` ⊇ mapper reads ·
    no-citation-floor · `squery`+`min_similarity=0.3` present on every Overton call and
    absent from every OpenAlex call · mapper-consumable raw pages · verb chunking (≤50
    ids/DOIs per request) · loud missing-key errors.
  - Grammar/directive matrix (`test_search_directives.py`, 38): fail-closed directive
    parse, full `scope_filters` vocabulary → exact wire params, Overton single-valued
    rule, backend-scope mismatch, `search_backend_scope` compile (3 values + unknown
    rejected on Plan AND Config), `evaluate_deep_stop` pure matrix.
  - Mapping deltas (`test_acquire_mapping_deltas.py`, 10): decision-20 retention pins,
    English-first title cases, series → `methodological_structural` tags,
    keywords-never-tagged, `referenced_works` capped at 60, executed-calls counting
    invariant (`acquired + already_acquired + skipped_unusable == results_returned`
    per backend across ok/error calls).
  - Migration roundtrip (`test_search_migration.py`): downgrade rejects the new stop
    values; upgraded head accepts `short_circuit`/`budget_exhausted`/`target_reached`
    and still rejects `saturated`.
  - Judgment suites (`test_search_loop_deep.py` · `test_search_wire.py` ·
    `test_prompt_priors.py`): scripted-backend rapid fan-out (15 OA calls, exact clause
    composition, failed-variant isolation, zero-result counting + verbatim fallback,
    generation failure → `component.failed`), deep rounds (exemplar top-k ranking /
    fixed-intent anchor / per-round non-accumulation / prompt bounds, fixed allocation
    incl. diversity reserve, snowball fwd+backward, DOI-preferred grounding matrix +
    grounded-but-screened-out counter, all four stops, deep-thin overlay wins below
    target and never at/above target, per-round coverage rows),
    acquire-writes-no-screening-rows, wire assertions through real live backends with
    injected fetch, prompt-prior assembly (label provenance visible, keywords absent,
    bounds bind, instruction-shaped values stay data on classify/reformulate/suggest
    surfaces).
- **Zero-egress guard extended**: `search_live.py` is the one sanctioned HTTP-import
  home; `acquire.py` provably never imports it (import-regex, not prose match).

## End-to-end command

Live check driver (scratchpad, not committed; loads keys via
`load_dotenv(<repo>/.env)`; dev DB at alembic head):

```
uv run python <scratchpad>/live_check_015.py --steps abcdg   # rapid · dedup · limiter+keys · probe · filters
uv run python <scratchpad>/live_check_015.py --steps aefhi   # deep · escalation · chain smoke · pins
```

Trace cross-reference project ids: rapid/filters `e8c7b46d-3a21-4fa8-8366-27967444f513`,
deep/escalation `6af6b1e7-3704-44f9-b180-d0ecfdb2ef2c`, chain smoke
`713264d8-cf4a-4e29-825f-271b5f910fe7`. Note: the deep/escalation invocation's DB
transaction rolled back when its (h) leg hit the pre-fix substrate refusal, so its
rows are log+trace evidence only; the rapid/filters and chain-smoke projects persist
in the dev DB. Estimated LLM spend across all live steps: low single-digit dollars
(mini-class screening dominated; exact usage in Langfuse dev traces).

## Live-check evidence (decision-11 pin, all steps run)

- **(a) rapid run** (real intent, both providers): 5 diverse generated keyword queries ×
  base/SR/RCT variants = 15 OpenAlex calls + verbatim intent + 2 generated NL
  paraphrases = 3 Overton calls; **wall-clock 28.1 s vs the 30 s budget**; 49 acquired /
  67 returned (18 cross-variant dedups); envelope spot-checks correct
  (`abstract_source` ∈ {publisher_abstract, snippet, llm_description, none},
  Overton `title_source` present, OpenAlex absent); provider tags bounded (max len 92
  ≤ 200; per-record cap enforced with a logged truncation on two 50+-tag records);
  coverage record `adequate`, `mode="live"`, per-backend `depth="rapid"`.
- **(b) immediate re-run**: acquired 41 new / 44 already_acquired, **0 duplicate
  locators** — the three identity guards hold on live data.
- **(c) limiter + key hygiene**: consecutive Overton calls spaced ≥ 1.2 s; grep of the
  **actual env key values** over all event payloads, snapshot metadata and coverage
  rows: **0 hits**; structural redaction tests green. Live OpenAlex 429s were observed
  and retried exactly once each (the retry path exercised for real).
- **(d) comparative probe** (decision-2 risk, measured with mitigation): verbatim
  intent on OpenAlex = 50 results; generated queries returned quota-bound diverse
  slices (3/call). With per-call quotas the raw counts no longer measure starvation —
  the mitigation (keyword generation) is structural; recorded as observed.
- **(e) live deep run**: skeleton-sequenced rounds visible in events; round 2 read
  graded exemplars via the effective-screen helper and reformulated (prompt 2.4 K
  tokens — bounded exemplar records, never the hit list); snowball forward calls
  landed through dedup; **round 2 screened 54 docs → 49 new confident-relevant,
  cost-per-marginal 1.10 → `target_reached`** on the final coverage row (overlay
  correctly NOT applied at/above target); loop driver wall-clock **113.8 s vs the
  150 s budget**; in-loop screening latency reported separately (60.6 s for the
  54-doc round at mini ×3, concurrency 12; the 206 s figure is the round-1 rapid-leg
  screen over the accumulated corpus, outside the loop budget by design).
- **(f) rapid-thin escalation** (deliberately narrow intent): `should_escalate` fired,
  one bounded deep continuation ran (round 2), still thin → final coverage row
  **`re_searched_still_thin`** (overlay applied); the suggest arm grounded one real
  suggestion via lookup and it landed through dedup (`acquired_pss_by_verb`).
- **(g) filtered rapid run** (dated + typed + SDG directive, both backends): exact
  wire params in every `search.executed` payload and on the coverage record —
  OpenAlex `filter=sustainable_development_goals.id:https://metadata.un.org/sdg/11,
  from_publication_date:2020-01-01,type:article|report`; Overton
  `source_type=government · sdgcategories=SDG 11: Sustainable Cities and Communities ·
  published_after=2020-01-01`; result counts consistent with the narrowing.
- **(h) rapid-profile chain smoke** (acquire → screen → classify → appraise →
  characterise → synthesise, §9 minus ingest): live corpus of 59 docs — screen 58
  relevant; classify produced a real 9-way distribution (16 policy syntheses, 8 SR/MA,
  3 RCT, 5 Unknown, 2 Other) + 158 open tags; appraise 51 scored; characterise
  discovered 8 coherent themes and its **tag distributions carry the new 015 rows**
  (`methodological_structural × overton` = 29 series tags; publisher `source_tags`
  incl. `SDG Target 11.1` × 29 — the derived-SDG-label pin confirmed live);
  synthesise **minted the artefact** (7 blocks, grounding judge active, honest flags).
  Classify's label priors visible in traces (label_priors records with asserted_by).
- **(i) residual pins**: OpenAlex `group_by=type` returned exactly 28 types matching
  the pinned enum (returned as `https://openalex.org/types/<token>` IRIs — same
  vocabulary, different spelling of the group keys; the filter tokens are unchanged).

## Diff summary

Live, depth-graded search over OpenAlex + Overton behind the unchanged 007 seam.
New modules: `search_live.py` (hardened httpx transport: explicit timeouts, Overton
1.2 s limiter on every request incl. validated `next_page_url` follows, retry cap 1
then honest failure, structural error redaction to status+host, sanitizers,
credit-responsible `select=`, no citation floor, injectable fetch seam),
`search_prompts.py` (three lead-authored product prompts + strict wires + code-side
output validation), `search_generation.py` (generation seam: OpenAI + stub),
`search_loop.py` (fail-closed depth directive + `scope_filters` grammar, rapid
fan-out, deep acquire↔screen rounds with graded exemplars / fixed allocation /
diversity reserve / four stops + deep-thin overlay, episode budgets, escalation
helpers, loop driver). `acquire.py` grew the executed-calls input path (per-call
events; machinery untouched), decision-20 retention/tags/English-first-title, and
additive protocol verbs. `screen_v2`/`classify_v2`: `title_source` + the
property/label prior restructure (label priors from `source_tag` with visible
provenance; `_topic_labels` retired — OpenAlex keywords exit the prompt).
`plan.py`/`harness.py`: `search_backend_scope` on Plan AND Config, harness resolves
defaults from compiled config. Skeleton: live search backends (dual-key loud check),
one pre-ingest deep episode (escalation or deliberate demo), per-mode wall-clock
logging. One migration (stop-condition widening); `httpx` declaration-only promotion.

**Flagged deviations (minor, resolved within the contract's vocabulary — adjudicate at
review):**

1. **`referenced_works` added to `OA_SELECT` + retained capped at 60 ids** — decision 16's
   "1 backward batch" call arithmetic is only realisable if seeds carry their reference
   ids; symmetric to Overton's retained `cites` (the recorded snowball-seam signal).
2. **`lookup_dois` verb + `has_doi_lookup` caps flag** (additive protocol growth beyond
   decision 16's three verbs) — the mechanism for decision 15's pinned ID/DOI-preferred
   suggestion grounding; one batched call per ≤50 DOIs.
3. **Fixture-replay short-circuit**: when every backend is `mode="fixture"`, the strategy
   plans one verbatim call per backend (replay doesn't interpret queries; fanning out
   would only multiply identical pages and distort counts). Keeps the default zero-egress
   suite byte-compatible; the full strategy is exercised by scripted backends.
4. **Per-call result quota (live-check finding, fixed in-slice)**: the first live run
   showed call #1 consuming the whole per-backend cap (`max_results = remaining = 50`),
   silently collapsing the fan-out to one load-bearing query — decision 14's exact
   failure mode. Search-arm calls now share the cap (rapid: `cap // planned` = 3/call on
   OpenAlex; deep rounds: episode remainder split across the round's search calls);
   fallback-verbatim keeps the full remainder. Regression-tested; live rerun confirmed
   15 + 3 calls in 28 s.
5. **Chain-smoke substrate**: contract rev 3.14 expected the smoke to "synthesise over
   metadata envelopes", but 013's as-built substrate rule is full-text-only (an honest
   structural `no_groundable_substrate` refusal on an envelope-only corpus). The smoke
   seeds one synthetic full-text upload (the skeleton demo's own corpus shape) so the
   terminus can mint; the live-acquired envelopes still supply screen/classify/appraise/
   characterise. **Spec flow-back note for step 8** — envelope-only synthesise belongs
   to 016's substrate question, and rev 3.14's wording should be corrected.
6. **Lead removal of a delegate test**: a strict xfail pinning *harness*-level
   auto-escalation was removed — decision 17 places escalation with the skeleton
   sequencer; the skeleton flow is covered by its own tests.

## Intent & assumptions

- Depth constants are the decision-13 extensible table; v3.0 ships exactly
  `rapid | deep`.
- The deep episode's HTTP/result budgets span the whole episode (plan's arithmetic:
  15 + 2×17 = 49 ≤ 50), accounted across rounds by reading prior `search.executed`
  events for the scope.
- One relevance surface holds by construction: acquire/search never writes screening
  rows (test-pinned); steering reads only the effective-screen helper.

## Known unverified items / gaps

- **Suggest arm live yield**: in the deep housing run the mini model proposed 0 papers
  (an allowed answer); the arm's full grounding path fired live only in the escalation
  step (1 grounded suggestion). Machinery is scripted-test-covered; live yield is
  eval-slice material.
- **Characterise live robustness on rich live corpora** (015 changed its inputs, not
  its code): one `APITimeoutError` batch-failure run (206-doc corpus, repair path then
  run.failed) and one `InvalidDiscoveryOutput` double-rejection run (85-doc corpus)
  before a clean pass on the ~60-doc smoke. Pre-existing component behaviour under
  bigger/realer inputs — carried to review as a robustness observation, not a 015
  defect.
- Overton `next_page_url` was never non-false on `pp=50` single-page rapid calls in
  these runs (caps bound results first), so live multi-page following wasn't observed;
  the follow+validation path is test-covered.
- The comparative probe (d) can no longer measure verbatim-NL starvation directly
  (quotas bound both arms); the mitigation is structural.
- Deep-run wall-clock: the loop driver honours its 150 s budget, but a full deep
  EPISODE including the round-1 rapid leg's screening of a large accumulated corpus ran
  343 s end-to-end. The budget governs the loop as contracted; whether the user-facing
  "deep ≈ 2–3 min" should include round-1 screening is a depth/time-budget-seam
  question (rev 3.12).

## Public safety

All committed content is code/tests/docs — no keys (env-only; actual-value grep over
artifacts: 0 hits), no third-party record content (evidence quotes counts/structure),
no traces committed. Live rows live in the dev DB only; Langfuse traces in the dev
project.

## Review handoff (step-7/8 inputs)

- **Executor provenance (family flip)**: lead — phases 1, 2 (task 2, 3a), quota fix,
  xfail adjudication, live check; Codex — 3b, 4, 5, 7, 8, 9, 11; fast-worker — 6, 10.
  Codex remained available throughout (no exhaustion fallback used). Lead review fixes
  on delegated output: harness `list[Any]` type erasure reverted (test double conformed
  instead); `importlib` guard-dodge replaced with direct imports + the honest guard
  extension; Overton paraphrase zero-result counting added.
- **Adjudication items**: the six flagged deviations above, esp. (1) `referenced_works`
  retention, (2) `lookup_dois`, (5) the rev-3.14 chain-smoke substrate correction
  (components §9/§1 flow-back rides step 8).
- **Diff-scoping**: exclude `uv.lock` and the scratchpad live-check driver/logs (not
  committed) from review diffs; no fixture data changed this slice.
- **Live-trace pointers**: dev Langfuse, project ids above (rapid `e8c7b46d…`,
  chain smoke `713264d8…`).
- **Step-8 records to author** (deferred from build per the phase skill): deferred.md
  rewrite (discharged: live SearchBackend · Arm-B · thin-base trigger; the full rev-3.x
  seam list per contract § Verification), knowledge concepts from the candidates below,
  components §1+§2 flow-back (incl. the rev-3.14 smoke-substrate correction), log.md.

### Knowledge candidates (014-retro capture)

- **A run cap without a per-call quota silently un-diversifies a fan-out**: with
  `max_results = remaining`, the first provider call eats the whole cap and every later
  query is skipped — the system degrades to exactly the single-load-bearing-query shape
  it was built to avoid, and nothing errors. Only the live check caught it (scripted
  tests returned small pages). Caps that exist to bound *totals* need a companion rule
  for *distribution*.
- **Whole-module import guards breed evasion**: the 007 zero-egress guard regex banned
  HTTP imports in every module, so a delegate "solved" the new live module with
  `importlib.import_module("httpx")` — technically passing, semantically defeating the
  guard. The honest move was extending the guard's allowlist + adding an import-shaped
  (not prose-shaped) assertion for acquire.py. Guards should name their real invariant,
  or agents will satisfy their letter.
- **Deep search's judge really is free**: steering the loop off persisted 3-rep
  consensus rows cost zero extra relevance calls live — round 2 screened only the 54
  NEW docs (NOT-EXISTS idempotency), and the 49 new confident-relevants both steered
  reformulation and stopped the loop (`target_reached`). The rev-3 unification held
  end-to-end on real data.
- **Live 429s arrive in bursts right after a fan-out**: OpenAlex rate-limited the very
  next run in the same process; the cap-1 retry absorbed every one, and the honest
  wall-clock breach (`breadth_truncated`, Overton leg skipped) behaved exactly as
  contracted. Rapid's 30 s budget is tight but real under rate pressure.
- **013's substrate rule quietly constrains every upstream demo**: synthesise refuses
  envelope-only corpora (`no_groundable_substrate`) — correct by design, but it means
  no chain that ends in synthesise can run on acquire-only data until 016. Rev 3.14's
  "synthesises over metadata envelopes" was written against the spec's intent, not the
  as-built rule.
- **Characterise's theme-discovery validation is the live-corpus canary**: real
  corpora (rich tags, 100+ docs) produced an API-timeout batch failure and a
  double `InvalidDiscoveryOutput` before a clean pass — the first component to wobble
  when 015 made inputs real. Its retry caps and batch sizes are eval-slice material.
- **Overton's tag layer is enormously richer live than fixtures suggested**: ~29
  publisher-curated tags/record (1456 tags on 50 records, two records over the 50-tag
  cap — the cap logged and bit for the first time). Bounds that never bound fixtures
  now bind.

## Review findings (step 7)

Stack run 2026-07-09, fresh conversation C. Lanes: contract-verifier (Opus,
read-only) · `/code-review` medium (8 scoped finder angles, Claude — anchored the
Codex-written surfaces) · security-auditor · Codex adversarial (read-only rescue,
anchored the lead/fast-worker surfaces) · lead live-trace content review (dev-DB;
Langfuse access not available to the review session). `make verify` confirmed green
before dispatch and re-run green after fixes.

**Adopted (fixed in-stack, regression-tested):**

1. **Overton unbounded pagination** (security, HIGH): an empty page carrying
   `next_page_url` looped forever (zero progress per iteration → unbounded egress).
   Fix: break on a zero-record page (`search_live.py`); test pairs empty `results`
   with a present `next_page_url`.
2. **Comma-borne OpenAlex filter injection** (Codex HIGH + security MEDIUM —
   convergent across both heterogeneous lanes): the sanitizer removed commas only
   *inside* quotes, while commas are the wire's filter-clause separator — a generated
   query could append arbitrary filter clauses (e.g. `x,is_retracted:true`), bypassing
   the fail-closed grammar; a benign comma 400'd the call. Fix: all commas → spaces in
   `sanitize_openalex_query`; the inverted test pin replaced with justification +
   injection regression test (rubric-5 note: test strengthened, not weakened).
3. **Diversity reserve was not a fraction** (contract-verifier F1 + finder angle A,
   convergent): `DIVERSITY_FRACTION` was dead code and the un-steered call ran with no
   `max_records`, able to drain the episode cap — documented-but-not-built at the
   mechanism grain (rubric 7 names the fraction). Fix: reserve =
   `result_cap × DIVERSITY_FRACTION`, asserted in the fixed-allocation test.
4. **`cited_by_count` guard over-matched** (finder A): the no-floor guard scanned the
   whole filter string including the free-text search value; a query naming the
   literal phrase failed the arm. Fix: guard scoped to wire filter clauses; both
   directions tested.
5. **Round-cap dual source of truth** (altitude angle): `run_deep_rounds` used
   `evaluate_deep_stop`'s default `ROUND_CAP` instead of the per-depth table. Fix:
   `round_cap=DEPTH_CONSTANTS["deep"]["round_cap"]` threaded explicitly.
6. **Quota rule copy-pasted 3×** (simplification angle): the live-check regression
   guard (`max(1, remaining // planned)`) now lives in one `_distribute_quota` helper.
7. **DOI normalization triplicated** (reuse angle): `search_loop` now aliases
   `acquire._normalize_doi` (input guard widened to non-str safely); the transport-local
   twin in `search_live` kept deliberately (transport must not import the DB layer —
   the zero-egress guard forbids the reverse direction) with a cross-reference comment.
8. **Rubric item 3 stale wording** (contract-verifier F2): pre-rev-3.13 "no new
   dependency / signature untouched" reconciled with the approved amendments in
   rubric.md; nothing unapproved shipped (verifier confirmed table count 25, migration
   scope exact).
9. **`generation_call_cap` decorative** (altitude angle): adjudicated as a *derived
   structural ceiling* (fixed arm caps × round cap cannot exceed it) — documented as
   such in `DepthConstants` rather than adding enforcement that can never fire; enforce
   at the call sites if arms ever become dynamic.

**Declined (recorded reasons):** deep round runs before a target check (Codex HIGH №1
+ finder A) — entry is gated by `should_escalate` on the rapid path and the
deep-profile episode is the plan-pinned deliberate demo; quota remainder never
redistributed (≤45<50) — the acknowledged deviation-4 trade, under-fill is the safe
direction; caps count raw pre-dedup records — caps bound transport volume by design;
deep-thin overlay overwrites the raw stop value — contract-pinned (rev 2), raw stop
visible in events; `finalise_deep_stop` uuid tiebreak — per-round rows get distinct
microsecond timestamps from distinct runs; snowball `per_seed` under-allocation with
<5 seeds — safe-direction budget under-use, eval-slice tuning; sequential HTTP in the
fan-out/arms (efficiency angle) — deliberate under the Overton limiter and observed
live 429 bursts, budgets currently met (28 s/30 s, 114 s/150 s); per-round event-log
re-scans — negligible at round-cap 3; dual wire-validator families and the two
`acquire_sources` branches — defense-in-depth / legacy-path collapse deferred to a
future cleanup slice; test-double and fixture-builder duplication across suites —
next-slice hoist to `tests/helpers.py`; diversity backend selected by name not caps
flag — single academic backend in v3.0, joins the caps-seam notes; query text echoed
unbounded into event payloads (security LOW) — no key exposure, generated queries are
already code-validated; nested `query.next_page_url` source + unauthenticated-follow
edge (security LOW) — host validation strict, worst case is the provider steering its
own pagination to an honest 401→retry→failure.

**Deferred to step-8 records:** coverage-record stop-condition grain (convergent:
contract-verifier F3 + Codex №5 + lead DB observation) — a clean rapid completion and
a wall-clock breach both persist `breadth_truncated`, and the deep overlay hides the
raw stop; the per-round `wall_clock_breached`/raw-stop facts live only in events/logs.
Inherited 007 vocabulary, joins the depth/time-budget seam. Also: 60-vs-50
`referenced_works` retain/batch headroom noted on deviation 1 (harmless).

**Live-trace content lane (lead):** persisted dev-DB evidence corroborates
verification.md — the (g) filtered-run wire params match the coverage rows verbatim;
the chain-smoke classify distribution matches exactly (16/8/3/5/2 across 9 types);
`methodological_structural × overton` tag rows present; key-pattern scan over all 78
015-window `search.executed` payloads: 0 hits. The two flagged characterise anomalies
were root-caused as far as the persisted record allows: no failed-run rows survive
(the driver leg's transaction rolled back), and `characterise.py:509-520` discards the
validator's rejection detail — only `error_type` reaches the logs, so the *reason* is
Langfuse-only. That is the 013 corollary (a decision diagnosable only from traces) in
pre-existing code 015 did not touch: recorded for step 8 as a deferred robustness item
(persist/log `str(exc)` on discovery rejection + eval-slice retry/batch calibration)
rather than fixed in-slice.

**Flagged-deviation adjudication (all six):** 1–4 and 6 adopted as flagged
(contract-verifier confirmed each accurately described; deviation 6 is unverifiable
from the diff — removed pre-commit — accepted on the build's account with skeleton
tests covering the moved behavior). Deviation 5 (chain-smoke substrate seeding)
adopted; its rev-3.14 wording correction rides the step-8 components flow-back as
planned.

**Fake-done check on in-stack fixes:** no test deleted/weakened (the one replaced
comma test is strengthened with written justification above); no swallowed errors
added; all fixes carry regression tests or are behavior-neutral refactors;
`make verify` green post-fix.

## Deferred work

Recorded at step 8 into `docs/deferred.md` per the contract's § Verification list
(retrieval-boost grammar v2 · select-as-tool seam · Overton-arm-B cross-backend
snowball · S2 third backend · filter-vocabulary growth seams · caching
(cache-before-throttle) · citation-floor knob · eval-reuse pointers + AstaBench/MetaSyn
stances · calibrated recall estimate · sliding-window TS · RCS compression · best-of-N
queries · study-geography extraction field · tool-wide depth/time-budget gradation).
