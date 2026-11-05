---
type: Convention
title: A model client's timeout is sized to that step's healthy tail, not to the model
description: One to three percent of model calls stall at the provider until the client timeout and then succeed on retry, on both routes and both model generations; the per-client timeout sets what a stall costs, so size it per step from the measured healthy tail, keep the SDK retry, and remember retried attempts are billed and untraced.
tags: [latency, timeouts, retries, openai, bedrock, "056", "057"]
timestamp: 2026-11-03
---

# Rule

- **Stalls are normal.** 1 to 3% of calls at every stage sit at the provider until the
  client's timeout and finish in seconds on retry (measured on gpt-5.6 and GPT-6, OpenAI direct
  and Bedrock). The model is not slow; the timeout decides the cost: a 300 s timeout on a
  5 s call parks a worker for ten minutes per stall.
- **Size per step from the healthy tail.** Measure the step's healthy latencies from stored
  calls and set the client timeout above the tail, not a round number: 60 s covered every
  healthy classify, screen, agent-turn, vetter and search-generation call measured (3 to 37 s).
- **Long-output steps get their own number.** A step that may emit tens of thousands of
  output tokens (the IOF and ICF extractors, the finding vetters) has a healthy tail of
  its own: stored calls reached 67 to 71 s. A timeout below the healthy tail fails the call
  three times in a row and the document loses its findings; measure before cutting.
- **Keep the retry, count its cost.** The SDK's two retries turn a stall into a minute's
  delay; the abandoned attempt completes server-side and is billed but never traced
  ([cost basis](cost-per-run-basis-before-target.md)). *057:* the SDK retries are off
  (`max_retries=0`) and each attempt is its own traced generation, up to three: a
  stall-then-stall on one step (4 to 6% per judge call at low effort) lost a synthesise
  attempt in most rounds under one retry, and the third attempt costs at most one more
  timeout.
- **Derive at the width the step runs at, and floor it.** Timeouts derived from p99s at
  width 12 cut 47 `screen_abstract` calls in one minute at width 48 with a 7 s timeout; a
  burst probe showed the extra time is the client opening 48 TLS connections at once (3 s
  each), not the model (the server wait was the same at both widths). The owner's floor is
  15 s and every value is 2 × the healthy p99 from at least 30 traced calls, rounded up to
  5 s; the derivation script takes `--min-n`, `--floor`, `--round-to`.
- **A failed attempt must carry its input.** The generation of a cut attempt records the
  step, attempt, call id and error; the caller's `update` sets the input on success only, so
  a call cut on every attempt cannot be diagnosed from the trace (long output, long reasoning
  and a stall look the same). Deferred seam: a `before` hook on `traced_attempts`.
- **The stalls are the provider's; do not engineer the client for them.** Two probes at
  the 057 review: every request on a fresh connection (keep-alive off) hung at the same
  rate, and the bare OpenAI SDK with its defaults, no schema and one request at a time
  hung 10 to 17% of judge-sized calls on Bedrock, the same as the pipeline; some hung calls
  returned on their own after 126 to 246 s for a 6 s call. The rate moves with the hour and
  with time in flight (a per-second hazard, so the long steps stall most). AWS documents no
  server timeout for the endpoint; its one documented silent hang (the 350 s idle drop
  behind NAT) cannot reach a pool that closes idle connections at 5 s. Cutting at 2 × p99
  and retrying beats waiting. The route to a cause is an AWS support case with request ids,
  not more client code (`docs/tasks/057-queued-ingest/bedrock-integration-brief.md`).
- **On Bedrock `max_completion_tokens` is a quota reservation, so size it from the
  recorded outputs.** Bedrock admits a request only if `input + max_tokens` fits the
  model's tokens-per-minute quota that minute (the 10× output burndown applies at
  settlement). A 48-wide classify burst with a 16,384 cap reserved a quarter of Luna's
  4,000,000 for answers of a few hundred tokens. Set each step's cap from Langfuse's
  `usage.output` (reasoning tokens included) with headroom above the max seen: screen
  2,048 (max 1,608 over 7,763 calls), classify 8,192 (max 3,610). Refresh the 056
  call-site fixture deliberately (`CALL_SITE_KWARGS_UPDATE=1`) when a cap changes.

# Why

Task 056's scoping run spent 38 minutes in `extract_interventions` whose median call took
5 s: 23 of 211 calls stalled to the 300 s timeout. Cutting the three extraction clients to
60 s took the stage to 229 s; the owner then reviewed every client against the measured
tails. The contract verifier at review flagged that the long-output extractors were never
measured on the fixed questions (standard depth has no extract stage), and a Langfuse pull of
their stored calls gave the 67 to 71 s tail above.
