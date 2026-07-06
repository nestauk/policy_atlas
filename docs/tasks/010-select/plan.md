# Implementation Plan: 010-select

> **Status:** rev 2 — plan-stage adversarial review adjudicated (Codex,
> 2026-07-06, 9 findings: 2 blockers · 6 majors · 1 minor — 9/9 adopted, finding
> 1 with a redesigned remedy; § Findings & adjudication). Pending human 🛑, which
> also covers the flagged contract amendment (explicit `characterisation_run_id`
> — contract rev 7). ADR 0006 written at that gate (Task 8b).
> Contract: [contract.md](contract.md) (approved 2026-07-06 · Shabeer Rauf, rev 5;
> contract-stage adversarial findings adjudicated at rev 6; user follow-ups at
> rev 6.1; plan-stage amendment at rev 7).

## Overview

One component and one small seam, on `task/010-select`:
1. **Schema** — `selection_result` (migration 10; tables 19 → 20).
2. **Ranking layer** — `RankingBackend` seam (live OpenAI + stub), the
   lead-authored `select_rerank_v1` prompt, Langfuse tracing on the live backend.
3. **`select.py`** — directive validation, signal assembly, stratification over
   the explicitly referenced characterisation row (`characterisation_run_id`),
   the exact allocation arithmetic, two strategies (`coverage_stratified_v1` ·
   `llm_rerank_v1`), bidirectional rationale, trigger flags, selection row,
   selection summary.
4. **Wiring + tests + one spec flow-back** (components §6 realisation refinement).

Smaller than 009 by construction: one table, one prompt, one backend seam, no
embeddings, no new dependency. The deterministic strategy is the suite path; the
LLM path degrades to it per document.

## Executor routing (plan-time decision, per harness.md ladder)

| Task | Executor | Why |
|---|---|---|
| 1 (schema + migration 10) | `lead` | gated surface; composite-FK targets verified against as-built uniques (008/009 precedent — the adjudicator owns migration subtleties) |
| 2 (`select_rerank_v1` prompt) | `lead` | prompt-bearing — lead-only per AGENTS.md, no exceptions |
| 3 (`ranking.py`: protocol + OpenAI + stub + tracing) | `codex` | implementation of a lead-designed seam against schema-constrained I/O (the `GroupingBackend` pattern, one stage instead of two); done = backend construction/stub/no-op tests |
| 4 (`select.py`: directive → signals → strata → allocation → strategies → rationale → row → summary) | `codex` | judgment-bearing execution with a fully pinned arithmetic spec (contract decisions 3, 4, 10); done = the allocation + directive + rerank test blocks |
| 5 (registry/harness/skeleton/helpers wiring) | `fast-worker` | mechanical from the 004–009 precedent + the exact spec below |
| 6 (test suite: contract bulk) | `fast-worker` | transcription of the contract's test list |
| 7 (test suite: judgment cases — adversarial allocation fixtures, counting double, socket-deny, injection shapes, commensurability) | `codex` | subtle-but-specified; each has an exact pass condition |
| 8 (spec flow-back + log.md) | `lead` | living-spec text, user-approved wording |
| 8b (ADR 0006) | `lead` | design record, written at plan confirmation before the build |
| 9 (verification.md + live manual run) | `lead` | needs operator keys, cost judgment, trace inspection |

Lead marks carry their justification inline; the burden sits on keeping work, not
delegating it. Codex briefs are one-concern, self-checkable; anything failing the
brief test at build time is a plan deviation to flag, not silently absorb.

## Plan-pinned details (the contract's named "plan gate" items)

- **Rerank model**: `gpt-5-mini` (constant in `ranking.py`; 009's recorded lesson —
  nano-class emits schema-valid empty output on batched structured judgment).
  Recorded in `selection_provenance`.
- **Batching**: rerank batch size **25** (score+reason output per doc is heavier
  than 009's assignment); concurrency = bounded executor, **4** in flight;
  `rerank_retry_cap = 1` (one retry per failed batch, then whole-batch fallback).
  Call budget: baseline `ceil(contested/25)`, enforced max
  `ceil(contested/25) × (1 + 1)`, checked before any live call.
- **Scores**: integers **0–10** (schema-enforced, contract rev 6.1); `reason` ≤ 240
  chars, printable unicode minus control chars (the 009 theme-description
  constraint applied); violations → that doc falls back (`rank_fallback`).
- **Ranked set per contested stratum**: its eligible candidates **minus
  must-includes** (already selected; never sent for ranking).
- **Default budget**: `DEFAULT_SELECTION_BUDGET = 25` (named constant; applies when
  the directive is empty or omits `budget`).
- **Composite signals — normalisation** (each to [0, 1]; missing values take the
  neutral 0.5 **and** flag the doc, flag-not-block):
  - recency: `max(0, 1 − age_years/15)` from metadata year; unknown year → 0.5.
  - quality: `(quality_score − 1)/4` (as-built 1–5 scale, schema.py:352).
  - screen confidence: as stored (`screen_decision_confidence`); null → 0.5.
  - origin: `uploaded` 1.0 · `acquired` 0.5.
  - text_basis: `full_text` 1.0 · `abstract_only` 0.25 (the rev-5 soft tilt).
- **Default weights** (`DEFAULT_WEIGHTS`, named constant): recency .25 · quality
  .25 · text_basis .20 · screen_confidence .15 · origin .15. Honestly arbitrary
  pending selection-quality evals — recorded as such in the constant's docstring.
- **Directive** (`SelectionDirective`, first-class dataclass; v3.0 source =
  `evidence_scope.context["selection"]`; exact JSON schema):
  `budget: int > 0` · `must_include_ids: [uuid]` ·
  `boosts: [{match, weight}]` where `match` is exactly one of
  `{column, equals|in}` (closed set: `origin`, `primary_evidence_type`,
  `text_basis`) / `{tag_type, tag[, asserted_by]}` (exact match) /
  `{year: {gte?, lte?}}`; each `weight ∈ [0.1, 10]` ·
  `weight_emphasis: {signal: mult ∈ [0.1, 10]}` (keys = the five signal names) ·
  `priority_strata: [pattern]` (case-insensitive substring match against stratum
  names; also matches if any stratum member carries a tag equal to the pattern).
  Boosts multiply the composite; the product of matched boosts is clamped to
  **[0.1, 10]** before applying. Unknown keys, wrong types, out-of-range values →
  **fail closed** (structured error, `component.failed`). Unknown column values /
  unmatched tag or priority patterns → flagged in provenance, non-fatal.
  **Effective-weight formula** (adversarial finding 6):
  `effective_w[i] = default_w[i] × emphasis[i]` (absent key → 1.0), **no
  renormalisation and no further clamp** — emphasis is already bounded [0.1, 10]
  and composites are compared **within a stratum only**, so absolute scale is
  inert; `composite(doc) = (Σ effective_w[i] × signal[i]) ×
  clamp(∏ matched_boost_weights, 0.1, 10)`. Effective weights and the clamped
  boost multiplier are recorded per-doc-class in `selection_provenance`.
  **Priority matching is casefolded on both sides** (adversarial finding 7):
  `pattern.casefold()` substring-matched against `stratum_name.casefold()`, and
  equality-matched against each member tag's `tag.casefold()`
  (`source_tag.tag` preserves source case — schema.py:489); mixed-case fixture
  test required.
- **Trigger thresholds** (named constants): `LARGE_STRATUM_SHARE = 0.20` (an
  unselected-from stratum holding ≥ 20% of eligible) · `SUFFICIENT_CONFIDENCE
  = 0.6` and `THIN_BASE_FLOOR = 10` (thin_base; honestly stub-constant until the
  LLM screen tool lands) · `THIN_FULL_TEXT_SHARE = 0.5` (selected set).
- **Eligibility vocabulary** (as-built strings, schema.py:286): Non-evidence =
  `"Other (Non-evidence documents)"` (excluded, counted); Unknown =
  `"Unknown / Insufficient information"` (eligible). Unclassified (NULL) docs are
  eligible (nothing has asserted non-evidence).
- **Candidate query**: reuse the `_screened_sources` query logic
  (characterise.py:186) — promote it to a shared helper or mirror it
  project-scoped; `_ScreenedSource` already carries every signal field
  (characterise.py:85–99).
- **Strata input**: the same-run `characterisation_result.themes` JSONB — as-built
  shape `{themes: [{name, description, member_ids, size}], unclustered_ids}`
  (characterise.py:683); `member_ids`/`unclustered_ids` are stringified pss UUIDs.
  Stratum membership at select time = member ids ∩ eligible set.
- **Selection summary shape**: `{strata: [{name, candidate_count,
  allocated_count, selected_count, selected_ids,
  full_text_share_candidates, full_text_share_selected}], selected: {count,
  by_reason}, excluded: {by_stratum_reason_counts, notable}, base: {screened_in,
  non_evidence, eligible}, characterisation_run_id, flags: [...],
  provenance: {...}}` — counts named as counts, per-stratum picks renderable
  from `selected_ids` (adversarial finding 9); exact keys frozen in Task 4 and
  asserted by the payload test.
- **Langfuse**: spans `rank:batch{i}` are opened **inside
  `OpenAIRankingBackend`**, where `response.usage` is available (adversarial
  finding 8 — the as-built grouping pattern, grouping.py:344: the protocol
  returns parsed data only, so token counts can't be traced from outside the
  backend); metadata = batch index, doc ids, model, prompt version, token
  counts, validation outcome, fallback counts; batch validation outcome as a
  score (`rank_batch_valid` 0/1). Full I/O per the settled posture. No-op
  without keys; the stub is never traced.
- **Stub ranker**: deterministic score = `int(sha256(pss_id)[:8], 16) % 11`,
  reason = fixed template string — spread, reproducible, egress-free. Misbehaving
  doubles (missing ids, duplicates, out-of-range scores) are Task-7 test fixtures,
  not the stub.

## Architecture decisions (all fixed in the approved contract)

- Candidates = screened-in **eligible** (Non-evidence excluded, counted; Unknown +
  unclassified eligible). Invariants: `screened_in == non_evidence + eligible`;
  `eligible == selected + not_selected`; `selected == must_include + breadth_floor
  + ranked`.
- Allocation, in order: must-includes (outside budget; satisfy their stratum's
  floor) → breadth floor one-per-uncovered-stratum in deterministic stratum order
  (candidate count desc, name), stopping when budget exhausts → largest-remainder
  proportional over remaining candidate counts with exhausted-stratum
  redistribution. Reason precedence `must_include > breadth_floor > ranked`.
- Two strategies over one structure; `llm_rerank_v1` orders **contested strata
  only** (allocation < candidates); scored-before-fallback within a stratum
  (score desc → composite desc → pss id; fallback block: composite desc → pss id);
  LLM scores order, never exclude; whole-stratum fallback ≡ deterministic order.
- Directive semantics: positive bounded multiplicative weights, clamp, fail-closed
  validation; boosts re-weight, never exclude; priority is soft for selection,
  hard for escalation.
- One run-scoped row per (scope, run) — keyed by **select's own run**; the
  characterisation it stratified over is an explicit reference
  (`characterisation_run_id`, required at compile, recorded in provenance).
  Written once at success, **as the last statement** after all fallible work;
  empty scope writes **no row** (summary + `empty_scope` flag only); retry =
  new run; UNIQUE makes same-run rewrite a loud error.
- Determinism (deterministic strategy): byte-identical payload columns, PK and
  `created_at` excluded.
- Trigger flags: `large_stratum_excluded` · `priority_stratum_excluded` (hardest)
  · `must_include_conflict` · `thin_base` · `thin_full_text`. Pause machinery
  stays a seam.
- Egress: env-only keys; stub default; skeleton live on configured key; pre-call
  budget check; socket-deny covers the suite path.

## Dependency graph

```
Task 1 (schema + migration 10)
   ├─→ Task 2 (prompt, lead) ─→ Task 3 (ranking.py + tracing)
   │                                └─→ Task 4 (select.py)
   └────────────────────────────────────┴─→ Task 5 (wiring) ─→ Tasks 6+7 (tests)
                            Task 8 (flow-back) · Task 8b (ADR, at plan 🛑) · Task 9 (verification)
```

---

## Phase 1 — Schema (separable commit)

### Task 1: `selection_result` + migration 10 — `lead`

**Files:** `src/policy_atlas/schema.py`, `alembic/versions/<hash>_select.py`.

- Table exactly per the contract's Schema block (CHECK on `strategy`, `budget > 0`,
  NOT NULL JSONBs, composite FKs `(evidence_scope_id, project_id)` /
  `(run_id, project_id)`, `UNIQUE (evidence_scope_id, run_id)`); FK targets
  verified against the as-built composite uniques (they exist from the 007/009
  precedent — verify, don't assume).
- Module docstring: "twenty tables, ten alembic migrations".
- No dependency changes (`openai` + `langfuse` already present — assert, don't add).

**Acceptance:** migration roundtrips; `make verify` green (nothing reads the table
yet). **Commit.** Scope: S.

## Phase 2 — Ranking layer

### Task 2: `select_rerank_v1` prompt — `lead` (prompt-bearing, lead-only)

One scoring prompt: intent-anchored purpose-fit instruction; id-keyed
`(id, title, abstract)` data records under explicit data/instructions separation;
output = per-doc `(doc_id, score 0–10, reason ≤ 240 chars)`; instructs honest
mid-scale uncertainty (uncalibrated confidence belongs at 5, not 8). Committed as a
constant with the version string.

### Task 3: `ranking.py` — `codex`

`RankingBackend` protocol (`rank(batch, intent) -> list[RankedDoc]`, `mode`) ·
`OpenAIRankingBackend` (strict structured outputs, integer-bounded score schema,
per-call timeout, bounded retry) · stub per the pinned spec · Langfuse spans/score
per the pinned spec (reusing the 009 tracing helpers; no-op without keys). Done =
backend construction/failure tests, stub determinism, no-keys no-op. Scope: S–M.
**Commit** after Phase 2 verify green.

## Phase 3 — The component

### Task 4: `select.py` — `codex`

`SelectionDirective` (parse + fail-closed validation from
`context["selection"]`) → candidate/eligibility query (shared helper) → signal
assembly + composite (pinned normalisations/weights/boosts) → strata from the
**referenced** characterisation row (`characterisation_run_id`; missing row →
structured failure) → allocation (the contract's exact arithmetic) → strategy
dispatch (deterministic order or contested-strata rerank with per-doc/batch
fallback and pre-call budget check) → bidirectional rationale + trigger flags →
selection summary → **`selection_result` row written last**, after all fallible
work (adversarial finding 2: `_run_scope_component` catches without rollback,
harness.py:171 — the row insert is the final statement of `select_scope`, so a
failure anywhere persists nothing; the residual completed-event window matches
the accepted 009 pattern). **Empty scope (`n = 0`) is an explicit branch**
(finding 3, per the contract): completed summary with `empty_scope` flag and
base counts, **no selection row**. Generic `_run_scope_component` failure path
suffices otherwise — select has no partial-payload-on-failure requirement
(unlike 009's coverage). Done = the allocation + directive + rerank + rationale
test blocks. Scope: L (~400 lines). **Commit** after Phase 3 verify green.

## Phase 4 — Wiring

### Task 5: Registry/harness/skeleton/helpers — `fast-worker`

- `plan.py`: `"select": {"requires": ["evidence_scope_id",
  "characterisation_run_id"]}` — `Plan`/`_ValidatedRunSpec`/`Config` gain the
  optional `characterisation_run_id: uuid.UUID | None` field, required-by-registry
  for select only (compile fails closed; the contract amendment from adversarial
  finding 1).
- `harness.py`: `ranking_backend: RankingBackend | None = None` on `run_harness`
  (stub resolved inside, the 009 pattern), threaded through `HarnessState`;
  `_run_select` via `_run_scope_component` with `SelectContext` carrying
  `characterisation_run_id` from the config; node + conditional edge.
- `skeleton.py`: select after characterise, as **its own run** — the
  one-run-per-component model is preserved (adversarial finding 1 killed the
  shared-run draft: `_finish` emits a terminal `run.completed`/`run.failed` and
  updates status on **every** `run_harness` call, harness.py:300–320, and
  `tracing.component_span` opens a `run:{run_id}` root per call, tracing.py:229
  — a shared run would mean two terminal events and two identically-named trace
  roots, and the contract's out-of-scope list keeps the capability-run entity
  deferred). Instead the linkage is **explicit**: `Plan`/`Config` gain a
  `characterisation_run_id` field, **required for `select`** by the registry
  (compile fails closed without it — the plan-as-object posture; no silent
  "latest row" default, honouring the contract's never-silently-reused rule).
  The skeleton passes the characterise run's id; select loads the
  characterisation row by `(scope, characterisation_run_id)` and records the
  reference in `selection_provenance` and the summary. **Contract amendment
  riding this gate** (decision 3's "same run's row" wording + gate 2 grows by
  this one compile-surface field — flagged for the human).
- Skeleton renders the selection summary; live ranker iff `OPENAI_API_KEY` set
  (egress is the product); logs the baseline call budget before live calls; demo
  directive in the fixture scope's `context["selection"]` pinned as **budget 8 +
  one tag boost** (adversarial finding 5: the fixture corpus is ~24–25 docs, so
  the default budget 25 would leave **zero contested strata** and the live
  rerank would never fire; the skeleton asserts-and-logs `contested > 0` before
  the live check).
- `tests/helpers.py`: `selection_result` in FK-safe delete order;
  `test_compile.py`: registry case. Scope: S–M. **Commit** with Phase 4.

## Phase 5 — Tests

### Task 6: Contract bulk — `fast-worker` (the contract's test list is the brief)

Migration roundtrip + 20 tables + constraint/FK/CHECK rejections · allocation math
vs hand-computed fixtures (incl. budget < strata, exhausted-stratum
redistribution) · breadth-floor anti-top-k · must-include bypass + floor
satisfaction + out-of-scope flag · non-evidence excluded-and-counted (Unknown +
NULL eligible) · counting invariants · determinism (two-run byte-identical payload
columns) · edge scopes (n=0, missing characterisation row, budget ≥ n,
unclustered-only) · text-basis tilt · directive semantics (boost reorders; boost
never excludes; unknown refs flagged; empty ≡ default; malformed fails closed;
executed directive in provenance) · trigger-flag fixtures (all five) · rationale
bidirectionality + full-text shares · summary payload shape · harness round-trip ·
`delete_project_data` · downstream untouched.

### Task 7: Judgment cases — `codex`

Contested-strata-only calls + budget maximum vs a counting double ·
scored-before-fallback ordering with both scores recorded (partial and
whole-batch fallback; all-fallback ≡ deterministic) · out-of-range/duplicate/
missing ids from a misbehaving ranker double → per-doc fallback, flagged, never
dropped/excluded · reason constraints + injection-shaped reason stored as inert
data · prompt-structure assertion (id-keyed data records; intent under
instructions, docs under data) · socket-deny scoped around a select round-trip
(008's Postgres-connection lesson) · key hygiene against captured output ·
priority-strata match + `priority_stratum_excluded`. Scope: M–L. **Commit**
(tests).

## Phase 6 — Flow-back + verification

### Task 8: Spec flow-back + log.md — `lead`

components §6: realisation "procedure" → procedure with bounded generative rerank
(hard rules code-side; scores order, never exclude) + `unclustered` named a
stratum; realisation table row updated; `log.md` entry. `make okf-validate` green.

### Task 8b: ADR 0006 — `lead` — **at plan confirmation, NOT a build task**
(adversarial finding 4: this is design-phase step 4; it listed under Phase 6 only
by 009's layout accident)

`docs/adr/0006-selection-strategy-directive-rerank.md`: the selection structure
(stratified, code-owned hard rules), the directive as the agent-facing surface
(and the policy-compiles-to-boosts integration path), the explicit
characterisation reference, the rerank seam + score semantics, the run-local
rationale record. **Written and Accepted at the plan 🛑, before the build
conversation opens** — the build inherits it done.

### Task 9: `verification.md` + live manual run — `lead`

Per the contract's evidence list: `make verify` table; migration roundtrip + 20
tables; the named test results; live skeleton run with `OPENAI_API_KEY`
(+ `LANGFUSE_*` dev): rendered selection summary, per-stratum picks, rerank
scores/reasons/fallbacks, visible directive effect, dev-instance trace (spans,
prompt version, tokens), honest cost note; determinism evidence; public-safety
confirmation (intent + titles/abstracts of contested candidates, openly-licensed
fixture text only). **Commit** (flow-back + verification).

### Review stack (rubric box 8 — owned by conversation C, not this plan)

Per the task-cycle spine: fresh conversation, Tier-3 lanes sized per the 009 retro
note (smaller diff → fewer finder angles). Handoff artifact is verification.md.

### Step-8 obligations (after the review stack, in the PR)

`docs/deferred.md` per the contract's list: steer-point pause reading the flags ·
agent-authored directives (invocation-time) · rerank-quality evals (incl. listwise
ordering) · Cohere-class cross-encoders at the `retrieve` seam · capability-run
entity · embedding-relevance-for-select (declined, rev 4) · selection-diversity
extensions · policy soft-prior tilt (integration shape: policy compiles into
directive boosts) · second strategies · full appraisal on the selected subset —
plus pointer updates where 009 entries already exist.

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Stale characterisation referenced (corpus changed since that run) | Selection stratifies over an outdated grouping | The reference is explicit + compile-required, recorded in provenance and the summary (`characterisation_run_id`) — attributable, never silent; the skeleton always passes the run it just executed; staleness *checks* are the capability-run seam |
| Strict structured outputs with bounded integer scores | Schema rejection or drift | JSON schema `integer, minimum 0, maximum 10`; out-of-range despite schema → per-doc fallback (code-side, tested with a misbehaving double) |
| Ranker returns duplicates/missing ids | Silent mis-ordering | Contract rule: mangled docs fall back per doc, flagged `rank_fallback`; asserted no-drop/no-exclude |
| Contested-strata scoping bug sends wholesale strata | Wasted egress + wrong surface | Counting-double test asserts exactly the contested candidates (minus must-includes) are sent |
| Rate limits on concurrent rerank batches | 429s mid-run | Concurrency cap 4 + bounded backoff in the backend; batches independent; whole-batch fallback if retry exhausts |
| Directive JSONB from scope context is malformed / stale keys | Silent misconfiguration | Fail-closed validation (structured error, never a silent default); unknown-reference flags for soft cases |
| Stratum membership ids drift from eligible set (docs excluded post-grouping) | Accounting mismatch | Membership = member_ids ∩ eligible; non-evidence docs in themes are counted in the base ladder, excluded from strata; invariant test covers it |
| Weight constants are arbitrary | Quality questioned in review | Named constants documented as eval-pending; the review bar is machinery correctness (contract) |
| Live rerank on fixture corpus looks unimpressive | Verification looks weak | The bar is machinery correctness + a visible directive effect; ranking quality is the recorded eval seam |
| Cost runaway | Spend | Pre-call enforced budget max; contested-strata-only scoping; batch cap; cost note in verification.md |

## Plan-phase adversarial review — findings & adjudication (Codex, 2026-07-06)

Nine findings, verified against the repo before adoption; **9/9 adopted** (finding
1 with a different remedy than proposed):

1. Shared-run resolution contradicts as-built run lifecycle (terminal
   `run.completed` per `run_harness` call, harness.py:300–320; `run:{id}` trace
   root per component, tracing.py:229) **and** the contract's own
   one-run-per-component out-of-scope line (blocker): **adopted, remedy
   redesigned** — one-run-per-component preserved; explicit
   `characterisation_run_id` on `Plan`/`Config`, required-by-registry for
   select, recorded in provenance/summary. **Contract amendment flagged at this
   gate** (decision 3 wording + gate 2 grows by the compile-surface field).
2. Row written before summary + `_run_scope_component` catches without rollback
   → failed run could persist a row, violating the contract (blocker):
   **adopted** — the row insert is the last statement after all fallible work;
   residual completed-event window = the accepted 009 pattern.
3. `n = 0` must not write a selection row (contract) but Task 4 wrote one
   unconditionally: **adopted** — explicit empty-scope branch, summary + flag,
   no row.
4. ADR 0006 mislaid under Phase 6 while due at plan confirmation: **adopted** —
   Task 8b re-marked as a plan-🛑 deliverable, not a build task.
5. Default budget 25 ≈ fixture corpus size → zero contested strata → the live
   rerank check never fires: **adopted** — demo directive pinned to budget 8 +
   one tag boost; skeleton asserts `contested > 0` before the live check.
6. `weight_emphasis` formula unpinned (renormalise? clamp?): **adopted** —
   `effective_w = default_w × emphasis`, no renormalisation (within-stratum
   comparisons make absolute scale inert), boost product clamped [0.1, 10],
   formula recorded in provenance.
7. Priority-strata tag matching case semantics unpinned (`source_tag.tag`
   preserves source case): **adopted** — casefold both sides, mixed-case fixture
   test.
8. Token counts unavailable outside the backend (protocol returns parsed data
   only — the as-built grouping precedent, grouping.py:344): **adopted** —
   `rank:batch{i}` spans open inside `OpenAIRankingBackend` where
   `response.usage` lives.
9. Summary `strata[].selected` ambiguous: **adopted** — `candidate_count` /
   `allocated_count` / `selected_count` / `selected_ids`.

## Open questions

None blocking — all design decisions are fixed in the approved contract plus the
one flagged amendment (explicit `characterisation_run_id`, adversarial finding 1)
awaiting the human at the plan 🛑.
