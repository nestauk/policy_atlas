# Verification: 018-dress-rehearsal

> **In progress** — this slice runs phased (contract § How this slice runs); evidence
> accrues per phase rather than landing whole at step 6. Live-run content stays private:
> ids/pointers only, per the contract's public/private boundary.

## Phase log

### B1 (2026-07-10): Phase 0 + A-model + A′ baseline-1 — complete

| Gate | Result |
|---|---|
| Phase 0 build-open full `make verify` | pass (998 passed, mypy 107 files clean, ruff clean, build ok) |
| Phase A-model `make verify-fast` | pass (950 passed, mypy clean, ruff clean) |

- **A-model landed** (commit `58e46f6`): full model-constant sweep per the plan table
  (`gpt-5-mini` → `gpt-5.4-mini`; classify `gpt-5.5` → `gpt-5.4-mini` @ xhigh; synthesis
  writer → `gpt-5.5`); provider-neutral `openai_kwargs` effort knob in `embeddings.py`;
  fake-client test pins the emitted kwargs; `grep '"gpt-5-mini"' src/ tests/` → zero hits.
  **`xhigh` SDK literal verified** against installed openai 2.44.0 (`ReasoningEffort`
  includes `"xhigh"`; `chat.completions.parse` accepts `reasoning_effort`) — no fallback
  substitution needed. Nothing prompt-bearing landed (diff = constants, comments, helper,
  tests). classify@xhigh remains a hypothesis to verify against baseline-1 (plan A1).
- **Baseline-0 recorded** (historical reference, pre-refresh): pointers + counts + block
  texts in `docs/verification/private/018/baseline-0/` (gitignored). **Deviation noted**:
  the contract names `128c0a81` as the second baseline-0 project, but it is the failed
  first attempt (acquire + two failed runs — no extract/synthesise substrate); replays use
  `e8ac8418` (2026-07-09 full chain, different intent) per user direction at B1 open.
- **Baseline-1 captured** (the loop baseline: new models, prompts byte-identical to merged
  dev; references pinned from the original runs' `plan.compiled` payloads):
  - `91d2d684`: extract `ad74f884` (10 docs, 54 findings), synthesise `37016a74` /
    artefact `c54eaaf4`.
  - `e8ac8418`: extract `392f9e5f` (25 docs, 11 extracted, 2 failed), synthesise
    `09596414` / artefact `195761c3`.
  - Records + block texts in `docs/verification/private/018/baseline-1/`; replay/export
    drivers preserved in `docs/verification/private/018/drivers/` (C1 generalises them).
  - Early signal for the loop (not adjudicated): `turn_cap_hit` fires on BOTH synthesise
    replays (absent at baseline-0) — the 5.5 writer works more tool turns (chunk claims
    0→44 on `91d2d684`); `e8ac8418` also flags `uncited_sections`.
- Langfuse traces locate by `run_id` metadata on run spans (sessions land at A2).

### B2 (2026-07-10/11): Phase A-rest (A2–A6) — complete

| Gate | Result |
|---|---|
| B2 build-open full `make verify` | pass (998 passed, mypy 107 files, ruff clean, build ok) |
| Wave 1 (A3–A6) `make verify-fast` | pass (974 passed, mypy 109 files, ruff clean) |
| A2 `make verify-fast` | pass (976 passed, mypy 110 files, ruff clean) |
| Phase A-rest exit full `make verify` | pass (1027 passed, mypy 110 files, ruff clean, build ok) |

- **Wave 1 landed** (commit `a05d984`; A3/A4/A5/A6 in parallel fast-worker lanes,
  lead wording in the same commit):
  - *A3 regrade*: standard row `deep_chain=False` / `selection_budget=None`
    (screen_stage2 + characterise kept; ADR 0013 spine untouched); `FACET_VALUE_CAP`
    150→400; standard×standard band kept at the measured pre-regrade value with a
    stale-flag comment (re-seed in Phase D). Blast radius honestly taken: runner/
    steering/orchestrate fixtures moved to `deep` where they exercise the deep chain,
    and `StubPlannerBackend`'s full-chain draft depth moved to `deep` (the stub was
    the root cause of the console-flow failures — flagged, one line).
  - *A4 planner history*: `build_planner_messages` emits a true user/assistant
    message array (bounding, per-position sanitisation caps, draft-as-data on the
    latest turn, unknown-role coercion preserved; defensive draft-only trailing
    message when the latest turn isn't a user turn). Lead re-anchored the
    anti-injection system-prompt section to the multi-message shape. New
    `tests/test_planner_prompt.py` (9 tests — the old blob shape had no direct tests).
  - *A5 direction rename*: `EFFECT_DIRECTIONS`/`EffectDirection` →
    increase/decrease; migration `64ff33416d1a` (drop `ck_iof_direction` → data
    `UPDATE` → recreate, both directions; constraint absent while transitional
    values exist); fixture sweep (10 test files) + spread-reader pin
    (`direction_spread` zero-fills from the tuple); round-trip test following the
    existing migration-test convention. Lead wording: extract-prompt example
    (`negative`→`decrease` — the rename's own motivating ambiguity) +
    movement-not-desirability guidance; synthesis tool-schema enum now reads
    `EFFECT_DIRECTIONS` directly. `extraction_records` field-description tokens
    renamed by the worker (prompt-adjacent; reviewed and approved as lead wording).
  - *A6 country filter*: grammar + wire mapping already existed (015) —
    the rider reduced to planner expression: `ScopeConstraints` +
    `PlanDraftWire.author_affiliation_countries` (2-letter codes, upper-normalised,
    no dupes/empty), compiled under `filters["openalex"]`, backend-scope coherence
    check (grey_lit_only rejects it), threading through `orchestrate._build_plan`.
    Lead prompt capability line names both geography filters' vocabularies honestly.
- **A6 live probes (lead)**: OpenAlex `authorships.countries:gb|GB` verified
  (9.14M works, case-insensitive; invalid filter keys 400 fail-closed).
  **017's Overton `publisher_country` open item CLOSED**: `source_country`
  filters correctly with Overton *display names* (`UK`/`USA`/`Canada` → 20/20
  results match) but **silently returns zero** on ISO codes and full official
  names ("United Kingdom") — hazard recorded in the planner prompt line
  (display-name vocabulary stated) and in knowledge candidates.
- **A5 migration up/down evidenced on the dev DB (real 017 rows)**: pre
  {positive 1085, negative 731, no_effect 208, mixed 22, unclear 140} →
  upgrade → {increase 1085, decrease 731, rest unchanged} with the new CHECK
  in place → downgrade → exact original distribution restored → re-upgraded;
  dev DB left at head `64ff33416d1a`.
- **A2 landed** (commit `daf90a5`; codex lane, session
  `019f4e57-33c8-7aa1-b173-7b1c38bc4728`): 17 backend-protocol methods return
  `UsageResult[T] = (wire, TokenUsage | None)` (new `usage.py`); `usage_totals`
  in `component.completed` payloads + `runner.component_usage` structlog
  aggregate (017 deferred item discharged); `component.timing` on a fresh
  transaction on success AND failure paths (fault-injected test);
  conversation uuid minted at orchestrate start → planner `plan_turn(session_id=)`
  + `component_span(session_id=)` → one Langfuse session per conversation;
  `_discover_themes` persists validator-rejection `str(exc)` (generic exceptions
  keep type-name only — bounded logs). **Substitution note (routing ladder):**
  codex's sandbox could not reach Docker/Postgres, so DB-gated acceptance ran in
  the lead lane; 7 mechanical leftovers (test-double `session_id` kwargs, frozen
  payload key sets) fixed by a fast-worker from the exact failure list.
- **User riders during A2 (2026-07-11, visible minor additions)**: the session
  uuid is also persisted into `run.started` payloads (`payload->>'session_id'`
  gives the DB→Langfuse session join the plan pin lacked); run trace roots
  renamed `run:{component}:{run_id}` (list-view scannability; metadata unchanged;
  replay-driver rootless traces deferred to C1's driver generalisation, noted).
- Contract A.2(e) (prompt-registry/datasets assess-don't-adopt): plan rev 3
  scoped it out of the A2 row — stands as an eval-slice item, no 018 action.
- Langfuse trace-convention questions (user, 2026-07-11) answered and recorded:
  planner turns are deliberately separate traces (now session-correlated);
  top-level `extract:*:w0`-style traces are the B1 replay drivers running
  without `component_span` (C1 fixes); empty-I/O `run:` traces come from the
  summary-attach guard — run `4077e12f` (succeeded characterise) shows the
  payload-lookup miss; flagged for a C-loop eye, not blocking.

### B3 (2026-07-11): Phase B (B0 flow-back + B-B1..B-B4) — complete

| Gate | Result |
|---|---|
| B3 build-open full `make verify` | pass (1027 passed, mypy 110 files, ruff clean, build ok) |
| B-B1 `make verify-fast` | pass (987 passed, mypy 111 files, ruff clean) |
| B-B2 / B-B3 / B-B4 `make verify-fast` | pass (986 / 997 / 997 passed) |
| Phase B exit full `make verify` | pass (1048 passed, mypy 111 files, ruff clean, build ok) |
| B smoke + annotation re-proof | pass (132 units, 0 span violations) |

- **B0 spec flow-back landed** (commit `8c24ff5`): capability.md + provenance-grounding.md
  two-block refinement (key-findings conditional-required, produced last / shown first;
  conclusions at the report foot, evidence-descriptive, never merged) + log.md entry.
  The ADR half (0015) predates this conversation (plan rev 3).
- **B-B1 emission wire v2** (commit `3cb88a7`): `SectionProseWire` (prose + claims,
  exact-substring anchoring, spans bound code-side); `bind_spans` (ordered-cursor,
  fail-closed, overlap-forbidden); block content = authored prose with per-claim span
  locators asserted at write time; repair v2 (`SectionRepairWire` segment splice,
  one-pass `splice_and_rebind`, claim:null removal lane); unspanned-prose plumbing
  (`synthesis_envelope_v2` carries prose + span map; `unspanned_assertion` annotations
  flag-not-drop; new counts/flags). Every 013 invariant test green on the new wire +
  span round-trip / repair-offset / unspanned fixtures (plan B-B1 test list discharged).
  **Substitution (routing ladder): codex out of credits at dispatch — B-B1 and B-B3
  built by deep-reasoner per the standing exhaustion fallback.**
  **Visible deviation (minor, contract-vocabulary):** a spliced replacement whose claim
  fails structural validation excludes the claim (counted) instead of v1's
  keep-original-verbatim — the spliced prose residual is the unspanned lane's territory.
- **B-B2 writer prompt v3** (commit `4fdd2ae`, lead): voice designed as one coherent
  whole — audience pinned (senior policy makers), environment-context preamble with
  context-not-content rule (machinery vocabulary named + banned), anchored-claim
  contract with motivation, takeaway-first + connected-argument + analyst-number
  prose rules, 150–450-word numeric bound, no meta-commentary; repair prompt v3
  aligned to splice mechanics. Conflict audit applied (each rule stated once).
  C2 validates the voice against baseline-1 per the loop protocol.
- **B-B3 envelopes + two blocks** (commit `b7833e9`): writer-envelope default set
  (year/evidence_type/appraisal_label/venue/cited_by, terse, adjacent, omit-if-absent;
  is_retracted NOT surfaced) on chunk results + finding records; judge envelope v2
  completed (intent + section_focus; finding-anchor chunk text explicit, deduped);
  conclusions section code-injected last (role=conclusions, pinned evidence-descriptive
  focus; proposed "Conclusion(s)" titles still rejected); key-findings pass produced
  last / shown first (roll-up index 0), citable = union of section-cited ids,
  conditional-required with explicit no-headline absence path (test-owned fixture).
  section_role lives in SectionSpec + roll-up JSON — **no schema change** (stop
  condition never approached). Deviations (flagged): anchored chunks absent from
  chunk_by_id stay dropped (text_basis unrecoverable from BasisText);
  generation_budget_max honestly expanded for the injected section + KF pass.
- **B-B4 judge prompt v2 + evidence** (commit `9ce295d` + this one, lead):
  grounding_judge_v2 — prose/span-map as claim context, intent/section_focus with the
  relevance-is-not-support leniency guard, finding claims judged against anchor quotes
  in chunk context, unspanned-assertion semantics (verbatim excerpts,
  report-when-in-doubt with motivated asymmetry); 013 self-certification guard kept
  verbatim. Key-findings prompt (headline bar, caveat fidelity, 3–7 claims / 60–180
  words, absence-is-correct).
- **Judge-envelope v2 evidence (contract Phase B protocol, gates this exit;**
  `docs/verification/private/018/judge-envelope-ab/`, driver `judge_envelope_ab.py`**)**:
  - *Verdict-shift*: recorded baseline-1 verdicts (envelope v1) vs live v2 re-judge on
    the same claims. `91d2d684`: 68 claims, 14 flips — dominant pattern tier_3→tier_2
    ×7 (anchor text visible → single-document support recognised), 3 stricter flips to
    unsupported (over-synthesis caught), 2 evidence-based upgrades; net unsupported
    7→9. `e8ac8418`: 38 claims, 15 flips — same shape; net unsupported 6→7.
    **Every flip hand-inspected: no intent-induced leniency found** (upgrade rationales
    cite textual support, never question-relevance); v2 is net stricter.
  - *Unchanged-verdict stratified sample* (3/lane/project) hand-inspected: rationales
    sound; no unchanged-but-wrong found.
  - *Self-certification fixture* (mandatory — v2 feeds the judge more chunk text): a
    chunk instructing the judge to up-tier its citers swayed NOTHING (verdicts
    identical to control; overstated claim held unsupported_mis_cited). PASS.
  - *Caveat recorded honestly*: arm 1 is recorded verdicts, arm 2 a live re-judge, so
    boundary flips carry a sampling-noise component; the protocol's hand-inspection is
    the control for that. Full judge calibration remains eval-workstream property.
- **B smoke (live, on the recorded `91d2d684` substrate; new wire end-to-end)**:
  run `5a044d71`, artefact `e25010be`, 10 blocks — key_findings first, 8 standard,
  conclusions last. **Annotation layer re-proven: 132 addressable units, 0 span
  violations** (`smoke_reproof.py`; every locator round-trips against block content).
  Claims 83 (tier_1 20 / tier_2 12 / tier_3 19 / tier_4 2 / unsupported 3), citations
  156 verified / 6 unverified, span_bind_failures 1, repair lanes exercised (incl. one
  repair_unparseable section — exhaustion semantics held). Early C-loop signal (not
  adjudicated): the judge flags unspanned assertions liberally (49 flagged + 18
  unbound excerpts) — writer anchoring vs judge threshold is a named C2 calibration
  item.
- Exact end-to-end command: `uv run python docs/verification/private/018/drivers/`
  `baseline1_replay.py 91d2d684 synthesise` (component replay, contract live-check
  scope) followed by `smoke_reproof.py 5a044d71`.

### B4 (2026-07-11): Phase C — in progress

| Gate | Result |
|---|---|
| B4 build-open full `make verify` | pass on serial re-run (exit 0; first attempt flaked: `test_stop_condition_widen_migration_roundtrip`, passes in isolation — concurrent worker-lane `verify-fast` against the shared test DB, the recorded B2 flake class) |
| C1 landing `make verify-fast` | pass (1004 passed, mypy 112 files, ruff clean) |
| C2 extraction r1 landing `make verify-fast` | pass (1004 passed, mypy, ruff) |
| C2 extraction r2 landing `make verify-fast` | pass (1004 passed, mypy, ruff) |

- **C1 landed** (commit `687a721`): `TokenUsage.cached` captured from
  `prompt_tokens_details.cached_tokens` through accumulator payloads,
  `usage_metadata`, and runner `usage_totals` (cost rider 1; new
  `tests/test_usage.py`). Replay drivers generalised in the gitignored private
  dir: `replay.py` (extract/synthesise on the pinned substrates + planner
  single-turn probe; prints per-run usage incl. cached), `export_artefact.py`,
  `export_findings.py`. Replays now carry `run:{component}:{run_id}` roots for
  free (they call `_run_component`, which post-A2 opens `component_span`).
  Codex quota probe: **credits restored** — C4 returns to the codex lane.
- **C2 extraction round 1** (commit `fd76d9d`, lead): `extract_iof_v2` —
  environment-context preamble (context-not-content paired), hortatory
  exclusion, self-contained-naming section (RETRO's four fix classes
  re-authored, mission-neutral examples; deterministic no-mission-vocab check
  run at authoring — added text clean, one heat-pump-adjacent example
  replaced pre-replay). Replays: extract on `91d2d684` (run `3143c2b2`,
  43 findings vs baseline 54) and `e8ac8418` (run `c2f30d5c`, 190 vs 157) —
  junk suppression confirmed (hortatory cluster 4→1; Institutional
  Accountability Framework doc 7→0; deictic outcomes gone; acronyms expanded)
  BUT the administrative scheme-results doc (BUS-in-four-charts) flipped
  extracted(5)→no_findings — over-suppression regression.
- **C2 extraction round 2** (commit landed post-r1, lead): `extract_iof_v3` —
  one programme-results clause (reported delivery/monitoring data passes the
  something-happened bar). Replay: extract on `91d2d684` (run `0510453b`,
  104 findings, 9/10 docs extracted): BUS doc recovered 0→10, but plan-type
  docs over-opened (Scotland CCP 1→41 incl. future-target aspirations and
  deictic entries; oral-evidence doc 0→7 vague witness-concern findings).
  Three arms with distinct failure profiles → **paused for the taste-judge
  verdict before the final bounded round** (contract: ≤3 rounds/surface).
- **C2 planner before-probes** (uncounted, pennies): current prompt already
  infers date windows — "recent" → `published_after=2015-01-01` stated as an
  assumption; "since 2000" → `2000-01-01` + `publisher_country="UK"` (display
  name, correct vocabulary) with honest assumptions. Lead recommendation:
  no date-inference prompt change (round 0 = validated as-is); evidence in
  `c-loop/planner-before-q{1,2}.json`.
- **Cache hit rate (rider 1 first data, extract surface)**: 17.6% / 24.6% /
  20.6% of prompt tokens cached across the three extract replays (per-doc
  one-shot calls — only the shared system-prompt prefix caches). The
  decision-relevant number is the synthesise replay's (2.80M input at the B
  smoke); measured at the next voice-round replay.
- Cost-per-run (extract, gpt-5.4-mini): `91d2d684` ≈ 239k tokens (v2) /
  252k (v3); `e8ac8418` ≈ 521k (v2). Mini-tier — negligible next to
  synthesise.
- **C2 extraction round 3 (final; user-confirmed)** (commit `55a03ab`, lead):
  `extract_iof_v4` — future-dated targets are aspirations even when
  quantified; testimony concerns/expectations are aspirations; deixis rules
  hold inside plans/testimony. Replay `91d2d684` (run `3063498e`, 126
  findings, 8/10 extracted): oral-evidence junk back to 0 ✓, BUS retained
  (9) ✓, consumer-loans doc extracted for the FIRST time in any arm (11,
  incl. the Home Energy Scotland grant-and-loan → heat pumps evidence the B
  smoke flagged as an inferred gap) ✓, direction-in-outcome fixed ✓. Residual
  junk concentrated in the one mega-plan doc (Scotland CCP 64 findings,
  ~10 still aspiration/self-referential shapes). Rounds exhausted →
  **residual junk after 3 bounded rounds = the contract's named trigger for
  the contingent C5 junk judge** (pre-approved: post-extract filter,
  flag-not-drop). Lead recommendation: pin v4 + build C5.
- **C2 voice round 2 (user verdict: pin v3 + round 2)** (commit `84ae79a`,
  lead): `synthesise_section_v4` — once-per-report figures + corpus-shape
  numbers get one home, classification/appraisal vocabulary translated,
  no restated-sentence claim carriers. Replay `91d2d684` (run `626b5f4e`,
  artefact `c6d562ab`, blocks in `c-loop/`): spreads now appear ~once each
  (vs ~5 sections at the B smoke), raw labels gone, hard duplicate opener
  gone (two soft echo sentences remain); tier_1 claims 20→33,
  span_bind_failures 0, unspanned flags 49→43. Lead verdict: pin v4.
  **A prior synthesise attempt failed at launch** — run concurrently with the
  extract replay on the SAME project; both append to the project event log
  (per-project sequence). Loop-protocol note sharpened: same-project replays
  serialize; cross-project stays parallel.
- **C2 planner round 1 (user verdict: author domain-tempo inference)**
  (commit `7585e5f`, lead): date-window inference at the question's tempo —
  never "recent"→a decade; ~last decade default only when no horizon implied;
  no hard-coded year mappings; window stated as changeable assumption, never
  as user scoping. After-probes (uncounted): "recent" heat-policy → 2023
  (was 2015) with tempo-reasoned assumption; "since 2000" respected
  unchanged; generative-AI probe → 2023 "reflecting the rapid post-ChatGPT
  adoption cycle". On the user's stated bar exactly. Lead verdict: pin.
- **classify@xhigh hypothesis FAILED validation** (commit landed, lead):
  first live exercise of the A1 setting — at xhigh, gpt-5.4-mini exhausted
  the full 16K completion cap on reasoning alone (LengthFinishReasonError,
  2.2K-token doc) before answering. At high: 26/26 pinned-project docs
  classified, 4/26 plausible boundary flips vs recorded gpt-5.5 labels
  (offline A/B driver `classify_ab.py` — direct backend calls, NO DB writes,
  substrate uncontaminated). `CLASSIFY_REASONING_EFFORT` → "high".
  Corroboration A/B on `e8ac8418` at high: 92/92 docs, no cap exhaustion,
  14 flips (~85% agreement — same rate as the mission project). Matches the
  prompting-research non-monotonicity note.
  **xhigh-uncapped experiment (user-requested)**: with a 64K cap xhigh
  completes — 221,913 reasoning tokens / 26 docs (mean 8.5K, max 18.6K; the
  16K production cap was too tight for the tail), cost well under $1. But
  quality is WORSE where it differs from high: 4 disagreement docs, all
  low-confidence churn (0.60–0.69) — including demoting the clearly-typed
  BUS-in-four-charts doc to Unknown/Insufficient at 0.63, which recorded and
  high both label correctly. xhigh's agreements with high's flips add
  nothing high didn't catch. ~10–30× output volume, ~1–2 min/doc vs seconds.
  **Verdict: keep high** — on quality, not cost. Evidence:
  `c-loop/classify-xhigh-uncapped.txt`.
- **Unspanned-flag calibration (named C2 item) — resolved by inspection, no
  prompt change**: the B smoke's 49 flags hand-sampled — the judge is
  correct; the writer under-anchors (spread counts in prose without pattern
  claims, "Inferred gap:" sentences not anchored as gap claims, attributed
  re-statements unclaimed). No judge change; voice v4 reduced the class
  (43); C4 renders unspanned flags as quiet markers, not errors; deeper
  claim-coverage behaviour is eval-slice territory.
- **Cost riders (approved list) — dispositions**:
  1. cached_tokens telemetry ✓ landed (C1). **Synthesise cache hit rate:
     63.8%** (2.438M prompt / 1.556M cached, run `626b5f4e`); extract
     18–25%.
  2. `prompt_cache_key` — **condition not met** (rider was "if hit rate is
     low"; 64% auto-caching); not adopted, recorded.
  3. multi-read-tool turns — LANDED (writer round 3, final; commit
     `5e77e10`): parallel read calls + per-call loop accounting + batching
     rule (≤6 reads/turn, emit alone; all-emit parallel turns honour the
     emission — lead fix on the delivered lane), `synthesise_section_v5`.
     Replay (run `347e3a2f`, artefact `64143a9d`): **input −31%**
     (2.438M→1.689M prompt) while gathering MORE evidence (71 read calls vs
     43; verified citations 161→198) — but the **cache hit rate collapsed
     64%→23%** (the eliminated repeated prefixes were the cached tokens), so
     the realized $ verdict depends on the provider cache discount (≈−10%
     at a 50% discount, ≈+30% at 90%) — **adjudicate against D1 billing**.
     Voice mostly held; three new polish-grade warts recorded for the
     pin-or-revert verdict (a rule-compliance meta-leak sentence, an
     "As reasoning," claim-type prefix, a repeated no-mixed/no-effect
     phrasing tic in the opening section). Writer rounds exhausted (3/3).
  4. chunk-dedupe — proxy measured: 43 read calls over 9 sections this
     replay; with 64% auto-cache, duplicated chunk content is largely
     cache-priced. Full per-chunk measurement deferred (re-open if D1 cost
     disagrees).
- **Env-context preamble (named C2 hypothesis) — surface dispositions**:
  writer ✓ (B-B2, validated), extractor ✓ (v2–v4), judge NOT adopted —
  prompt fresh from B-B4 with evidence green; screen/classify excluded at
  plan time (dilution).
- **Pin verdicts (user, 2026-07-11 afternoon)**: writer `synthesise_section_v5`
  PINNED (multi-read; $ curve adjudicated at D1) · extraction `extract_iof_v5`
  + junk judge PINNED (production wiring added: RunnerBackends.junk_judge +
  live-bundle construction — commit `65cb827`) · classify `high` stands
  (xhigh evidence complete) · **C4 re-sequenced by the owner**: no merge into
  `demo-live-run` until this branch lands in dev through review — demo
  surface + rehearsal follow the merge, not Phase C.
- **C2 sections round (owner-scoped addition)**: the proposal surface was
  overlooked at planning; owner brought it into the loop (this slice exists
  to check every prompt) with the design steer: intent-led discovery stays —
  V2's templated grammar (imperative core answer, fixed background,
  interventions table, exactly-3-4 recommendations) is the recorded
  anti-pattern, and several template sections belong to future capabilities
  (deferred.md § EB report-shape boundary). Landed `synthesise_sections_v2`:
  an evidence-descriptive role menu (context under specific titles /
  cross-cutting patterns / enablers-and-barriers-as-described), each only
  when the substrate supports it. Proposal-only before/after probes on both
  pinned projects (pennies, excluded from the replay tally; archived in
  `c-loop/sections-v{1,2}-*.txt`): on the finance intent the menu surfaced
  a genuine enablers-and-barriers section + a specific-titled architecture-
  context section; on the mission intent it absorbed into existing sections
  rather than force-spawning — no generics, no verdicts, lead sections now
  cross-cutting-pattern-shaped on both. Lead verdict: improvement; user
  eyeball pending.
- **C5 junk judge — built (trigger fired) and adoption-replayed** (commit
  `4dd3353` + lead fix; replay run `df216bce`, extract_iof_v5 + judge live on
  `91d2d684`): 36 findings flagged {aspiration 21, vague_outcome 13,
  self_referential 2}, `junk_judge_failed` 0. Flag set covers the lead's
  hand-identified junk list nearly exactly (woodland future-targets, VETS
  ambitions, the "→ households" vague-outcome family, both self-referential
  records); the two debatable flags spot-checked via recorded reasons — both
  correct (quotes were purpose statements / a 2026–27 expectation). One doc
  went all-junk → honest no_findings (per-doc junk_flagged count preserves
  the distinction). Judge cost ≈ 25k mini output tokens per extract run.
  Lead verdict: PASS — pin pending user confirmation.
- **C3 taxonomy pins — planner replay across the 7 v2 categories** (real
  questions from the recorded V2 list, one per category; probes uncounted;
  drafts in `c-loop/c3-pin-cat*.json`). **Per-category composition-adequacy
  verdicts (lead): 7/7 adequate.**
  1. *Intervention* (ACEs early-intervention): standard×standard + full deep
     chain ✓ — the chain's home shape.
  2. *Topic search* ("refugee integration"): no axes proposed on turn 1 —
     asked its ONE shape-changing question (landscape vs effectiveness)
     first; within the ask-only-shape-changing rule for a 2-word intent.
     Adequate; recorded as an observation, not a failure.
  3. *Impact* (free school meals → childhood obesity): deep chain ✓,
     international default + under-18 assumption stated.
  4. *Statistics* (primary-care demand/costs, deprived vs non-deprived):
     composed WITHOUT the deep chain, explicitly reasoning
     "descriptive/comparative, not intervention" — the owner bar exactly
     (neither refuses nor pretends; honest evidence-descriptive
     composition).
  5. *Literature* (planning system / unhealthy food outlets): read as a
     policy-effect ask → deep chain ✓, 2010+ window domain-reasoned.
  6. *Benchmarking* (nuclear decommissioning across countries): the
     textbook off-diagonal — landscape × deep search, characterise only,
     geo filters declined with reasons; screen_stage2 correctly absent with
     landscape.
  7. *Opinions* (left/right narrative effectiveness): no refusal, no deep
     chain (narratives aren't IOF material), honest interpretive
     assumptions ("better" defined, scope pinned to national politics).
  Cross-cutting: the planner date-tempo rule behaved on all 7 (defaults
  stated as changeable assumptions); deep-chain selection tracked intent
  shape perfectly (in: 1/3/5, out: 4/6/7).
- **C3 no-mission-vocabulary checks (deterministic, adopted prompts)**:
  extract_iof_v4 / synthesise_section_v4 / key_findings_v1 / sections_v1 /
  planner — all CLEAN except one pre-existing v1 example in the extract
  prompt ("one in five children are obese", the prevalence example, predates
  018): obesity is a mission domain, so the example is swapped to a neutral
  domain as part of the C5 landing (riding the C5 adoption replay rather
  than spending a 4th extraction round).
- **C3 desk reviews (each adopted rule × the 7 question shapes)**:
  *extract_iof_v4*: hortatory/aspiration + programme-results — benchmarking
  questions read country programmes with delivered results (kept by the
  programme-results clause); opinions questions rarely route through
  extract at all (planner composes without the chain — pin 7 evidence).
  Future-target rule: watch item — modelled projections are results, not
  targets (v4 kept grant/price projections; dropped the BAU-scenario
  finding, defensible but recorded for the eval slice). Testimony rule:
  witness concerns are not IOF effects on ANY question shape. Naming rules:
  shape-neutral (acronym expansion helps literature shapes most).
  *synthesise_section_v4*: once-per-report figures / label translation /
  no-restatement are shape-neutral prose rules; landscape-shaped reports
  keep their counts (stated once).
  *planner date-tempo*: stats questions want current values (recent-tempo
  fits); explicit horizons respected (probe q2); slow domains stretch
  naturally (pin 6). No misfire found on any shape.
- **C3 synthesis spot-check on the non-mission project** (replay 13, run
  `8c2b5f2e`, artefact `25dbb39a`, pinned section_v5; blocks in `c-loop/`):
  the voice generalizes — analyst register, connected argument, quoted
  anchors, labelled inferences, NO mission-vocabulary bleed,
  span_bind_failures 0. Thinner corpus shows honestly (tier_1 18 vs the
  mission project's 33; 19/198 unverified citations on a 60%-abstract
  substrate). Usage 3.42M tokens, 24% cached (consistent with v5's cache
  profile). PASS.
- **C3 extraction spot-check on the non-mission project** (replay 9, run
  `c333f2c3`, 215 findings): v4 behaviour on the finance intent is rich and
  question-appropriate — communiqué stays 0 ✓, meaty ERDF programme-delivery
  doc grew honestly (71→123 administrative results), macrofiscal doc
  tightened (35→18). **Anti-overfit pin PASSES** (failure modes are
  domain-neutral, no mission vocabulary encoded). One instructive flip: the
  Institutional Accountability Framework doc came back 7→6 at v4 (v2 had
  correctly zeroed it) — the programme-results clause re-admits
  framework-mechanism descriptions ("framework → public transparency
  [increase]"). Domain-neutral junk class; strengthens the C5 trigger
  evidence (judge build in flight).

## C-phase riders — synthesis cost reduction (user-approved 2026-07-11, post-B3)

Evidence: the B smoke recorded **2.85M tokens (2.80M input / 47k output)** across 61
gpt-5.5 writer calls (51 section turns + 8 repairs + proposal + KF) ≈ **$13/run**
(owner-observed billing; fork-probe arms $17/$10). The cost is writer *input volume* —
the stateless loop re-sends the full transcript (incl. chunk texts) every turn; the
mini judge is negligible. Approved riders, in order:

1. **C1 (telemetry, zero quality risk):** capture `prompt_tokens_details.cached_tokens`
   into `TokenUsage` + the usage aggregates — measure the OpenAI cache hit rate on the
   next replays. (`token_usage_from_provider` currently drops the detail.)
2. **C2 (if hit rate is low):** cache-routing hint at the `openai_kwargs` seam
   (OpenAI `prompt_cache_key` per run+section). Provider note: Bedrock caching is
   explicit `cachePoint` markers, not automatic — the SEAM carries over at migration
   (deterministic append-only prefixes already suit both); only the kwarg is
   OpenAI-specific.
3. **C2 (replay-evidenced):** multi-read-tool calls per turn — raise the one-call-per-
   turn loop rule for READ tools substantially (user direction: push well above 2–3;
   emit stays alone), gathering the same evidence in fewer frontier calls and shorter
   re-sent transcripts. Before/after replay per the loop protocol.
4. **C2 (measure first):** chunk-duplication rate across a section's tool results;
   dedupe repeats ("already returned as <id>") only if material. Quality-safe by
   construction (content already in context once).

Each C2 replay records cost-per-run alongside quality so both curves are visible.
(Depth-graded SECTION_CAP was raised as a further linear lever — a product coverage
trade, not adopted here.)

## Live component replay tally (bound: ≤30; baselines/fork-probe/B-smoke/D excluded)

| # | Phase | Replay | Counted? |
|---|---|---|---|
| – | A′ | baseline-1: extract ×2, synthesise ×2 | excluded (baseline) |
| – | A-rest | none (OpenAlex/Overton wire probes are search-API calls, not component replays) | n/a |
| – | B | B smoke: synthesise ×1 on `91d2d684` (run `5a044d71`) | excluded (B smoke, named) |
| – | B | judge-envelope A/B re-judges (per-block judge calls on recorded claims, both projects) + self-cert fixture | not component replays (judge sub-calls; the contract's in-B evidence protocol) |
| 1 | C2 extraction r1 | extract `91d2d684` (run `3143c2b2`, extract_iof_v2) | counted |
| 2 | C2 extraction r1 | extract `e8ac8418` (run `c2f30d5c`, extract_iof_v2) | counted |
| 3 | C2 extraction r2 | extract `91d2d684` (run `0510453b`, extract_iof_v3) | counted |
| – | C2 planner | 2 single-turn probes (before-arm) | excluded (planner-only probes: pennies, unrestricted — plan live-check script) |
| 4 | C2 extraction r3 | extract `91d2d684` (run `3063498e`, extract_iof_v4) | counted |
| 5 | C2 voice r2 | synthesise `91d2d684` — failed at launch (same-project event-log contention with replay 4; no artefact) | counted (honest accounting) |
| 6 | C2 voice r2 | synthesise `91d2d684` (run `626b5f4e`, artefact `c6d562ab`, section_v4) | counted |
| 7 | C2 classify | classify A/B `91d2d684` @ high, 26 docs (offline, no DB writes; the @xhigh attempt fast-failed on doc 1, LengthFinishReasonError) | counted |
| 8 | C2 classify | classify A/B `e8ac8418` @ high (corroboration) | counted |
| – | C2 planner | 3 single-turn after-probes (incl. AI-tempo) | excluded (planner-only) |
| 9 | C3 spot-check | extract `e8ac8418` (run `c333f2c3`, extract_iof_v4) — anti-overfit arm | counted |
| – | C3 pins | 7 planner taxonomy probes | excluded (planner-only) |
| 10 | C2 writer r3 | synthesise `91d2d684` (run `347e3a2f`, artefact `64143a9d`, section_v5 multi-read) | counted |
| 11 | C5 adoption | extract `91d2d684` with junk judge live (run `df216bce`, extract_iof_v5) | counted |
| 12 | C2 classify | xhigh-uncapped experiment, 26 docs (user-requested; offline A/B, no DB writes) | counted |
| 13 | C3 spot-check | synthesise `e8ac8418` (run `8c2b5f2e`, artefact `25dbb39a`, pinned section_v5) | counted |
| – | C2 sections | 4 proposal-only probes (v1/v2 × both projects) | excluded (single bounded calls, planner-probe class) |

Running total: **13 / 30**.

## Loop protocol notes (flow-back candidates for the eval-slice convention)

- **Parallel-by-default replays (user direction, 2026-07-10):** independent C-loop
  replays run in parallel by default (e.g. the two pinned projects' spot-checks
  together); serialize only when two runs contend for the same substrate or when
  isolating one variable's trace matters. Baseline-1 ran sequentially (driver shakedown
  + rate-limit caution) — that caution is not the convention.

## Review handoff (accrues; finalised at Phase E)

- **Knowledge candidates:**
  - Contract-pinned baseline project id was wrong (`128c0a81` = failed first attempt);
    the replayability check (does the project have the component runs you need?) belongs
    at contract time, not build time.
  - Overton `source_country` takes Overton *display names* (`UK`, `USA`, `Canada`) and
    **silently returns zero** on anything else (ISO codes, "United Kingdom") — a
    fail-closed grammar cannot protect against provider-side silent misses; live-probe
    filter *values*, not just keys, before a prompt promises them (B2, 2026-07-11).
  - Parallel same-tree agents: string-Edit-based concurrent edits to the same test file
    interleaved cleanly, but concurrent DB-backed suite runs against the one shared
    test DB flaked (one deadlock, vanished on re-run) — partition test *runs*, not just
    file sets, or give lanes separate DATABASE_URLs (B2).
  - Codex sandbox cannot reach Docker/Postgres: brief codex to gate on pure tests +
    mypy/ruff only and plan a lead-lane DB-gated acceptance pass after delivery —
    that's a routing-ladder property, not a codex quality issue (B2).
  - `run:` trace-level input/output attaches only when the component's score-summary
    payload lookup succeeds (`skeleton.py` guard) — a *succeeded* run can still show an
    empty-I/O trace (seen: `4077e12f`, characterise); make the attach unconditional or
    log the miss if it starts mattering (B2; C-loop eye).
  - LLMs cannot emit reliable char offsets: span-anchoring works by asking the model
    for verbatim TEXT and binding text→offset code-side (exact substring, fail-closed).
    Never put offsets on a model-facing wire (B3).
  - Offset arithmetic after splicing is where span bugs live — a one-pass rebuild that
    recomputes every offset by construction (emit pieces, record positions) plus a
    round-trip assertion at persist time beats delta-shifting (B3).
  - Judge verdict tiers are a function of what the envelope lets the judge SEE: adding
    anchor chunk text moved tier_3 mass to tier_2 (single-doc support recognised) and
    net-raised unsupported. Tier distributions are NOT comparable across envelope
    versions — re-baseline whenever the envelope changes (B3).
  - An asymmetric "report when in doubt" judge rule produces high flag volume on first
    contact (49 unspanned flags / 83 claims on the B smoke) — plan a calibration pass
    before such flags reach a user surface (B3; named C2 item).
  - Codex quota exhausted at B-B1 dispatch: the fallback ladder held — deep-reasoner
    delivered both machine-verifiable refactor lanes green on first delivery; the
    precise pinned brief (every design decision decided by the lead, agent implements)
    is what made the substitution costless (B3).
