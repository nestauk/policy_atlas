---
type: Integration quirk
title: Langfuse usage buckets are exclusive; send one usage shape, read usageDetails
description: Langfuse maps the OpenAI usage shape server-side into exclusive buckets (input_cached_tokens, input_cache_write_tokens, output_reasoning_tokens) and forwards usage_details untouched, so sending both shapes double counts; the older usage field stays inclusive and totalCost is null.
tags: [langfuse, tracing, cost, usage, "056"]
timestamp: 2026-11-02
---

# Rule

A generation sends **one** usage shape. Either the provider's OpenAI-format `usage` object,
which Langfuse maps server-side into exclusive buckets (`input`, `input_cached_tokens`,
`input_cache_write_tokens`, `output`, `output_reasoning_tokens`), or a hand-built
`usage_details` dict, which the SDK forwards untouched. Sending both counts the cached and
reasoning tokens twice. Read costs and counts back from `usageDetails` and `costDetails`; the
older `usage` field is inclusive (`input` holds the cached tokens too) and `totalCost` is null
on our instance.

Two shapes to know:

- The OpenAI Python SDK's `PromptTokensDetails` does not declare `cache_write_tokens`; the
  value survives only because the SDK's models allow extra fields. Read it with `getattr`, and
  expect a future SDK to keep or drop it without notice.
- The observations API on our self-hosted instance has only the v1 list endpoint; pulling one
  session's generations takes about 40 s, so a 20-session comparison is a 25-minute job.
  `scripts/cost_per_run.py` saves what it pulls.

# Why

Task 056 added the cache-write and reasoning buckets (contract N1) so the 1.25x write charge
became visible: the first runs with the bucket showed section turns writing 62% of their input
to the cache and `extract_interventions` writing 99%. The double-count risk was found while
wiring the buckets (`core/usage.py`, `test_usage.py`); the `totalCost`-is-null and v1-only
facts came from building the cost script against the live instance.
