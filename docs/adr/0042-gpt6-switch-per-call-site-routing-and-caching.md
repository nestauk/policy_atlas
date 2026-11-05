# ADR 0042 — The GPT-6 generation, one route step per model call, deliberate caching, and an Unrated appraisal

- **Status:** Accepted — 2026-11-02 (Shabeer Rauf, owner, task 056 plan gate).
- **Date:** 2026-10-30; accepted 2026-11-02
- **Task:** [056-cost-latency](../tasks/056-cost-latency/contract.md)
- **Builds on:** [ADR 0041](0041-bedrock-inference-route-and-model-route-file.md) (the
  route file and its three layers) · [ADR 0015](0015-prose-first-section-emission.md)
  (claims verified against frozen text, flag-not-drop) ·
  [prompting.md](../specs/system/prompting.md) rule 12 and § Provider-specific.

## Context

A standard-depth Evidence search run cost a median of $2.12 in late October 2026
(six runs, $1.60 to $4.88), with the writer's model, GPT-5.6 Terra, carrying 55 to 75% of
it. The owner set a broad target of a median under $2 and a sequence: measure, switch
model generation first, then take the cheap levers, with the owner's own read of four fixed
questions as the only quality guard and no eval harness.

Four facts measured during the design shaped the decisions below. First, OpenAI's GPT-6
models are served from Amazon Bedrock London and from OpenAI direct at roughly half the
price per token of GPT-5.6, and the Terra-class and Luna models accept the request shapes
the code uses (effort `none`, function tools, structured output), while the Sol-class models
refuse `none` and refuse function tools on Chat Completions. Second, the route file's one
step for `synthesis` and one for `longlist_judgment` hid six and twelve call sites
respectively, and the reasoning-effort knob reached only three call sites; the two shared
request paths carry no effort at all, so most steps run at the provider default. Third,
on GPT-5.6 and later, both routes store the prompt cache at breakpoints and charge 1.25x
input to store a prefix on every long call that misses; the default breakpoint sits at the
end of each request, so a section's shared prefix is written once per section and never
read on Bedrock, and about 30% of input volume sits in calls that never repeat. Fourth,
the appraise pass skips documents the classifier could not type, so the writer reads but
cannot cite them, and each such citation triggers a repair pass; those documents are mostly
grey literature the owner wants citable.

## Decisions

1. **The model set moves to the GPT-6 generation on both routes**, by editing the route
   file only: `fast` = gpt-6-luna, `standard` = gpt-6.1-terra, `frontier` = gpt-6.1-sol
   at `low`, which serves the thirteen Options scoping call sites that run on the frontier
   tier today). Those thirteen are moved down per step only after small-scale replays at
   several effort levels, read side by side by the owner (owner, 2026-11-01). No prompt text
   changes with the switch: it is the same model family, so prompting rule 12 does not fire.
   The judge and summariser prompts are refined afterwards, together, because the new writer
   model reads their rules more literally (measured), and that refinement is deliberate
   prompt work with version bumps and replay sets.

2. **Every model call site has its own route step, and reasoning effort is a per-step
   route value.** The `[steps]` table names each call once, after its trace name; a step
   exception may carry a `model` and a `reasoning_effort`. Effort literals leave the code.
   **The default effort is `medium`** (the owner's ruling): steps that sent nothing before
   are written as `medium` explicitly, so the first commit changes no behaviour and a test
   pins today's resolved model and effort for every step. A step moves below medium only on
   a measurement (classify to `medium` from `high` is the first). Sending `none` where
   medium runs today is a behaviour change and is treated as one. Calls that must share a
   model (section turns and repair for the cache; the two screen-vote calls) share a step by
   convention, not by code.

3. **Caching is set per call site through the one request builder**, with three modes:
   `auto` (the provider's default), `off` (explicit mode with no breakpoints, which removes
   the write charge from calls that never repeat), and `breakpoint` (an explicit breakpoint
   after a stable prefix, which lets a repeated prefix be read at the cached price). The
   section writer's step is `auto` in the mode table, with a breakpoint placed by hand on its
   run message in `build_section_prefix`, and the repair request is built
   from the section's own first turn, with the same five tools, `allowed_tools` restricting
   the loop, and `parallel_tool_calls` identical on every turn, so repairs read the
   section's cache. The mode for each other site is chosen by measurement, since several
   "one-shot" sites have system prompts over the 1,024-token threshold that repeat hundreds
   of times per run. The caching option is OpenAI-format-specific and lives in one builder,
   which is what the prompting spec allows. All of this was measured on GPT-5.6 and is
   re-measured on GPT-6 before it is built.

4. **Documents the classifier could not type are appraised as Unrated, not skipped.** The
   appraisal row gets a null score and an `unrated` flag; the 1 to 5 check stays for scored
   rows; selection and steering, which read the score, are unchanged. The documents become
   citable under the existing rule that only appraised evidence is cited, and the writer and
   the reader see the word "Unrated" wherever appraisal is shown. Grounding verdicts are the
   judge's alone and are untouched. This was the owner's choice over a score of 0, which a
   review showed would have been a wider schema and interface change.

5. **Small levers are judged per call name, whole runs judge the switch.** Cost per run is
   computed from token counts and list prices, never from Langfuse's stored cost, and
   Langfuse receives cache-write and reasoning tokens as exclusive usage buckets so the
   write charge is visible. Levers worth 3 to 5% are measured on the call sites they touch,
   because the run-to-run spread hides them.

## Consequences

- One migration (nullable score, relaxed check, `unrated` flag) and one new label in the
  API's strength vocabulary and the frontend copy; the web-api spec gains a stage key for
  full-text reading, the longest stage of a run, which today has no progress row.
- The section writer's prompt text moves into its own pinned module, and four more
  prompt-holding modules join the hash guard's include list; every re-pin in the slice is
  recorded with its diff in verification.md (nine code-only re-pins fell outside the
  contract's list and are decision items at review).
- Rerankers, pointer citations and the emit-schema rewrite stay out: the design-time
  experiments showed reranking adds nothing on today's retrieval and pointers cut writer
  output by 43%, both routed to the synthesis refinement task.
- The queued-parsing task that follows inherits the parse-stage facts: on `openai-direct`
  parsing dominates the ingest stage and the in-process scheduler fix recovers half of it on
  a laptop; on `bedrock` the stage's wall clock is dominated by Cohere embedding with
  rate-limit sleeps (final NEET run: fetch 180 s, parse 89 s, then minutes of embedding), so
  the fix shows less there; the quote failures the writer suffers are mostly parser markup
  and interleaved headers, to be fixed where the text is made.
- Risks accepted by the owner: quality is guarded by the owner's read, not an eval set;
  per-step downgrades from the frontier tier rest on small replays and the owner's read,
  not on an eval set.
