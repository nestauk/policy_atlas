---
type: Testing rule
title: A prompt-cache measurement isolates every block with a nonce, because timed-out requests still store
description: Replaying stored requests against the provider to compare cache modes needs a nonce in the system prompt per site-and-mode block; a request that times out client-side still completes and stores its prompt at the provider, so the retry reads it and makes the mode look cheap.
tags: [caching, measurement, langfuse, openai, bedrock, "056"]
timestamp: 2026-11-02
---

# Rule

When replaying stored requests to measure prompt caching (reads, writes, cost by mode):

1. **Isolate every block.** Put a nonce in the system prompt of each site-and-mode block, so
   no block can read what another stored. Without it, `off` reads what `auto` wrote a minute
   before and every mode looks the same.
2. **Count only first-time successes.** A request that hangs to the client timeout still
   completes at the provider and stores its prompt; the retry reads it. Items that needed a
   retry in any mode are excluded from the comparison.
3. **Send what the product sends.** A measurement harness that adds the explicit-mode body
   while the product sends the breakpoint alone measures a different request (task 056's
   first final run: `screen:full` still wrote 100% under the product's "breakpoint").
4. **Judge per call name, with a Bedrock confirmation.** Bedrock reports reads where OpenAI
   direct reports writes for the same request shape; one pass on each.

# Why

Task 056's first per-site pass (ten stored requests per site, three modes) was unreadable:
64 attempts hung to the 600 s timeout and completed server-side, so the retries read what
the hung attempts had stored. The second pass with a nonce per block and first-time-only
items gave a clean answer (`breakpoint` never worse than `off` or `auto` at any site).
Related: [omitted effort and GPT-6 shapes](reasoning-effort-omitted-is-medium-gpt6-shapes.md).
