---
type: Convention
title: A model client's timeout is sized to that step's healthy tail, not to the model
description: One to three percent of model calls stall at the provider until the client timeout and then succeed on retry, on both routes and both model generations; the per-client timeout sets what a stall costs, so size it per step from the measured healthy tail, keep the SDK retry, and remember retried attempts are billed and untraced.
tags: [latency, timeouts, retries, openai, bedrock, "056"]
timestamp: 2026-11-02
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
  ([cost basis](cost-per-run-basis-before-target.md)).

# Why

Task 056's scoping run spent 38 minutes in `extract_interventions` whose median call took
5 s: 23 of 211 calls stalled to the 300 s timeout. Cutting the three extraction clients to
60 s took the stage to 229 s; the owner then reviewed every client against the measured
tails. The contract verifier at review flagged that the long-output extractors were never
measured on the fixed questions (standard depth has no extract stage), and a Langfuse pull of
their stored calls gave the 67 to 71 s tail above.
