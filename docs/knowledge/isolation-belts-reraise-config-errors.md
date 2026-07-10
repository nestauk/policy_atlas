---
type: Convention
title: Per-item exception-isolation belts must re-raise configuration errors first
description: A blanket except Exception belt that turns failures into reason-coded rows must re-raise configuration-class errors before catching, or a systemic misconfiguration masquerades as N ordinary per-item failures with the component reporting green.
tags: [convention, error-handling, ingest, "016"]
timestamp: 2026-07-10
---

# Rule

A per-item exception-isolation belt (`except Exception` → reason-coded row,
component stays green) must re-raise configuration-class errors *before* its
catch-all, or a systemic misconfiguration masquerades as N ordinary per-item
failures. Enumerate the specific config-error types the belt re-raises
explicitly (see `ingest_full_text.py::_safe_fetch`), and pin the loud path
through the **real pipeline entry point** — not just a direct unit call,
since a unit-level raise test proves nothing about the belt sitting above it
in the actual call chain.

# Why

The 016 review stack (code-review lane, CONFIRMED) found that `_safe_fetch`'s
blanket catch swallowed `FixtureFetcher`'s fail-loud `FileNotFoundError`
(raised when the fixture corpus is missing) into per-document `fetch_error`
rows. A run over a missing corpus exited green, with every single document
marked "unreachable" — indistinguishable from real per-document fetch
failures, when the actual cause was a missing corpus one directory up. The
existing unit test that asserted the raise happened at the unit level and
never proved anything about what the belt above it did with that exception.

See also [[per-doc-fanout-isolates-decision-call]] (the isolation-boundary
placement this belt sits inside) and [[fail-loud-before-first-write]] (the
sibling fail-loud convention for the write path).
