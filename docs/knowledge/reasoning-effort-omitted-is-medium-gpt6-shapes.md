---
type: Live behaviour
title: Omitting reasoning_effort equals medium; the GPT-6 request shapes each route accepts
description: On gpt-5.6 and gpt-6 models, both routes, an omitted reasoning_effort behaves as medium (16 paired comparisons, no consistent direction); gpt-6-luna refuses function tools at medium (400), gpt-6.1-sol refuses none; the cache-breakpoint content part needs the explicit-mode body as well.
tags: [models, gpt-6, bedrock, openai, reasoning-effort, caching, "056"]
timestamp: 2026-11-02
---

# Measured (2026-11-02, 236 probe calls, both routes)

- **Omitted effort is `medium`.** Omitted vs explicit `medium`, five calls a side on
  gpt-5.6-luna, gpt-5.6-terra, gpt-6-luna and gpt-6.1-terra, an easy and a hard prompt: no
  consistent direction (lowest p 0.06). Omitted is not `none` (every call reasoned) and not
  `low`. Writing `medium` where nothing was sent changes no behaviour, which is why every route
  step names its effort (task 056 D4).
- **Shapes accepted.** gpt-6-luna structured output at `none`, `low`, `medium`, `high`;
  gpt-6.1-terra structured at `none`, `medium`, `high`, function tools with `none` and
  `parallel_tool_calls=True`, `tool_choice = allowed_tools`, streaming with `include_usage`;
  gpt-6.1-sol structured at `low` and `medium` (it refuses `none`). Reasoning tokens are 0 on
  every `none` call.
- **Shapes refused.** gpt-6-luna with function tools at `medium` (400 on both routes). It was
  not tried with tools at other efforts; no Luna step uses tools.
- **Caching.** The cache-breakpoint content part works on gpt-6.1-terra and gpt-6-luna on
  both routes, but only with `prompt_cache_options: {mode: explicit}` in the body as well:
  the breakpoint alone leaves the provider storing every whole request at the 1.25x surcharge.
  Explicit mode with no breakpoint writes and reads nothing. On Bedrock, `off` stops the write
  being reported but identical calls still read; on OpenAI direct it is a true off.

# Why

Task 056's switch to GPT-6 (contract D2) needed the shapes confirmed before any caching code
(the stop condition of N3). The breakpoint-needs-explicit-mode fact was found on the first
final fixed-question run, not in the probe, because the probe sent both and the product sent
one (commit 12c31228).
