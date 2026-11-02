# Task contract: 056-cost-latency

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** approved, revision 2. Drafted 2026-10-29. **Contract approved (before
> planning): 2026-10-30 · Shabeer Rauf (owner).** Revision 2 (2026-10-30) folds the
> contract-stage adversarial review ([adversarial-review-contract.md](adversarial-review-contract.md),
> 24 findings; the Codex pass could not run, workspace spend cap, so a fresh Opus reasoner
> stood in) and the owner's two rulings on it: Unrated appraisal as a flag plus label, not a
> score of 0 (finding 1, route b); reasoning effort: medium is the default; steps that send
> nothing today are written as `medium` and changed only deliberately in P5 (finding 4). Gates approved at this contract:
> the model set (D2, D2a: runtime egress to GPT-6 models on both routes), the
> public-interface change for the reading stage (S5), the spec amendments S1 to S3 as
> revised, and the new Europe PMC host (S7) subject to a named approval at the plan gate.
> Plan-gate items decided 2026-11-01 (owner took the lead's recommendation on all seven; see
> [adversarial-review-plan.md](adversarial-review-plan.md)): X5 dropped; three more prompt
> pins approved; typed count fields on the progress tick (S5); the S3 label wording deviation
> recorded; the N8 batch hand-over fix in; Europe PMC egress approved (host `www.ebi.ac.uk`,
> data sent: a PubMed Central id only); the `components.md` § 9 repair wording accepted as
> spec item S9. **Plan approved (before implementation): 2026-11-02 · Shabeer Rauf (owner).** ADR:
> [0042](../../adr/0042-gpt6-switch-per-call-site-routing-and-caching.md), Accepted
> 2026-11-02 · Branch: `task/056-cost-latency`.

## Goal

Make a standard-depth Evidence search run cost under $2 end to end, and make Options
scoping cheaper through the same shared components. Latency improvements are taken where
they come free; they are not a goal. Reports change only where a decision below says so:
grey literature becomes citable with a visible Unrated label (D7), and the summary judge
becomes less strict about qualifier and clause-order nitpicks (O3). Nothing else about what
a report says is meant to move, and the owner's read of the fixed questions is the guard.

Measured baseline (token counts at list prices, 22 to 29 October 2026, saved in
`docs/research-and-development/synthesis-refinement/experiments/cost-baseline-per-session-2026-10-30.txt`;
the folder is gitignored, so every `experiments/` path below is relative to that folder):

| Run type | Runs | Median | Range | Sessions |
|---|---|---|---|---|
| ES standard depth | 6 | $2.12 | $1.60 to $4.88 | 0e8f8431 7c930ede d1055c42 c1737b8b e5ec049d c1b7ae0c |
| ES landscape depth | 5 | $0.87 | $0.67 to $1.19 | 1273de3d 291f222a d69acfc9 5e3eb2bb 0a0bdc29 |
| Options scoping | 9 | $3.46 | $2.09 to $6.26 | 4a374775 564a6e66 c5e023db 146b481e 1ce81c6a e2846e81 71ecedb0 258c15b4 6575e1a5 |

Four of the six standard runs still used gpt-5.4-mini for classify (an older checkout); the
two on the current route cost $1.96 and $3.80. Synthesise is 55 to 75% of a standard run.
In scoping the Sol calls are $1.16 to $3.88 per run, 40 to 60% of the run. Cache writes are
not in these numbers (not recorded until P0), so real cost is a few percent higher.

## Why this is safe to do now

- Every model name lives in one committed file since task 053 (`model_routes.toml`), so a
  model change is a reviewed one-line edit per tier.
- Langfuse prices every call on both routes since 2026-10-29: nine custom price rows for
  the GPT-5.6, GPT-6 and Cohere models, with patterns that accept the Bedrock names.
- GPT-6 models answer from Bedrock London and from OpenAI direct with the request shapes
  the code uses; probe output saved in `experiments/gpt6-capability-probe-2026-10-30.txt`.
- Prompt caching gives reads on both routes with no request change, but on Bedrock a
  section's first turn reads nothing and every long call writes at 1.25x; both are
  measured and both have a request-level fix (D8, D3).

## Deliverable

A pull request where:

1. Langfuse records cache-write and reasoning tokens on every generation, and a committed
   script reports cost per run by stage and by call name for a session (P0).
2. The three tiers in `model_routes.toml` name GPT-6 models on both routes, every model
   call site has its own route step, and reasoning effort is a per-step route value with
   today's behaviour preserved by the first commit (P1, D4, D9).
3. The judge and summariser prompts are refined together for the new writer model (O3).
4. The caching levers are built the way the GPT-6 re-test says (P2: D3, D8, D10).
5. Untyped documents are citable and shown as Unrated (P3, D7).
6. The repair input guard, the per-step effort settings, the ingest scheduler, the
   progress stage and the XML route are built in the order of the mapping table (P4 to P6).
7. `verification.md` holds, per phase, the measures named in D1 and the owner's read.

## Terms

| Term | Meaning |
|---|---|
| **Standard depth** | An Evidence search run at the `standard` analysis depth: acquire, screen (two stages), classify, appraise, ingest full text, characterise, select, synthesise (`runtime/task_plan.py` `ANALYSIS_DEPTH_TABLE`). Not the `standard` model tier. |
| **Cost per run** | The sum of every model call's cost inside one Langfuse session, from token counts and list prices, not from Langfuse's stored cost (wrong for rows before 2026-10-29). |
| **Route** | A named set of models in `backend/src/policy_atlas/model_routes.toml`. `openai-direct` calls OpenAI; `bedrock` calls Amazon Bedrock in London. Staging runs `bedrock`, production `openai-direct` (`infra/pa_config.json`). |
| **Model tier** | A role in the route file: `fast`, `standard`, `frontier`. After D2 the `frontier` tier is gpt-6.1-sol at `low` and serves the thirteen Options scoping call sites until replays justify moving each one down. |
| **Route step** | One named model call site in the route file's `[steps]` table. After D9 every call site has one. Distinct from a pipeline stage (acquire, screen, …) and from a task-cycle step (contract, plan, …). |
| **Prompt cache** | The provider keeps a prompt prefix for 30 minutes so a later call with the same prefix pays the cached-read price for those tokens: 10% of input on GPT-5.6, 5% on gpt-6.1-terra and gpt-6.1-sol, 10% on gpt-6-luna (see § Facts, prices). On GPT-5.6 and later the provider also charges 1.25x input to store the prefix, on every call over 1,024 tokens whose prefix is not already stored. Entries are stored at breakpoints; the default places one at the end of each request. |
| **One-shot call** | A call whose whole prompt never repeats. Many "one-shot" sites still share a system prompt over 1,024 tokens, so they may do better with a breakpoint after it than with caching off (finding 6, D3). |
| **Reasoning effort** | The request knob `reasoning_effort`. Terra-class and Luna models accept `none`; Sol-class models refuse it. Where the code sends nothing, the provider default applies (medium on these models). Today only three call sites send it (D4). |
| **Function tools** | The request shape where the model calls named tools: the section writer, the repair call and the chat loop. Every other site uses structured output (`response_format`). |
| **Prompt hash guard** | `make prompt-guard`; every prompt module and the files in `EXTRA_FILES` are pinned by hash in `scripts/prompt_hashes.json`. A pin is name-based (`*prompt*`) plus the explicit list; `synthesis_backend.py` is not pinned today (P0 fixes this by moving its prompt text out, D11). |
| **Fixed questions** | Three Evidence search questions at standard depth and one Options scoping question (O5), run fresh as new tasks before P1, after the model-only switch, after the prompt loops, and after each later phase. |
| **Unrated** | The appraisal state of a screened-in document the classifier typed as `Unknown / Insufficient information` or `Other (Non-evidence documents)`. After D7 it has an appraisal row with no score and the label Unrated, is citable, and is shown as Unrated wherever appraisal is shown. |
| **Decided / Leaning / Open** | Decided is settled. Leaning is the recommended choice unless the owner objects. Open means the owner chooses at the named gate. |

## Facts we rely on

Probed or measured 2026-10-29 and 2026-10-30; file names are under the experiments folder.

| Fact | Source | Consequence |
|---|---|---|
| Baseline cost per run as in § Goal. | `cost-baseline-per-session-2026-10-30.txt`, `costbase.py` | Target sits at today's median; the spread is the problem. |
| GPT-6 on Bedrock London (`global.openai.` prefix) and OpenAI direct: gpt-6.1-terra, gpt-6-luna and gpt-6-sol accept `reasoning_effort = "none"`, function tools and structured output; gpt-6.1-sol and gpt-6-astra refuse `none` and refuse function tools on Chat Completions, structured output works at `low`. | `gpt6-capability-probe-2026-10-30.txt` | D2's model set. |
| List prices per million tokens, input / cached read / output, from OpenAI's pricing page as read 2026-10-27 and the Langfuse default price file (`worker/src/constants/default-model-prices.json` at commit 0c531be): gpt-5.6-luna 0.20 / 0.02 / 1.20; gpt-5.6-terra 2.00 / 0.20 / 12.00; gpt-5.6-sol 4.00 / 0.40 / 20.00; gpt-6-luna 0.10 / 0.01 / 0.50; gpt-6.1-terra 1.00 / 0.05 / 5.00; gpt-6.1-sol 2.00 / 0.10 / 10.00. Bedrock states it matches first-party rates (AWS blog, 2026-07-30). | Langfuse custom rows created 2026-10-29 (ids `cmvte6l*`) | Equal tokens, about half the cost. |
| Both routes write the cache at 1.25x on every call over 1,024 tokens that misses; reads need no breakpoint; `prompt_cache_options = {"mode": "explicit"}` with no breakpoints gives zero writes. Measured on GPT-5.6 only. | `cache_probe*.py` outputs in the seed's `scripts/`; `cache-breakpoint-test.md` | P2 re-measures on GPT-6 before building (finding 5). |
| Cache reads land only at the end of an earlier request; an explicit breakpoint on the run message makes a second section's first turn read tools + system + run (7.8k of 8.6k tokens) on both routes; a repair request that starts with the section's first turn reads it too, if tools and `parallel_tool_calls` are identical. | `cache-breakpoint-test.md`, `repair-cache-miss.md` | D8, D10. |
| Input token shares, 1,000 generations 22 to 25 October: section_turn 23% (44% cached), screen:abstract 12% (85%), judge:grounding 11% (0%), screen:full 9% (0%), extract 17% (20 to 29%), repair 7% (10%), classify 5% (0%), judge_summary 3% (4%). | Langfuse query in the seed (`cost-latency-task-seed.md` § Prompt caching) | D3's site list. |
| Classify on gpt-6-luna at `medium` holds agreement with `high` inside run-to-run noise and is 19% cheaper and 22% faster; `none` and `low` change about 20 of 90 labels in one direction. | `classify-effort-sweep.md` | N7. |
| Screen on gpt-6-luna: recall 0.924 against 0.924 to 0.938 on task 051's 288-document labelled set; classify agreement inside noise. | `screen-labelled-replay.md`, `fast-tier-swap.md` | D2 safe for the `fast` tier. |
| Summary judge: no cheaper model let a corrupted summary through; gpt-6.1-terra rejected 20 of 45 summaries the old judge passed; adjudication found 7 real faults, 9 defensible, 4 over-strict; 12 of 20 were gaps reworded as facts. | `summary-judge-tiering.md`, `summary-judge-adjudication.md` | O3. |
| Pointer citations cut writer output 43% with support held; not this slice. | `pointer-citation-prototype.md` | Synthesis refinement task. |
| Repair input: chunk text is 38% of it; 28 of 118 chunks over 10,000 characters carry 82% of chunk text; windowing all saves $0.02 to $0.05 a run with quality risk. | `repair-payload-share.md` | N5 as a guard only. |
| Ingest: fetch under 1%, parse 89 to 92% of the stage; any-free-slot draining plus a preloaded forkserver cut parse wall 49 to 56% on a laptop with byte-identical output; staging has 2 CPUs. | `ingest-profile.md`, `ingest-scheduler-prototype.md` | N8. |
| Full text: 1,625 of 1,978 local full texts came from PDF, 353 from HTML; no PubMed Central id is stored; Europe PMC returned XML for 15 of 16 ids; HTML alone covers 24% of parse time and loses headings as parsed today. | `html-vs-pdf.md`; local DB query 2026-10-30 | N10 build order. |
| `ingest_full_text` has no stage key; `StageKey` is pinned vocabulary in `api/contract/sse.py`, rendered by `frontend/src/views/workspace/runProgress.ts`. | `api/stage_vocabulary.py` | N9, S5. |
| The appraisal score column has `CHECK quality_score BETWEEN 1 AND 5` (`core/schema.py`, migration `d6a1c4e9b2f7`); the strength labels are a closed Literal in `api/routers/read_models.py` mirrored in the generated frontend types; `select.py` and `steering_triggers.py` read the score. | finding 1 | D7 is a flag plus label, never a score. |
| Only `chat_backend_openai.py`, `synthesis_backend.py` (`_synthesis_openai_kwargs`) and the case-studies call read `route().reasoning_effort_for`; `traced_parse` and `parse_structured` carry no effort, so every other step runs at the provider default. Four modules hard-code `"high"` (classify, two finding vetters, relevance annotator). | finding 4; `core/openai_client.py`, `core/tracing.py` | D4 inventory. |
| `openai_kwargs` is used by chat, synthesis, finding_vetter, relevance_annotator and classify; grounding judge, mrs_note, report intro, screening, group clustering and rerank call `.parse` or `parse_structured` directly; the summary judge shares the writer's kwargs. | finding 3 | D3 plumbing. |
| Section turns send `parallel_tool_calls = not force_emit`, so the forced final turn differs from earlier turns and misses the cache today. | finding 13; `synthesis_backend.py` | D10. |
| The section seed's ledger is built from claims judged and repaired so far; a section's claims join it only after its judge and repair. | finding 12; `synthesise.py` | X5 is limited. |

## Read first

- `docs/research-and-development/synthesis-refinement/cost-latency-task-seed.md` and the
  experiments folder beside it (gitignored): every measurement this contract cites.
- [ADR 0041](../../adr/0041-bedrock-inference-route-and-model-route-file.md) (the one
  titled "Inference moves to Amazon Bedrock; models are named in a committed route file").
- [system/prompting.md](../../specs/system/prompting.md) rule 12 and § Provider-specific.
- The runtime-egress gate in the [task-cycle spine](../../../.claude/skills/task-cycle/SKILL.md)
  § Stop conditions.
- [capabilities/evidence-search/components.md](../../specs/capabilities/evidence-search/components.md)
  § 3 classify (Non-evidence excludes from select and extract), § 4 appraise and full-text
  ingestion, § 9 synthesise (repair as a micro-call, never a transcript resend).
- [capabilities/evidence-search/provenance.md](../../specs/capabilities/evidence-search/provenance.md)
  § citable bar.
- [deferred.md](../../deferred.md) § Synthesise, § Synthesis optimisation, § System-level
  cost and latency, § Execution ("Langfuse costs ignore prompt-cache hits", "Prompt-hash
  guard is name-based").
- Code: `core/openai_client.py`, `core/usage.py`, `core/tracing.py` (`traced_parse`),
  `core/model_routes.py`, `model_routes.toml`, `evidence_search/synthesis/synthesis_backend.py`,
  `synthesise.py`, `synthesis_tools.py`, `grounding_judge.py`, `summary_prompts.py`,
  `evidence_search/assess/appraise.py`, `classify_prompt.py`, `evidence_search/sourcing/ingest_full_text.py`,
  `fetch_live.py`, `search_live.py`, `api/stage_vocabulary.py`, `api/contract/sse.py`,
  `scripts/prompt_hash_guard.py`.

## Numbered needs

| # | Need | Where it lives today | Measure |
|---|---|---|---|
| N1 | Record cache-write and reasoning tokens as exclusive Langfuse usage buckets, and commit a cost-per-run script. | `core/usage.py` builds `usage_details` in the OpenAI shape and drops `prompt_tokens_details.cache_write_tokens` and `completion_tokens_details.reasoning_tokens`. `usage_totals` is also persisted in component summaries. | Keys: `input_cache_write_tokens` (subtracted from `input`) and `output_reasoning_tokens` (subtracted from `output`), matching the custom price rows' `cache_write_tokens` and `output_reasoning_tokens` prices; one live generation checked in Langfuse shows the buckets and a non-zero write price. The stored payload gains `cache_write` and `reasoning` fields. Script: `scripts/cost_per_run.py`, reproducing the baseline table for the sessions listed in § Goal. |
| N2 | Move the three tiers to GPT-6 on both routes. | `model_routes.toml` tiers and `knobs.reasoning_effort`. | Fixed questions before and after the model-only switch (whole-run cost, owner's read); then again after the prompt loops. |
| N3 | Cut cache-write waste. Per site, choose between a breakpoint after the stable prefix and caching off, by measurement. | Sites with 0% reads: judge:grounding, screen:full, classify, judge_summary, group assign, finding vetters, case studies, rerank. Their system prompts are often over 1,024 tokens and repeat per run (finding 6). | Per site: a few calls each way on GPT-6; the cheaper of (read at 5 to 10%) vs (no write) wins; recorded cache read and write shares per call name before and after. |
| N4 | Make untyped documents citable and visibly Unrated (D7). | Appraise skips `Unknown` and `Other (Non-evidence)`; `synthesise.py` rejects their citations (`unappraised_doc_citation`), which triggers repair. The writer already sees `appraisal_label` and `evidence_type` per chunk. | Citations to Unrated documents accepted and labelled; `unappraised_doc_citation` count on the fixed questions; owner's read. |
| N5 | Repair input guard: send chunks over the oversized threshold as a window around the quote. | `build_section_repair_messages` sends whole dependency chunks; `OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS` and the window rule exist in `synthesis_tools.py`; deferred.md records "repair resends oversized chunks un-windowed". | Repair input tokens per call before and after; no change in repair pass rate. |
| N6 | Summary judge and summariser prompts refined together for gpt-6.1-terra (O3). | `summary_prompts.py` (judge, block summary, artefact summary); `judge_summary` shares the writer's model. | Zero corrupted summaries pass on the 90-item set; the 20 adjudicated items re-run; first-attempt pass rate on the fixed questions up. |
| N7 | Reasoning effort per step, set deliberately, with `medium` as the default (owner). | See D4. Classify measured: `medium` on gpt-6-luna. | Per-step tokens, reasoning tokens and latency before and after; labels or outputs within run-to-run noise. |
| N8 | Ingest: any-free-slot draining and preloaded workers; keep timeouts and safeguards. | `_run_parse_jobs`, `_drain_parse_job`, `_worker_entry`; the shared ingest semaphore from task 045; the per-document timeout and large-payload safeguards. | Parse wall time on the fixed questions; output byte-identical on a committed fixture corpus and on the saved local corpus; the batch hand-over in `ingest_full_text_sources` measured and fixed in the same phase (owner, 2026-11-01); staging measurement recorded. |
| N9 | A progress stage for full-text reading with counts from the document store (S5). | No stage key for `ingest_full_text`. | The stage appears with fetched and parsed counts on a fixed-question run. |
| N10 | Prefer structured non-PDF full text: store PubMed Central ids, add a Europe PMC XML path, HTML with headings only if a share remains (S7). | `candidate_urls` is PDF first; HTML parse is plain text. | Share of documents taking the XML route on the fixed questions; chunk headings and tables at least as good as PDF. |

## Decisions

**D1. Measure from token counts, on fixed questions; small levers by call name. Decided.**
Cost per run is computed by `scripts/cost_per_run.py` from Langfuse token counts and the
list prices, keyed by session. The fixed questions (O5) run before P1, after the model-only
switch, after the prompt loops, and after each later phase; one of them also runs on
`openai-direct` after P1 and after P2, since production runs there. Whole-run cost judges
P1 and the final comparison. P2 to P5 are judged on tokens and cost per call name for the
sites each lever touches, because the run-to-run spread ($1.60 to $4.88) hides a 3 to 5%
lever (finding 11). The owner reads the fixed-question reports after P1, P2 and P3.

**D2. The model set. Decided (owner, 2026-10-29 and 2026-10-30).** Both routes:
`fast` = gpt-6-luna (Bedrock `global.openai.gpt-6-luna`), `standard` = gpt-6.1-terra,
`frontier` = gpt-6.1-sol at `low` (the lowest effort it accepts). Effort is per step (D4);
the model-keyed knob table is deleted. The tool-bearing Terra steps carry `none`. **The
thirteen Options scoping call sites on the frontier tier today stay on `frontier` at the
switch** (owner, 2026-11-01, replacing the earlier lean to move them all to `standard`):
gpt-6.1-sol at `low` is their like-for-like replacement, all thirteen use structured output,
and each is moved down to `standard` or `fast` only after a small-scale replay on its own
stored inputs shows agreement within the run-to-run noise floor at several effort levels
(`experiments/frontier-steps-replay.md`, started 2026-11-01; results carried into the plan
and pinned per step in P5). The `bedrock-claude` route follows `bedrock`. No prompt text changes
in the switch itself (same model family, prompting rule 12 does not fire). Data residency
is unchanged: the same `global.` profiles as today.

**D2a. Before P1. Decided.** Confirm Bedrock London quotas for the three GPT-6 ids and
record them in `verification.md`.

**D3. Caching mode is set per call site through the real plumbing. Decided, with the
mode chosen per site by measurement (N3).** `openai_kwargs` gains `prompt_cache: Literal["auto", "off", "breakpoint"]`;
`parse_structured` and `traced_parse` gain the same argument and pass it through, because
the grounding judge, mrs_note, the report intro, screening, group clustering and rerank do
not use `openai_kwargs` today (finding 3). "off" sends `extra_body = {"prompt_cache_options": {"mode": "explicit"}}`
with no breakpoints; "breakpoint" marks the end of the stable prefix as a text content part
with `prompt_cache_breakpoint = {"mode": "explicit"}`. The summary judge gets its own kwargs
(D9 gives it its own step). A test lists every model call site with its caching mode.

**D4. Reasoning effort lives in the route file, per step; the first commit changes no
behaviour. Decided (owner, 2026-10-29: "move hard-coded effort into the model configs";
finding 4 folded 2026-10-30).** Today the knob is keyed by model id and reaches three call
sites; `traced_parse` and `parse_structured` carry no effort, so the scoping judgment steps,
the task agents and the agent run at the provider default; classify, the two finding vetters
and the relevance annotator hard-code `"high"`. After this slice: the `[routes.<name>.steps]`
exception table gains a table form with `model` and `reasoning_effort` keys (a bare tier or
model id still works); `traced_parse` and `parse_structured` gain an effort argument; the
four constants are deleted; and the inventory records today's effective value per step.
**The default is `medium` (owner, 2026-10-30: "reasoning at medium by default is right").**
Steps that send nothing today run at the provider default, which is medium, so the route
file writes `medium` for them explicitly and the first commit changes no behaviour (a test
pins every step's resolved effort to today's effective value). The only departures are the
ones a measurement or a provider rule requires: classify moves from `high` to `medium`
(measured); the tool-bearing Terra sites stay at `none` (the provider refuses function
tools otherwise); the two finding vetters and the relevance annotator keep `high` until P5
measures them. P5 may lower a step below medium only on its replay set or the fixed
questions. Sending `none` where medium runs today is a behaviour change and is treated as one.

**D5. Phase map. Decided.** The order is owner-decided (switch first); the table maps every
kept item to a phase and the files it touches.

| Phase | Items | Files touched |
|---|---|---|
| P0 instrument and tidy | N1; D11 (prompt text out of `synthesis_backend.py`, hash guard include list); the tidy-ups in § Tidy-ups; D2a | `core/usage.py`, `core/tracing.py`, `scripts/cost_per_run.py`, `synthesis/section_prompt.py` (new), `scripts/prompt_hash_guard.py`, `scripts/prompt_hashes.json`, the moves and deletions listed |
| P1 switch | N2, D2, D9, D4 (inventory and plumbing, no behaviour change), O3 and N6 (judge and summariser prompt loop), X1, X2, X4; fixed questions after the model-only switch and after the prompt loop | `model_routes.toml`, `core/model_routes.py`, `core/openai_client.py`, `core/tracing.py`, every module with a `route().model_for` lookup (inventory in the plan), `summary_prompts.py`, `grounding_judge.py` (if X1's read asks), the four effort-constant modules |
| P2 caching | N3 with the GPT-6 re-test first; D3; D8; D10; X3 | `core/openai_client.py`, `synthesis/section_prompt.py`, `synthesis_backend.py`, `synthesis_tools.py` (lookup kinds), the one-shot sites |
| P3 unrated | N4, D7 (S1 to S3 as revised) | `assess/appraise.py`, `core/schema.py` (nullable flag column: see D7), a migration, `api/routers/read_models.py` label, `synthesise.py`, frontend label copy |
| P4 repair guard | N5 | `synthesis_backend.py`, `synthesis_tools.py` |
| P5 effort | N7 | `model_routes.toml` |
| P6 ingest, progress, XML | N8; N9 and S5; N10 and S7 | `ingest_full_text.py`, `fetch_live.py`, `search_live.py` (OpenAlex `ids`), `api/stage_vocabulary.py`, `api/contract/sse.py`, `frontend/src/views/workspace/runProgress.ts`, a JATS parser module |

P6 is last and the first to cut if budget runs short; queued parsing (the next task)
supersedes most of N8 on staging.

**D6. What this slice does not touch. Decided.** No emit-schema or pointer-citation
rewrite (synthesis refinement task). No Flex or batch tiers. No stripping of Bedrock
prefixes in tracing. No Langfuse version change. No cross-task reuse of parsed text (S6
out). No faster parse profile (S8 out). No spec edits beyond S1 to S3, S5 and S7 as the
owner accepted them. No change to timeouts, pool sizes or fetch threads.

**D7. Unrated appraisal as a flag plus label. Decided (owner, 2026-10-30, route b after
finding 1).** Documents the classifier typed as `Unknown / Insufficient information` or
`Other (Non-evidence documents)` get an appraisal row with `quality_score` null and a new
boolean `unrated = true` (a nullable score needs the `CHECK` to allow null; the 1 to 5 rule
stays for scored rows; one migration). `select.py` and `steering_triggers.py` are unchanged
because they read the score, which stays null, exactly as today for these documents. The
per-run rubric override is unchanged. The citation check accepts a chunk whose document has
an appraisal row, so Unrated documents are citable; `unappraised_doc_citation` stays the
backstop for rows a failed appraise never wrote. The writer sees `appraisal_label` =
"Unrated" beside the `evidence_type`. The reader sees "Unrated" wherever appraisal labels
appear: the strength vocabulary (`api/routers/read_models.py`, the generated frontend
types and the copy at the places finding 1 lists) gains the one label. Grounding verdicts
are untouched. Coverage counts by tier include Unrated as its own bucket. No prompt text
changes unless the owner's read shows over-trust of unrated sources; then one sentence, as
a recorded re-pin.

- **S1 (spec).** `components.md` § 4: "Non-evidence and Unknown are skipped-and-counted"
  becomes "appraised as Unrated (no score), citable, and counted"; § 3: `Non-evidence`
  still excludes from select and extract; `provenance.md` and `provenance-grounding.md`
  list Unrated where tiers are listed.
- **S2 (spec and words).** The citable bar treats Unrated as below bar for pattern and
  coverage counting; the reader-facing word is "Unrated"; the spec's internal term "below
  policy" is not surfaced. Grounding is the judge's verdict alone.
- **S3 (code).** The flag column, the migration (drop NOT NULL on the score, add the
  consistency check; the 1 to 5 check is untouched because a CHECK passes on NULL), a
  separate `UNRATED_LABEL = "Unrated"` beside `SCORE_LABELS` (which maps 1 to 5 and cannot
  hold a null key; wording deviation recorded, owner 2026-11-01), the label in the API
  vocabulary, the rubric-domain test extended to the two types, and
  `DEFAULT_RUBRIC_VERSION` bumped. Readers that compare `quality_score` filter nulls
  (`steering_triggers.py`) or already treat None as missing (`select.py`); tests pin both.

**D8. Explicit cache breakpoint in the section writer. Decided; verified on GPT-5.6, to
be re-verified on GPT-6 at the start of P2.** The run message becomes a text content part
carrying `prompt_cache_breakpoint = {"mode": "explicit"}`; `prompt_cache_options` stays
unset. Measured on GPT-5.6: a second section's first turn reads about 7.8k of 8.6k tokens
on both routes. The prompt text is unchanged; the message shape changes (`section_prompt.py`
re-pinned).

**D9. One route step per model call site. Decided (owner, 2026-10-29).** The `[steps]`
table lists every named model call once (synthesis splits into section turns and repair
sharing one step, planning, block and artefact summary, summary judge, key findings;
`longlist_judgment` splits into its named calls; `screen` into stage 1 and stage 2), each
with a default tier and, with D4, its own effort. Tiers stay. Section turns and repair share
a step by convention (D10); so do the screen vote's two calls. The plan carries the full
inventory (module, call name, step, default tier, effort today). A test pins the resolved
model and effort for every step on the committed routes against today's values.

**D10. The repair request starts with the section's first turn. Decided (owner,
2026-10-30, as S4); verified on GPT-5.6, re-verified in P2.** Section turns and the repair
send the same five tools in the same order (four section tools plus `emit_repairs`), the
same system message, the run message with the breakpoint, and the section task message.
Section turns use `tool_choice = {"type": "allowed_tools", "allowed_tools": {"mode":
"required", "tools": [the four]}}`; the repair appends one user message and forces
`emit_repairs`. `parallel_tool_calls` is `True` on every section turn, including the forced
final turn (today it is `not force_emit`, so the final turn misses the cache), and on the
repair; the forced turn gets a check that rejects more than one tool call. Both requests
come from one builder in `section_prompt.py` (byte-identical prefix pinned by a test). The
section-turn and repair surfaces both get a version bump and the owner's read.

**D11. The section writer's prompt text moves to `synthesis/section_prompt.py`. Decided
(finding 7).** The system prompt, run and task templates, repair template and tool
descriptions move out of `synthesis_backend.py` into a module the hash guard picks up by
name; `finding_vetter.py` joins `EXTRA_FILES`. Code-only edits in pinned prompt modules
(the `route().model_for` and effort lines for D4 and D9) are expected re-pins, listed in §
Prompt hashes with their diffs.

## Owner decisions (2026-10-29 and 2026-10-30)

- **O1.** Target: median standard-depth run under $2; a broad target, lower is better.
- **O2 (revised 2026-11-01).** The thirteen frontier call sites move to gpt-6.1-sol at
  `low` at the switch (like for like) and are downgraded per step only on replay evidence
  at several effort levels; the owner reads side-by-side samples before any downgrade is
  pinned. (Their effort today is "not sent", D4.)
- **O3.** Judge prompt and the two summariser prompts refined together as one loop for
  gpt-6.1-terra, aiming at a judge that rejects only summaries that would mislead; the
  retry carries the judge's reason (X2). Replay set: the 90 items and the 20 adjudicated.
- **O4.** Ingest latency work in this slice, last.
- **O5.** Fixed questions: "What interventions reduce the number of young people aged 16
  to 24 who are not in education, employment or training (NEET) in England?"; "What is the
  effect of zonal electricity pricing on energy bills and energy security?"; "What works
  to reduce childhood obesity?"; Options scoping: "How do we reduce the potential economic
  disruption to the labour market caused by the rise in AI?". Run fresh as new tasks.
- **S5 (public interface).** A `StageKey` for full-text reading ("Reading the full texts")
  in `api/contract/sse.py` and the web-api spec; the tick frame gains typed optional
  `fetched`, `parsed` and `total` count fields (owner, 2026-11-01), filled from the document
  store's statuses; and the frontend case in `runProgress.ts`.
- **S6.** Out. **S7.** In: XML first. Egress approved 2026-11-01: host `www.ebi.ac.uk` (Europe PMC
  REST `fullTextXML`), data sent a PubMed Central id only. XML parsed with Python 3.12's
  expat (amplification limits, no external entity fetching), `defusedxml` only if a test
  shows a need, as an approved dependency. **S9 (spec, owner 2026-11-01).** `components.md`
  § 9: "repair as a dependency-complete id-carrying micro-call (never a transcript resend)"
  becomes "repair as a dependency-complete id-carrying call that starts with the section's
  own first-turn request so it reads the section's prompt cache, never a resend of the tool
  transcript". **S8.** Out.
- **X1.** Grounding judge replay on gpt-6-luna before P1 ships, with prompt refinement if
  the read asks. **X2.** In O3. **X3.** The section writer's `lookup` tool lists only the
  kinds the run can serve (4 to 7 wasted `characterisation_summary` calls per scoping
  baseline). **X4.** Replay the 046 tuning set for `extract_interventions` and the
  option-profile folding calls on gpt-6-luna; prompt work only if it fails (fold stays on
  `standard` by O2 unless D9's split moves it). **X5.** Dropped (owner, 2026-11-01): the
  ledger is sent in the section task message from the first turn and there is no separate
  write turn, so the overlap needs a prompt-shape change; it goes to the synthesis
  refinement task. **X6, X7.** Out. **X8.** Gather/writer split
  moved to the synthesis refinement task.

## Tidy-ups folded into P0 (owner, 2026-10-30)

Delete `synthesis/synthesis_prompts_v6.py`, its `prompt_variant` switch, the one test and
its hash entry. Move `evidence_search/clustering_engine.py` to `core/clustering_engine.py`
(test to `tests/core/`, fix the path in `docs/knowledge/two-stage-clustering-closes-partition-cliff.md`).
Move `options_scoping/longlist/longlist_backend.py` to `options_scoping/scoping_backend.py`
and `options_scoping/longlist/lever_types.py` to `options_scoping/option_profile/lever_types.py`.
Rename `tests/evidence_search/sourcing/test_ingest.py` to `test_ingest_upload.py`,
`tests/options_scoping/test_longlist_coverage_046.py` to `test_coverage.py`,
`extract/extract_interventions_prompt.py` to `interventions_prompt.py`,
`options_scoping/theme/longlist_theme_prompt.py` to `theme_prompt.py`. Delete
`scripts/rename_038.py`, `rename_044.py`, `rename_engine.py` with their three tests, and
`scripts/evals/search/experiments/probe_051.py`. Rename `api/routers/_access.py` and
`_common.py` to public names; settle the `readmodels` / `read_models` and `checkin_read` /
`check_ins` spelling on one form. Fix two stale docstrings (`screening_backend.py`,
`options_scoping/model_calls.py`). The eval-only `V2SearchGenerationBackend` stays. No
behaviour change; `make verify` green is the whole check. The dependency-direction knots
(core importing a capability; scoping and API read models reaching into each other) go to
`docs/deferred.md`.

## Research and deferred-log coverage

The cost research report's nine levers and the deferred log's entries are mapped in
`experiments/deferred-sweep-056.md` and the earlier revision of this contract (git history);
the kept items are the X series above. Close-out updates the log: the "Langfuse costs
ignore prompt-cache hits" entry (read half fixed 2026-09-18, write half by N1; a new entry
for deleting the custom GPT price rows when Langfuse is upgraded); the Bedrock routes
entry's pricing line; the Unknown-resolution, rubric-version, counting, unappraised-chunk
and citable-bar entries for D7; the repair "micro-call" wording in `components.md` § 9 for
D10 (an owner spec item at the plan gate); the cross-task snapshot entry for S6; and an
in-or-out line for every entry in § System-level cost and latency.

## Scope / Out of scope

- **In:** `core/usage.py`, `core/tracing.py`, `core/openai_client.py`, `core/model_routes.py`,
  `model_routes.toml`, `core/schema.py` and one migration (D7 flag), `scripts/cost_per_run.py`,
  `scripts/prompt_hash_guard.py` and `prompt_hashes.json`, every module with a model call
  (inventory in the plan), `evidence_search/synthesis/*` (new `section_prompt.py`,
  `synthesis_backend.py`, `synthesise.py`, `synthesis_tools.py`, `summary_prompts.py`,
  `grounding_judge.py`), `evidence_search/assess/appraise.py` and `classify_prompt.py`,
  `evidence_search/sourcing/ingest_full_text.py`, `fetch_live.py`, `search_live.py`, a new
  JATS parser module, `api/stage_vocabulary.py`, `api/contract/sse.py`,
  `api/routers/read_models.py` (one label), the frontend progress case and appraisal label
  copy, the tidy-up moves, tests beside each, `docs/deferred.md`, one ADR, the web-api and
  evidence-search spec amendments the owner accepted.
- **Out:** the emit schema and span binder; prompt text beyond O3, X1, X3, D7's possible
  sentence and the D10 request shape; the Langfuse deployment; `infra/` (routes keep their
  names; no config value changes); the queued-parsing architecture; cross-task reuse; any
  other capability.

## Constraints & approval gates

- **Runtime egress.** The model set (D2) is approved at this contract. The Europe PMC
  host (S7) is new egress: named approval at the plan gate with the host and the data sent
  (a PubMed Central id, nothing else).
- **Schema.** One migration: the appraisal row's nullable score plus `unrated` flag (D7).
  Approved at this contract as route (b); the slice stays Tier 3 because the change adds a
  nullable column and relaxes one check, with no data rewrite.
- **Public interface.** S5 (stage key and progress payload) and the one appraisal label
  (D7), both approved here; the web-api spec is amended as an owner spec item.
- **Dependencies.** None planned; `defusedxml` only if the plan shows the standard
  library cannot parse JATS safely, approved then.
- **Production config.** None.
- **Prompt hashes.** Expected re-pins, each recorded with its diff: P0 `section_prompt.py`
  (new pin), `finding_vetter.py`, `ranking.py`, `theme_grouping.py`, `group_clustering.py`
  (new pins, owner 2026-11-01; they hold model-facing text outside the guard), `interventions_prompt.py` and `theme_prompt.py`
  (renames), deletion of the v6 entry; P1 `summary_prompts.py` (O3), `grounding_judge.py`
  (X1 if needed), `classify_prompt.py` and the other pinned modules whose `route().model_for`
  or effort lines change for D4 and D9 (code-only diffs); P2 `section_prompt.py` (D8
  message shape, D10 request shape, X3's tool description); caching modes live in one
  committed table module keyed by call name, so no other pinned file changes for D3; P3 `section_prompt.py` only if D7's
  sentence is added. Any re-pin not on this list stops the slice.
- **Tests stay offline.** Stubs return the usage shape with cache-write and reasoning
  counts.

## Public / private boundary

Committable: code, tests, the route file, the cost script, this folder's documents with
numbers. Private: Langfuse and provider keys, report text from the fixed questions
(verification cites session ids and totals), probe outputs that include document text.

## Model route

The slice changes the model set (D2), gives every call site its own step (D9) and its own
effort (D4), and sets caching per site (D3). Prompt-bearing changes: O3 (judge and two
summariser prompts), X1 (grounding judge, if needed), X3 (the `lookup` tool description),
D10 (the repair and section-turn request shape), D7 (one sentence, only if needed). Each
is a version bump, a re-pin and a replay or owner read.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves.** No label, type or flag that does not change v3.0 behaviour
  (the `unrated` flag changes citability and display).
- **Flag, don't drop.** Unrated is shown, never hidden; unsupported claims stay flagged.
- **Honest absence.** Coverage counts carry their base; Unrated is its own bucket.
- **First commits change nothing.** D4, D9 and the tidy-ups land with tests that pin
  today's values before any value moves.
- **Measure before and after, one lever at a time**, by call name for the small levers.

## Stop conditions

Halt and escalate when: a gate above is hit; a re-pin not on the list is needed; the GPT-6
re-test in P2 does not reproduce the GPT-5.6 caching behaviour (then D8 and D10 stop and the
owner decides); a phase's measurement shows cost up or the owner's read shows a quality
drop (revert that phase, record it, continue); a GPT-6 model refuses a request shape a call
site needs; scope would grow past this slice; the turn or token budget is spent.

## Acceptance checks

- `make verify` green at the build-open baseline, after P1, after P3 (schema), and at the
  step-6 exit; `make verify-fast` between the other phases; `make prompt-guard` at every
  commit.
- Deterministic tests: usage mapping with cache-write and reasoning buckets; the caching
  mode per call site list (D3); the resolved model and effort per step on the committed
  routes, with "not sent" preserved (D4, D9); the byte-identical shared prefix and the
  forced-turn single-tool check (D10); the breakpoint content-part shape (D8); the `lookup`
  kinds offered match what the run can serve (X3); the Unrated row, its citability and its
  label, with the 1 to 5 check intact for scored rows (D7); the window guard reusing the
  oversized-chunk helper (N5); the scheduler keeps the per-document timeout, the
  large-payload safeguards and the shared ingest semaphore, with byte-identical output on
  the saved corpus (N8); the stage key and progress payload (S5); the JATS parser on saved
  XML (N10).
- Manual: the fixed questions as D1 says, on `bedrock`, plus one on `openai-direct` after
  P1 and P2; the owner's read after P1 (twice: model-only, then with the prompt loops), P2
  and P3.
- Live check scope: the fixed questions only.

## Verification evidence expected

Per phase in `verification.md`: the cost table (whole-run for P1 and the end; per call name
for P2 to P5) with session ids; cache read and write shares per call name before and after
P2; reasoning tokens per step before and after P5; the owner's read notes; every re-pin's
diff; the GPT-6 re-test output; the exact commands; anything reverted and why.

## Risk tier & review focus

**Tier 3.** Runtime egress (the model set, the Europe PMC host), a nullable-column
migration with one relaxed check, two public-interface additions, and shared Evidence
search components. Review: contract verifier, code and security review (the migration, the
XML parser on untrusted input, the new host), the adversarial pass at plan stage, human
deep review of the model set and the measurements. Focus: no prompt text moved unnoticed,
caching modes applied per the measurement, "not sent" effort preserved by the first commit,
numbers read from saved results, and scope creep into the synthesis refinement task.
