# Verification: 019-folding-pass

Evidence for one slice. Public-safe — no secrets, raw source text, credentials or unredacted traces.
Step 6 sections filled at build exit (2026-07-12); **Review findings** + **Rubric status** follow the
review stack (step 7, fresh conversation).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | final step-6 exit run — see § Final verify below |
| `make typecheck` | pass | mypy, 120 source files |
| `make lint` | pass | ruff |
| `make build` | pass | sdist + wheel |

Gate history: Phase 0 baseline full `make verify` green (1081 tests). Per-phase gates green at every
landing — A1/A2 `verify-fast` 1034 · A3 full `make test` 1086 (suite-wide socket deny proven on the
whole suite incl. ingest integration) · B `verify-fast` 1062 · C `verify-fast` 1081 · D2
`verify-fast` 1094 · Phase D exit full `make verify` exit 0 (migrations present). Any red mid-build
was fixed before its commit landed (see Diff summary item on the two codex-written DB tests).

## Checks beyond the build

- **Deterministic tests** (all in-suite, named in the phase commits): cache hit/expiry/
  throttle-interaction + error-non-caching + env-disable · embed 429-backoff paths + 128-unit
  poisoned-batch split isolation · allowlist fail-closed (`XX` rejected; "United Kingdom"/"GB"
  rejected for Overton `publisher_country` with the probed "UK" hinted) · Tier-1 group-expansion
  determinism + pinned counts (OECD 38 · G7 7 · G20 19 · EU27 27 · EEA 30 · Europe 51 incl. GB ·
  North America 41 · Oceania 29) · `country_group` plan-row round-trip (all three fields) ·
  ≤100 pass-through / 101–200 two-variant split / >200 rejection · Overton post-filter pagination +
  exclusion counts on event & coverage record · migrations `921d3a781f3f` + `b7f3d9a2c5e1` up/down
  round-trips (incl. pre-migration new-value rejection, historical-value retention, persisted
  step-name rewrite + `component.completed` untouched) · `excluded_retracted` (no backend call for a
  retracted doc; own funnel bucket; never eligible for classify/stage 2; idempotent rerun) ·
  stop-grain (`completed` / `wall_clock_exceeded` / `error` precedence) · select-at-standard
  composition (step lists, budget 15/25, findings-chain invariants, synthesise
  `deepest_successful_reference` picks the selection run at standard) · executor context propagation ·
  parallel-vetter parity with the sequential baseline + per-doc failure isolation · two-scopes-one-
  project coverage isolation · suite-wide socket-deny pin (`SocketConnectBlockedError`).
- **AI evals**: none — no judge-behaviour change in this slice (per contract).
- **Planner replay (lead, live probes — pennies pin)**: `planner_v2 → planner_v3`; two refine-replay
  rounds, 15 probes total. Round 1 exposed principled-but-inconsistent setting-vs-origin routing
  (the group filter fired on 1/5 group phrasings; the model correctly reasoned that an
  author-affiliation filter drops foreign-authored studies ABOUT a region, but applied the rule
  inconsistently). Refined line codifies it: study/programme-setting phrasings → screening
  criterion + the filter offered in the reply; source-origin phrasings → `country_group`. Round 2:
  Tier-1 labels fire on origin asks ("G7", "OECD members"), "Europe" chosen over "EU27" with the
  UK-inclusion reasoning stated; Tier-2 proposes explicit lists with the definitional choice named
  and a confirm question ("Nordic countries" → DK/FI/IS/NO/SE; "developing countries" → World Bank
  low/middle income, 139 codes — the >100 split case); exclusion grouping ("everywhere except the
  UK") declined honestly with a screening-rule fallback; select composes at standard in every
  standard-depth draft. Raw probe I/O retained locally + in Langfuse; summaries only here.
- **Manual / live**: the D1 rider run — § D1 rider below; Langfuse trace-nesting check rides its
  trace (item 4 acceptance): per-doc generations (screen reps, extract windows, vetter) nest under
  their component roots, vs the 018-recorded detached-root wart as the before state.

## End-to-end command

```
# from the repo root, .env providing OPENAI_API_KEY / LANGFUSE_* / OVERTON_API_KEY / DATABASE_URL
uv run python -m policy_atlas.orchestrate
# intent: "What interventions are effective at increasing heat pump adoption in UK homes?"
# -> approve (as proposed: standard×standard, characterise + screen_full + select)
# -> every steer point answered 1) Continue
```

(The recorded D1 run drove `orchestrate.main()` with a deterministic rule-based console — same code
path as the `python -m` entrypoint, the 017 pattern; transcript retained locally. First attempt
failed honestly at acquire on the un-migrated dev DB — the old `ck_scov_stop_condition` rejected the
new `completed` value, the 017 failure backstop caught it, collation rendered, exit 2, pennies spent;
`alembic upgrade head` on the dev DB, then the one composed run below.)

## Diff summary

Pre-eval Slice A: harden observed live weak points and discharge the folding-pass deferrals before
eval baselines are cut. Six phase commits on `task/019-folding-pass`:

- **A1** — unify `search_loop.py`'s two wire-validator helper families into one parameterized family
  (strict/coerce semantics preserved per call path, prep for the grammar growth); collapse
  `acquire_sources`' legacy no-executed-calls branch into the executed-calls path via a synthetic
  `_LegacySearchCall`; hoist duplicated `oa_record`/`ScriptedGenerationBackend` test doubles into
  `tests/helpers.py` (parameterized to preserve both files' drifted behaviours; `ov_record`
  deliberately left duplicated — divergence too risky to paper over mechanically).
- **A2** — `_discover_themes` rejection detail (`str(exc)`, 500-char cap) into logs + failure
  records; `bound_contextvars(project_id, run_id, component)` once per component execution at
  `run_harness`; `dict_tracebacks`/`format_exc_info` in the log processor chains; two-scopes-one-
  project coverage fixture test.
- **A3** — `pytest-socket` suite-wide deny with loopback allowlist (dev dep, gate 4 approved); five
  per-test deny patterns retired; the 016 worker-process guard and the fetch_live SSRF-assertion
  monkeypatches deliberately kept.
- **B** — country filters (item 3): new `country_filters.py` (ISO-3166 table; probed Overton
  display-name allowlist, 186 names; Tier-1 pinned provenance-stamped group tables); fail-closed
  allowlists on both single-country filters; `ScopeConstraints.country_group`
  {label, countries, authorship} with per-backend compile (OpenAlex ISO expansion, Overton native
  `publisher_region` for Tier-1, `source_country_post_filter` for Tier-2 — never a wire param);
  >100 two-variant split at the planned-call seam; Overton post-filter + deeper pagination with
  exclusion counts (owner decision 5); CLI render label+count+authorship; code-side authorship flip
  to `user-amended`; planner_v3 capability line (lead).
- **C** — `tracing.submit_with_context` on every traced/LLM executor fan-out; finding-vetter
  parallelized (workers judge, parent applies in input order); in-process TTL+LRU search-response
  cache checked before the rate limiter; embeddings 429 backoff + recursive split-on-failure.
- **D1/D2** — migration `921d3a781f3f` (stop-grain + `excluded_retracted` CHECK widenings, gates 1+2)
  and code: acquire records `completed`/`error`, rapid wall-clock breach `wall_clock_exceeded`;
  retracted docs exclude at stage 1 pre-backend as the distinct status, read paths updated.
  Migration `b7f3d9a2c5e1` (gate 3): `screen→screen_abstract`, `screen_stage2→screen_full` plan
  vocabulary + one-time data migration over persisted plan rows and the three step-name-carrying
  event types; `registry_component_for()` replaces the 11-row map (parity assert kept);
  `deep_chain` split into `select`/`findings_chain`, standard buys select at plan-pinned budget 15.

**Flagged deviations (minor, in-vocabulary):**
1. Item 6's fix also closed the analogous rejection-detail gaps on characterise's assignment path
   (same component; the deferral text said "when this component is next touched"). Cleanly separable.
2. Legacy-path `search.executed` events gained `verb`/`query_origin` keys (payload enrichment from
   the branch unification; `filters` stays `{}` exactly as pinned).
3. The two-scope coverage test's first draft asserted scope-local bases; the code's project-pool
   base is the documented pool-wide-screening semantics (owner-verified 2026-07-12), so the test now
   pins THAT: the other scope's docs are honestly `unscreened` for this one.
4. The Overton display-name probe took 265 rate-limited pp=1 calls (no vocabulary endpoint exists —
   verified against the API docs first): the contract's sanctioned "dev-time lookup" had no
   single-call form. Probe data + method stamped in `country_filters.py` provenance.
5. `breadth_truncated` is no longer written by any path (retained in the CHECK for historical rows;
   documented at the constraint).

## Review findings

Added after the review stack (step 7) — what each review caught and how it was resolved:

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review** (Tier 2+):
- **`/simplify`:**
- **`/okf validate`** (if specs/knowledge changed):

## Review findings

Added after the review stack (step 7) — what each review caught and how it was resolved:

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review** (Tier 2+):
- **`/simplify`:**
- **`/okf validate`** (if specs/knowledge changed):

## Rubric status

Filled at step 7 (review stack), per rubric.md. Note for the reviewer: rubric items 1–7 and 9–12
have their evidence in this file; item 8 (review stack) is the step-7 conversation's own output.

## Intent & assumptions

- Standard-depth `selection_budget` = 15 is a plan-pinned constant the lead chose (deep stays 25);
  the calibration is eval-slice work by contract. Nothing downstream keys on the specific value.
- Tier-1 group tables are OURS, provenance-stamped (M49 for continentals; institutional lists
  verified against oecd.org/europa.eu 2026-07-12); Overton's native `source_region` membership is
  the provider's — never asserted identical (both wires stamp what was actually sent).
- G20 expands to its 19 sovereign members (EU/AU institutional members deliberately not expanded);
  North America = M49 Northern America + Caribbean + Central America. Both choices stamped in
  `GROUP_PROVENANCE` and surfaced by the planner's honesty lines.
- Unsupported Overton display names (63, mostly territories + HK/CD/CG/TL with zero Overton
  documents) fail closed on `publisher_country` — functionally indistinguishable from invalid
  (filtering on them can only silently zero), which is exactly the hazard the allowlist closes.

## Known unverified items

- Overton `source_country_post_filter` behaviour is scripted-test-verified; no live Tier-2 group
  run was spent (live pin: D1 only). First live exercise arrives with real usage or evals.
- The 101–200 two-variant split is compile/test-verified; no live >100 search was run.
- Cache behaviour under a real 429 burst is test-simulated; the observed-burst scenario recurs
  naturally in eval sweeps.
- Planner_v3 depth-composition probes ran BEFORE Phase D's code landed (wire-level draft evidence);
  the post-D live proof that a standard draft compiles-and-runs with select is the D1 run itself.

## Public safety

All committed data is public-safe: country membership tables (public standards data with
provenance stamps), probed display names + counts (aggregate totals, no document content), planner
replay SUMMARIES only (raw probe I/O stays local/Langfuse). The D1 transcript and trace ids stay
local/Langfuse; no acquired source text in evidence. No secrets anywhere (probe scripts read keys
from .env; cache keys exclude credentials by construction).

## Review handoff (step-7/8 inputs)

- **Adjudication items**: the five flagged deviations in § Diff summary; the classify funnel choice
  (excluded_retracted folded into classify's blended "skipped" count, renamed
  `effective_not_relevant_or_excluded_retracted` — D1-lane justification: classify's skip bucket is
  already a catch-all, screening's own funnel carries the distinct bucket); `last_post_filter_excluded`
  as mutable backend state read post-call (serial-per-backend today; note for the concurrency-minded
  reviewer); exclusion counts homed in `search_coverage_record.scope_filters["post_filter_exclusions"]`
  (JSONB reuse, no schema change — is that the right long-term home?).
- **Executor provenance (family flip)**: Phase B and C product code is codex-authored
  (sessions 019f5444-f2cc-7a13-887f-83522dd8017c, 019f545d-9bed-7bb1-b9d8-22e858b15d80) — Claude
  lanes should anchor the review of those diffs. Phase A/D code is Claude-fast-worker-authored,
  lead-reviewed; a codex review lane is the natural heterogeneous check there. All prompt-bearing
  work (planner_v3) and all membership/allowlist source data: lead.
- **Diff-scoping exclusions (review-stack economy)**: `src/policy_atlas/country_filters.py`'s data
  literals (ISO table, display-name map, group tables — machine-derived from probes/M49/CSV,
  cross-checked by the lead against the source data byte-for-byte) and `uv.lock`. Review the
  helpers/validators in that module, not the table rows.
- **Live-trace pointers**: D1 run ids in § D1 rider below; raw traces in Langfuse.
- **Knowledge candidates** (014 retro; step 8 authors docs/knowledge/ from these + review findings):
  - Overton documents.php has NO facet/vocabulary enumeration (probed all param shapes + docs);
    display-name allowlists can only be built by per-candidate probing. Overton's idiom is common
    short names ("UK", "USA", "South Korea") plus the non-country value "IGO".
  - A planner capability line teaching a filter vocabulary can be silently defeated by an EARLIER
    honesty rule: the model routed group asks away from the new surface (study-geography ≠
    source-geography reasoning) until the prompt said which reading selects which surface. Only
    replay rounds catch this class — unit tests can't. (Refine-replay earned its keep again.)
  - Coverage base at characterise is project-pool-wide BY DESIGN (pool-wide per-question
    screening): scope-isolation tests must assert the other scope's docs as `unscreened`, not 0.
  - `contextvars.copy_context()` at executor submit propagates the OTel/Langfuse span context AND
    structlog bound_contextvars in one mechanism — telemetry items 4 and 7a composed for free.
  - `UsageAccumulator` is not thread-safe; the parallel-fan-out pattern is: workers return, the
    submitting thread accumulates in input order.
  - pytest-socket patches only the current process (multiprocessing-worker guards must stay) and
    raises `SocketConnectBlockedError` on connects — NOT a subclass of `SocketBlockedError`.
  - The codex sandbox has no Postgres and no localhost sockets: DB-backed tests codex writes are
    untested code — both such tests this slice carried a real bug (IOF rows have no pss column;
    doc identity joins through `source_extraction_record`). Lead must run them before commit.
  - A live run on the dev DB is a migration smoke test: the first D1 attempt failed exactly at the
    un-migrated CHECK and the 017 failure backstop caught it cleanly (honest failure + collation).
    `alembic upgrade head` on dev is now a pre-live-run checklist item.
  - The wall-clock-breach signal was already computed in `run_search` but never persisted — the
    honest-attribution fix was pure plumbing (parameter, not update-after) because acquire runs
    synchronously inside the same invocation.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) — this slice's sweep discharged/narrowed 16
entries (country filters, caching, stop-grain, Langfuse thread half, embed robustness, rejection
detail, socket deny, vetter parallelization, is_retracted half, registry collapse, rename,
select-at-standard half, review-stack cleanups, bind_contextvars) and ADDED the multi-question-
project reuse seam entry (§ Data model / evidence) + folded the left-out groups (VHHD · APAC ·
exclusion groups · is_global_south probe evidence) into filter-vocabulary growth.

## D1 rider (018 Phase D carriage — measured run, band re-seed, $ adjudication)

**The one composed standard run** (live pin honoured — rubric item 12): 2026-07-12, heat-pump
anchor question, standard×standard with the select-at-standard composition (characterise +
screen_full + select), project `b63ac9b0`, plan `8334ecb0`, exit 0, artefact minted.
**805 s ≈ 13.4 min end to end** (per-component: acquire 12.0s · screen_abstract 14.1s ·
classify 58.3s · appraise 0.1s · ingest 75.7s · screen_full 5.8s · characterise 8.1s ·
select 5.3s · synthesise 602.2s). 58 docs acquired; `stop_condition: completed` — the new
stop-grain vocabulary live; the persisted step names show the rename live.

- **`TIME_BANDS` standard×standard re-seeded** `~30-45 min` → `~10-20 min` (measured anchor in the
  code comment). Band-target verdict: INSIDE ~15–20 min. Select-at-standard adds ~5 s.
- **Multi-read `$` verdict: PIN STANDS** — realized synthesise cache hit 42.2% (994,517 prompt /
  419,840 cached); v5 bills ≈20% less input than the v4 counterfactual at a 50% cached-token
  discount and ≈neutral at 90%. Full working + verdict written to 018 verification.md
  (§ Phase log D1 + § Review handoff). No revert; no prompt change.
- **Item-4 trace evidence:** zero parentless generations across all component traces —
  `run:screen_abstract:b180de7f` (trace `b2e159e284de6ea4057f4a191910ec1b`): 174 generations, 1
  root; synthesise (`5c6a340e…`): 49 generations, 0 orphans. Before-state: 018's recorded
  detached-root executor wart.
- **Incidents:** two failed attempts before the run (pennies; recorded in 018 § Phase log D1):
  un-migrated dev DB tripping the new CHECK (backstop worked — `alembic upgrade head` on dev now a
  pre-live-run step), and a driver missing the `__main__` spawn guard (the 014 lesson) plus a
  planner turn proposing standard×deep on the same intent (driver now verifies the composition
  before approving). No additional e2e runs were spent.

## Plan-time probe evidence (2026-07-12, lead; owner authorized the Overton key)

**OpenAlex (keyless, 4 calls):** `authorships.countries` filter caps at 100 values —
131 codes → HTTP 400 "Maximum number of values exceeded … Decrease values to 100 or
below"; 100 codes → 200, total 38,370,301. Native
`authorships.institutions.is_global_south:true` → 200, total 40,827,452
(magnitude-consistent with the ~100-country hand list).

**Overton (6 calls, keyword mode `query=climate` so totals are uncapped; `pp=1`):**
`source_country=France` → 42,183 · `Germany` → 42,370 ·
`France,Germany` → **0, no error** · `France|Germany` → **0, no error** ·
`source_country[]=France&source_country[]=Germany` → **0, no error** ·
`source_country=France&source_country=Germany` (repeated) → **42,370 =
last-value-wins, silent discard**. Conclusion: `source_country` is single-valued;
every multi-value idiom fails silently (the 015-recorded silent-zero hazard shape).
Feeds plan § Gate decisions item 5.

## Gate decisions (owner, 2026-07-12 — at plan approval; rubric item 9)

1. Coverage stop-grain CHECK migration: **APPROVED** as scoped (one-line widening +
   down-migration).
2. `is_retracted` at screening: **distinct excluded status** (e.g.
   `excluded_retracted`) riding the same migration — visible, attributed, never
   conflated with a relevance verdict; read paths updated.
3. Screen-stage rename persisted vocabulary: **one-time data migration** (rows exist
   only in dev/test DBs pre-launch; no permanent read-side alias).
4. `pytest-socket` dev dependency: **APPROVED**.
5. Tier-2 Overton handling: **post-filter + deeper pagination APPROVED** (rank-
   preserving, membership-enforcing, exclusions on coverage/provenance). Per-country
   fan-out REJECTED (covert budget stratification — owner reasoning recorded in
   plan § 5); pure asymmetry REJECTED (screen does not enforce membership);
   `is_global_south` adoption DROPPED (owner de-scope: "developing" is a rare ask
   for target users; probe evidence parked at the filter-vocabulary seam).

## Post-approval amendment (owner, 2026-07-12)

Contract item 13 **select-at-standard regrade** added after plan approval, pulled
forward from Slice C phase 2: select runs at standard depth decoupled from
extraction (extract + group stay deep-only). Owner rationale: the D1 rider re-seeds
`TIME_BANDS` standard×standard, and measuring the without-select composition would
mint a band known to be wrong as soon as the regrade lands — select at standard
guides synthesis (retrieval prior + citation-origin accounting) and was already an
owner call (2026-07-12 adjudication). Slice C retains the boost *calibration* and
the cost-work band re-measure.
