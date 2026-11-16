---
type: Convention
title: Define the cost-per-run basis before setting a target; the traced figure is a floor
description: "Cost per run" is the session total (every model call, embeddings and the Task Agent's planning turns included) at list prices from token counts; it is a floor because a request that completes after the client timeout is billed but never traced; small levers are judged per call name, whole runs judge a switch.
tags: [cost, langfuse, measurement, embeddings, "056"]
timestamp: 2026-11-02
---

# Rule

- **Basis first.** Cost per run means the Langfuse **session** total: every model call in the
  session, embeddings and the Task Agent's planning turns included, priced from token counts at
  list prices (never from Langfuse's stored cost). Say which basis a figure uses; the
  `run:*`-traces-only total is 5 to 10% lower.
- **It is a floor.** A request that completes at the provider after the client's timeout is
  billed, retried by the SDK and never reaches Langfuse, so the traced total misses the
  abandoned attempts. With 1 to 3% of calls stalling, the gap is a few percent of a run.
- **Levers of 3 to 5% are judged per call name**, on the sites they touch, with reads of the
  saved results; the run-to-run spread (corpus size moves a session by about ±$0.10) hides them
  in whole-run totals. Whole runs judge a model switch.
- **Embedding is a model line.** On the `bedrock` route (Cohere, priced as input) embedding is
  the largest non-generation line (21 to 30% of a run) and dominates the ingest stage's wall
  clock with rate-limit sleeps; a parse speed-up shows mostly on `openai-direct`.

# Why

Task 056's contract set a $2 target against a baseline table that left embeddings and planning
turns out; the first runs with the full basis measured $2.68, not $2.12. The review stack's
Codex and security lanes converged on the floor caveat. The per-call-name method found the
breakpoint-mode gap (the product sent the breakpoint without the explicit-mode body, so
`screen:full` still wrote 100% of its input) that whole-run totals had hidden. Related:
[Langfuse usage buckets](langfuse-usage-buckets-are-exclusive.md).
