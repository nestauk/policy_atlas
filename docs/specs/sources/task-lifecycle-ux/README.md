---
type: Frozen design source
title: Task lifecycle UX prototype (2026-08-17)
description: The owner's clickable prototype for the task-lifecycle IA — the design reference for task 032.
tags: [source, ux, frozen]
timestamp: 2026-08-17
---

# Task lifecycle UX prototype

`task-lifecycle-prototype.html` is the owner's clickable prototype, supplied
2026-08-17. It is the design reference for task
[032-task-lifecycle-ia](../../../tasks/032-task-lifecycle-ia/contract.md).

**Frozen origin** ([ADR 0002](../../../adr/0002-spec-governance.md)). Do not edit
it. If the design needs to change, change the spec or the task contract.

## How to read it

The file is a bundled artifact, not readable HTML. The component source is
gzipped base64 inside the page. To get at it:

1. Read `<script type="__bundler/template">` — it holds a JSON-encoded string
   containing the actual page.
2. Inside that page, the `<x-dc>` element holds the markup template and the
   `<script type="text/x-dc" data-dc-script>` block holds the component logic
   (about 1,600 lines).
3. `<script type="__bundler/manifest">` holds the runtime and the fonts, which
   are not needed for reading the design.

## What it is and is not

It is a picture of the intended shape: the workspace level (new task, tasks,
projects), the task lifecycle (plan, results, sources, share, history), and the
supporting overlays (source drawer, report chat, task finder, download menu).

It is **not** a contract. It contains invented content the backend does not
produce — most importantly the case-study cards and an "authors" line on the
report. The task contract's § Reading the prototype records which of its outputs
are deliberately not built, and why.
