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

Per-phase commits on `task/056-cost-latency`:

| Phase | Commit | Gate |
|---|---|---|
| 0 | d14d3f33 | 2 (full) |
| 1 A | 3a2b5ba3 | A (verify-fast) |
| 1 B | 7561a822 | B (verify-fast) |
| 1 C | (see git log) | C (verify-fast) |

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
