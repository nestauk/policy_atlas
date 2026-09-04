---
type: Frozen design source
title: Options scoping — concept and wireframes (2026-09-03)
description: The frozen origin for the options-scoping capability — the owner-agreed concept with its rulings, and the wireframe canvas the rulings were made on.
tags: [source, options-scoping, ux, frozen]
timestamp: 2026-09-04
---

# Options scoping — concept and wireframes

This folder is the **frozen origin** for the options-scoping capability
([ADR 0002](../../../adr/0002-spec-governance.md)). The declarative spec distilled from it is
[../../capabilities/options-scoping/](../../capabilities/options-scoping/capability.md). Do not
edit these files; if the design needs to change, change the spec or the task contract and
record the decision.

## Contents

| File | What it is | How to use it |
|---|---|---|
| [options-scoping-concept.md](options-scoping-concept.md) | The concept agreed with the owner on 2026-09-01/02 and the fourteen wireframe-round rulings of 2026-09-03. | The canonical statement of intent and rulings; the spec distils it. Its last section wins over its earlier sections where they differ. |
| [options-scoping-wireframes.html](options-scoping-wireframes.html) | The wireframe canvas as a bundled, viewable page (the same content as the live canvas linked from the concept). | Product intent only: screens, copy, states and interaction patterns. Never a schema or contract source. |
| [boards/](boards/) | The readable source of every board on the canvas — one `.dc.html` per board plus `canvas.json` for layout and titles. | Read these rather than the bundled page. Each board is plain HTML with inline styles. |

## How to read the canvas

The bundled page carries the canvas editor and is not readable as HTML. The boards are.
`canvas.json` lists them in journey order with their titles; the journey page holds the numbered
boards and the second page holds two structural alternatives and one behaviour sketch.

The journey, by board title:

1. Ask · 2. Plan, agreed in dialogue · 3. Baseline, the run pauses for plan confirmation ·
4. Longlist, list view (and 4b, an option before assessment) · 5. Longlist, grid view (and 5b,
the shortlist before assessment) · 6. Shortlist, assessed, with the summary above the table ·
6b. Sources, what was searched · 7. Option profile, every section open (7b after a full evidence
search; 7c the full report as an evidence-base task; 7d the tasks list) · 8. Sense-check one
option, rapid.

The sample question throughout is reducing the number of 16 to 24 year olds who are not in
education, employment or training. **Every figure, study count, quotation and named source on
the boards is placeholder sample data.** Nothing on them is a finding.

## What it is and is not

It is a picture of the intended shape: the conversation as the spine, the evidence-base task's
navigation, the three depths of evidence work, the longlist and shortlist as one list at
different stages, and the outputs written as linear text in the evidence-base report's design
language.

It is **not** a contract. It contains outputs the backend does not yet produce, invented
numbers, and chat turns written to show behaviour rather than transcribed from a run. Where a
board and the concept's rulings differ, the rulings win.
