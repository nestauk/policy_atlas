---
type: Convention
title: structlog is the only logger
description: All application logging goes through structlog from the first slice; no print or stdlib logging.
tags: [logging, observability, convention]
timestamp: 2026-06-24
---

# Rule

Every application log call goes through **structlog**. Do not use `print()` or the stdlib `logging`
module directly. Structured JSON output in deployed environments; console-friendly output locally.

# Why

Logs are part of the observability plane and must stay machine-parseable and consistent from the
first scaffold — retrofitting structured logging later is costly, and ad-hoc prints bypass redaction.

# Watch out

Mandatory from the **first** slice onward, not a later hardening step. New modules import the project
logger, never `logging.getLogger` or `print`.

**`configure_logging(cache_logger_on_first_use=True)` and
`structlog.testing.capture_logs()` are mutually exclusive across a test
suite** (033): once any code path configures with caching and a
module-level logger fires, `capture_logs` in *later* tests silently sees
nothing. Symptom: order-dependent failures in suites alphabetically after
the configuring one. The entrypoint config runs with caching off — one
config lookup per call is the price of testability. Related: bare
`capture_logs()` replaces the processor chain, so a test asserting
contextvars-bound keys must pass
`capture_logs(processors=[structlog.contextvars.merge_contextvars])`.

**Binding contextvars from a sync FastAPI dependency does not work** (033
review): FastAPI runs a sync dependency in a worker thread whose context is
a *copy*, so the bind lands where no later code can read it. The dependency
that binds the route template must be `async`; the middleware half
(request id, method) is safe either way.

# Citations

- [engineering-considerations.md](../agentic-ops/engineering-considerations.md) §Stack
- [AGENTS.md](../../AGENTS.md)
