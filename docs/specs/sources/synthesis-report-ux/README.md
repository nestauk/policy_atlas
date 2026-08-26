---
type: Frozen design source
title: Synthesis report UX prototype (2026-08-26)
description: The owner's clickable prototype for the report's Results tab — the design reference for task 034.
tags: [source, ux, frozen]
timestamp: 2026-08-26
---

# Synthesis report UX prototype

`completed-run-prototype.html` is the owner's clickable prototype
(`completed-run.html` in the supplied `nesta-policy-atlas-prototype-main`
bundle, 2026-08-26). Its **Results tab** is the design reference for task
[034-synthesis-report](../../../tasks/034-synthesis-report/contract.md).

**Frozen origin** ([ADR 0002](../../../adr/0002-spec-governance.md)). Do not
edit it. If the design needs to change, change the spec or the task contract.

## How to read it

The file is a bundled artifact, not readable HTML — the same packaging as the
[task-lifecycle prototype](../task-lifecycle-ux/README.md):

1. Read `<script type="__bundler/template">` — a JSON-encoded string holding
   the actual page.
2. Inside that page, the `<x-dc>` element holds the markup template and the
   `<script type="text/x-dc" data-dc-script>` block holds the component logic.
   The Results-tab data lives in the component methods `keyFindings()`,
   `keyFindingsOld()` (the anti-target copy), `countryList()` (case studies),
   `topSources()` / `topSourceCards` (most relevant sources) and
   `sectionList()`.
3. `<script type="__bundler/manifest">` holds the runtime and fonts — not
   needed for reading the design.

## What it is and is not

It is a picture of the intended Results-tab shape: front matter (answer
callout, metadata strip, key findings with bold lead-colon bullets and a
distinct gap bullet, case-study cards, most-relevant-sources cards) ahead of
the collapsed body sections, with References and Method at the foot.

It is **not** a contract, and the task contract deliberately departs from it
in recorded places: no Authors line, no confidence rating, a softer label
than "THE ANSWER", 031's included-based source count wording instead of
"found · cited", and a real heading hierarchy (the prototype's headings are
visually flat). The contract's § Reading the prototype records each
departure and why.

The pasted language samples that accompany the prototype (the "good" target
and the "current" anti-target) live in
[design-inputs.md](../../../tasks/034-synthesis-report/design-inputs.md).
