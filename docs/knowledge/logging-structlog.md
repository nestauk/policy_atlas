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

# Citations

- [engineering-considerations.md](../agentic-ops/engineering-considerations.md) §Stack
- [AGENTS.md](../../AGENTS.md)
