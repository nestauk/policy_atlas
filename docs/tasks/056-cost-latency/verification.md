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
| P5 | Phase 5 (effort per step), tree = Phase 6 + the Phase 5 pins | `make verify-fast` + prompt-guard | 3,882 passed, **2 failed**: two literal `== "high"` pins (`test_classify.py`, `test_finding_vetter.py`) that the Phase 5 pins change by design; updated, those files re-run green; ruff E501 on two comment lines shortened; typecheck, eval-check clean; prompt-guard 41 unchanged. |
| P2 B | Phase 2 commit B (cache modes), tree = Phase 5 + the commit B patch | `make verify-fast` + prompt-guard | **green**: 3,884 passed, 1 skipped (668 s); typecheck 439 files, lint, eval-check clean; prompt-guard 41 unchanged after the five import-line re-pins. |
| P2 B fix | Phase 2 commit B fix (breakpoint sends explicit mode), tree = commit B + the fix | `make verify-fast` + prompt-guard | 3,883 passed, **1 failed**: `test_step_kwargs_send_the_steps_model_and_effort` pinned a breakpoint step's kwargs without the body; updated, the three affected files re-run: 94 passed; ruff, mypy clean; eval-check green; prompt-guard 41 unchanged. |
| P5 pins | Phase 5 step 1b (frontier pins), tree = P2 B fix + the pins | `make verify-fast` + prompt-guard | 3,882 passed, **2 failed**: the route test's two Sol pins (`task_agent_scoping_turn` on bedrock; `TASK_AGENT_SCOPING_MODEL`), changed by design; updated while the gate ran, the two files re-run: 101 passed; mypy 439 files, ruff, eval-check clean; prompt-guard 41 unchanged. |
| 6 | Step-6 exit, tree = 67bc0ac7 | `make verify` | **green** (exit 0): backend 3,884 passed, 1 skipped (797 s); infra 95 passed; okf-validate, build, audit-paths (202 files), prompt-guard (41 unchanged), font-guard, drift-check OK; frontend 943 tests in 88 files; one pre-existing eslint warning in `SplashField.tsx` (not touched by this task). |
| 6b | Step-6 exit re-run, tree = 3b5456dd (the stall fix: extractor timeout 60 s, 8 workers) | `make verify` | **green** (exit 0): backend 3,884 passed, 1 skipped (756 s); infra, okf-validate, build, audit-paths, prompt-guard (41 unchanged), font-guard, drift-check OK; frontend 943 tests in 88 files. |
| 6c | Step-6 exit re-run, tree = 9fe7ca2f (grounding_judge_v3) | `make verify` | **green** (exit 0): backend 3,884 passed, 1 skipped (753 s); prompt-guard 41 unchanged after the judge re-pin; drift-check OK; frontend 943. |
| 6d | Step-6 exit re-run, tree = c34ec5e7 (the suite on every core) | `make verify` | **green** (exit 0) in 504 s end to end (the serial gate took about 860 s): backend 3,884 passed, 1 skipped in 407 s on 8 workers; mypy 439 files; prompt-guard 41 unchanged; drift-check OK; frontend 943. |
| 6e | Step-6 exit re-run, tree = 8d841e2d (longlist client timeout 60 s) | `make verify` | **green** (exit 0) in 475 s: backend 3,884 passed, 1 skipped (381 s on 8 workers); frontend 943; every other step OK. |
| 6f | Seven client timeouts to 60 s + worker-database names with the process id | `make verify` | backend 3,883 passed, **1 failed**: `test_slow_first_job_does_not_delay_later_jobs` (completion order `[1, 2, 0, 3]`) under eight workers plus the live scoping run; alone 3 of 3 passes; the slow job's sleep widened 4 s → 10 s (assertion unchanged). |
| 6g | Same tree + the test margin | `make verify` | backend 3,884 passed (423 s), mypy clean; **prompt-guard red**: `finding_vetter.py` drifted on its timeout line (a pinned prompt surface; diff `p-timeouts-repin-diffs.patch`); re-pinned. |
| 6h | Seven timeouts tree = c8a3bfff | `make verify` | **green** (exit 0) in 462 s: backend 3,884 passed, 1 skipped (367 s on 8 workers); mypy 439 files; prompt-guard 41 unchanged; drift-check OK; frontend 943 tests. |
| 6i | tornado 6.6 in the lock file | `make verify` (with `make audit` alongside: clean) | backend 3,883 passed, **1 failed**: `test_a_fan_out_that_raises_part_way_interrupts_the_children_it_sent` (10 s poll deadline; the same test as Gate 1's flake) under eight workers plus the audit's install; alone 2 of 2. |
| 6j | Same tree, machine idle | `make verify` | the same test **failed again** (no child status within 10 s), so it is not a rare flake under the parallel suite; the two 10 s deadlines in `test_option_search.py` widened to 30 s, assertions unchanged. |
| 6k | Step-6 exit, final tree = f08293c9 | `make verify` | **green** (exit 0) in 451 s: backend 3,884 passed, 1 skipped (359 s on 8 workers); prompt-guard 41 unchanged; drift-check OK; frontend 943. |
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
| 5 | 540f32a8 | P5 (verify-fast) |
| 2 B | e90a7f36 | P2 B (verify-fast) |
| 2 B fix | 12c31228 | P2 B fix (verify-fast) |
| 5 (1b) | 67bc0ac7 | P5 pins (verify-fast) |
| stall fix | 3b5456dd | 6b (full) |
| judge v3 | 9fe7ca2f | 6c (full) |
| suite on every core | c34ec5e7 | 6d (full) |
| longlist timeout | 8d841e2d | 6e (full) |
| seven timeouts, worker-db pid, test margin | c8a3bfff | 6h (full) |
| tornado 6.6, option-search waits | f08293c9 | 6k (full) |

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

**Fixed questions after the model-only switch (step 5; this commit, `bedrock`, unattended,
2026-11-02; `cost-modelonly-*.txt`).** Same four questions as new tasks, priced by session:

| Question | Session (task id) | Session total | vs baseline | Run total | Notes |
|---|---|---|---|---|---|
| NEET | 0ee5df1d | $1.28 | −52% ($2.68) | $1.26 | |
| zonal pricing | 81583952 | $1.08 | −49% ($2.10) | $1.06 | |
| childhood obesity | c7dcc8f0 | $1.32 | −56% ($3.01) | $1.30 | synthesise 53% ($0.70); embeddings now 21% ($0.28), the largest non-model line |
| **ES standard median** | | **$1.28** | **−52% ($2.68)** | **$1.26** | |
| scoping (AI and the labour market) | 19fbb5fd | $1.29 | −60% ($3.25) | $1.24 | option_profile $1.08 → $0.14 (gpt-6.1-sol at `low`); extract_interventions $0.45 → $0.29 with 212 calls (152 before) |

The switch alone takes the Evidence search median past the $2 target (O1) and the scoping
question to $1.29. Section turns still write 64% of their input to the cache (obesity: read 42%,
write 58%), which Phase 2 addresses. The `openai-direct` run the contract asks for after P1 was
not run at this point (one executor, one route per server; recorded as a deviation; the final set
runs NEET on `openai-direct` alongside).

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

**Summary judge on the fixed questions (N6, judge calls minus summaries written).** Baseline
(gpt-5.6-terra writer, `summary_judge_v1`): 9 to 16 rejections per run on 10 to 11 summaries
(the old loop retried more than once per block). Model-only switch: 1 to 4. Final: zonal 0,
obesity 1, NEET 4 then 1 (fixed commit), NEET on `openai-direct` 1 and 1. First-attempt pass
rate on the final runs is 0.64 to 1.00 against at most about 0.2 on the baseline: not lower.

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
this run." Measured after: 0 unservable lookups on all eight final sessions (§ Phase 3 live check
file); total lookups per run 2 to 9 against the baseline's 13 to 24. Prompt text unchanged (the byte-identity pin passes); `section_prompt.py` re-pinned for
the message shape and the X3 sentence (diff saved as `p2-section_prompt.patch`). Owner item: the
repair template still says "you cannot make tool calls" while five tools are offered with
`emit_repairs` forced — true in effect; prompt text left unchanged by design.

**Per-site modes (N3, step 3, builder measured, lead picked; commit e90a7f36;
`experiments/cache-modes-per-site-2026-11-02.md`, $3.18, 2 passes on `openai-direct` plus a Bedrock
confirmation).** Ten stored requests per site replayed in `off`, `auto` and `breakpoint`; the
first pass is unreliable (64 attempts hung to the 600 s client timeout and completed server-side,
so retries read what the hung attempt had stored); the second pass isolates every site-and-mode
block with a nonce in the system prompt and reports only items that succeeded first time in all
three modes. Result: `breakpoint` is never worse than `off` or `auto` at any site, on both routes.
Input-cost saving against `auto` on `openai-direct` (matched items): judge:grounding 19.8% (7),
screen:full 19.9% (10), classify:document 16.9% (9), judge_summary 19.1% (10), group:assign 20.0%
(8), vet_iof 19.4% (8), vet_icf 20.0% (9), write_case_studies 19.9% (7), select:rerank 20.0% (7),
screen:abstract 15.9% (9), extract:iof_findings 19.7% (5). Under 1,024 tokens of system prompt
`breakpoint` stores and reads nothing, so it equals `off` (the 25% storing surcharge removed);
over it, it stores the system prompt plus schema once and reads it on every later call, where
`auto` stores the whole request at 1.25x on every call and never reads the per-call tail back.
On Bedrock `auto` read 0 tokens on all 40 calls, so `breakpoint` saves 26.1% (judge:grounding)
and 62.7% (classify) of input cost there. Stored prefixes: judge:grounding 1,438, classify 1,343,
screen:abstract 1,068, write_case_studies 1,072, extract:iof 6,033 tokens; every other site is under
1,024.

The pick (`cache_modes.py`): `breakpoint` at the 45 one-shot steps (the measured sites and, by the
same shape, the unmeasured characterise, group:discover, extract:icf, interventions, relevance,
search, longlist, option-profile and synthesis one-shot writer steps); `auto` at the 11 steps
whose whole prompt repeats across turns (`chat`, the seven `agent_*` steps, `task_agent_turn`,
`task_agent_scoping_turn`, `synthesise_section_turn` with its own run-message breakpoint from
commit A). `write_block_summary` retries with the previous attempt appended (X2), so the first
request is a prefix of the retry, but at about one retry in fourteen calls the whole-request store
costs more than the one read saves: `breakpoint`. Wiring (fast-worker, patch `p2-commitB.patch`):
every `parse_structured` and `traced_parse` site passes `prompt_cache=cache_mode_for(step)`; the
direct `.parse`/`.create` sites in `synthesis_backend.py` go through `_cache_messages(step,
messages)` and `_step_kwargs`; the grounding judge and the chat backend read the table; the
enumerating test `test_every_step_has_a_cache_mode_and_sends_it` passes for all 62 captured sites,
the kwargs fixture re-captured (`extra_body` stays `None` everywhere; `system_shape` becomes
`parts+breakpoint` at the 45 steps), and the extraction fingerprint is unchanged (no re-pin). Two
test adaptations: the `longlist_shortlist` test driver now sends a system message (the real call
does); two characterise tests read the system text through the content parts. Flagged deviation:
five prompt-surface files re-pinned for import and `prompt_cache=` lines only (`ranking.py`,
`theme_grouping.py`, `finding_vetter.py`, `group_clustering.py`, `grounding_judge.py`; diff saved as
`p2-commitB-repin-diffs.patch`), the same class as the Phase 0 import-line re-pins. **Gap found by the first final NEET run and fixed (commit 12c31228, Gate P2 B fix).** Under the
product's `breakpoint` screen:full still wrote 100% of its input to the cache (787k write tokens),
judge_summary 86% and write_block_summary 100%, the same as under `auto`: the measurement's
`breakpoint` sent explicit cache mode plus the breakpoint, the product sent the breakpoint alone,
so the provider kept storing every whole request. `openai_kwargs` now sends the explicit-mode body
for `breakpoint` as for `off`; the client tests, the enumerating test, the synthesis kwargs pin and
the fixture (`extra_body` at the 45 breakpoint steps) follow. NEET on both routes and scoping
re-ran on the fixed commit (the final cost table below); zonal and obesity ran on e90a7f36 and
carry the pre-fix write shares. Not measured
(synthesis refinement task): a second breakpoint after run-stable user-message blocks (judge_summary
`detail`, group:assign label list, screen:abstract scope block, extract document envelope); the
`bedrock-claude` route. Owner items: the unmeasured one-shot sites are picked by shape, not
measurement; 124 timed-out attempts in waves across every mode and route during the measurement
(completed server-side, probably billed) are a separate problem outside this slice.

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

Live check (`unappraised_doc_citation` repair reasons per session, from the X3 scripts re-run over
the final sessions; `experiments/x3-wasted-lookups-2026-11-02-after-table.txt`): baseline NEET 6,
zonal 3, obesity 0, scoping 2; **0 on all eight final sessions** (NEET ×4 on both routes, zonal,
obesity, scoping ×2). The owner's read of the Unrated labels in the reports is still open.

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

**Measured on the fixed questions (repair_claims per run, from `cost_per_run.py`).** Baseline: 6
calls on every question, about 21,500 input tokens a call, all written to the cache ($0.25 to $0.36
a run on gpt-5.6-terra). Final: NEET 2 calls, zonal 5, obesity 4, NEET on `openai-direct` 7 and 6,
fixed-commit NEET 5; input per call 15,000 to 19,000 tokens of which 70 to 94% is read from the
cache (D10: the repair reads the section's first turn), $0.01 to $0.05 a run. The windowing's own
share cannot be separated from the model and cache changes on these runs (the synthetic payload
measure above is the guard's own evidence). Pass rate: every final run ends with 0 unverified
citations and 0 to 2 structural rejections against the baseline's 5 to 13 (table in § Final
fixed-question set), so the guard did not lower the repair outcome; the 2,000 threshold stays.

## Phase 5 — effort per step (N7, O2) — commit 540f32a8, Gate P5

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
the three efforts and the two vetted extraction fingerprints, which embed the vetter effort). 
**Step 1b, the thirteen frontier steps (owner read 2026-11-02 in the build conversation; commit
67bc0ac7, Gate P5 pins).** The replay (`experiments/frontier-steps-replay.md`, 7 inputs per step,
$7.36 to $9.70) was walked through with the owner in three groups and the owner chose per step.
After the like-for-like switch the thirteen calls cost about $0.26 of the $1.29 scoping run, so the
whole decision is worth about $0.20 a run.

| Group | Steps | Owner's pin | Replay evidence |
|---|---|---|---|
| A (drop inside noise) | `task_agent_scoping_turn`, `option_profile_line`, `option_profile_potential_impact`, `option_profile_ambition`, `longlist_constrain`, `longlist_distinct` | gpt-6.1-terra `none` (tier `standard`) | closed fields 1.000 on every configuration (final turns only); judge grades 2.29 / 2.35 / 2.53 against Sol's 2.29 / 2.40 / 2.48, inside the 0.43 judge floor; constrain and distinct could not separate configurations (no "breaks", no duplicate in any output) |
| B (one to a few items differ) | `longlist_assign_themes`, `longlist_type` | gpt-6-luna `medium` (tier `fast`) | 1 of 146 and 4 of 86 items differ against Sol's 0 and 3; Luna lands on the stored primary or runner-up type 100% |
| B | `longlist_authority` | gpt-6.1-terra `none` | 9 of 192 differ against Sol's 7 (gpt-5.5 labels) |
| B | `longlist_themes` | gpt-6.1-terra `medium` | pair agreement 0.935 against 0.940 |
| C (real drop) | `option_profile_setting` | gpt-6.1-terra `high` | main-setting agreement 0.75 against Sol 0.80; `none` and Luna 0.60 |
| C | `longlist_shortlist`, `longlist_discover` | stay `frontier` (gpt-6.1-sol `low`) | Sol keeps 0.77 of stored picks against Terra's 0.63 to 0.69; discover's measure cannot separate and Terra proposes more options per call |

Pinned as tier and effort changes in `[steps]` (eleven steps); the kwargs fixture diff is exactly
eleven model ids and eleven efforts; the route test's two Sol pins moved (`TASK_AGENT_SCOPING_MODEL`
→ Terra; `LONGLIST_JUDGMENT_MODEL` reads `longlist_discover` and stays Sol). The scoping fixed
question ran once more on the finished tree for the owner's read of the longlist: task 67e2d89f,
23 options in 8 themes, saved as `experiments/longlist-final-2026-11-02-67e2d89f.json`
(the all-Sol longlist for comparison is task fa7e7194, 24 options in 8 themes). Judge-prompt
caveat: the free-text judge was written by the builder, not reviewed by the lead; the owner's
read, not the grades, carried the Group A and C decisions.

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
amended (S5). Live check: on the final NEET run (bedrock) the event stream carried `stage.started`
`{"stage": "ingest", "label": "Reading the full texts"}` at 08:06:50 and ticks with counts
(`"81 of 170 read, 89 fetched."`, `fetched` 89, `parsed` 81, `total` 170), saved in the session
scratchpad (`sse-final-neet.txt`). **N8 live:** `ingest.batch_handover` per batch on the final runs
(laptop, bedrock): NEET 89 documents, fetch 179 s, parse 89 s, idle gap 0.3 s; zonal 124, 196 s,
138 s, 0.02 s; obesity 151, 250 s, 250 s (overlapped a verify-fast gate), 0.01 s; the fixed-commit
NEET 129, 102 s, 228 s (overlapped a gate). The ingest component's wall clock on bedrock stays
8 to 11 minutes (NEET 637 s for 82 ingested against the baseline's 999 s for 73; zonal 485 s / 64
against 651 s / 53; obesity 675 s / 109 against 693 s / 83) because after fetch and parse the stage
embeds every chunk through Cohere on Bedrock with rate-limit sleeps: on this route embedding, not
parsing, dominates the stage (owner item; the contract's ingest-profile fact was parse-dominated).
On `openai-direct` the same NEET ingest took 188 s end to end (91 ingested).

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
carry no ids. No `acquire.py` change was needed. Live share on the fixed
questions (`source_kind` on the stored full-text snapshots): NEET 7 of 82 (bedrock) and 1 of 91
(direct) and 6 of 117 (fixed commit); zonal 0 of 64; obesity 36 of 109 (33%); scoping 0 of 8. So
the XML route carries a third of a health question's full texts and almost none of an
education or housing one, as the pmcid counts predicted. Chunk quality (headings and tables
against the PDF parse) was not read on the live runs; the three JATS fixtures carry the
structure checks.

## Final fixed-question set and the quality counts

**Synthesis outcome counts** from each run's `component.completed` record (claims written,
citations verified against the source text, citations that failed verification, chunk claims the
reader rejected, claims rejected for structure, section-writer tool calls):

| Set | Question | Sections | Claims | Citations verified | Citations unverified | Chunk claims rejected | Structural rejections | Tool calls |
|---|---|---|---|---|---|---|---|---|
| baseline d14d3f33 | NEET | 8 | 57 | 47 | 0 | 4 | 13 | 38 |
| baseline | zonal | 7 | 53 | 64 | 0 | 2 | 6 | 30 |
| baseline | obesity | 9 | 64 | 94 | 0 | 2 | 5 | 38 |
| baseline | scoping | 10 | 59 | 47 | 0 | 0 | 8 | 33 |
| model-only 7561a822 | NEET | 8 | 73 | 82 | 0 | 0 | 1 | 37 |
| model-only | zonal | 6 | 74 | 111 | 0 | 1 | 3 | 27 |
| model-only | obesity | 8 | 81 | 93 | 0 | 0 | 1 | 35 |
| model-only | scoping | 10 | 67 | 57 | 0 | 0 | 6 | 39 |
| final e90a7f36 | NEET | 8 | 102 | 127 | 0 | 0 | 1 | 39 |
| final | NEET (openai-direct) | 9 | 115 | 150 | 0 | 0 | 0 | 46 |
| final | zonal | 7 | 85 | 126 | 0 | 0 | 2 | 33 |
| final | obesity | 8 | 104 | 158 | 0 | 0 | 0 | 42 |
| final 12c31228 | NEET | 8 | 103 | 152 | 0 | 0 | 1 | 40 |
| final 12c31228 | NEET (openai-direct) | 8 | 114 | 137 | 0 | 0 | 0 | 44 |
| final 12c31228 | scoping (all Sol) | 10 | 55 | 36 | 0 | 0 | 7 | 42 |

The final writer (gpt-6.1-terra, `synthesise_section_v11`, five tools under `allowed_tools`)
writes about 1.8 times the claims of the baseline with about twice the verified citations, no
unverified citation on any run, structural rejections down from 5 to 13 to 0 to 2, and chunk
rejections down from 2 to 4 to 0. Standard depth has no extract stage, so no finding is cited.
These are counts, not a reading; the owner's read of the reports is the quality guard (O1).

**Cost per run on the fixed questions (O1, D1), session totals from `cost_per_run.py`, list
prices, `bedrock` unless marked.** The baseline median for Evidence search was $2.68 against the
$2 target.

| Question | Baseline d14d3f33 | Model-only 7561a822 | Final e90a7f36 (cache modes, pre-fix) | Final 12c31228 (breakpoint fix) | Change |
|---|---|---|---|---|---|
| NEET | $2.68 | $1.28 | $1.15 | $1.21 (117 full texts, embedding $0.36) | −55% |
| NEET on `openai-direct` | — | — | $0.97 | $0.85 | −12% from the fix alone |
| zonal pricing | $2.10 | $1.08 | $0.89 | — | −58% |
| childhood obesity | $3.01 | $1.32 | $1.14 | — | −62% |
| **Evidence search median** | **$2.68** | **$1.28** | **$1.14** | | **−57%, under the $2 target** |
| scoping (AI and the labour market) | $3.25 | $1.29 | — | $1.18 (all thirteen on Sol) | −64% | |
| scoping on the frontier pins 67bc0ac7 | | | | $1.04 (eleven steps moved down) | −68%; −12% against all-Sol |
| scoping on the finished tree 8d841e2d (pins, cache fix, both client timeouts at 60 s) | | | | $1.08, 24.6 min end to end | −67%; whole run 122 min → 24.6 min |

Where the change came from (NEET, bedrock): the model switch took $2.68 to $1.28 (synthesise
$1.43 to $0.70 on zonal; option profiles $1.08 to $0.14 on scoping); the caching phase took the
one-shot sites' 25% write surcharge off and gave the section turns 66 to 73% reads (NEET $1.28 to
$1.15 with a larger corpus); the breakpoint fix took a further 12% off the `openai-direct` run.
Embedding is now the largest non-model line on `bedrock` (21 to 30% of a run; Cohere on Bedrock,
priced as input); the remaining model spend is the section writer (18 to 28%) and the two
screening stages (12 to 18%). Run-to-run corpus size moves a session by ±$0.10 (NEET's two final
runs: 82 and 117 full texts).


## Prompt pass after the switch (owner, 2026-11-02; commit 9fe7ca2f)

The owner asked for the two measured prompt drifts to be worked now rather than deferred.
Report: `experiments/prompt-pass-2026-11-02.md`. Both passes replay the X1 and X4 stored inputs
with the system message swapped, on gpt-6-luna at `medium`.

**Grounding judge, `grounding_judge_v2` → `grounding_judge_v3` (shipped).** The reasoning-claim
rule now tests what a claim asserts as settled, not what it is about: a claim that states as
established something needing a citation (a fact or figure, a causal effect, a comparison, an
evaluation) is unsupported; a claim that visibly frames a question, a hypothesis or assumption to
check, a dispute between the sources, or a limit of the cited evidence stays tier_4 even when it
names the policy, place, population or outcome. On 119 stored calls (587 claims): reasoning
claims' agreement with the stored verdicts 62.1% → 78.8%, stricter flips 25 → 5, stored tier_4
kept 15 of 40 → 35 of 40; nine stored-unsupported reasoning claims now pass (hand-read: seven are
scope or assumption statements the spec means by tier_4, two hedged interpretations of cited
results); chunk-claim verdicts unchanged within noise (stricter flips 45 → 49, looser 6 → 4), so
the stricter chunk reading X1 judged correct is kept. Hash re-pinned; the version pin test
updated. Cost about $0.25.

**Interventions extractor (not shipped; stays `extract_interventions_v4`).** Three wordings on
the 60 X4 items: an "also an intervention" bullet over-extracts (15 extra `described` records);
folding the regulation, inspection and standard clause into the exclusion bullet with a tighter
'mentioned' cut the "covers no intervention" disagreements 4 → 2 and lifted name F1 0.825 →
0.893, but dropped role agreement 86.8% → 75.3% (roles are what the longlist reads); the clause
alone changed nothing that matters (4 disagreements, F1 0.837). On 60 items these sit inside the
model's own noise. Reverted to the incumbent wording; the two X4 shifts stay recorded for the
synthesis refinement task with a larger labelled set. Cost about $0.60.

## The test suite on every core (owner, 2026-11-02; commit c34ec5e7)

The owner asked why `make verify` takes 14 minutes (12.6 of them the backend suite, 3,884 tests
on one core, most of them against a real Postgres) and chose to fix it in this slice. Change:
`pytest-xdist` in the dev dependency group (an owner-approved dependency, outside the contract's
list); `tests/conftest.py` gives each xdist worker its own copy of the test database (the base
name plus the worker id, created fresh from the base database in autocommit mode, `DATABASE_URL`
rewritten for that process so every reader of the variable sees the copy, dropped when the worker
exits; a run without xdist keeps the plain database); `make test` and `make test-fast` pass
`-n auto`. CI runs the same `make verify`, so it inherits the change on its compose Postgres 16.
Result on this laptop (8 cores): the full backend suite in 400 s against 753 s serial, all 3,884
passed, worker databases dropped, no new warning kinds (the swig deprecation now prints once per
worker). The cut is 1.9x rather than 4x because the long tail (the real-document ingest tests and
the thread tests with poll deadlines) and database contention set the floor; a `--durations` read
would show the next lever. Gate: the full `make verify` below.

## Latency on the scoping path, and the stall fix (owner, 2026-11-02; commit 3b5456dd)

The owner asked why the scoping question still takes an hour when the expectation is a
shortlist inside 20 minutes. From the server logs (per-component wall clock) and Langfuse
(per-call latency):

| Part of the scoping run (fuller path, `bedrock`) | Baseline d14d3f33 (gpt-5.6) | All-Sol 12c31228 (GPT-6) |
|---|---|---|
| Evidence search half: acquire, screen, classify, ingest, synthesise, 11 option searches | 19 min | 18 min |
| `extract_interventions` | 3.5 min | 38.5 min |
| The thirteen longlist and option-profile calls | 72 min | 3.6 min |
| **Whole run** | **122 min** | **60 min** |

Two readings. First, the 15 to 20 minute expectation (`plan-as-object.md`) is for the rapid
path; `fixed_questions.py` answers the Task Agent's depth question with the fuller path (the plan
never reached ready otherwise), so no run in this build exercised the rapid path, and the baseline
on this path was two hours before any change. Second, the extractor is not slow per call: on
gpt-6-luna the median `extract:interventions` call is 5.3 s (baseline 4.8 s), but a tail of
requests sits at the provider until the client's 300 s timeout, is retried, and finishes in
seconds, so each one costs 600 s or more (max 621 s; the baseline's max was 17.6 s). With four
calls in flight each stall parked a quarter of the extractor for ten minutes; 211 calls that
would take about 5 minutes took 38. The pinned run was worse again (76 calls in 32 minutes, mean
89 s). These are the same stall waves the cache measurement (124 timed-out attempts) and the
frontier replay (900 s stalls) hit on GPT-6 calls on both routes; the cause is at the provider or
the transport and is outside this slice.

A count of calls over 120 s per call name (`experiments/stalled-calls-2026-11-02.txt`) shows the
stalls are not new and not the extractor's alone: the baseline NEET run on gpt-5.6 already had 12
of 170 classify calls hit the 180 s timeout and 2 of 15 judge calls; on the final runs screening
(4 of 117 full-text, 12 of 435 abstract on `openai-direct`), the grounding judge and the section
writer each show one to twelve stalled calls, every one capped by its client's timeout (about
120 s for screening, 180 s for classify). The rate is 1 to 3% of calls at every stage on both
models and both routes; the extractor's 23 of 211 (11%, p90 302 s) on the all-Sol scoping run is
the outlier, and with a 300 s timeout each stall cost the most. Knowledge candidate below.

**Owner's decision (2026-11-02):** (1) the three extraction clients' per-request timeout goes from
300 s to 60 s, so a stalled request is retried after a minute (the SDK's two retries kept);
(2) `MAX_CONCURRENT_EXTRACT` goes from 4 to 8; (3) after the stall-fix scoping run showed one
stalled folding call holding the option-profile stage for a quarter of an hour, the longlist
backend's client timeout goes from 300 s to 60 s as well (commit 8d841e2d); (4) the owner then
reviewed every model-client timeout against the healthy latencies measured today (classify and
screening calls take 1 to 6 s, agent turns 3 to 12 s, vetter and search-generation calls
seconds to 20 s) and moved seven more clients to 60 s (commit c8a3bfff): classify (was 180 s),
screening (120), the two finding vetters (180), the relevance annotator (180), the agent and
Task Agent clients (180) and search generation (120); the grounding judge (120 s, healthy tail
37 s), the section writer and summaries (120), chat (120), group clustering (120), characterise
and rerank (60) and embeddings (30) stay. All four are behaviour changes beyond the contract's
list, recorded here as owner-approved. Gates: the full
`make verify` runs below. The scoping question ran once more on the extractor fix (3b5456dd):
the extractor took 229 s against 2,311 s and 5,004 s on the two runs before it, but that run
then failed in its option-profile stage on a folding call that stalled on both component attempts
behind the longlist client's 300 s timeout, which is what prompted decision (3). The run on the
finished tree (8d841e2d, task 67e2d89f) completed in **24.6 minutes** end to end against 122 at
the baseline: Evidence search half 15.8 min (synthesise 361 s, eleven option searches), extractor
195 s, longlist 167 s, option profiles 77 s, constrain 66 s, theme 8 s, shortlist 12 s. On the
rapid path, with its smaller targets, the 20-minute expectation is now within reach; the fuller
path sits at 25 minutes, most of it the Evidence search half.

## Checks beyond the build

- Deterministic tests added in P0: usage buckets (21 in `test_usage.py`), cost script (8),
  call-site kwargs (62), loader shape tests (Phase 1).
- Live: probes (a), (b), (c) above; fixed-question baseline runs (step 9) below.

## End-to-end command

The live check at the contract's scope (the fixed questions only). Each set ran the server from a
detached worktree at the phase's commit so later edits could not reload it mid-run
(`scripts/fixed_questions.py` creates the tasks, answers the Task Agent unattended, and starts the
runs; the Langfuse session id is the task id):

```
# Server (one per route; the final set ran bedrock on :8000 and openai-direct on :8001):
cd ../policy_atlas-live/backend && git checkout --detach <commit> && \
  DATABASE_URL=... .venv/bin/alembic upgrade head && \
  POLICY_ATLAS_MODEL_ROUTE=bedrock PA_BACKEND_MODE=live \
  .venv/bin/uvicorn policy_atlas.api.app:create_app --factory --port 8000 \
  --env-file /Users/shabeer.rauf/repos/policy_atlas/backend/.env
# One question at a time as the executor frees up (RUN_EXECUTOR_MAX=2):
uv run --project backend python scripts/fixed_questions.py --only neet --base-url http://localhost:8000
# ... zonal, obesity, scoping; then the cost per session:
set -a; source backend/.env; set +a
python3 scripts/cost_per_run.py <task-id-prefix>
```

Sets run: baseline (d14d3f33), model-only (7561a822), final (e90a7f36, plus NEET on
`openai-direct`). Task ids and outputs are in the session scratchpad (`tasks-*.txt`,
`cost-*.txt`).

## Diff summary

Per-phase detail is in the phase sections above. Flagged deviations, resolved inside the
contract's vocabulary and listed here so the review sees them:

- **Re-pins without prompt-text change:** P0 two import-line re-pins; P2 A `section_prompt.py`
  (message shape and the X3 sentence); P2 B five files for import and `prompt_cache=` lines
  (`p2-commitB-repin-diffs.patch`); `finding_vetter.py` for its timeout line
  (`p-timeouts-repin-diffs.patch`). Deliberate prompt changes: P1 C `summary_prompts.py` (O3) and
  `grounding_judge.py` (v3, the owner's prompt pass).
- **Test margins widened:** the ingest scheduler's completion-order test sleeps its slow job 10 s,
  not 4; the option-search tests' two poll deadlines are 30 s, not 10 (that test failed twice under
  the eight-worker suite, once on an idle machine). Assertions unchanged in both.
- **Test pins that embed a model id or an effort** re-pinned at P1 B (nine) and P5 (two
  literal `"high"` asserts, two vetted extraction fingerprints).
- **P2 A:** `extra_tool_calls_ignored` is counted on the loop result and span metadata, not
  persisted as provenance. **P2 B:** two test adaptations (a test driver gained the system
  message the real call sends; two characterise tests read the system text through content
  parts); the unmeasured one-shot sites take `breakpoint` by shape.
- **P3:** `COMPATIBLE_RUBRIC_VERSIONS` treats `v2-hierarchy-v1` scores as current under
  `v2-hierarchy-v2` (the 1 to 5 scores did not change; without it every linked Evidence search
  task re-classifies every document).
- **P4:** the repair guard threshold (2,000 characters, ±300 margin) is a first value; the
  pass-rate check is on the final runs below.
- **P5:** `extract_annotate_relevance` stays at `high` (no stored call exists to replay); the
  thirteen frontier pins wait on the owner's side-by-side read.
- **P6:** the parent-side socket guard admits `AF_UNIX` only (a security-test change, see the
  phase section); N10 ships without reference extraction (left out by design).
- **Process:** phases were built by agents in parallel worktrees and serialised at the lead's
  gates (the plan's P9 "no parallel phases" was about the shared test database, which each
  agent avoided with its own `policy_atlas_aN_test`); the contract's per-phase fixed-question
  sets were collapsed to three (baseline, model-only, final) with P2 to P5 judged on replays
  and per-call-name tables as D1 allows; the `openai-direct` question after P1 was not run (it
  runs in the final set); the dev database was one migration behind when the final set
  started and `alembic upgrade head` was applied two minutes in, before any run reached
  appraisal.

## Review findings

Added after the review stack (step 7, a fresh conversation):

- **Contract verifier:**
- **`/code-review`:**
- **`/security-review`:**
- **Adversarial review:**
- **`/simplify`:**
- **`/okf validate`:**

## Rubric status

Checked against [rubric.md](rubric.md) on 2026-11-02 at the step-6 exit. ✓ holds; ◐ partly, with
the reason; ✗ not satisfied, with the reason; ☐ belongs to a later step.

1. ✓ Every phase the owner kept (P0 to P6) is built; the contract verifier at step 7 checks the item by item.
2. ◐ Full `make verify` green at the build-open baseline (Gate 2; Gate 1's one red was a load flake,
   re-run green), end of Phase 3 (Gate 4), end of Phase 6 (Gate 5) and the step-6 exit (Gate 6).
   The "after P1" full run did not happen at the P1 boundary (Gates A to C were `verify-fast` per
   the plan's gate map); the first full run containing P1 was Gate 4. `make prompt-guard` green at
   every commit.
3. ✓ Only the approved changes: the GPT-6 model set, the D7 migration (`152a234e2391`), the S5 stage
   key and payload, the Unrated label, the Europe PMC host. No production config, auth, CI or
   dependency change.
4. ✓ Generated frontend types regenerated (`drift-check` green); no secret or generated file edited by hand.
5. ✓ The v6 test and the rename-script tests deleted by the owner's tidy-up decision (P0, recorded);
   P2 B adapted two tests to the content-part system message; the N8 socket-guard test now admits
   `AF_UNIX` only (recorded as an adjudication item). Nothing skipped or weakened without a note.
6. ✓ This document, read from the saved results in the session scratchpad and the experiments folder.
7. ◐ Gaps and seams are listed in § Known unverified items and § Deferred work; the `deferred.md`
   entries themselves are written at step 8.
8. ☐ The review stack runs at step 7 in a fresh conversation.
9. ✓ N1: both buckets exclusive on every generation; a live generation priced the cache write
   (1.25× input); `cost_per_run.py` reproduces the baseline sessions (P0 fixture test).
10. ✓ D11: `section_prompt.py` pinned; `finding_vetter.py` pinned; the v6 module, switch, test and hash entry gone.
11. ✓ Tidy-ups with no behaviour change (Gate 2 green; imports updated; knowledge-note path fixed).
12. ✓ D2a quotas recorded (the owner ran the read-only command).
13. ✓ Both routes name gpt-6-luna, gpt-6.1-terra and gpt-6.1-sol; the rubric line was rewritten on
    the owner's instruction (2026-11-02) to carry the rulings: eleven former frontier steps on
    `standard` or `fast` per the replay, `longlist_shortlist` and `longlist_discover` on `frontier`.
14. ✓ D9 and D4: 56 steps, one per call site; the inventory and the pin test; the four effort
    constants deleted; `traced_parse` and `parse_structured` carry the effort.
15. ◐ Fixed questions ran after the model-only switch (costs and session ids recorded) and at the
    end (the final set, twice for NEET, four times for scoping as the fixes landed), with NEET on
    `openai-direct` twice; the set "after the prompt loop" was collapsed into the final set
    (recorded deviation). The owner read the final reports at the end of the build ("The reports
    look fine"); the intermediate reads were not taken separately.
16. ✓ O3 and N6: judge v2 and writer v3 refined together; 0 of 45 corrupted summaries pass; the 20
    adjudicated items re-run; first-attempt pass rate on the fixed questions not lower (above); X2
    retries carry the judge's reason; re-pins recorded.
17. ✓ X1 (flipped verdicts hand-read; no prompt change) and X4 (recorded; fold stays fast).
18. ✓ The breakpoint test re-run on both GPT-6 models and both routes before any caching code; the
    stop condition was not hit.
19. ✓ D3: the mode on `openai_kwargs`, `parse_structured` and `traced_parse`; the enumerating test;
    per-site modes chosen by measurement (`breakpoint` never worse than `off`), recorded; the
    explicit-mode gap found on the first final run and fixed (12c31228).
20. ◐ D8 and D10 built and tested; read and write shares per call name recorded before and after
    (section turns from 62% written to 66 to 73% read; one-shot sites from 86 to 100% written to 0%).
    The owner's read of the final reports: fine.
21. ✓ X3: the `lookup` tool offers only servable kinds; unservable lookups before = 2.22
    `characterisation_summary` per older scoping session (the contract's "4 to 7" overstated) and
    8, 5 and 9 `grouping_groups` on the three baseline Evidence search runs; after = 0 on every
    final session (eight sessions), with total lookups per run down from 16 to 24 to 2 to 9.
22. ◐ D7 and S1 to S3 built as listed (null score + `unrated`, check untouched, consistency check,
    steering filter, citable, "Unrated" to writer and reader, coverage bucket, rubric version bumped
    with a compatibility set, specs amended). The owner's read of the final reports: fine.
23. ✓ N5: windowing through the existing helper; repair input per call before and after recorded;
    pass rate not lower.
24. ✓ N7: classify and the two vetters at `medium` on replay evidence with tokens, reasoning tokens
    and latency recorded; the relevance annotator stays `high` (no stored call to replay); the
    eleven frontier downgrades on the owner's read.
25. ✓ Nothing to check (X5 dropped); the ledger-move entry is a step-8 item.
26. ◐ N8 built with the hand-over fixed; byte-identical output on the committed fixture corpus (test)
    and the saved local corpus (`ingest-scheduler-n8-verify.py`); timeout, safeguards and semaphore
    kept (tests); parse wall recorded locally. The staging measurement cannot run from this build
    (owner item after deploy).
27. ✓ N9 and S5: the stage appears with typed counts on a fixed-question run (event stream saved);
    the web-api spec amended.
28. ◐ N10 and S7: pmcids present in fresh acquisitions (16.7% of OpenAlex rows); the egress approval
    recorded; billion-laughs and external-entity tests; XML share on the fixed questions recorded
    (33% on obesity, 1 to 9% on NEET, 0 on zonal); chunk quality read on the three JATS fixtures only,
    not on the live runs.
29. ◐ O1: the final Evidence search median ($1.14 against the $2 target) and the scoping run on
    the finished tree ($1.08, 24.6 min) are recorded with the per-phase path; the owner read the
    final reports and the longlist: fine.

## Intent & assumptions

- The provider's default reasoning effort is `medium` (probe b), so writing `medium` where
  nothing was sent is a no-behaviour change.
- Cost comparisons use the session total (the contract's "cost per run" term: every model call
  in the session, embeddings and planning turns included); run totals are given alongside.
- The fixed questions ran unattended: `fixed_questions.py` answers the Task Agent with a fixed
  follow-up that names standard depth, where the contract's owner read assumed a person.
- `breakpoint` at an unmeasured one-shot site is assumed never worse than `auto` because every
  measured one-shot site showed it (the mechanism is the same: a stable system prompt, a user
  message that never repeats).
- The contract's X3 figure ("4 to 7 wasted lookups a session") was 2.22 on the nine older
  scoping baselines; the lever is real but smaller than the contract states.

## Known unverified items

- The owner read the final reports and the final longlist at the end of the build conversation
  (2026-11-02): "The reports look fine." Recorded as the O1 quality read for the final tree; the
  contract's intermediate reads (after P1 twice, P2, P3) were not taken separately.
- The `breakpoint` content part on the `bedrock-claude` route (unmeasured; no route selects it today).
- N8 on staging (2 CPUs): parse wall time measured on a laptop only.
- Chunk quality of the XML route on live documents (fixtures only).
- The frontier downgrades beyond the replay's 7 inputs per step: the pinned scoping run is the
  first whole-run exercise; `longlist_constrain` and `longlist_distinct` moved on a measure that
  could not separate configurations (no "breaks", no duplicate in any stored output).
- The 124 timed-out provider requests during the cache measurement (cause unknown; outside the slice).
- `make audit` (run because `pytest-xdist` was added) reported three CVEs on tornado 6.5.10, a
  transitive dev dependency of ipykernel locked before this task; the owner approved the bump and
  tornado moved to 6.6 (commit f08293c9; audit clean after it).

## Public safety

Experiment files live in the gitignored `experiments/` folder. The committed cost fixture holds
only ids, names, timestamps, models and token counts (test-enforced). No report text is quoted.

## Review handoff (step-7/8 inputs)

- **Owner's rulings in the build conversation (2026-11-02):** the owner read the list of
  decisions the lead made where the contract was silent (the session-total cost basis, unattended
  steering, three fixed-question sets instead of one per phase, the X3 figure, the repair template
  wording, `breakpoint` at unmeasured sites by shape, the Unrated side decisions, the 2,000-character
  repair threshold, the effort pins kept at `high` and `fast`, references left out of the JATS
  parse and the Europe PMC rate, the socket-guard test change, ignored extra tool calls not
  persisted, embedding dominating ingest on bedrock) and ratified every one; rubric item 13 was
  rewritten on the owner's instruction to carry the frontier rulings. The owner also asked for
  the two prompt passes (X1, X4) in this slice (the judge pass shipped, the extractor pass did not
  beat the incumbent, § Prompt pass), reviewed the client timeouts, chose the parallel test suite,
  approved the tornado bump, and read the final reports and the longlist at the end of the build
  ("The reports look fine"). Still open for the owner: N8 on staging after deploy.
- **Adjudication items:** the re-pins without prompt-text change (P0, P2 A, P2 B); the
  session-total comparison basis; the wire models moving into the pinned prompt module;
  unattended steering for the fixed questions; the frontier pins awaiting the owner's read (P5);
  the X3 contract figure (2.22 measured against "4 to 7"); the repair template wording (P2 A);
  N10 without reference extraction; `COMPATIBLE_RUBRIC_VERSIONS` (P3); the N8 socket-guard
  test change; `breakpoint` at the unmeasured one-shot sites by shape (P2 B); the per-phase
  fixed-question sets collapsed to three.
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
  - The walk executor's capacity check counts running walks in the database, not in the
    process: two API servers on one database share one `RUN_EXECUTOR_MAX`, so a second server
    on another route steals the first server's slot (the final set's three bedrock launches
    got HTTP 409 for this reason and were re-posted as slots freed).
  - A live worktree's server shares the dev database; a phase that adds a migration needs
    `alembic upgrade head` on that database before its live run (the final set started one
    migration behind and was upgraded two minutes in, before any run reached appraisal).
  - Replaying stored requests against the provider to measure caching needs an isolated
    prefix per block (a nonce in the system prompt): a timed-out request still completes on
    the server and stores its prompt, so the retry reads it and makes the mode look cheap.
  - Request hangs to the client timeout came in waves across every mode, route and site during
    the cache measurement (124 of about 1,000 attempts), completed server-side and were
    probably billed; a product client sees the same as a timeout plus a paid retry.
  - On the `bedrock` route the ingest stage's wall clock is dominated by Cohere embedding with
    rate-limit sleeps, not by parsing (final NEET: fetch 180 s, parse 89 s, then minutes of
    embedding); the N8 parse speed-up shows mostly on `openai-direct`, which embeds elsewhere.
  - One to three percent of model calls stall at the provider until the client timeout and then
    succeed on retry, on both routes and both model generations; the per-client timeout, not the
    model, sets what a stall costs (a 300 s timeout on a 5 s call parks a worker for ten minutes).
    Size timeouts to the call's real tail and keep the retry.
  - A test that polls with a fixed deadline sized for one core fails under a parallel suite; the
    fix is the deadline, not the assertion (two tests widened today, both after re-runs alone passed).
  - Two pytest-xdist suites on one Postgres collide, because their workers share the names
    gw0, gw1, ...: a per-worker database name needs the process id as well.
  - The healthy tail of a model call, not the model, should set a client's timeout: 60 s covered
    every healthy call measured today (3 to 37 s), and the stall rate of 1 to 3% then costs a minute
    a stall instead of three to fifteen.
  - `fixed_questions.py` posts `{}` to start a run; a task whose run got HTTP 409 keeps its
    approved plan, so the run can be re-posted later without re-planning.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) at step 8: the dependency-direction
knots the tidy-ups exposed (core importing a capability; scoping and API read models reaching
into each other); the Claude-direct search path reads only `cacheReadInputTokens` (no cache-write
capture; no route selects it); `baseline_prompt.py:14` comment still names `synthesis_backend.py`
as the home of the shared core (pinned file; fix at the next deliberate re-pin).
