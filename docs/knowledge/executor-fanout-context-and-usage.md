---
type: Convention
title: Thread fan-outs submit through copy_context and accumulate usage on the submitting thread
description: tracing.submit_with_context propagates the OTel/Langfuse span context AND structlog bound contextvars in one mechanism (contextvars.copy_context at submit); UsageAccumulator is not thread-safe, so workers return their usage and the submitting thread accumulates in input order.
tags: [threading, langfuse, tracing, structlog, usage, executor]
timestamp: 2026-07-12
---

# Rule

Every traced/LLM call submitted to a `ThreadPoolExecutor` goes through
`tracing.submit_with_context` (`contextvars.copy_context()` at submit). One mechanism
carries **both** telemetry planes: the OTel/Langfuse span context (per-doc generations
nest under the component root instead of minting detached root traces) and structlog's
`bound_contextvars` (`task_id`/`run_id`/`component` on every worker log line).

`UsageAccumulator` is **not** thread-safe. The fan-out pattern that keeps it serial:
workers *return* their usage payloads; the submitting thread accumulates them in input
order (see the finding-vetter parallelization in `extract.py` — workers judge, the
parent applies verdicts and adds usage).

# Why

019 items 4 + 7a composed for free once the submit seam owned context propagation —
copying the context at submit is strictly more general than hand-threading kwargs or
re-binding inside workers. The D1 live run verified the nesting end to end (all five
component traces: 1 root, 0 parentless generations). The usage story exists because
adding a lock inside `UsageAccumulator` would have serialized nothing else and hidden
the ordering question; returning usage keeps accumulation deterministic.

# Watch out

- A new executor call site must use `submit_with_context` — a bare `executor.submit`
  regresses to detached root traces silently (nothing fails; the traces just orphan).
- Parallelizing a loop that touches `UsageAccumulator` means moving the `add` to the
  submitting thread, not locking the accumulator.

# Citations

- `src/policy_atlas/tracing.py` (`submit_with_context`); call sites in `screen.py`,
  `extract.py`, `classify.py`, `characterise.py`
- [019 verification.md § Review findings](../tasks/019-folding-pass/verification.md)
  (live-trace lane: nesting verified on the D1 traces)
