---
type: Convention
title: The generated SSE frame union forces reducer coverage at regen time — land no-op cases in the schema phase
description: Because the frontend reducer switches exhaustively over the generated frame union, regenerating the client after adding SSE event types fails the typecheck until the reducer names the new cases; the B-phase regen left explicit no-op cases for D.1 to fill — additive SSE work gets a compile-time to-do list instead of silently dropped frames.
tags: [sse, codegen, reducer, typescript, exhaustiveness]
timestamp: 2026-07-29
---

# Rule

When adding SSE event types: regenerate the client in the same phase as the
backend change and let the reducer's exhaustive switch fail the typecheck,
then land **explicit no-op cases** (comment: which later phase fills them).
The union, not a runbook, carries the to-do — a frame type can't reach the
store unhandled, and the filling phase gets a compiler-enforced checklist.

027 shipped instance: phase B added the three `artefact.*` frames and no-op
reducer cases; phase D.1 replaced them with the liveSections logic.

# Why

The alternative default-case reducer silently ignores new frames — the bug
shape is invisible until someone wonders why the live view never updates.
Exhaustiveness moves that discovery to `pnpm typecheck`.
