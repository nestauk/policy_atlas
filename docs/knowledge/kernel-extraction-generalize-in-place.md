---
type: Convention
title: Reusing an agent loop = generalize it in place, not move it
description: run_section_loop was already the tool-loop kernel — 029 extracted it by parameterising the emission key, injecting the turn function, and labelling the emit tool, leaving a byte-identical section adapter. No module move, synthesis suite untouched.
tags: [tool-loop, kernel, synthesis, chat, refactoring, reuse]
timestamp: 2026-08-11
---

# Rule

When a second surface needs an existing agent loop, prefer the 029 shape:
keep the loop where it lives (`synthesis_tools.run_tool_loop`), parameterise
exactly what differs (emission key · injected turn fn · emit label), and prove
the incumbent caller unchanged (the section adapter compiled byte-identical;
the synthesis suite ran untouched). The new caller (chat) brings its own final-
emission adapter.

# Why

The obvious alternative — lift the loop into a new shared module — churns every
synthesis import and its test pins for zero behaviour. The 029 Codex
adversarial lane specifically hunted the extraction for behaviour drift and
found none, which is the property this shape buys: reviewability of "nothing
changed for the incumbent".

# Watch out

The extraction's tool allowlist is per-call-site: pin the mapping actually
handed to `run_tool_loop` at each site (the 029 stack added that test after
finding the allowlist test pinned only the shared builder — a synthesis-driven
fourth tool would have passed the chat surface's security test).
