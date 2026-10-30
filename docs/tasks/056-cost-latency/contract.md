# Task contract: 056-cost-latency

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** approved. Drafted 2026-10-29. **Contract approved (before planning):
> 2026-10-30 · Shabeer Rauf (owner).** Owner decisions O1 to O5, D4, D7 to D9, S1 to S8 and
> X1 to X8 taken 2026-10-29 and 2026-10-30 and recorded in their sections; N11 withdrawn
> 2026-10-30. Gates approved at this contract: the model set (D2, D2a; runtime egress to
> GPT-6 models on both routes), the public-interface change for the reading stage (S5),
> and the spec amendments S1 to S3. Plan approved (before implementation): _pending_ ·
> ADR: _0042 planned (model generation change, per-call-site routing, the caching rule)_ ·
> Branch: `task/056-cost-latency`. Contract-stage adversarial review: _in progress_.

## Goal

Make a standard Evidence search run cost under $2 end to end, and make Options scoping
cheaper through the same shared components, without changing what the reports say.
Latency improvements are taken where they come free; they are not a goal of this slice.

A standard run today costs a median of $2.12 and ranges from $1.60 to $4.88 (six runs,
22 to 29 October, recomputed from token counts at current list prices). The writer's
model (Terra) is 55 to 75% of that. The slice has four parts, in this order: measure
properly, move to the GPT-6 generation, stop paying for cache writes that never pay back,
and then the smaller synthesis levers. Each part is measured on the same fixed questions
before the next one starts.

## Why this is safe to do now

- Every model name lives in one committed file since task 053 (`model_routes.toml`).
  A model change is a one-line edit per tier, reviewed in a pull request.
- Langfuse now prices every call on both routes: nine custom price rows were added on
  2026-10-29 for the GPT-5.6, GPT-6 and Cohere models with patterns that accept the
  Bedrock names (`global.openai.*`). Before that, every Bedrock call showed $0.
- GPT-6 models answer from Bedrock London and from OpenAI direct. Probed 2026-10-29 with
  a forced tool call and with structured output (§ Facts).
- Prompt caching works on both routes without any request change (§ Facts). The thing
  that costs money is the write charge on calls whose prompt never repeats, and turning
  it off is one request option, probed on both routes.

## Deliverable

A pull request where:

1. Langfuse records cache-write tokens on every generation, and a documented command
   reports cost per run by stage for a session (P0).
2. The three tiers in `model_routes.toml` name GPT-6 models on both routes, with the
   reasoning-effort knob set per model (P1).
3. One-shot call sites send the request option that turns prompt caching off, so they
   pay no cache-write charge (P2).
4. The synthesis levers the owner keeps from § Numbered needs are built (P3 to P5).
5. `verification.md` holds, for each phase, the cost per run of the same fixed questions
   before and after, and the owner's read of the reports.

## Terms

| Term | Meaning |
|---|---|
| **Standard run** | An Evidence search run at `standard` depth: acquire, screen (two stages), classify, appraise, ingest full text, characterise, select, synthesise. `runtime/task_plan.py` `ANALYSIS_DEPTH_TABLE`. |
| **Cost per run** | The sum of every model call's cost inside one Langfuse session, in USD. Computed from token counts and list prices, not from Langfuse's stored cost, because stored costs were wrong before 2026-10-29 and stay wrong for old rows. |
| **Route** | A named set of models in `backend/src/policy_atlas/model_routes.toml`. `openai-direct` calls OpenAI; `bedrock` calls Amazon Bedrock in London. Staging runs `bedrock`, production `openai-direct` (`infra/pa_config.json`). |
| **Tier** | A role a model plays: `fast` (cheap, high volume), `standard` (writing, chat, agents), `frontier` (the two Options scoping judgment calls). Each route says which model each tier is. |
| **Prompt cache** | The provider keeps the first part of a prompt (the prefix) for 30 minutes, so a later call with the same prefix pays 10% of the input price for those tokens (a *cache read*). On GPT-5.6 and later, the provider also charges 1.25 times the input price to store the prefix (a *cache write*), on every call over 1,024 tokens whose prefix is not already stored. |
| **One-shot call** | A model call whose prompt will never be sent again, for example classifying one document. It can never get a cache read, so its cache write is pure cost. |
| **Reasoning effort** | A request knob (`reasoning_effort`) that sets how much the model thinks before answering. `none` means no reasoning tokens. Terra-class models need `none` to accept function tools; Sol-class models refuse `none`. Lives in the route file's `knobs` table, keyed by model id. |
| **Function tools** | The request shape where the model calls named tools. Used by the synthesis section writer and the chat loop only. |
| **Structured output** | The request shape where the model returns JSON matching a schema (`response_format`). Used by every other model call site. |
| **Prompt hash guard** | `make prompt-guard`. Every prompt module is pinned by a hash in `scripts/prompt_hashes.json`. A model change does not touch prompt text and needs no re-pin. |
| **Fixed questions** | Three Evidence search questions and one Options scoping question, chosen by the owner at the contract gate (O5), run before and after each phase. The before-and-after pairs are the slice's measurement. |
| **Decided / Leaning / Open** | Decided means settled. Leaning means the recommended choice unless the owner objects. Open means the owner chooses at the approval gate. |

## Facts we rely on

Probed on 2026-10-29 unless marked otherwise. Probe scripts are in the seed folder.

| Fact | Consequence |
|---|---|
| Whole-run cost, recomputed from token counts at current list prices, 22 to 29 Oct: ES standard median $2.12 (n=6, $1.60 to $4.88); ES landscape $0.87 (n=5); Options scoping $3.46 (n=9, $2.09 to $6.26). Four of the six standard runs still used gpt-5.4-mini for classify (an older checkout); the two on the current route cost $1.96 and $3.80. Synthesise is 55 to 75% of a standard run; in scoping the Sol calls (option profiles) are 40 to 60%. | The target sits at today's median. The spread, not the median, is the problem. Cache writes are not in these numbers (not recorded), so real cost is a few percent higher. |
| Both routes charge a cache write on every call over 1,024 tokens that misses, at 1.25 times input. Both give cache reads on a repeated prefix with plain string messages and no cache key. Sending `prompt_cache_options = {"mode": "explicit"}` with no breakpoints gives zero writes and zero reads on both routes. | Caching needs no code to work. One-shot sites can opt out with one request option, in the shared request builder. |
| Share of input tokens in 1,000 recent generations: section_turn 23% (44% cached), screen:abstract 12% (85% cached), judge:grounding 11% (0%), screen:full 9% (0%), extract 17% (20 to 29%), repair 7% (10%), classify 5% (0%), judge_summary 3% (4%). About 30% of input volume is one-shot. | Turning caching off on one-shot sites saves about 25% of 30% of input cost, roughly 4 to 5% of a run, with no quality effect. |
| `core/usage.py` reads `prompt_tokens_details.cached_tokens` and ignores `cache_write_tokens`. | Langfuse has never shown the write charge. P0 fixes this. |
| GPT-6 models on Bedrock London (`global.openai.` prefix) and on OpenAI direct: gpt-6.1-terra, gpt-6-luna and gpt-6-sol accept `reasoning_effort = "none"`, function tools and structured output. gpt-6.1-sol and gpt-6-astra refuse `none` (minimum `low`) and refuse function tools on Chat Completions; structured output works on them at `low`. | `standard` can move to gpt-6.1-terra and `fast` to gpt-6-luna with the same knob as today. `frontier` is an owner choice between gpt-6.1-sol at `low` and gpt-6-sol at `none` (O2); both frontier call sites use structured output, so either works. |
| List prices per million tokens (input / cached / output): gpt-5.6-luna 0.20 / 0.02 / 1.20; gpt-5.6-terra 2.00 / 0.20 / 12.00; gpt-5.6-sol 4.00 / 0.40 / 20.00; gpt-6-luna 0.10 / 0.01 / 0.50; gpt-6.1-terra 1.00 / 0.05 / 5.00; gpt-6.1-sol 2.00 / 0.10 / 10.00; gpt-6-sol 2.00 / 0.20 / 10.00. Bedrock matches OpenAI first-party rates (AWS). | At equal token counts the switch roughly halves every tier's cost. The writer's output tokens, the largest single line, drop from $12 to $5 per million. |
| GPT-5.6 to GPT-6 is the same model family (OpenAI GPT). The prompting spec's rule 12 (fresh prompt at a model-family swap) does not fire. | No prompt text changes in P1. The owner's read of the fixed questions is the quality check. |
| Only two call sites send function tools: the synthesis section writer and the chat tool loop. Every other site uses structured output. | The `none` constraint matters only for the `standard` tier. |
| Latency: ingest of full text is 38 to 41% of a run's wall time and 91 to 95% of it is download and PDF parsing, not model time. Synthesise is 21 to 23%. (20 runs, 19 to 26 Oct.) | Model changes move at most a quarter of the wait. Ingest work is latency-only and sits last (N8). |
| Langfuse (self-hosted 3.225.5) prices only new generations. Custom rows take priority over built-in rows. | Old rows stay wrong; measurements use token counts. When Langfuse is upgraded to a version whose built-in OpenAI patterns accept the Bedrock names, the custom GPT rows must be deleted (`docs/deferred.md`). |

## Read first

- The seed document with every measurement, the owner's rulings of 2026-10-29 and the
  confirmed intent:
  `docs/research-and-development/synthesis-refinement/cost-latency-task-seed.md`
  (gitignored folder; the two research reports beside it are background, not authority).
- [ADR 0041](../../adr/0041-bedrock-inference-route-and-model-route-file.md): the route
  file, its three layers, and the knob rule. This slice edits the file, not the mechanism.
- [system/prompting.md](../../specs/system/prompting.md) rule 12 (fresh prompt only at a
  family swap), § Provider-specific (caching: "only the kwarg is provider-specific"), and
  the refine-replay rule that cost is judged on the cache-discounted curve.
- [system/execution-orchestration.md](../../specs/system/execution-orchestration.md) §
  egress: the inference route is product egress and is gated.
- [capabilities/evidence-search/components.md](../../specs/capabilities/evidence-search/components.md)
  § 9 synthesise (the section loop, `produce-grounded-block`, repair as a micro-call, the
  task 022 cost set) and § 4's full-text ingestion paragraph.
- [deferred.md](../../deferred.md) § Synthesise ("Gather/writer model split", head of the
  post-eval cost queue) and § Execution ("Langfuse costs ignore prompt-cache hits").
- Code: `core/openai_client.py` (`openai_kwargs`, the one shared request builder),
  `core/usage.py`, `core/model_routes.py`, `model_routes.toml`,
  `evidence_search/synthesis/synthesise.py` (`_write_and_judge_summary`,
  `_failing_records`, the `unappraised_doc_citation` rejection),
  `evidence_search/synthesis/synthesis_backend.py` (`build_section_repair_messages`,
  `judge_summary`), `evidence_search/synthesis/grounding_judge.py`,
  `evidence_search/sourcing/ingest_full_text.py` (worker and timeout constants).

## Numbered needs

Every later section, the rubric and the plan use these numbers.

| # | Need | Where it lives today | Expected saving |
|---|---|---|---|
| N1 | Record cache-write tokens and reasoning tokens, and report cost per run by stage from token counts. | `core/usage.py` drops `cache_write_tokens` and `completion_tokens_details.reasoning_tokens`; no per-run cost command exists (the seed folder has a script). | Measurement only. Everything else is judged with it; N7 needs the reasoning count. |
| N2 | Move the three tiers to GPT-6 on both routes, with the two prompts that the experiments show read differently on the new models refined as part of the switch. | `model_routes.toml` tiers and `knobs.reasoning_effort`. Experiment 2026-10-29 (`experiments/fast-tier-swap.md`, 90 documents, two runs per model, 720 calls, $0.22): classify agreement between gpt-5.6-luna and gpt-6-luna (80 to 86%) is inside gpt-5.6-luna's own run-to-run agreement (87%), and gpt-6-luna is more self-consistent (96%), so classify can move on this evidence. Screen on gpt-6-luna keeps more documents (4 to 7 excluded of 90 against 11 to 16), including thin web pages the old model drops under the outcome criterion; On task 051's 288-document human-labelled set (`experiments/screen-labelled-replay.md`, 1,557 calls, $0.27, the production two-call vote rebuilt): gpt-6-luna's recall 0.924 against 0.924 to 0.938, precision 0.689 to 0.700 against 0.696 to 0.700, model-to-model agreement equal to each model's self-agreement, 46% cheaper, median 3.6 s against 3.0 s. The extra keeps are thin web pages whose envelope reports no outcome, which gpt-6-luna keeps under the prompt's own rule that an unreported criterion is never a reason to exclude; the labelled set holds only research abstracts, so that case is measured by the owner's read of the fixed questions, not by a replay. gpt-6-luna is slower (screen median 4.2 s against 3.0 s; classify p90 8.3 s against 6.9 s) but halves the two steps' cost. Classify hard-codes `reasoning_effort = "high"` in code and screen sends none, so the route knob does not reach them (fact for N7). | About half of model cost at equal tokens. The summary prompts get a refinement loop (O3); the screen prompt does not unless the owner's read shows thin web pages reaching the corpus. |
| N3 | Turn prompt caching off on one-shot call sites; put an explicit cache breakpoint after the section writer's run-stable block; and build the repair request on the section's own first turn (S4). | `openai_kwargs` in `core/openai_client.py`; one-shot sites: classify, screen stage 2, grounding judge, summary judge, group assign, finding vetters, case studies, rerank. Experiment 2026-10-29 (`experiments/repair-cache-miss.md`, 20 traced runs): cache reads only ever land at the end of an earlier request (minus a fixed 122-token tail), never on a shared middle block; on Bedrock every section's first turn and every repair read 0 of 79 and 0 of 52; on direct OpenAI repairs read only the tools-plus-system block stored by an earlier repair (3.6k of up to 15k). The repair request differs from the section turn from the first tool definition (four section tools against one repair tool). The summary judge has no stable block over 1,024 tokens, so nothing can be cached there. | One-shot opt-out 4 to 5% of a run. Breakpoint after the run-stable block: on Bedrock, up to 7.5k tokens per section read instead of written, about 8% of synthesise; needs a two-call live test first (D8). |
| N4 | Make screened-in documents the classifier could not type citable, at a visible "unrated" appraisal, so the writer can use grey literature and the reader sees its lower standing. | Appraise scores only the seven evidence types in `DEFAULT_RUBRIC`; `Unknown / Insufficient information` and `Other (Non-evidence documents)` are skipped and counted (task 006). The writer's retrieval returns their chunks for reading, but `synthesise.py` rejects any citation to them (`unappraised_doc_citation`), which triggers a repair pass. The writer already sees each returned chunk's `appraisal_label` and its `evidence_type` (the classification the appraisal is based on, so "Unknown / Insufficient information" is visible beside "Unrated"). | Part of the repair share (16 to 20% of synthesise), and a quality gain: grey literature becomes citable, flagged. Owner decision: spec change S1 to S3 below. |
| N5 | Repair input: cap outsized cited chunks only. (Corrected 2026-10-30 twice: the repair already returns one patched segment per claim; and the payload measurement shows general windowing is not worth its risk.) | Measured over 94 repair calls in 20 runs (`experiments/repair-payload-share.md`): chunk text is 38% of repair input, the shared prefix 48%, the claim records 5%. The cost sits in a few huge chunks: 28 of 118 chunks over 10,000 characters carry 82% of the chunk text, the largest 233k characters (about 58k tokens), against 200-character quotes. Windowing every chunk would save $0.035 to $0.052 per run today, $0.018 to $0.026 after the switch, with five runs giving 77% of it, and it risks cutting the passage a repair needs, since 43% of cited quotes in repair calls are "quote not found" failures. Sending each chunk once per call saves $0.014 per run; only 17 of 118 chunks are cited twice. | Build only the guard: chunks over about 10,000 characters are sent as a window around the quote (or around the longest matching stretch when the quote was not found); smaller chunks go whole. About 3% of synthesise. The 43% quote-not-found rate and the 233k-character chunks are recorded for the synthesis refinement task. |
| N6 | Summary judge moves to gpt-6.1-terra with P1; the judge prompt and the two summary writer prompts are refined together as one loop (O3). | `judge_summary` uses the synthesis model, 15 to 19 calls per run. Experiment 2026-10-29 (`experiments/summary-judge-tiering.md`, 90 items): no cheaper model let a corrupted summary through, but gpt-6.1-terra rejected 20 of 45 summaries the old judge had passed, gpt-6-luna 39 of 45. The 45 "pass" labels are the old judge's own verdicts, so an adjudication of the 20 disputed items is running (`experiments/summary-judge-adjudication.md`). The 90 items are the judge prompt's replay set. | Judge cost halves with P1 ($0.80 to $0.39 per 100 calls). A prompt refinement is deliberate prompt work: version bump, re-pin, replay on the 90 items, zero false passes. No move to the `fast` tier: gpt-6-luna's rejection rate rules it out. |
| N7 | Reasoning effort and model per step in the route file, then tuned where a replay set exists. | `knobs.reasoning_effort` is keyed by model id; four call sites hard-code an effort in code (classify, two finding vetters, relevance annotator); screen sends none; six synthesis jobs share one step (D9). | 3 to 10%. D4 and D9 first (no behaviour change), then each step's model and effort are tuned on its replay set. Classify is measured (`experiments/classify-effort-sweep.md`, 1,080 calls): on gpt-6-luna, `medium` holds agreement with `high` inside run-to-run noise and saves 19% of classify cost and 22% of its wall time (per-call p90 7.8 s to 5.6 s); `none` and `low` are 2.4 to 2.9 times faster but change 19 to 21 of 90 labels against `high` (noise changes about 7), pushing written evidence and thin web pages towards "Policy Syntheses & Guidance", so they are a behaviour change, not an option. Classify therefore moves to `medium` in P5. |
| N8 | Latency: let a parse job start in any free slot, and cut the per-document process start-up cost; leave timeouts, pool size and fetch threads alone. | Experiment 2026-10-29 (`experiments/ingest-profile.md`, 55 PDFs from 55 hosts, the real `ingest_full_text_sources` with a throw-away database, four runs): fetch is under 1% of ingest wall time (55 downloads in about 12 s), parse is 89 to 92%. The parse pool drains jobs in submission order, so one slow PDF holds back free slots: effective concurrency was about 2 of 4 and 3 of 8, and an any-free-slot scheduler simulates 40 to 50% less parse wall time on the laptop (less on staging's 2 CPUs, where parse is CPU-bound). Each document pays 1.3 to 2.3 s to spawn a fresh process and import pymupdf4llm, trafilatura and openai, 26 to 29% of worker time, pure CPU on staging. A 60 s parse or 15 s fetch timeout would drop 0 of 55 here and dev history shows 2 parse and 13 fetch timeouts in 3,372 links; the 30 s fetch timeout is per step, not per download. Parse time follows page count (correlation 0.87), not bytes. | Wall time only. Prototyped 2026-10-30 (`experiments/ingest-scheduler-prototype.md`, 52 documents, 16 runs, output byte-identical, 747 chunks every time, stuck and crashing parses still killed and recorded): any-free-slot draining plus a preloaded forkserver cut the parse stage by a mean of 49% at pool 4 (148 to 75 s) and 56% at pool 8, on a noisy laptop; effective concurrency rose from about 2 to 3.2 to 3.7 of 4 slots and per-document start-up fell from 1.2 to 2.4 s to about 10 ms. Product change about 20 to 25 lines in `_run_parse_jobs` and 5 to 10 for the start method; `_drain_parse_job` and `_worker_entry` unchanged. Not yet shown: the gain on staging's 2 CPUs, and the batch hand-over in `ingest_full_text_sources`, which can still hold a batch behind one slow document and is measured in the build. A test pins that the new scheduler still takes the shared ingest semaphore task 045 added for parallel option searches. |
| N9 | Show full-text reading in the progress box, with counts read from the document store's per-document statuses. | `api/stage_vocabulary.py` maps every registry component to a public stage key except `ingest_full_text`, so the longest stage of a run is invisible and the box looks stalled (owner, 2026-10-30). `StageKey` is the pinned public contract vocabulary (`api/contract.py`, web-api spec), so adding a key is a public-interface change: decision S5. | Perception only. One stage row, "Reading the full texts", with fetched and parsed counts of the eligible total, ticking per document. Counting from the store rather than the loop means the row survives the move to queued parsing (next task). |
| N10 | Prefer structured non-PDF full text where the provider offers it: an XML path for PubMed-indexed articles first; HTML only with headings kept. (Owner S7, 2026-10-30; mechanism set by the measurement below.) | `candidate_urls` orders PDF first and reaches the landing page last; when the landing HTML parses above the thin threshold the cascade keeps it and does not follow the PDF link it discovered (deferred.md § full-text cascade; 353 of 1,978 local full texts are HTML), otherwise the discovered PDF is fetched. Measured 2026-10-30 (`experiments/html-vs-pdf.md`, 30 documents): where a full-article HTML page is reachable, parsing takes 0.06 s against 4.7 s for the PDF, but those documents are 24% of PDF parse time, and the slow tail (20 to 62 s: long government and NIHR reports, a thesis) has no HTML at all. HTML is usable on Frontiers, PLOS, Nature and BMC/Springer (the last two only if the fetcher keeps cookies; today a login-redirect loop hits the 5-hop cap), and not on MDPI, JMIR (bot challenges), NIHR (403), Cambridge, medRxiv or repository and government hosts. Today's HTML parser asks trafilatura for plain text, so switching would lose section headings (its markdown output keeps 35 to 48 at the same speed) and the tables are not in the page text on BMC, PLOS and Nature. Europe PMC returned structured full text for 15 of 16 PubMed Central ids in about 0.8 s, including the MDPI and JMIR articles; no PubMed Central id is stored locally (OpenAlex `ids` and `locations` are not fetched), and there is no JATS XML parser. Locally, 1,625 of 1,978 ingested full texts came from PDF. | Wall time on the journal share only; the slow tail is untouched and stays with N8. Build order: (1) request OpenAlex `ids` so PubMed Central ids are stored (search backend field change, same host); (2) Europe PMC JATS XML fetch and parser, new host, egress gate at the plan; (3) HTML markdown output and cookie handling only if (2) leaves a measurable share. Chunk quality must hold: XML headings and tables are at least as good as PDF layout analysis. |
| N11 | Withdrawn (owner question 2026-10-30: the matcher ladder treats symptoms). The funnel (`experiments/citation-funnel-measurement.md`) shows the roots: 80 of 128 failed quotes are markup left in chunk text by the parser, 24 are interleaved page headers or footnotes, and the copying step itself is the design no other system uses (the pointer prototype had zero quote failures). Clean chunk text and header or footnote handling go to the queued-parsing task as a new parse profile; pointers go to the synthesis refinement task; normalised matching survives only for re-anchoring old citations after a re-parse, also in the parsing task. | | No cost lever in this slice. |

## Parsing: what the numbers say and what could change

Parsing is about a third of a standard run's wall time, not 90% of it: ingest is 38 to
41% of the run and parsing is about 90% of ingest. It is still the single largest
stage, and it is CPU work on a 2-CPU container, not model time. The options, with
where each sits:

| Option | What it would do | Where it sits |
|---|---|---|
| Any-free-slot scheduler and cheaper process start-up | Recover the 40 to 50% of parse wall time the laptop loses to head-of-line blocking and per-document spawn and imports. | **In: N8.** |
| Reuse parsed text across tasks | Today `already_ingested` means "this task already has a snapshot"; a document fetched for an earlier task is fetched and parsed again. Recurring documents (childhood obesity has run six times locally) would skip parse entirely with a store keyed by URL or content hash. | **Out (owner, 2026-10-30, S6): not in this task.** Recorded in `docs/deferred.md` as a seam. |
| Prefer publisher XML or HTML over PDF | Europe PMC and some publishers serve open-access full text as XML or HTML, which needs no PDF parsing. | **In (owner, 2026-10-30, S7): N10.** Today's cascade is PDF first (`best_oa_location.pdf_url` → `primary_location.pdf_url` → `oa_url` → landing page); HTML is parsed only as the last fallback. |
| A faster parse profile | `pymupdf4llm.to_markdown` does layout analysis for headings and tables; plain text extraction is several times faster but loses structure the chunker uses. The parse profile is versioned (`PDF_PARSE_PROFILE`). | **Out (owner, 2026-10-30, S8): chunk quality is not traded for time.** |
| Parse outside the web container | Functions triggered by a queue, one per document, writing parsed text and a status into the shared document store; the web server queues the jobs, waits on the store with a deadline, and shows progress per document. | **Agreed as the next task (owner and DevOps colleague, 2026-10-30), not this one.** Tier 4, its own slice. The parsing decisions in this slice are shaped to survive it: N8 keeps local and in-process parsing fast and trims the parse worker's imports, which the function image needs too; N9's progress counts are read from the document store's statuses, not from the in-process loop, so the same stage row works when a queue fills the store; N10's XML parser is a pure function from body to chunks, so a function can call it. No parse-backend interface is added now: one implementation does not need one, and the next task adds the seam with its second implementation. |
| Start downstream steps as documents land | Screen stage 2 and characterise per document as each parse finishes, instead of after the whole batch. | Out: pipeline order, the synthesis refinement task or its own slice. |


## Decisions

**D1. Measure from token counts, on fixed questions. Decided (owner intent).** Cost per
run is computed from Langfuse token counts and the list prices in one small script
committed under `scripts/`, keyed by session. The owner names three Evidence search
questions and one Options scoping question at the plan gate. They are run once before
P1 on GPT-5.6 and once after each phase. The pairs go in `verification.md`. The owner
reads the reports; no eval harness is built.

**D2a. Before P1: confirm Bedrock London quotas for the five GPT-6 model ids (the Bedrock routes entry in deferred.md still lists quota checks as to do), and record the numbers in verification.md.** Tiny.

**D2. GPT-6 on both routes, with prompt refinement where a replay set shows the new model reads a prompt differently (owner, 2026-10-29: refine the prompt, do not reject the model). Leaning: `fast` = gpt-6-luna, `standard` = gpt-6.1-terra,
`frontier` = O2.** The `frontier` tier serves only the two Options scoping judgment steps (see O2). The knob table gains `gpt-6.1-terra = "none"` and, if O2 picks
gpt-6-sol, `gpt-6-sol = "none"`; if it picks gpt-6.1-sol, `gpt-6.1-sol = "low"`. The
`bedrock-claude` route (not in use) follows the `bedrock` route. No prompt text changes.
The data-residency position is unchanged: GPT-6 on Bedrock uses the same `global.`
profiles as GPT-5.6 today. Both routes change together so staging and production move
in one review.

**D3. Caching off is a call-site flag in the shared request builder. Leaning.**
`openai_kwargs` gains a `one_shot: bool` argument. When true it adds
`extra_body = {"prompt_cache_options": {"mode": "explicit"}}`. The one-shot sites pass
it; the section writer, repair, screen stage 1, extract and chat do not. The kwarg is
OpenAI-format-specific and lives in one place, which is what the prompting spec allows.
A route that does not understand the option would reject the request loudly, so the
Claude backend never receives it (it does not use `openai_kwargs`).

**D4. Reasoning effort lives in the route file, per step. Decided (owner, 2026-10-29:
"move hard-coded effort into the model configs").** Today the route file's knob is keyed
by model id, so every step on one model shares a value, and four call sites bypass it
with constants in code: classify (`CLASSIFY_REASONING_EFFORT`), the two finding vetters
(`FINDING_VETTER_REASONING_EFFORT`, `ICF_FINDING_VETTER_REASONING_EFFORT`) and the
relevance annotator (`RELEVANCE_ANNOTATOR_REASONING_EFFORT`). After this slice there is
one mechanism: the `[routes.<name>.steps]` exception table gains a table form with
`model` and `reasoning_effort` keys (a bare tier or model id still works), and the four
constants are deleted; their values move into the route file for both routes so the
first commit changes no behaviour. The loader keeps failing loud on unknown keys, and a
test pins that every step's resolved effort on the committed routes equals today's
value. This is the smallest extension of ADR 0041 and it is what N7 then tunes.

**D5. Order of phases. Decided (owner, 2026-10-29).** P0 instrument (N1) → P1 switch
(N2, carrying N6) → P2 caching off (N3) → P3 unrated appraisal (N4) → P4 repair patching
(N5) → P5 reasoning effort per step (N7) → P6 ingest scheduler and process start-up (N8), last and the first to cut if budget runs short, since queued parsing (next task) supersedes most of it on staging. The owner can stop after any phase;
each phase leaves the branch mergeable.

**D6. What this slice does not touch. Decided.** No prompt text changes except where a
lever's own contract says so (P3 changes appraisal (D7), not the prompt, unless the owner's read asks for one sentence; P4
changes the repair message template, which P0 brings under the hash guard so the change
is re-pinned with the diff recorded). No emit-schema rewrite (the claim-text repeat belongs to the synthesis
refinement task). No Flex or batch tiers. No stripping of Bedrock prefixes in tracing.
No Langfuse version change. No spec edits without an owner decision item.

**D7. Unrated appraisal for untyped documents (N4). Proposed; needs the owner's spec
decisions S1 to S3, because the specs say these documents are skipped.** Mechanism: the
default rubric gains the two non-evidence types at a new score 0, label "Unrated", so
every screened-in document gets an appraisal row and the grounding rule "cite only
appraised evidence" (execution-orchestration § tool wiring) stays intact. The writer sees
"Unrated" in the `appraisal_label` of every returned chunk, as it sees "Weak" today. The
reader sees the source's standing as its appraisal label ("Unrated"), in the source list
and the claim's provenance sheet, exactly as "Weak" is shown today; the grounding
verdict is the judge's alone and is not touched (S2). Making the per-run override the
default is the "steerable, never baked" gate the deferred log names (deferred.md § citable
bar); the owner's acceptance of S1 to S3 is that gate. The existing per-run
rubric override already allows exactly this for one run; D7 makes it the default. No
prompt text changes unless the owner's read shows the writer over-trusts unrated
sources; then one sentence is added to the section writer's system prompt as a recorded
re-pin.

- **S1 (spec).** `components.md` § 4 appraise: "Non-evidence and Unknown are
  skipped-and-counted" becomes "scored 0, Unrated, and counted"; the invariant counts
  change accordingly. `provenance.md` and `provenance-grounding.md` gain the Unrated
  tier wherever tiers are listed.
- **S2 (spec and reader-facing words). Revised 2026-10-30.** Grounding is the judge's
  verdict and stays untouched: the only grounding flag a reader sees is the report's
  "The grounding review could not fully verify this claim against its source" note,
  set by the judge alone. The source's standing is shown separately, as the appraisal
  label on the source and in the claim's provenance sheet, where "Unrated" appears
  beside the classification it rests on ("Unknown / Insufficient information" or
  "Other (Non-evidence documents)"). No new term reaches the reader: "below policy" is
  the spec's internal name for the citable-bar rule (`provenance.md` § citable bar) and
  is not used in code or in the interface; the owner finds it uninterpretable, so this
  slice does not surface it and the spec amendment for the Unrated tier uses plain
  words ("sources the classifier could not type are cited and shown as Unrated").
  Pattern and coverage claims that count by tier include Unrated as its own bucket,
  never folded into Weak.
- **S3 (code, follows S1).** `SCORE_LABELS` gains `0: "Unrated"`; the rubric-domain test
  that pins "exactly the seven evidence types" is rewritten to pin all nine; the
  `unappraised_doc_citation` rejection stays as the backstop for genuinely unappraised
  rows (a run that failed mid-appraise). `DEFAULT_RUBRIC_VERSION` (`v2-hierarchy-v1`)
  is bumped, because every appraisal row carries it and the appraisal-reuse seam is
  keyed on it (deferred.md § rubric version).
- **S5 (public interface).** Add a stage key for full-text reading to `StageKey` and
  the web-api spec, with its label and blurb, and emit started and progress events from
  ingest with fetched and parsed counts (N9).
- **S6. Decided out (owner, 2026-10-30).** No cross-task reuse of parsed text in this task.
- **S7. Decided in (owner, 2026-10-30): prefer HTML or XML full text over PDF where
  available (N10).** The measurement makes XML the mechanism: Europe PMC's full-text
  service for documents with a PubMed Central id is a new host, so it is new runtime
  egress and needs the owner's written approval at the plan gate with the host named.
  HTML-first alone is not worth building: it covers a quarter of parse time and loses
  headings and tables as the parser stands.
- **S8. Decided out (owner, 2026-10-30).** No faster parse profile.

## Research findings, checked against this slice (2026-10-29)

The cost research report (seed folder, "Cost optimisation for research agents") ranks
nine levers. Where each one sits:

| Report lever | Here | Note |
|---|---|---|
| 0 Instrument (cached, cache-write, reasoning tokens; cost per run; p99) | N1 | Budget gate and tool-call cap not added: the section loop already has a hard turn cap. |
| 1 Fix caching (stable prefixes, judge and repair grouped per section, pre-warm) | N3, partly | One-shot opt-out and the repair-miss measurement are in. Pre-warming and regrouping judge calls are out: the grounding envelope is unique per section, and the summary judge moves to the cheap tier instead. |
| 2 Flex or Batch | Out | Owner, 2026-10-29: minutes of extra wait; not on Bedrock. |
| 3 Writer output economy (prose once, claim markers, no quote copy) | Out | The emit-schema rewrite; the largest remaining lever at 10 to 25%, parked for the synthesis refinement task because it touches the span binder, judge envelope and prompt hash together. |
| 4 Reasoning effort per stage | N7 | |
| 5 Repair economics (patch the claim; cap retries) | N5 | Retry caps already exist (`SUMMARY_REGENERATE_CAP`). |
| 6 Judge tiering with an agreement protocol | N6, with the owner's read as the guard | Owner, 2026-10-29: no eval harness. The report's warning stands: small judges passed only under a kappa protocol. Recorded as an accepted risk. |
| 7 Retrieval and context (seen-set, pruning, stopping, rerank pool) | Out | Synthesis refinement task. |
| 8 GPT-6 migration, last | N2, first | Owner, 2026-10-29: first, because no eval set is being built that the order would protect. |

The second report ("Holistic evidence views in deep research") is about the writer's
view of the corpus, not cost; none of it belongs here. One of its findings bears on D7:
grey literature and mixed policy corpora are the weakest-evidenced input for these
systems, which is a reason to show the writer the Unrated label rather than hide the
documents.

**D8. Explicit cache breakpoint in the section writer. Decided; verified live
2026-10-30 (`experiments/cache-breakpoint-test.md`, 96 calls on both routes, $1.22).**
GPT-5.6 stores the prompt cache at breakpoints; the default places one at the end of
each request, which is why reads only ever land on the end of an earlier request. The
section writer's shared block (tools, system prompt, run message, up to 7.5k tokens) is
never the end of a request, so it is written once per section and never read. Marking
the run message as a text content part with `prompt_cache_breakpoint = {"mode":
"explicit"}` is accepted on both routes (invalid values are rejected with a 400, so the
field is really checked) and makes a second section's first turn read the whole block:
about 7.8k of 8.6k tokens in the test, against 3.8k on direct and 0 on Bedrock without
it. `prompt_cache_options` stays unset: setting it to `explicit` drops the automatic
end-of-request entry that later turns rely on. The prompt text is unchanged; only the
message shape changes.

**S4. Decided (owner, 2026-10-30): the repair request starts with the section's own
first-turn request, for quality as much as for cost. Verified live the same day.** The
test shows the repair reads the whole shared prefix with a different forced
`tool_choice` (all but the last 120 to 130 tokens, both routes), but reads nothing if
the tools list or `parallel_tool_calls` differs. The shape to build, the same for every
section turn and every repair: the same five tools in the same order (the four section
tools plus `emit_repairs`); the same system message; the run message as a text part
carrying the breakpoint; the section task message. Section turns use
`tool_choice = {"type": "allowed_tools", "allowed_tools": {"mode": "required", "tools":
[the four section tools]}}`, which both routes accept and which keeps the loop off the
repair tool without changing the tools list. The repair appends one user message with
the repair instructions and forces `tool_choice` on `emit_repairs`, with
`parallel_tool_calls` set identically to the section turn. The repair therefore sees
the section plan and ledger when it rewrites, which the owner expects to improve the
rewrites. Both requests come from one message builder so the two prompt variants stay
byte-identical. The repair surface is a prompt-shape change: version bump, re-pin,
replay on the fixed questions with the owner's read. Untested and to be pinned by a
test: whether an omitted `parallel_tool_calls` matches an explicit `True` (send it
explicitly on both). In P2.

**D9. One route step per model call site. Decided (owner, 2026-10-29: "each LLM call
site in Policy Atlas should be configurable independently").** Today a step in the
route file can stand for many calls: `synthesis` covers six jobs in
`synthesis_backend.py` (section turns, repair, section planning, block and artefact
summary writing, summary judging, key findings) through one `_synthesis_openai_kwargs()`;
`longlist_judgment` covers about twelve named calls (discover, themes, assign themes,
type, constrain, authority, distinct, shortlist, and the five option-profile calls);
`screen` covers stage 1 (`screen:abstract`) and stage 2 (`screen:full`). After this
slice the `[steps]` table lists every named model call once, with the trace name as the
step name's basis, each with a default tier; with D4 each can also carry its own effort.
Tiers stay, so a route is still three lines unless a step is overridden. Calls that must
share a model keep sharing it by convention, not by code: section turns and repair
(D8, the cache), and the adaptive screen vote's two calls. The plan carries the full
inventory (module, call name, new step name, default tier, effort today), as task 053's
plan did for the model constants. First commit changes no behaviour; a test pins the
resolved model and effort for every step on the committed routes against today's
values. Chat, the agents and the task agents already have one step each.

## Owner decisions at the contract gate (2026-10-29)

- **O1. Decided.** The target is a median under $2 for a standard run. It is a broad
  target, not a strict measurement; lower is better. No p90 rule.
- **O2. Leaning: no frontier tier. The two judgment steps move to the `standard` tier
  (gpt-6.1-terra at `none`); gpt-6.1-sol at `low` is the step-up if the owner's read of
  the scoping fixed question says the longlist got worse.** Today `frontier` is
  gpt-5.6-sol on every route and serves two steps: `task_agent_scoping` (the Options
  scoping task agent's conversation turns, which write the scoping plan) and
  `longlist_judgment` (the longlist's discover, themes, assign-themes, type and
  constrain calls, and the five option-profile calls: potential impact, ambition,
  setting, fold, place sentences). Evidence search never uses the tier. In the nine
  scoping runs measured, these Sol calls were $1.16 to $3.88 per run, 40 to 60% of the
  run. No record in tasks 046, 053 or 055 shows a measurement that these steps need
  Sol: the tier arrived as the scoping branch's environment default and was kept at the
  2026-10-22 three-tier cut. P1 therefore moves them to `standard` as a step exception
  on each route; the `frontier` tier stays in the file naming gpt-6.1-sol with the knob
  `gpt-6.1-sol = "low"`, so stepping up is a one-line change. Both call sites use
  structured output, which gpt-6.1-sol accepts at `low`.
- **O3. Decided (owner, 2026-10-29): the judge moves to gpt-6.1-terra with P1 and the
  prompts are refined for it.** The adjudication of the 20 disputed rejections
  (`experiments/summary-judge-adjudication.md`, one reader, not a human label) found 7
  real faults the old judge had passed, 9 defensible strict calls and 4 over-strict ones;
  the new judge's stated reason matched the fault in all 16 non-faithful items. Twelve
  of the 20 follow one pattern: a "no source found" gap reworded as a fact ("England
  lacks NEET trends"). So the new judge is mostly right, and the prompts leave five
  rules open: what wording keeps a gap's status, whether a qualifier may be dropped,
  whether "leads with" means clause order or main point, whether annotation labels must
  survive, and "be strict" against "would mislead a reader". P1 therefore refines the judge prompt and the two summary writer prompts (section
  block summary and artefact summary, `summary_prompts.py`) **in tandem, as one loop**
  (owner, 2026-10-29: they interact, so they are changed together). The writer prompts
  state the same gap, qualifier and emphasis rules the judge checks; the writer prompt's
  200-character cap and vocabulary ban push it to drop scope words, so without the
  shared rule the stricter judge would retry and drop more summaries. Prompt-bearing,
  lead-only, version bumps, re-pin. The loop's measures: zero corrupted summaries pass
  on the 90-item replay set; the 20 adjudicated items re-run; and the first-attempt pass
  rate of freshly written summaries on the fixed questions goes up, not down (fewer
  retries is the cost gain). No move to the `fast` tier.
- **O4. Decided.** Ingest latency work (N8) is in this slice, as the last phase.
- **O5. Fixed questions. Leaning, after the owner asked for one question outside the
  intervention and social-policy shape.** Evidence search at standard depth, one from
  each of three of the real user-question categories: "What interventions reduce the
  number of young people aged 16 to 24 who are not in education, employment or training
  (NEET) in England?" (intervention) · "What is the effect of zonal electricity pricing
  on energy bills and energy security?" (impact, energy economics) · "What works to reduce
  childhood obesity?" (the most-run local question, so earlier reports exist to compare).
  Options scoping: "How do we reduce the potential economic disruption to the labour
  market caused by the rise in AI?". Each is run fresh as a new task so the before and
  after runs share nothing.

## Tidy-ups folded into P0 (owner, 2026-10-30; hygiene sweep in `experiments/repo-hygiene-sweep.md` when it lands)

- **`synthesis/synthesis_prompts_v6.py`.** A frozen copy of the task 022 section prompt
  kept so a cost-harness "legacy arm" could be replayed; selected only by
  `OpenAISynthesisBackend(prompt_variant="v6")`, which no product path sets, and imported
  by one test. Delete the module, the `prompt_variant` switch and the test's use of it.
  The v6 text stays in git history. No version numbers in module names.
- **`evidence_search/clustering_engine.py`.** A generic two-stage clustering engine
  (discover labels, assign in validated batches) used by Evidence search characterise and
  group and by Options scoping longlist and theme. It is the only module at the package
  root and it is not specific to Evidence search, so it moves to `core/clustering_engine.py`;
  five import lines and their tests change.
- From the sweep (`experiments/repo-hygiene-sweep.md`): move the clustering engine's test
  to `tests/core/` and fix the stale path in
  `docs/knowledge/two-stage-clustering-closes-partition-cliff.md`; rename
  `tests/evidence_search/sourcing/test_ingest.py` to `test_ingest_upload.py` and
  `tests/options_scoping/test_longlist_coverage_046.py` to `test_coverage.py`; rename
  `extract/extract_interventions_prompt.py` to `interventions_prompt.py` and
  `options_scoping/theme/longlist_theme_prompt.py` to `theme_prompt.py` (both hash-pinned;
  re-pin, text unchanged); fix two stale docstrings (`screening_backend.py` names
  `screen_v2`; `options_scoping/model_calls.py` claims every scoping step). No behaviour
  change; `make verify` green is the whole check.
- Owner answers on the sweep (2026-10-30): the eval-only `V2SearchGenerationBackend`
  class stays as is; the finished rename scripts (`scripts/rename_038.py`, `rename_044.py`,
  `rename_engine.py`, their three tests) and `scripts/evals/search/experiments/probe_051.py`
  are deleted (git history keeps them); the underscore-private router helpers
  `api/routers/_access.py` and `_common.py`, imported from `runtime` and elsewhere, get
  public names (`api/access.py`, `api/router_common.py`) with their imports updated; the
  `readmodels` / `read_models` and `checkin_read` / `check_ins` spelling drift in `api` is
  settled on one spelling, about 20 imports. `options_scoping/longlist/longlist_backend.py` moves to
  `options_scoping/scoping_backend.py` (the walk's shared model seam, beside
  `model_calls.py`), and `options_scoping/longlist/lever_types.py` moves to
  `options_scoping/option_profile/lever_types.py` (owner, 2026-10-30); imports and tests
  follow, no behaviour change. The dependency-direction knots (core
  importing a capability, scoping and api read models reaching into each other) go to
  `docs/deferred.md` as one entry each.

## From the deferred log (sweep 2026-10-30, `experiments/deferred-sweep-056.md`)

The log's § System-level cost and latency was routed to this task by the owner on
2026-09-28, and several other entries touch it. Tiny items are folded above (the hash
guard include list, the rubric version bump, the Bedrock quota check, the ingest
semaphore test, and three wording corrections). The rest are the owner's call:

| # | Entry | Lean | Size |
|---|---|---|---|
| X1 | Grounding judge replay on gpt-6-luna before P1 ships: it moves with the `fast` tier unmeasured, and a stricter judge means more repairs. Hand-read every flipped verdict, as the summary-judge experiment did. | **In (owner, 2026-10-30): P1, with prompt refinement if the read asks for it.** | Small; under $1 of calls. |
| X2 | The summary regenerate resends an identical seed with no judge feedback. Give the retry the judge's reason. (The product sets no temperature anywhere; the deferred log's "byte-identical" wording assumed determinism the model does not promise, but the lever is the same.) | **In (owner, 2026-10-30): part of the O3 loop, whose aim is also stated now: the summary judge rejects only summaries that would mislead a reader, not qualifier or clause-order nitpicks, so it becomes less strict overall while still passing no corrupted summary.** | Small, prompt-bearing. |
| X3 | The section writer's `lookup` tool lists `characterisation_summary` as a kind on every run; the scoping baseline runs no characterise step, so each attempt fails with "requires characterisation" (`synthesis_tools.py`), 4 to 7 wasted tool calls per baseline (046 item 24). List only the lookup kinds the run can serve. | **In (owner, 2026-10-30): beside S4.** | Small; re-pin of the tool description. |
| X4 | Replay the 046 tuning set for `extract_interventions` and the option-profile folding calls on gpt-6-luna; 046's measures M15 to M17 were accepted unmet and the model tier was named as the next lever. | **In (owner, 2026-10-30): P1 measurement; prompt work only if it fails.** | Small to medium. |
| X5 | Run the grounding judge for section N while section N+1 reads (about 25 s per baseline, more on a seven-section report). | **In (owner, 2026-10-30): last of P5.** | Medium; orchestration inside synthesise. |
| X6 | Option-search query variants and fallback ladder, the screen memo across scopes, and the two bounded loops (046 items 21, L1, L3). | **Out (owner, 2026-10-30).** | Medium each. |
| X7 | In Options scoping, the shortlist proposal step builds the text of every included option's card (the same card the user sees on the longlist, from the same read model) to show the model. It calls the read model once per option, and each call re-reads the task-wide data, so a 40-option list makes several hundred database queries before one model call: 9 to 27 s per proposal, a delay the user has not yet noticed (055). A batch reader would read the task-wide data once. | **Out (owner, 2026-10-30).** | Medium. |
| X8 | Gather/writer model split (head of the post-eval cost queue). Still pinned post-eval; D8 and S4 make it costlier (the cache is per model, so a separate gather model loses the shared prefix); D9 gives it no switch because read and write turns share one step. | **Moved to the synthesis refinement task (owner, 2026-10-30; may be dropped there).** | n/a |

Close-out updates the log: the "Langfuse costs ignore prompt-cache hits" entry (the read
half was fixed in `core/usage.py` on 2026-09-18 but never recorded; N1 closes the write
half; a new entry records deleting the custom GPT price rows when Langfuse is upgraded);
the Bedrock routes entry's "Langfuse pricing for the Bedrock model ids" line (done
2026-10-29); the Unknown-resolution, rubric-version, counting, unappraised-chunk and
citable-bar entries for D7 and S1 to S3; the repair "micro-call, no transcript resend"
wording for S4; the cross-task snapshot reuse entry for S6 (amended, not duplicated); and
an in-or-out line for every entry in § System-level cost and latency.

## Scope / Out of scope

- **In:** `core/openai_client.py`, `core/usage.py`, `core/tracing.py` (usage keys),
  `core/model_routes.py` and `model_routes.toml`, the one-shot call sites named in N3,
  `synthesise.py` and `synthesis_backend.py` for N4 to N6, `scripts/` (cost per run),
  `ingest_full_text.py` and `fetch_live.py` for N8, tests beside each, `docs/deferred.md`,
  one ADR, `.env.example` if a variable changes.
- **Out:** every other capability; the emit schema and span binder; prompt text outside
  P4's repair template; the Langfuse deployment; `infra/` (no config value changes: the
  routes keep their names); the database schema; the frontend.

## Constraints & approval gates

- **Runtime egress.** Changing which model the product calls is a change to the inference
  route. The owner approves the model set (D2, O2) at this contract gate. The endpoints,
  keys and data-residency profiles do not change.
- **Production config.** None. `infra/pa_config.json` keeps `bedrock` for staging and
  `openai-direct` for production; the route file carries the models.
- **Dependencies, schema, auth, CI, public interfaces, scaffold.** None.
- **Prompt hashes.** The guard is name-based and does not cover `synthesis_backend.py`
  (the section system prompt, the repair template) or `finding_vetter.py` (deferred.md
  § Prompt-hash guard is name-based). P0 adds both to the guard's `EXTRA_FILES` and
  re-pins, so every later prompt change in this slice is seen. P1 re-pins the two
  summary prompts (O3) and `classify_prompt.py` (its effort constant moves to the route
  file, D4; the diff shows only that line). P2 and S4 re-pin `synthesis_backend.py` for
  the repair request shape. P4 re-pins the repair template. If any other pinned file changes, the slice stops and says why.
- **Tests stay offline.** Stubs return the usage shape with cache-write counts so the
  mapping is tested without a provider.

## Public / private boundary

Committable: code, tests, the route file, the cost script, this folder's documents with
numbers. Private: Langfuse keys, provider keys, the fixed questions' report text if it
quotes documents (verification cites session ids and totals, not report bodies), probe
outputs that include document text.

## Model route

All of it. The slice's first substantive change is the model set (D2). Reasoning effort
stays in the route file. No prompt-bearing change except P4's repair template.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no label/type/flag that doesn't change v3.0 behaviour.
- **Flag, don't drop** — below-bar / weakly-grounded material is flagged, never hidden.
- **Honest absence** — any gap/coverage claim carries its base.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md), not silent omissions.
- **Measure before and after, one lever at a time.** A phase that is not measured is not done. The target (O1) is a median, read as a broad target.

## Stop conditions

Halt and escalate when: a gate above is hit; a phase's measurement shows cost up or the
owner's read shows a quality drop (revert that phase, record it, continue to the next);
a GPT-6 model refuses a request shape a call site needs; scope would grow past this
slice (for example the emit schema); the turn or token budget is spent.

## Acceptance checks

- `make verify` green at the build-open baseline, after P1, and at the step-6 exit;
  `make verify-fast` between the other phases. `make prompt-guard` green at every commit.
- Deterministic tests: usage mapping with cache-write tokens; `openai_kwargs` one-shot
  shape; route loader with the per-step effort form; N4's retrieval filter; N5's repair
  message shape.
- Manual: the fixed questions run before P1 and after each phase on the `bedrock` route
  (dev machine, Bedrock key), cost per run from the script, the owner's read recorded.
- Live check scope: the fixed questions only. No full live end-to-end beyond them.

## Verification evidence expected

In `verification.md`: the before-and-after cost table per phase per fixed question; the
cache read and write shares per call name before and after P2; the owner's read notes
per phase; the diff of any re-pinned prompt module; the exact commands run; the list of
anything reverted and why.

## Risk tier & review focus

**Tier 3.** The slice changes the models the running product calls (runtime egress) and
edits shared Evidence search components that every capability runs through. No schema,
auth or dependency change. Review: contract verifier, code and security review, one
adversarial pass at contract and plan, human deep review of the model set and the
measurements. Focus: that no prompt text moved unnoticed, that caching off is applied
only to true one-shot sites, that the measurements are read from saved results and not
inferred, and scope creep into the synthesis refinement task.
