# Plan: 019-folding-pass

> **Status:** APPROVED — 2026-07-12 · owner, with all five gate decisions decided
> as recommended (§ Gate decisions): 1 CHECK migration approved as scoped ·
> 2 `is_retracted` = distinct excluded status riding the same migration ·
> 3 rename = one-time data migration · 4 pytest-socket approved · 5 Overton
> post-filter mechanism approved (fan-out + pure asymmetry rejected;
> `is_global_south` dropped as owner de-scope).
> **Amended post-approval (owner, 2026-07-12): contract item 13 select-at-standard
> joins Phase D** — must precede Phase E so D1 measures the with-select composition.
> Contract: [contract.md](contract.md) (approved 2026-07-12). Rubric: [rubric.md](rubric.md).
> Executor marks default to subagents (orchestrator-delegation convention); lead marks
> carry justification inline.

## Probe evidence already in hand (2026-07-12, keyless dev-time)

- OpenAlex `authorships.countries` hard-caps at **100 values** — 131 codes → HTTP 400
  ("Decrease values to 100 or below"); 100 codes → 200, 38.4M works.
- OpenAlex native `authorships.institutions.is_global_south:true` → 200, 40.8M works
  (magnitude-consistent with the hand list) — a one-boolean native option for
  "developing"-shaped groups, if the owner wants it (filter-vocabulary growth, one key).
- **Overton `source_country` is single-valued — PROBED 2026-07-12 (6 calls,
  owner-authorized):** France 42,183 · Germany 42,370 · `France,Germany` **0
  (silent)** · `France|Germany` **0 (silent)** · `source_country[]` array **0
  (silent)** · repeated param → **42,370 = last-value-wins (silent discard)**. Every
  multi-value idiom fails without error — the recorded silent-zero hazard shape,
  now evidence-complete.

Compile consequence: Tier-2 lists validate to ≤100 per OpenAlex call; >100 splits into
two filter variants at compile (the loop's multi-query fan-out already merges variants).

## Phases

**Phase 0 — baseline + probe + gate package** — **lead** *(gate adjudication is
judgment)*
- Full `make verify` baseline (mandatory open-gate class).
- ~~Overton probe~~ DONE at plan time (owner-authorized, 2026-07-12; evidence above
  + verification.md) — Phase 0 carries no live calls.
- Present the gate package (§ Gate decisions below) → 🛑 owner adjudication.
  Items 5, 8, 12 and the pytest-socket dep do not start until their gates clear.

**Phase A — ungated mechanical lanes** — **fast-worker** ×2 lanes *(mechanical,
test-pinned; one suite runner at a time — per-lane test DBs stay deferred)*
- Lane A1: item 10a wire-validator unification (BEFORE Phase B grows the grammar) ·
  10c acquire legacy-branch collapse · 10d test-double hoist → `tests/helpers.py`.
- Lane A2: item 6 `_discover_themes` rejection-detail persistence · item 7a
  `bind_contextvars` per run/component + `exc_info` traceback renderer · item 10e
  two-scope coverage fixture.
- Item 7b pytest-socket lands here once the dep gate clears (deny-by-default,
  DB-host allowlist; retire the three per-test deny patterns).
- Gate: `make verify-fast` per lane landing.

**Phase B — country filters (item 3)** — code **codex**, prompt **lead**
- Codex brief (machine-verifiable: pure tests + mypy/ruff; lead runs the DB-gated
  acceptance pass after delivery — codex sandbox has no Postgres): ISO-3166 allowlist
  for `author_affiliation_countries` · probed display-name allowlist for
  `publisher_country` (from Phase-0 evidence) · Tier-1 group tokens with per-backend
  compile (Overton native `source_region`; OpenAlex pinned ISO tables, UN-geoscheme
  for continentals, UK ∈ Europe test-pinned) · `{label, countries, authorship}` plan
  field (additive; **round-trip test mandatory** — the 018 `declared_hatches` lesson)
  · ≤100-per-call validation + >100 split-at-compile · CLI plan render label+count.
- **Lead (prompt-bearing):** planner capability line — Tier-1 vocabulary,
  Tier-2 propose-and-confirm pattern (name the definitional choice), honest decline
  for what neither tier serves. Replay-evidenced on planner probes across group-token
  phrasings incl. "developing countries" and one decline case. Probes are pennies,
  unrestricted.

**Phase C — telemetry + robustness** — **codex** primary *(scoped, machine-verifiable)*
- Item 4 Langfuse thread-context propagation into executor workers FIRST (extract
  windows, screening fan-outs; manual trace check on one recorded replay = the
  acceptance evidence, lead-run).
- Item 11 finding-vetter parallelization SECOND (same executor pattern, thread-safe
  usage accumulation; ordering constraint honoured by construction).
- Items 1–2: search-response caching (cache-before-throttle; poisoning/staleness
  posture documented for the security lane) · embed-pass 429 backoff +
  split-on-failure batch isolation.
- Gate: `make verify-fast` per landing; lead DB-gated acceptance after codex delivery.

**Phase D — gated items (post-adjudication)** — **fast-worker** with **lead** review
- Item 5 coverage stop-grain CHECK migration + item 8 `is_retracted` screening gate
  (one migration file if decision 2 below lands as an enum widening — both ride it).
- Item 12 screen-stage rename + 10b registry-map collapse together (same vocabulary
  surface), per the decision-3 handling.
- Item 13 select-at-standard: `ANALYSIS_DEPTH_TABLE` `deep_chain` flag split into
  per-component gradation + runner step lists + standard `selection_budget` pin —
  **fast-worker** (behaviour tests pinned: standard composes select, never
  extract/group); planner depth-composition text — **lead**, batched into the
  Phase-B planner prompt change + replay set.
- Gate: full `make verify` at Phase D exit (migrations present).

**Phase E — D1 rider** — **lead + owner** *(owner-present session; live env)*
- Runs AFTER item 13 lands — the band must measure the with-select composition.
- ONE composed standard run → `TIME_BANDS` standard×standard re-seed (trace id
  recorded) · band-target verdict (~15–20 min or record honestly) · multi-read `$`
  adjudication on the run's billing; revert (if called) is a lead-only prompt change
  in this PR. Write 018's D1 phase-log entry + § Review handoff `$`-verdict line.
- Schedulable any time after Phase A; independent of B–D.

**Phase F — records + review stack** — **lead** judgments, **fast-worker** sweeps
- deferred.md sweep: discharge/narrow the folded entries; ADD the multi-question
  reuse seam entry (contract 10e) + fold the left-out groups (VHHD · APAC ·
  exclusion groups) into filter-vocabulary growth.
- verification.md complete; knowledge candidates; loop flow-back note.
- Review stack (per review-stack economy): medium `/code-review`, per-angle scoping —
  migration lane · country-filter/grammar lane · telemetry/parallelization lane;
  **one** security lane headlined by allowlist fail-closedness, cache
  poisoning/staleness, socket-deny coverage, and prompt-injection posture of the
  planner group guidance; contract-verifier fresh-context (step 7). Budgets ≤250K
  reasoning / ≤500K fast-worker; membership tables + fixtures excluded from diffs.
- Gate: full `make verify` at exit (mandatory final-exit class).

## Gate decisions (adjudicate at this plan approval)

1. **Coverage stop-grain CHECK migration** (schema): approve the one-line widening +
   down-migration. *Recommend: approve as scoped.*
2. **`is_retracted` at screening** (eligibility): options —
   (i) deterministic pre-screen exclusion recorded as `not_relevant` + attributed
   reason (no schema change; conflates policy exclusion with relevance judgment);
   (ii) **distinct status value** (e.g. `excluded_retracted`) riding the same
   migration as decision 1 — visible, attributed, never conflated; read paths
   (effective-screen helper, funnel counts) updated. *Recommend (ii): don't-flatten-
   status argues a policy exclusion is not a relevance verdict.*
3. **Rename persisted-vocabulary handling**: one-time data migration rewriting step
   names in persisted `orchestration_plan` rows + event payloads, vs permanent
   read-side alias. *Recommend migration: rows exist only in dev/test DBs (v3.0
   pre-launch), the slice already ships a migration, and an alias is permanent
   complexity for a one-time rename.*
4. **pytest-socket dev dependency**: approve.
5. **Tier-2 Overton handling** (probe evidence complete — `source_country`
   definitively single-valued; see § Probe evidence). Rejected at plan drafting,
   both by owner reasoning (2026-07-12): **per-country fan-out** (covert
   equal-budget stratification — distorts the evidence distribution vs the
   provider's ranking over the filtered universe) and **pure asymmetry** (screen
   judges topical relevance, not membership — the constraint would not bind on
   Overton at all). *Adopted mechanism:* **deterministic post-filter + deeper
   pagination** — one Overton call per query variant with normal provider ranking;
   records post-filtered code-side against the group's stamped country table
   (`source.country` metadata) before ingest, paging until the quota fills or the
   loop's existing budgets bind (rank order is preserved under subsetting, so this
   returns exactly what a native group filter would). Exclusion counts recorded on
   coverage/provenance — directive-driven, never a silent transport filter.
   Owner de-scope (2026-07-12): "developing countries" is a rare ask for the
   target users (senior UK policymakers) — build NOTHING specific to it. The
   `is_global_south` key adoption is DROPPED (YAGNI; probe evidence stays recorded
   at the filter-vocabulary growth seam if ever wanted). Groups >100 countries
   remain reachable via the generic Tier-2 path (OpenAlex two-variant split, mild
   between-halves distortion accepted for a rare case; Overton post-filter
   unaffected). Real Tier-2 asks are expected small ("Nordic countries"-scale) —
   single OpenAlex call + Overton post-filter. Corollary retained: per-country
   stratification remains legitimate as an explicit *diversity directive*
   (select's territory, steerable) — never a silent search-compile artifact.
   *Decision needed: approve the post-filter mechanism.*

## Live-check pins

Planner probes: pennies, unrestricted. Overton wire probe: ≤6 calls, Phase 0. D1:
exactly ONE composed standard run. NO other e2e runs.

## Dependencies

10a → before B. 4 → before 11. Gates 1/2 → Phase D migration; gate 3 → item 12.
Item 13 → before Phase E (D1 measures the with-select composition); its planner
text rides the Phase-B prompt change. D1 (Phase E) otherwise independent after A.
C4/D2 live outside this slice (018 trailing).
