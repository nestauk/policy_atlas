---
type: Invariant
title: Plan→config compile fails closed
description: An invalid plan is rejected with a pydantic ValidationError at construction, before execution; the harness never runs on it — no silent or partial run.
tags: [plan, compile, invariant, fail-closed]
timestamp: 2026-06-24
---

# Rule

The plan is canonical; the machine config is compiled from it deterministically. A plan that does
not validate raises a pydantic `ValidationError` at construction — **before** execution — so the
LangGraph harness never starts on an invalid plan ("robust by construction": `Config` likewise
cannot be built with invalid values). There is no silent or partial run.

# Why

Plan-as-object means the plan is the source of truth and the compile is "robust by construction."
Failing closed at compile time stops a malformed plan from producing a half-executed, unattributable
run.

# Watch out

Keep the compile **strict** — don't add lenient coercion or defaulting that lets a bad config
through, and don't start the harness before validating. Either would be a regression against this
invariant. Verified by the plan→config compile test (valid compiles; invalid is caught).

# Citations

- [system/plan-as-object.md](../specs/system/plan-as-object.md) (robust compile by construction)
- [001-walking-skeleton/contract.md](../tasks/001-walking-skeleton/contract.md) (plan → config compile)
- [001-walking-skeleton/verification.md](../tasks/001-walking-skeleton/verification.md) (invalid plan rejected at construction; harness never runs)
