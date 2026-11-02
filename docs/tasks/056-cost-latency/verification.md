# Verification: 056-cost-latency

Evidence for one slice. Public-safe: no secrets, no raw source text, no report text from the
fixed questions (session ids and totals only). Contract: [contract.md](contract.md) (rev 2);
plan: [plan.md](plan.md); rubric: [rubric.md](rubric.md); ADR 0042.

Executor note: Codex was unavailable for this slice (workspace spend cap), so every
judgment-bearing build step the plan marked `codex`/`deep-reasoner` ran on `deep-reasoner`
(Opus), mechanical sweeps on `fast-worker` (Sonnet), live probes on `builder` (Opus). The
review stack (fresh conversation) supplies the family flip.

Terms for a reader who is not DevOps: a *gate* is one run of `make verify` (every test and
check the repo has); a *route* is which provider the app calls (`openai-direct` = OpenAI,
`bedrock` = Amazon Bedrock in London); a *step* is one named model call site in the route
file; *Langfuse* is the tracing tool that records every model call and its token counts.

## Commands run (gates)

| Gate | When | Command | Result |
|---|---|---|---|
| 1 | Build open, HEAD c17da9eb (run while five agents edited the tree) | `make verify` | backend 3,804 passed, **1 failed**: `tests/runtime/test_option_search.py::test_a_fan_out_that_raises_part_way_interrupts_the_children_it_sent` (`_await_statuses` 10 s poll deadline exceeded under load). Re-run alone on the same DB: 1 passed in 2.75 s. Load-induced timing flake, not a code red. Later stages did not run (make stops at the first red); Gate 2 is the first full green run. |
| 2 | End of Phase 0, tree at d14d3f33 | `make verify` | **green**: okf-validate pass; backend 3,754 passed, 1 skipped (642 s); infra 95 passed; audit-paths, prompt-guard (41 files), font-guard, drift-check pass; frontend 938 tests in 88 files pass. |
| A | Phase 1 commit A (steps, effort plumbing) | `make verify-fast` + prompt-guard | 3,764 passed, **1 failed** (`test_bedrock_names_bedrock_models_and_cohere`: six stale old-step names in the lead's own loader test); fixed, that file + the kwargs test re-run: 100 passed; typecheck and lint clean; prompt-guard 41 unchanged after the re-pin. |
| B | Phase 1 commit B (the switch) | `make verify-fast` + prompt-guard | 3,759 passed, **9 failed**: four extraction-fingerprint pins (iof/icf × stub/live), four intervention-profile fingerprint pins and one `kwargs["model"] == "gpt-5.6-luna"` assert — every one a value that embeds the model id, which the switch changes by design; re-pinned, those three files re-run: 60 passed. Prompt-guard unchanged (no prompt file touched). |
| C | Phase 1 commit C (O3 prompts, X2) | `make verify-fast` + prompt-guard | backend tests all passed, typecheck and lint clean; **`eval-check` red** on `ruff format --check scripts/evals/screening` (one comment line from commit A's `run_screen.py` edit; the A and B gates stopped before `eval-check` ran); formatted, `make eval-check` re-run: exit 0. Prompt-guard 41 unchanged after the `summary_prompts.py` re-pin. |
| P2 A | Phase 2 commit A (caching plumbing, D8/D10, X3) | `make verify-fast` + prompt-guard | **green**: 3,796 passed, 1 skipped (803 s); typecheck, lint, eval-check clean; prompt-guard 41 unchanged after the `section_prompt.py` re-pin. |
| P4 | Phase 4 (repair guard) | `make verify-fast` + prompt-guard | **green**: 3,822 passed, 1 skipped (667 s); typecheck, lint, eval-check clean; prompt-guard 41 unchanged after the re-pin. |
| 5 | End of Phase 6 (ingest-adjacent), tree = Phase 4 + the Phase 6 patch | `make verify` | **green**: 3,884 passed, 1 skipped (766 s); okf-validate 182 concepts; build, infra, audit-paths, prompt-guard, font-guard, drift-check OK; frontend 943 tests. |
| 4 | End of Phase 3 (schema), tree = Phase 2 A + the Phase 3 patch | `make verify` | **green**: 3,812 passed, 1 skipped (674 s); build, infra 95, audit-paths, prompt-guard, font-guard, drift-check OK; frontend 939 tests in 88 files. |

Per-phase commits on `task/056-cost-latency`:

| Phase | Commit | Gate |
|---|---|---|
| 0 | d14d3f33 | 2 (full) |
| 1 A | 3a2b5ba3 | A (verify-fast) |
| 1 B | 7561a822 | B (verify-fast) |
| 1 C | 35c92e59 | C (verify-fast) |
| 2 A | 43bf7a34 | P2 A (verify-fast) |
| 3 | 3bcd3044 | 4 (full) |
| 4 | ae9a720b | P4 (verify-fast) |
| 6 | a4fb1bb2 | 5 (full) |

## Phase 0 — instrument, baseline, tidy (N1, D11, D2a, tidy-ups)

### N1: cache-write and reasoning tokens as Langfuse buckets

`core/usage.py`: `TokenUsage` gains `cache_write` and `reasoning`; `token_usage_from_provider`
reads `prompt_tokens_details.cache_write_tokens` (the OpenAI SDK does not declare this field;
its models keep unknown fields, proven by a test on a real `CompletionUsage`) and
`completion_tokens_details.reasoning_tokens`; `usage_details()` keeps the OpenAI shape and adds
both; `UsageAccumulator` and the stored `usage_totals` payload carry `cache_write` and
`reasoning`. Lead follow-ups: `runtime/runner.py` `_usage_totals`, `corpus/characterise.py`
and `sourcing/search_generation.py` `_combine_usage` carry the two keys (they rebuilt the dict by
hand); seven test expectations widened to the six-key payload. `core/tracing.py` needed no
change: the embed span has no cache or reasoning buckets and every other span calls
`usage_details()` (plan step 3 folded into step 2; executor deviation fast-worker → deep-reasoner,
no code resulted).

**Live check (probe a, 2026-11-02, 6 calls, both routes; `experiments/langfuse-buckets-probe-2026-11-02.md`):**
Langfuse shows exactly `input_cached_tokens`, `input_cache_write_tokens` and
`output_reasoning_tokens` as exclusive buckets: call 1 `input` 3 + `input_cache_write_tokens`
1,346 = raw prompt tokens 1,349 (openai-direct; 2 + 1,343 on bedrock); call 2 `input` 3 +
`input_cached_tokens` 1,346; reasoning supplement `output` 18 + `output_reasoning_tokens` 83 =
raw completion 101. Priced from the custom row `gpt-5.6-luna` (id `cmvte6laa031lny074cuir13k`,
pattern accepts the `global.openai.` prefix): input 2e-7, cached 2e-8, cache write 2.5e-7
(1.25×), output 1.2e-6, reasoning 1.2e-6 USD per token. `calculatedTotalCost` call 1 $0.000379
vs call 2 $0.000067. Sessions `33106bdf` (direct), `9f157d3f` (bedrock), `685eaa92`, `2f0851a7`
(reasoning supplements). Gotcha: Langfuse's older `usage` field still shows inclusive totals and
`totalCost` is null; read `usageDetails` / `costDetails` / `calculated*Cost`.

### Cost script and fixed-questions script

`scripts/cost_per_run.py` (stdlib only): cost per session from token counts and list prices (price
table dated at the top), by stage and by call name; two totals per session — *run total* (the
`run:*` traces, embeddings included) and *session total* (every trace in the session, so the Task
Agent's planning turns and the option-profile calls too). Fixture
`backend/tests/scripts/data/cost_per_run_fixture.json` (session 0e8f8431 stripped to ids, names,
timestamps, model and `usageDetails` — no inputs or outputs, enforced by a test — plus one
hand-made new-shape session); 8 tests.

**Live reproduction of the contract's § Goal table (2026-11-02, 20 sessions, 25 min):** every
session matches `cost-baseline-per-session-2026-10-30.txt` to the cent on the baseline's own
basis (generation rows under `run:*` traces), medians $2.12 / $0.87 / $3.46. On the two wider
bases:

| Run type (n) | Contract baseline (generation rows under `run:*`) | Run total (+ embeddings) | Session total (every trace) |
|---|---|---|---|
| ES standard (6) | 2.12 (1.60 to 4.88) | 2.22 (1.61 to 4.90) | 2.33 (1.79 to 5.18) |
| ES landscape (5) | 0.87 (0.67 to 1.19) | 0.88 (0.76 to 1.19) | 1.15 (0.86 to 1.38) |
| Options scoping (9) | 3.46 (2.09 to 6.26) | 3.51 (2.10 to 6.26) | 3.88 (2.23 to 6.33) |

Lead decision (owner item for the review): the contract's own term is "the sum of every model
call's cost inside one Langfuse session", so later phases are judged on the **session total**; the
baseline is restated above on all three bases. The $2 target (O1) was set against the $2.12
figure. Small differences: the script dates session d1055c42 by its earliest trace (2026-10-27;
the baseline file said 10-28); the baseline file's tenth scoping session (62260a82) is not in the
contract table and was not run.

`scripts/fixed_questions.py` creates the four fixed questions (O5) as fresh tasks through the
web API (`POST tasks` → `task-agent-turns` → `GET plan` → `PATCH plan` with standard depth →
`POST runs`), answering one clarifying Task Agent turn with "go with your recommended choices"
(max 3). Langfuse session id = task id (`routers/runs.py` `_dispatch_run`). Lead decision:
steering mode `unattended` (no one answers check-ins in a scripted run; it adds no model calls);
the baseline runs were attended through the app, so the runs are not like-for-like on steering.

### D11: the section writer's prompt text is pinned

`evidence_search/synthesis/section_prompt.py` now holds, unchanged, every model-facing constant
from `synthesis_backend.py` (section system prompt and preambles; run, task, final-turn and
repair templates; the five tool schemas; the sections-proposal, key-findings, case-studies,
source-note and intro prompts) and the text-only message builders. The 18 wire (response) model
classes moved too, because the `emit_section` and `emit_repairs` tool schemas are built from their
JSON schema (an import loop otherwise) and their docstrings are the schema descriptions the model
reads. Byte identity: 64 items hashed before (from `synthesis_backend`) and after (from
`section_prompt`), identical; the existing pin `test_section_prompt_templates.py` passes with only
its import changed (`SECTION_SYSTEM_PROMPT` still equals the pinned `_V10_SHA256`).
`synthesis_prompts_v6.py`, the `prompt_variant` switch and
`test_relevance_consumer.py::test_v6_baseline_byte_identical_regardless_of_flag` (it only
exercised v6) are deleted. `finding_vetter.py`, `ranking.py`, `theme_grouping.py`,
`group_clustering.py` join `EXTRA_FILES`. The screen test's "never mentions screening criteria"
file list gains `section_prompt.py`.

### Tidy-ups (owner, 2026-10-30), no behaviour change

Moves: `evidence_search/clustering_engine.py` → `core/`; `options_scoping/longlist/longlist_backend.py`
→ `options_scoping/scoping_backend.py`; `longlist/lever_types.py` → `option_profile/`. Renames:
`test_ingest.py` → `test_ingest_upload.py`; `test_longlist_coverage_046.py` → `test_coverage.py`;
`extract_interventions_prompt.py` → `interventions_prompt.py`; `longlist_theme_prompt.py` →
`theme_prompt.py`; `api/routers/_access.py`, `_common.py` → `access.py`, `common.py`;
`api/readmodels/` → `api/read_models/`; `api/checkin_read.py` → `api/check_ins_read.py`. Deleted:
`scripts/rename_038.py`, `rename_044.py`, `rename_engine.py`, their two state files, three tests,
`scripts/evals/search/experiments/probe_051.py`. Docstrings: `screening_backend.py` (no longer
names `screen_v2`), `options_scoping/model_calls.py` (`final_check` wording). The knowledge note
`two-stage-clustering-closes-partition-cliff.md` has the new path. Kept on purpose: the
`longlist_backend` identifiers in `runtime/harness.py`, `runner.py` and one test name (they are
names, not module paths), and `lever_types` as a data field name.

### Prompt hash re-pins (P0)

| File | Why | On the contract's list? |
|---|---|---|
| `synthesis/section_prompt.py` | new pin (D11) | yes |
| `extract/finding_vetter.py`, `corpus/ranking.py`, `corpus/theme_grouping.py`, `group/group_clustering.py` | new pins (owner 2026-11-01) | yes |
| `interventions_prompt.py`, `theme_prompt.py` | renamed keys, same hash | yes |
| `synthesis_prompts_v6.py` | entry removed | yes |
| `option_profile/lever_typing_prompt.py`, `suggest/suggest_prompt.py` | **one import line each**: `options_scoping.longlist.lever_types` → `options_scoping.option_profile.lever_types`, forced by the owner-decided move of `lever_types.py`; no prompt text changed | **no — flagged deviation** (code-only, same class as the P1 code-only re-pins) |

### D2a: Bedrock London quotas (read by the owner 2026-11-02, read-only `aws service-quotas`)

| Model | Global cross-region tokens per minute | Tokens per day |
|---|---|---|
| GPT-6 Luna | 4,000,000 | 5,760,000,000 |
| GPT-6.1 Terra | 4,000,000 | 5,760,000,000 |
| GPT-6.1 Sol | 2,000,000 | 2,880,000,000 |
| today: GPT-5.6 Luna / Terra / Sol | 4,000,000 / 20,000,000 / 2,000,000 | — |

Terra's per-minute quota falls five-fold at the switch; a standard-depth run is well under one
million tokens, so no risk at current volume. No requests-per-minute rows exist for these models.

### Live probes (step 8, builder, 2026-11-02, 236 calls; `experiments/effort-default-probe-2026-11-02.md`, `gpt6-shapes-probe-2026-11-02.md`)

- **(b) Is the provider default `medium`?** Omitted vs explicit `medium`, five calls each side,
  gpt-5.6-luna, gpt-5.6-terra, gpt-6-luna, gpt-6.1-terra, both routes, an easy and a hard prompt:
  16 comparisons, exact Mann–Whitney, lowest p 0.06, no consistent direction. Omitted is not
  `none` (every omitted call reasoned) and not `low` on gpt-6.1-terra (hard prompt: omitted 61 to 93
  reasoning tokens vs `low` 46 to 52 on direct; 64 to 86 vs 50 to 51 on bedrock). So D4's explicit
  `medium` changes no behaviour (caveat: five calls per side cannot rule out about ±15%).
- **(c) Request shapes on GPT-6.** Accepted on both routes: gpt-6-luna structured output at `none`,
  `low`, `medium`, `high`; gpt-6.1-terra structured at `none`, `medium`, `high`, function tools with
  `none` and `parallel_tool_calls=True`, streaming with `include_usage` (usage in the last chunk),
  the P5 `tool_choice = allowed_tools` shape (no `extra_body` needed); gpt-6.1-sol structured at
  `low` and `medium`. The cache-breakpoint content part works on gpt-6.1-terra: first call writes
  1,396 tokens (direct) / 1,392 (bedrock), second reads the same; `prompt_cache_options` explicit
  with no breakpoint writes and reads nothing. Reasoning tokens are 0 on every `none` call. The
  only rejection: gpt-6-luna with function tools at `medium` (400 on both routes); no Luna step
  uses tools.

### Call-site kwargs fixture (plan step 1, the Phase 1 safety net)

`backend/tests/core/data/call_site_kwargs_056.json` + `tests/core/test_call_site_kwargs.py`: the
provider kwargs every call site builds today (model, effort, response format, tools, tool choice,
parallel tool calls, token cap), captured through a recording client behind
`resolve_openai_client`; 59 entries (56 steps; the two shared steps split into their 2 and 3
sub-sites); 0 disagreements with the plan's § Steps table; identical when captured from a
`git archive HEAD` snapshot. Uncaptured: the Claude/boto3 search path (no route step; no route
selects it). The chat entries have no trace name (the span opens in `api/answer_core.py`).
Extraction fingerprints pinned: `extraction_fingerprint('live', finding_vetter_active=True)` =
`e2ded5c8…7400c`, ICF `95b9b1c0…abc3b8`.

## Phase 1 — steps, effort plumbing, the switch, the prompt loop (N2, N6, D2, D4, D9, O3, X1, X2, X4)

### Phase 0 baseline runs (step 9) — this build, `bedrock`, unattended, 2026-11-02

Server: the Phase 0 commit (d14d3f33) in a detached worktree. `scripts/fixed_questions.py` needed
two fixes on first live use: an `--only` flag (the executor admits two runs at once,
`RUN_EXECUTOR_MAX=2`, so the third question got HTTP 409 "at capacity") and a follow-up message
that names the depth, because the scoping Task Agent asks "shorter or fuller path" with no
recommendation. Session totals from `cost_per_run.py` (run totals in brackets):

| Question | Session (task id) | Session total | Run total | Notes |
|---|---|---|---|---|
| NEET | 19e974e7 | $2.68 | $2.62 | |
| zonal pricing | a57ff6ec | $2.10 | $2.05 | synthesise 68% ($1.43); section turns 62% of input as cache WRITE, repair 99%, summary judge 87% |
| childhood obesity | e99d1502 | $3.01 | $2.98 | synthesise 70% ($2.11) |
| **ES standard median** | | **$2.68** | **$2.62** | first runs with the write bucket visible: writes were ~57% of all input tokens in zonal |
| scoping (AI and the labour market) | cabaa778 | $3.25 | $3.09 | option_profile 33% ($1.08), synthesise 27% ($0.86), extract_interventions 14% ($0.45, 99% of its input written to the cache: 1.18M write tokens); the option-profile calls took ~5 min each on gpt-5.6-sol; the walk ran 2 h |

### X1 — grounding judge replay on gpt-6-luna (builder; `experiments/grounding-judge-replay-2026-11-02.md`)

119 stored `judge:grounding` calls (all with today's `grounding_judge_v2` prompt; 113 older
gpt-5.4-mini calls excluded), 587 claims: collapsed agreement 86.2% against the incumbent's own
re-run noise floor of 95.4%; supported→unsupported flips 12.9% against 4.0% noise; one-directional
(gpt-6-luna stricter: 19.8% unsupported vs 8.9% stored). Groups: 25 of 40 Tier-4 reasoning claims
→ unsupported ("policy-specific framing not labelled as background reasoning"); 45 chunk claims
on one detail (a dropped hedge, a date not in the cited text, scope widened); the 6 looser flips
all correct wrong stored verdicts. Cost per call $0.00358 → $0.00198; clean latency median 15.6 →
15.4 s. **Lead's read: no prompt change.** The chunk flips are the rubric as written; the
reasoning flips are the prompt's own rule ("a reasoning claim that asserts policy-specific …
content is unsupported_mis_cited") applied literally — the spec's intent (provenance-grounding:
"must not escape into Tier 4"). Risk recorded: more repairs on "What is contested" / "Key
assumption" sections; the post-switch fixed questions' repair and rejection counts and the owner's
read of those sections are the check.

### X4 — extract_interventions and fold replays (builder; `experiments/x4-replay-2026-11-02.md`)

`extract:interventions` on gpt-6-luna vs stored (60 items from nine scoping sessions): fuzzy
record F1 0.825 (0.846 on the 20 noise items) vs noise floor 0.921; categorical fields at or
above noise; two systematic shifts — 7 of 91 matched records `described → mentioned`, and 4 of 60
borderline governance/commentary papers marked "covers no intervention" (incumbent re-run 1 of
20); cost −47% per call. `option_profile:fold` on gpt-6-luna (the like-for-like): same-group
0.767 / ARI 0.649 vs noise 0.793 / 0.706 — within noise, no word id lost, cost −53%;
gpt-6.1-terra 0.650 / 0.49 at 2.5× the cost, builds one large group — not warranted. **Lead's
read:** fold stays on `fast`; the extract shifts are a stricter reading, no prompt work (X4's
rule: only if it fails); the owner's read of the scoping longlist checks whether the extra "no
intervention" calls matter.

### Commit A (3a2b5ba3): one route step per call site, effort from the route file (D4, D9)

- `model_routes.toml`: `[steps]` now lists 56 steps (one per model call site; section turns +
  repair share `synthesise_section_turn` and the three chat calls share `chat`, by contract),
  each `{ tier, reasoning_effort }`. The model-keyed `knobs.reasoning_effort` table is gone.
  Today's efforts written out: `high` on classify, the two finding vetters and the relevance
  annotator (the four deleted constants); `none` on the eight Terra sites that read the knob;
  `medium` on every step that sent nothing (the provider default, probe b).
- `core/model_routes.py`: `Route.effort_for(step)`; a step exception is a bare tier/model id
  or a table with `model` and/or `reasoning_effort`; fail loud on stray keys, unknown effort
  values, an empty table and a leftover `knobs` table.
- `core/openai_client.py`: `openai_kwargs(model, *, reasoning_effort)`, `parse_structured` and
  `traced_parse` take the effort (required keyword) and record it in the span metadata.
- The 58 call sites (fast-worker sweep from the lead's table): every site passes
  `route().effort_for(<its step>)`; `_synthesis_openai_kwargs()` became per-step
  `_step_kwargs(step)`; the summary judge has its own kwargs; the source-note and intro sites
  now send `medium` explicitly; `scoping_backend._call` derives the step from the trace name
  (`longlist:discover` → `longlist_discover`); the Task Agent profiles carry `step`.
- Safety net: `test_call_site_kwargs.py` re-captures every site's kwargs against the Phase 0
  fixture — the only difference was `reasoning_effort: null → "medium"` on the 44 sites that
  sent nothing (44 of 44 diffs, nothing else); `test_model_routes.py` pins (model, effort) per
  step on all three routes; the extraction fingerprint kept its value (`e2ded5c8…`).
- Code-only re-pins (11 pinned modules, diffs saved as `p1-commitA-repin-diffs.patch` in the
  scratchpad and summarised here): `classify_prompt.py`, `screen_prompt.py`, `ranking.py`,
  `theme_grouping.py`, `finding_vetter.py`, `icf_prompt.py`, `interventions_prompt.py`,
  `iof_prompt.py`, `group_clustering.py`, `search_prompts.py`, `grounding_judge.py` — model
  and effort lookup lines, imports, one closing brace; no prompt text changed (checked line by
  line).
- Two eval scripts updated for the new signatures (`scripts/evals/search/experiments/snowball_recall.py`,
  `scripts/evals/screening/checks/run_screen.py`).

### Commit B (7561a822): the switch (D2)

Tiers on all three routes: `fast` gpt-6-luna, `standard` gpt-6.1-terra, `frontier` gpt-6.1-sol;
the thirteen frontier steps' effort `medium → low` (Sol refuses `none`; owner 2026-11-01). The
kwargs fixture re-captured: the diff is exactly 59 model ids, 44 efforts (31 `medium`, 13 `low`)
and the two extraction fingerprints (they embed the extraction model id: `708e0aed…` /
`4baac912…` live-vetted). Nine model-bearing test pins re-pinned (listed in the gates table).

### O3: the summary judge and the two summariser prompts (lead, prompt-bearing), with X2

Replays on gpt-6.1-terra at `none`, 90 labelled items (45 should pass, 45 corrupted should fail)
plus the 20 adjudicated: `experiments/summary-judge-v2-replay-2026-11-02.md` (round 1) and
`summary-judge-v2b-replay-2026-11-02.md` (round 2).

| Judge | True pass | False fail | True fail | False pass |
|---|---|---|---|---|
| `summary_judge_v1` (today) | 27 | 18 | 45 | 0 |
| draft A | 21 | 24 | 45 | 0 |
| **`summary_judge_v2` (draft B, shipped)** | **28** | **17** | **45** | **0** (both passes; repeat agreement 43/45) |

Round 1 showed draft A coherent with its own standard (19 of 24 failed positives were the
summariser's gap wording). Draft B fails only wording that asserts a fact about the world,
lets scope words drop when the shorter gap stays true, treats an assumption's content as carried
unless asserted as fact, and makes "would a reader who never opens the detail be misled" the
deciding question with omission never a fault. Adjudicated items under v2: UNSUPPORTED 7/7 fail;
FAITHFUL 2/4 pass (pos-15 read as widening a neighbourhood-scoped gap; pos-35 as the reasoning
label stated as fact — both defensible strict readings, owner's read); BORDERLINE 4/9 pass. Every
fail reason quotes the summary words at fault (69/69 vs 6/63 under v1).

Writer `summariser_v3` (gaps stay gaps; labels travel; a `previous_attempt` rule) regenerating
the 45 positives, judged by v2: first attempt **42/45** vs 37/45 for today's writer; both 45/45
after one retry carrying the judge's reason. Length: mean 170 chars (v2 165), 4/45 over 200
(ceiling 300). Cost: +262 input tokens per judge call (+6.5%), latency unchanged.

X2 (deep-reasoner): `_write_and_judge_summary` sends `{**seed, "previous_attempt": {"summary",
"judge_reason"}}` on a retry (judge reason, or a plain sentence for `over_length` /
`citation_markers`), only the latest attempt, first attempt unchanged; one `synthesise.summary_retry`
log per retry; three tests in `test_summary_runtime.py`. Re-pin: `summary_prompts.py` (the
diff is the three summariser rules in both prompts, the judge's rules block, the version bumps
and the module docstring; saved as `p1-commitC-summary_prompts.patch`).

## Phase 2 — caching (N3, D3, D8, D10, X3)

**Stop condition (step 1, builder, 183 calls, $0.85; `experiments/cache-breakpoint-gpt6-2026-11-02-*`):
not hit.** gpt-6.1-terra and gpt-6-luna reproduce GPT-5.6 on both routes: implicit reads need no
breakpoint (a request that starts with an earlier request reads it: 9,698 direct / 9,622 bedrock);
the run-message breakpoint makes section 2's first turn read tools + system + run (terra 7,849 to
7,851 / 7,767 to 7,771; luna 6,363 / 6,361), writing only the 809-token tail; all 69 cold calls over
1,024 tokens wrote; the repair reads the section's first turn (about 9,570 / 9,490) only when the
tools list and `parallel_tool_calls` are identical, 0 otherwise; the opt-out writes 0 on all 34
calls; `allowed_tools` keeps the cache across turns and into the repair. Headline lever: today's
forced final turn (`parallel_tool_calls=False`) reads nothing and costs $0.0155 in the mock against
$0.0025 with the flag true. Bedrock caveat (GPT-5.6 behaves the same): `off` stops the write being
reported but identical calls still read (terra 8,517 of 8,574); on OpenAI direct it is a true off.

**Commit A (43bf7a34).** `core/openai_client.py`: `PromptCache = auto | off | breakpoint`
(`off` → `extra_body={"prompt_cache_options": {"mode": "explicit"}}`; `breakpoint` → the first
system message as a text content part with `prompt_cache_breakpoint`); `parse_structured` and
`traced_parse` carry the mode and record it in the span. `synthesis/cache_modes.py`: one table
keyed by step (56 entries, all `auto` until commit B), read by the sites; the enumerating test in
`test_call_site_kwargs.py` checks every captured call site against it (the fixture gained
`extra_body` and `system_shape` on every entry, nothing else). D8/D10 in `section_prompt.py` /
`synthesis_backend.py`: one `build_section_prefix(seed)` (system; the run message as a breakpoint
content part; the task message) shared byte-for-byte by section turns and the repair (test); the
same five tools in the same order on both (`section_request_tools(seed)`); normal turns use
`tool_choice = allowed_tools` over the four section tools, the forced turn forces `emit_section`,
the repair forces `emit_repairs`; `parallel_tool_calls=True` everywhere including the forced turn
and the repair; a second tool call on a forced turn or the repair takes the first `emit_*` call,
logs `synthesise.extra_tool_calls_ignored` and is counted on the loop result and span metadata
(not persisted provenance: lead's call). `synthesise_section_v11`; new
`SECTION_REPAIR_PROMPT_VERSION = "synthesise_repair_v2"` on the repair span. X3: the `lookup`
tool offers only the kinds the run can serve (`available_lookup_kinds` from the same run facts the
reader checks: selection, characterisation, grouping runs; put on every section seed so the prefix
is run-stable); the description gains the lead's sentence "Only the kinds listed here exist for
this run." Prompt text unchanged (the byte-identity pin passes); `section_prompt.py` re-pinned for
the message shape and the X3 sentence (diff saved as `p2-section_prompt.patch`). Owner item: the
repair template still says "you cannot make tool calls" while five tools are offered with
`emit_repairs` forced — true in effect; prompt text left unchanged by design.

**Per-site modes (N3, commit B):** pending the measurement (`cache-modes-per-site-2026-11-02`).

## Phase 3 — Unrated (N4, D7, S1 to S3) — commit 3bcd3044, Gate 4 full verify

Built by a deep-reasoner in its own worktree (patch `p3-unrated.patch`, 40 files): migration
`152a234e2391_unrated_appraisal` (revises `b33ffb8c3a16`): `quality_score` nullable, `unrated
BOOLEAN NOT NULL DEFAULT false`, `ck_sar_unrated_consistent`; the 1 to 5 check untouched; downgrade
deletes Unrated rows (documented as lossy); round-trip and admission tests (null score without the
flag refused, score 3 with the flag refused, score 6 refused; an Unrated row, a score of 3 and a
default row admitted). `appraise.py`: `UNRATED_LABEL`, `UNRATED_TYPES`, `appraisal_label()` /
`appraisal_tier()`; Unknown and Non-evidence get a row with no score and `unrated = true`;
`appraised_unrated` counted; `DEFAULT_RUBRIC_VERSION` `v2-hierarchy-v1 → v2-hierarchy-v2`; a
rubric override that scores one of these types still wins. `steering_triggers.py` filters null
scores (output unchanged with Unrated rows present: test); `select.py` unchanged (an Unrated row
reads as missing, exactly as no row: test). Citability: the citation check keys on row existence,
so Unrated documents are citable (test: accepted; a document with no row still rejected with
`unappraised_doc_citation`); the writer records carry `appraisal_label` "Unrated" (`appraised:
true`); `appraisal_order` "Unrated" last; characterise, coverage, place sentences, read models
(strength sort: scored → Unrated → no appraisal), the `strength` Literal, `answer_core`,
`chat_scope`, `steering_bundles` show "Unrated" as its own bucket. Frontend: regenerated types;
`STRENGTH_FILTER_OPTIONS` + "Unrated" last; mocks and tests. Lead words: the two hints end "…;
Unrated when the type is not scored."; the Unrated hover reads "Unrated — the document type (X) is
not scored; the source can be cited but counts below the evidence bar."

Unforeseen by the contract, lead decisions (owner items): (1) the rubric bump made every inherited
appraisal "stale" in `options_scoping/labels.py` (a linked scoping task would re-classify every
document) → `COMPATIBLE_RUBRIC_VERSIONS = {v2-hierarchy-v1, current}` for inherited rows, since
the 1 to 5 scores did not change; (2) `runner.resolved_skip_ids` now skips classify and appraise
only when the tier came through the link (else inherited untyped documents would never get a row);
(3) `skipped_non_evidence` / `skipped_unknown` now always 0 under the default rubric, kept with a
docstring; (4) frontend `artefactPresentation.APPRAISAL_ORDER` was already stale (old label names)
— only "unrated" appended; deferred; (5) the synthesis boost vocabulary still lists tiers 1 to 5 —
data, not prompt text, left.

Live check (`unappraised_doc_citation` count before and after; the owner's read): pending the
post-Phase-3 fixed-question runs.

## Phase 4 — repair input guard (N5)

Built by a deep-reasoner in its own worktree (patch `p4-repair-guard.patch`): the inline
tool-return window rule became `oversized_chunk_window()` in `synthesis_tools.py`, used by the tool
return and by the new `window_repair_dependency_chunks(failing)` that `build_section_repair_messages`
applies before the JSON dump. Threshold: the existing oversized rule (`UNIT_CHAR_BUDGET`, 2,000
characters; the contract's "oversized threshold"); window = anchor ± 300 characters, clipped; the
anchor is the claim's citation quote(s) matched with `QuoteMatcher` (verification normalisation),
else the longest shared stretch (deterministic); finding claims anchor on their dependency
findings' grounding quotes (beyond the brief; accepted); already-windowed and unanchorable chunks
pass unchanged; the window carries the same `window_start` / `window_end` marker as tool returns.
Prompt text byte-identical; `section_prompt.py` re-pinned for builder code (import, docstring, the
call). Synthetic payload: the repair message falls from 15,551 to 3,052 characters (−80%); worst
case (a 104,890-character chunk, quote absent) 0.087 s. Ten tests. Lead decision: keep the 2,000
threshold and judge it on the repair pass rate of the post-Phase-4 fixed questions; raise to
10,000 as a recorded change if the rate falls.

## Phase 5 — effort per step (N7, O2)

Replay (builder; `experiments/effort-high-steps-2026-11-02-*`, 160 calls, $0.46) for the three
steps still at `high`. The stored vetter calls (214 since 2026-09-01) all ran on gpt-5.4-mini, so
the noise floor is that model's own repeat and a gpt-6-luna `high` repeat was added.

| Step | luna `high` vs stored (verdict) | luna `medium` vs stored | noise floor | medium vs high | medium: reasoning tokens / latency / cost | Pin |
|---|---|---|---|---|---|---|
| `extract_vet_iof_findings` (30 items, 453 findings) | 0.951 | 0.947 | 0.937 (mini), 0.921 (luna repeat) | 0.987 | −37% / −25% / −15% | **medium** |
| `extract_vet_icf_findings` (30 items, 619 findings) | 0.950 | 0.961 | 0.952 / 0.952 | 0.963 | −56% / −35% / −24% | **medium** |
| `extract_annotate_relevance` | — | — | — | — | no stored call exists at any date (runs only with a user relevance emphasis) | **high** (cannot tell) |
| `classify_document` | contract fact (`classify-effort-sweep.md`): `medium` within noise, 19% cheaper, 22% faster | | | | | **medium** |

The differences between `medium` and `high` go both ways on borderline findings; the one
repeated lean is ICF `medium` flagging "aims to / seeks to" mechanism statements as aspiration.
Pinned in `model_routes.toml` (the per-step pin test and the kwargs fixture re-captured: exactly
the three efforts and the two vetted extraction fingerprints, which embed the vetter effort). The
thirteen frontier steps stay on `frontier` (gpt-6.1-sol at `low`): the plan's 2026-11-02 amendment
makes any downgrade conditional on the owner reading
`experiments/frontier-steps-replay-samples.md` side by side — an owner gate this build cannot pass
on its own, recorded as open.

## Phase 6 — ingest scheduler, progress stage, XML route (N8, N9/S5, N10/S7) — commit a4fb1bb2, Gate 5 full verify

Built by three deep-reasoners in their own worktrees (N8; N9 on N8; N10 parser + the wiring on
both), patches `p6-n8.patch`, `p6-n8n9.patch`, `p6-n10.patch`, `p6-all.patch`.

**N8.** `_ParseScheduler`: any-free-slot draining (`multiprocessing.connection.wait` over every
running worker's pipe; the first finished job frees its slot) and a `forkserver` context that
preloads the parser modules so each job forks a warm helper; `_drain_parse_job` / `_worker_entry`
reused; the per-document deadline, hard-kill, corrupt-on-death and the task-045 shared ingest
slots unchanged; worker count, timeouts, pool sizes and fetch threads unchanged (D6). The batch
hand-over inside a cascade round is now continuous (a fetched body enters the queue as it lands);
one `ingest.batch_handover` log per round (`batch`, `documents`, `fetch_wall_s`, `parse_wall_s`,
`idle_gap_s`). Measured on the saved 52-document corpus (replayed fetch times, pool 8): old wall
152.1 s with 713 idle slot-seconds → new 56.9 s with 9.3 (product log `idle_gap_s` 0.27);
`ingest-scheduler-n8-verify.py`: pool 8 49.4 s, pool 4 61.6 s, 747 chunks, digest
`35e8ebb3bba09ba5` = the prototype's reference, 0 mismatches. Committed corpus
(`tests/data/fulltext`: three CC-BY-4.0 PDFs + a CC0 corrupt file): digest `15f69fc2…078b9`
identical for the old scheduler (workers 1 and 4), the new one (1 and 4) and a same-process
parse; pinned by `test_scheduler_output_is_byte_identical_workers_1_vs_4`. **Security note for
the review:** the parent-side guard in `test_zero_egress_socket_deny` now allows `AF_UNIX` only
(the forkserver's local socket); the worker-side guard still refuses every socket. Not yet run on
the 2-CPU staging container (plan step 4).

**N9 / S5.** `StageKey` gains `ingest` after `appraise`; `STAGE_BY_REGISTRY["ingest_full_text"]
= "ingest"` so the harness's events produce the row; `TickFrame` gains optional typed `fetched`,
`parsed`, `total` (omitted when absent, so a tick without counts is byte-identical to before);
`publish_current_tick` carries them; an in-memory `_IngestProgress` mirrors the `full_text_status`
values the end-of-run write pass stores (total = eligible set; already-ingested rows count as
fetched and parsed; fetched on body arrival; parsed on `ingested`), ticked after each finished
fetch batch and each drain. Words (lead): label "Reading the full texts", blurb "Fetching each
selected document's full text and reading it into sections.", beat "Reading the full texts:
{parsed} of {total} read" (or "{fetched} fetched" before any is read). The plan panel lists the
stage after appraise (server plan steps and `planVocabulary.ts`), and ticks are now shown: the
running card takes `liveness` and shows the beat on the in-progress row. Spec `web-api.md` § SSE
amended (S5). Live check (the stage with counts on a fixed-question run): pending.

**N10 / S7.** `sourcing/parse_jats.py`: the stdlib expat parser driven directly
(`SetParamEntityParsing NEVER`, `ExternalEntityRefHandler` raises → `corrupt`, skipped entities →
U+FFFD), about 75 undefined JATS named entities replaced before parsing; output = the segmenter's
page shape (`#` title, `##` Abstract and sections nested to `######`, pipe tables with their
captions, figure captions, TeX formulas; reference lists left out — lead accepts, owner item);
hostile input: billion laughs refused in 0.30 s, quadratic blow-up in 0.06 s, `file://` and
`http` external entities refused with zero socket calls and a loopback listener that never
receives a connection; `pyexpat` 2.6.3 locally with a test that asserts ≥ 2.4.1 (the production
`python:3.12-slim` image is unchecked). `fetch_europe_pmc_xml(pmcid)`: `PMC[0-9]{1,12}` full match
before any request; `https://www.ebi.ac.uk/europepmc/webservices/rest/{id}/fullTextXML` through
the pinned-IP transport, product user agent, no redirects, body cap; only the id is logged;
under the live fetcher's global semaphore and per-host slot (≤ 2 concurrent, starts ≥ 1 s apart;
Europe PMC's published guidance is believed to allow about 10 requests/s — to confirm at review).
Wiring: a document whose OpenAlex metadata carries `provider_fields.ids.pmcid` (a link with the
number; `normalise_pmcid`) tries the XML first, then today's PDF-first candidates; a missing,
empty or corrupt XML falls through to the next candidate by the existing cascade rule; fixture
replay never contacts Europe PMC (the hook exists only on the live fetcher); `source_kind` stored
per document (`europe_pmc_xml | pdf | html | plain`) and `by_route` counts in the run summary.
Three CC BY 4.0 JATS fixtures (PMC11210863, PMC5264339, PMC11218303; digests pinned). Fresh
acquisitions (read-only SQL on the three 2026-11-02 ES tasks): 100 of 599 OpenAlex rows carry a
pmcid (16.7%); of the rows screened relevant, 3 of 96, 0 of 144 and 74 of 164 — so the XML share
depends on the question (about 45% on obesity, near 0 on NEET and zonal pricing); Overton rows
carry no ids. No `acquire.py` change was needed. Live share and chunk quality on the fixed
questions: pending.

## Checks beyond the build

- Deterministic tests added in P0: usage buckets (21 in `test_usage.py`), cost script (8),
  call-site kwargs (62), loader shape tests (Phase 1).
- Live: probes (a), (b), (c) above; fixed-question baseline runs (step 9) below.

## End-to-end command

```
# Baseline server (Phase 0 commit, bedrock route), from a detached worktree so later edits
# cannot reload it mid-run:
cd ../policy_atlas-live/backend && POLICY_ATLAS_MODEL_ROUTE=bedrock PA_BACKEND_MODE=live \
  .venv/bin/uvicorn policy_atlas.api.app:create_app --factory --port 8000 \
  --env-file /Users/shabeer.rauf/repos/policy_atlas/backend/.env
# The four fixed questions, then the cost per session:
set -a; source backend/.env; set +a
uv run --project backend python scripts/fixed_questions.py
uv run --project backend python scripts/cost_per_run.py <session-id> ...
```

## Diff summary

See the per-phase sections. Flagged deviations: the two import-line re-pins (P0); plan step 3
folded into step 2 (no code resulted).

## Intent & assumptions

- The provider's default reasoning effort is `medium` (probe b), so writing `medium` where
  nothing was sent is a no-behaviour change.
- Cost comparisons use the session total (lead decision above; owner to confirm).

## Known unverified items

- `fixed_questions.py`'s Task Agent follow-up loop against the real agent (first live use is
  the Phase 0 baseline run).

## Public safety

Experiment files live in the gitignored `experiments/` folder. The committed cost fixture holds
only ids, names, timestamps, models and token counts (test-enforced). No report text is quoted.

## Review handoff (step-7/8 inputs)

- **Adjudication items:** the two import-line re-pins; the session-total comparison basis; the
  wire models moving into the pinned prompt module; unattended steering for the fixed questions.
- **Executor provenance:** every build step on Claude (deep-reasoner / fast-worker / builder /
  lead) — Codex unavailable; the review conversation must supply the family flip.
- **Diff-scoping exclusions:** `backend/tests/scripts/data/cost_per_run_fixture.json` (277 KB),
  `backend/tests/core/data/call_site_kwargs_056.json` (data files; audit lane, not review diff).
- **Knowledge candidates:**
  - A `git stash` / `git stash pop` by one agent while sibling agents edit the same tree reverts
    their in-flight files for the window between the two commands; parallel-agent briefs must
    forbid `git stash` (a fast-worker did this during the tidy-ups; no damage found at hand-back).
  - A 10-second status-poll deadline in a thread test fails under the load of several agents plus
    the full suite; the fix is to rerun alone before calling the base red.
  - Langfuse maps the OpenAI usage shape server-side into exclusive buckets named
    `input_cached_tokens`, `input_cache_write_tokens`, `output_reasoning_tokens`; the SDK forwards
    `usage_details` untouched, so sending both shapes would double count. Its older `usage` field
    stays inclusive and `totalCost` is null; read `usageDetails` / `costDetails`.
  - The OpenAI SDK's `PromptTokensDetails` does not declare `cache_write_tokens`; the value
    survives only because the SDK models allow extra fields.
  - Pydantic class docstrings become JSON-schema descriptions the model reads: wire models used
    in tool schemas are prompt text and belong under the hash guard.
  - Omitting `reasoning_effort` equals `medium` on gpt-5.6 and gpt-6 models on both routes;
    GPT-6 models refuse function tools at any effort but `none` on Chat Completions.
  - The baseline's "cost per run" left out embeddings and the Task Agent's planning turns (about
    5 to 10% of a session); define the basis before setting a target.
  - The Langfuse observations API on our instance has no v2 endpoint; pulling a session takes
    about 40 s, so a 20-session comparison is a 25-minute job.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) at step 8: the dependency-direction
knots the tidy-ups exposed (core importing a capability; scoping and API read models reaching
into each other); the Claude-direct search path reads only `cacheReadInputTokens` (no cache-write
capture; no route selects it); `baseline_prompt.py:14` comment still names `synthesis_backend.py`
as the home of the shared core (pinned file; fix at the next deliberate re-pin).
