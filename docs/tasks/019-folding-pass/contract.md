# Task contract: 019-folding-pass

Pre-eval **Slice A** of the owner-adjudicated sequencing (2026-07-12): the folding pass.
Small robustness/hygiene deferrals that must land before eval baselines are cut, because
they either shift what a run records (screening eligibility, coverage stop grain) or
protect eval runs from observed live failure modes (429 bursts). Prompt/constant tuning
stays post-eval; nothing here retunes quality knobs.

> **Status:** approved. Contract approved (before planning): 2026-07-12 · owner ·
> Plan approved (before implementation): 2026-07-12 · owner (all five gate decisions
> decided — see plan.md § Gate decisions and verification.md § Gate decisions) ·
> ADR: none (owner accepted the CHECK migration as a constraint-vocabulary widening).

## Goal

Harden the live pipeline's already-observed weak points and discharge the folding-pass
deferrals so the eval slice measures the system, not its known warts: search-response
caching before throttling, embed-pass 429/batch robustness, fail-closed country filters
with deterministic group expansion, Langfuse trace nesting for threaded workers, honest
coverage stop attribution, persisted grouping-rejection detail, and the two logging /
test-hygiene riders. One explicitly gated eligibility decision: `is_retracted` at
screening.

## Deliverable

One PR to `dev` landing the items below, with the two gate decisions (coverage-grain
CHECK migration · `is_retracted` screening eligibility) recorded as decisions, not
inherited. Source deferrals in `docs/deferred.md` discharged or narrowed in the same PR.

## Read first

- `docs/deferred.md` — the entries this slice discharges: § Live search (country filter
  allowlists; caching cache-before-throttle; coverage-record stop-condition grain under
  the depth-gradation entry), § Characterise/embeddings/telemetry (Langfuse trace
  grouping; embed-pass live robustness; `_discover_themes` rejection detail), § Select
  (suite-wide socket deny), § end matter (`bind_contextvars` + `exc_info`), § Acquired
  envelope (`is_retracted` retained-but-unread).
- [EB capability](../../specs/capabilities/evidence-base/capability.md) § screening —
  for the `is_retracted` gate framing (flag-not-drop discipline).
- [data-model](../../specs/system/data-model.md) — coverage record, before touching its
  CHECK.
- `docs/specs/system/prompting.md` — binding for the planner capability-line half.

## Scope / Out of scope

**In** (with the adjudicated delegation posture — largely delegable; the one
prompt-bearing half is lead-only):

1. **Search-response caching (cache-before-throttle)** — `search_live.py`: cache live
   search responses so back-to-back runs (and eval sweeps) stop re-triggering observed
   OpenAlex 429 bursts. Cache is an egress *reducer*; no new endpoints.
2. **Embed-pass robustness** — `embeddings.py`: rate-limit backoff under real 429s
   (documenting the `max_retries` HTTP-ceiling multiplier at the client seam) and
   batch-failure isolation (split-on-failure so one bad unit no longer fails its whole
   128-unit API batch).
3. **Country filter allowlists + country-group support** — build on what 015 already
   shipped: Overton group filtering EXISTS as `publisher_region` → `source_region`
   against the pinned named-group enum (`OVERTON_REGION_GROUPS`; live-probed, 015
   param-pinning: 50/50 verification on `OECD members`). Remaining work: (a)
   fail-closed allowlists for the two shape-only single-country filters — static
   ISO-3166 set for OpenAlex `author_affiliation_countries`, probed display-name
   list for Overton `publisher_country` (the recorded silent-zero hazard); (b) the
   **group vocabulary (owner calls, 2026-07-12)** — anchored on Overton's named
   groups, expanded per backend from static provenance-stamped tables at compile,
   never the LLM listing members inline. Two tiers:
   *Tier 1 (build unconditionally — Overton-native named groups):*
   `OECD members` · `G7` · `G20` · `EU27` · `EEA` (institution-defined) plus the
   continentals `Europe` · `North America` · `Oceania` (owner: continental
   assumptions are acceptable; the UK case is motivating — "Europe" must include
   the UK where `EU27` would not). Overton → native `source_region` named group;
   OpenAlex → pinned ISO expansion (UN-geoscheme-based for continents). Both wires
   stamp what was actually sent; Overton's membership is the provider's, ours is
   the table's — never asserted identical.
   *Tier 2 — planner-proposed explicit lists (owner refinement, 2026-07-12, of the
   2026-07-11 "never LLM inline" ruling):* for any grouping outside Tier 1
   ("developing", "Commonwealth", "MENA", non-Overton-native continents, …) the
   planner proposes an **explicit country list in the plan surface**, names its
   definitional choice, and the user confirms or amends it before the run. The
   approved plan persists **both the phrase and the list** — `{label, countries,
   authorship}` (owner, 2026-07-12: the phrase is the label, the list is the
   truth): compile reads ONLY `countries`, validated fail-closed against the
   item-(a) allowlist; `label` is display/provenance metadata; `authorship`
   records pinned-table | planner-proposed/user-approved | user-amended. Display
   collapses to label + member count (the count is the one-glance signal a large
   expansion happened), expandable to full membership — for this slice that means
   the CLI plan render shows label + count and the conversation supplies the full
   list on request; the disclosure widget is web-app-slice territory inheriting
   this shape. If the user amends a proposed list, authorship flips to
   `user-amended` and the surface says so — a label must never keep claiming a
   definition its list no longer matches. The refined principle: LLM-authored
   lists are legitimate when plan-visible and user-confirmed — what stays
   forbidden is silent compilation. No pinned tables for the tail; the build here
   is planner prompt guidance (part of the capability-line half) + the validation
   that (a) ships anyway. Wire probe still
   required: OpenAlex `author_affiliation_countries` takes lists (probe long-list
   behaviour at ~130 values); Overton `source_country` is **single-valued as
   built** — probe multi-value support. If Overton cannot: owner decides at plan
   approval between honest asymmetric filtering (OpenAlex filtered, Overton
   unfiltered — stamped on provenance and surfaced, never silent) and a planner
   decline for list-shaped groups.
   (c) **Left out**: `Very high human development`, `APAC` (not continental,
   definitionally fuzzy) and V2-style exclusion groups ("All but UK", untested) —
   seam-recorded in deferred.md's filter-vocabulary growth entry, not built.
   (d) Surface note: the planner today emits plan-level `scope_constraints`
   (`publisher_country`, `author_affiliation_countries` — taught in 018);
   `publisher_region` has been grammar-only since 015 and planner-dark. The group
   work gives the planner a group-token surface that compiles per-backend as above.
   Touches grammar + both wire mappings + the planner capability line — **the
   capability-line half (teaching the group vocabulary) is prompt-bearing:
   lead-only, replay-evidenced on planner probes**.
4. **Langfuse thread-context propagation** — propagate the component-span context into
   `ThreadPoolExecutor` workers (extract windows, screening fan-outs) so per-doc
   generations nest under the component root instead of minting detached root traces.
   Planner-turn conversation-root grouping stays out (recorded second half; separate
   call).
5. **Coverage-record stop/attribution grain** — richer stop/attribution vocabulary so a
   clean rapid completion and a wall-clock breach stop persisting the same
   `breadth_truncated`; one-line CHECK migration. **Schema gate — see Constraints.**
6. **`_discover_themes` rejection-detail persistence** — persist/log `str(exc)` so
   grouping rejection reasons stop being diagnosable only from Langfuse.
7. **Riders:** `structlog.contextvars.bind_contextvars` once per run/component (stop
   hand-threading `project_id`/`run_id` kwargs) + an `exc_info`/traceback renderer in
   the processor chain; `pytest-socket` suite-wide socket deny (deny by default,
   allowlist the DB host), replacing the three per-test deny patterns. **Dependency
   gate — see Constraints.**
8. **Gated decision — `is_retracted` at screening** (owner, 2026-07-10: its home is
   screening, not the writer envelope): whether/how a retracted document screens out.
   Eligibility change with flag-not-drop implications — a retracted doc that screens
   out must do so as a visible, attributed outcome, never a silent drop. Must precede
   evals (it shifts screening baselines). **Decision recorded at plan approval; if the
   owner declines, the deferral stays and says why.**
9. **D1 rider (018 Phase D carriage — owner-present session; this PR is the commit
   vehicle only):** one fresh composed standard run → re-seed `TIME_BANDS`
   standard×standard (displayed-band-is-measured); record the ~15–20 min target
   verdict honestly; adjudicate the multi-read `$` verdict on that run's billing
   (cache-discounted curve, 64%→23% hit-rate question — verification.md § Review
   handoff item). If the verdict is revert, the revert to `synthesise_section_v5`'s
   multi-read wiring is a small **lead-only prompt-surface change** riding this PR.
   The rider also carries 018's D1-shaped records: the D1 phase-log entry in
   `docs/tasks/018-dress-rehearsal/verification.md` and the `$`-verdict line in its
   § Review handoff. Deliberately short-lived: Slice C re-measures the band again
   (select-at-standard + cost work change standard-run timing) — no over-investment.
10. **Trigger-fired cleanups + micro-wins (deferred.md sweep, 2026-07-12 — all
    mechanical, fast-worker lane, behaviour-preserving, tests pin each):**
    (a) unify the two wire-validator families in `search_loop.py` — the 015-recorded
    trigger ("when the filter grammar next grows") fires with item 3's growth;
    (b) collapse `_REGISTRY_COMPONENT_BY_STEP` to a one-line function keeping the
    startup parity assert — owner-queued (2026-07-11) for the next slice touching
    `orchestration_plan.py`, which item 3 (and the D1 `TIME_BANDS` re-seed) does;
    (c) collapse `acquire_sources`' legacy no-executed-calls branch into the
    executed-calls path (015 cleanup candidate);
    (d) hoist the duplicated `oa_record`/scripted-generation test doubles into
    `tests/helpers.py` (015 cleanup candidate);
    (e) the two-scopes-one-project coverage fixture test (009/012 — semantics verified
    correct, combination untested); alongside it, the PR's deferred.md sweep adds one
    NEW seam entry (docs only, no build): multi-question-project reuse questions for
    the workspace-cluster contracts (owner conversation, 2026-07-12) — project-grain
    classify label reuse (an extraction-memo-style seam, respecting the
    Unknown-resolution staged-result pattern) · appraisal reuse keyed on
    `rubric_version` (per-scope rows are a deliberate hedge for the plan-carried
    rubric seam) · pool-wide per-question screening cost growth.
    Any of these growing beyond a mechanical diff is a stop condition: drop it back to
    deferred.md rather than negotiate scope.
11. **Finding-vetter parallelization (owner call, 2026-07-12 — pulled forward from its
    D-phase-timing trigger):** `_apply_finding_vetter` currently loops one live mini
    call per extracted doc on the main thread (`extract.py` post-`_run_windows`),
    right after the same file fans out the window calls on a 4-wide
    `ThreadPoolExecutor`. Parallelize the vetter loop with the existing executor
    pattern + a thread-safe usage-accumulation story (`usage_accumulator.add` is the
    serial assumption). **Ordering constraint: lands WITH or AFTER item 4** — the
    vetter's traces nest under the extract component root today precisely because it
    runs sequentially on the main thread; parallelizing without the thread-context
    propagation would mint detached traces (regressing the wart item 4 fixes).
12. **Screen-stage rename `screen` → `screen_abstract`, `screen_stage2` →
    `screen_full` (owner call, 2026-07-12):** plan-vocabulary strings only — the DB
    stores stage as an integer (`ck_ssr_stage`) and component names never reach the
    UI. Touches `DiscretionaryComponent`, runner step lists, the
    `_REGISTRY_COMPONENT_BY_STEP` map (do together with item 10b — the collapsed
    function stays one line), and the **persisted** `orchestration_plan` rows and
    event payloads that carry step names. **Gate decision at plan approval:** data
    migration rewriting persisted vocabulary vs a read-side alias (see Constraints).

**Out:** Slice B (extract schema bump — `effect_basis`, envelope fencing, study
geography) · Slice C (multi-facet grouping, cost/surface work) · retrieval-boost
grammar v2 · Thompson sampling / recall estimates / best-of-N · planner prompt work
beyond the one capability line · appraisal's `is_retracted` second-pass visible-flag
reading · the demo branch and **D2** (C4 + the rehearsal stay 018 trailing work on
their own lanes; only D1's artifacts ride here) · everything else in
`docs/deferred.md`.

## Constraints & approval gates

- **Schema (needs human approval):** item 5's CHECK migration — coverage-record
  stop-vocabulary widening. One-line, with down-migration. No other schema change.
- **Screening eligibility (needs human approval):** item 8 — behaviour change to what
  screens in; adjudicated explicitly at plan approval.
- **Dependencies (needs human approval):** `pytest-socket` (dev-only test dependency).
- **Persisted-vocabulary handling (needs human approval):** item 12's rename — old
  step names live in persisted `orchestration_plan` rows and event payloads; decide
  data migration vs read-side alias at plan approval (a migration is another schema
  gate; an alias is code-only but permanent read-path vocabulary).
- **Egress:** no new egress; caching reduces calls to existing approved providers. The
  Overton display-name probe is a dev-time lookup, not product egress.
- Country membership tables are static, provenance-stamped data — not fetched at
  runtime, not LLM-generated.

## Public / private boundary

All code, tables and migrations are public-safe. Planner replay evidence lands as
summaries in `verification.md`; raw traces stay in Langfuse.

## Model route

One prompt-bearing change: the planner capability line for country groups (OpenAI
route, unchanged models). Lead-only, replay-evidenced (planner probes are pennies,
unrestricted per the 018 live-check pin). Contingent second: if the D1 `$` verdict
says revert, the multi-read revert on `synthesise_section_v5` — lead-only, decided
by measured billing, not re-tuned. No other inference change. Live-run budget: the
D1 rider is exactly ONE composed standard run (the 018 live-check pin carried over);
no other e2e runs.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — the stop-grain vocabulary widens only to values the
  loop actually distinguishes today.
- **Flag, don't drop** — governs the `is_retracted` design and split-on-failure
  accounting (failed chunks re-embed next pass, honestly reported).
- **Honest absence** — coverage stop attribution is exactly this discipline applied to
  the coverage record.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: any gate above is hit without recorded approval · the country
allowlist work would grow into filter-vocabulary expansion (venue/funder/topic — out) ·
Langfuse propagation demands restructuring the executor beyond context-passing ·
`is_retracted` turns out to need appraisal-side work · budget spent.

## Acceptance checks

- `make verify` green (all deterministic: no judge-behaviour change in this slice).
- New tests: cache hit/expiry + throttle-interaction · backoff + split-on-failure
  isolation (one poisoned unit fails only itself) · allowlist fail-closed (`XX`
  rejected; ISO codes / "United Kingdom" hazard covered for Overton) · group-token
  expansion determinism · stop-grain migration up/down · rejection-detail presence ·
  suite green under `pytest-socket` with DB allowlist.
- Planner replay: capability-line change evidenced on recorded planner probes across
  group-token phrasings, including one honest-decline case.
- Manual: one recorded replay's Langfuse trace shows per-doc generations nested under
  the component root (before/after screenshot or trace-id note).
- D1 rider: `TIME_BANDS` standard×standard re-seeded from the measured run (trace id
  recorded); band-target verdict and `$` adjudication written to 018's
  verification.md; if reverted, multi-read revert replay-evidenced.

## Verification evidence expected

`verification.md`: command results, migration up/down evidence, planner replay
summaries, the two gate decisions with owner sign-off dates, deferred.md diff summary,
known gaps.

## Risk tier & review focus

**Tier 2** (feature slice), with two elements called out above their tier: the CHECK
migration (migration class — human-approved plan + rollback note required; a full ADR
looks disproportionate for a constraint-vocabulary widening, owner may overrule at
contract approval) and the `is_retracted` eligibility change (data-integrity-adjacent —
include in the security/adversarial focus). Review stack per
[review-stack economy]: medium `/code-review`, one security lane (allowlist
fail-closedness, cache poisoning/staleness posture, socket-deny coverage), contract
verifier fresh-context, per-angle diff scoping, data tables excluded from review diffs.

Focus: fail-closed completeness of the allowlists · flag-not-drop fidelity of the
screening change · migration correctness · no scope creep into Slice B/C surfaces.
