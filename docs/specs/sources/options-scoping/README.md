---
type: Frozen design source
title: Options scoping — concept and wireframes (2026-09-03; boards redrawn 2026-09-07/08)
description: The frozen origin for the options-scoping capability — the owner-agreed concept with its rulings (1–44), and the wireframe canvas, redrawn to those rulings on 2026-09-07.
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
| [options-scoping-concept.md](options-scoping-concept.md) | The concept agreed with the owner on 2026-09-01/02, the fourteen wireframe-round rulings of 2026-09-03 and the review-round rulings 15–44 of 2026-09-07 and the board-refinement rulings 45–47 of 2026-09-08. | The canonical statement of intent and rulings; the spec distils it. Its last section wins over its earlier sections where they differ. |
| [options-scoping-wireframes.html](options-scoping-wireframes.html) | The wireframe canvas as a bundled, viewable page (the same content as the live canvas linked from the concept). | Product intent only: screens, copy, states and interaction patterns. Never a schema or contract source. |
| [boards/](boards/) | The readable source of every board on the canvas — one `.dc.html` per board plus `canvas.json` for layout and titles. | Read these rather than the bundled page. Each board is plain HTML with inline styles. |

## How to read the canvas

The bundled page carries the canvas editor and is not readable as HTML. The boards are.
`canvas.json` lists them in journey order with their titles; the journey page holds the numbered
boards and the second page holds two structural alternatives and one behaviour sketch.

The journey, by board title:

1. Ask: job and depth, no default depth · 2. Plan, agreed in dialogue, in the Agent tab · 3. Baseline,
with what is contested; the run pauses · 4. Longlist, list view (and 4b, an option before assessment
with its source-quality profile) · 3c. Report, provisional: the Result from the longlist stage ·
5. Longlist, grid view: rows are primary lever types · 5b. Longlist, shortlist view · 6. Report,
assessed: the Result, one verdict strip per option · 6b. Sources: the Evidence search Sources component
· 6c. Longlist, shortlist view after assessment: the comparison table · 7. Option profile, every
section open (7b after a full evidence search, the child task's report shown in place; 7c the child
task's Sources tab; 7d the tasks list) · 8. Sense-check one option, rapid.

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

**Review round, 2026-09-07.** An adversarial product review led to the concept's last sections
("Review-round rulings" and "Pass-3 rulings", rulings 15–44). The boards were **redrawn to those
rulings on 2026-09-07** at the owner's direction: the task's tabs (Agent · Result · Sources · Share ·
History) with the plan in the Agent tab; the report as the Result, in a provisional form from the
longlist stage (3c) and an assessed form (6), with Baseline and Longlist as working views; a variant
option with its own search; three kinds of constraint, the evidence-scope kind never excluding an
option; a source-quality profile per option before assessment, never "how sure"; grid rows as primary
lever types with ambition as a tag "as described, not measured"; the proposal as a provisional
allocation of reading effort; the do-nothing band as the situation the options would change; each
effect with its own comparator, population and period; transferability from three context sources
with the weakest leg deciding and no factor fractions; Sources stating what was read at which depth,
set aside and not read under the cap; the sense-check as a rapid entry branch with questions to put to
the department. Page 2's structural alternatives are kept for reference and marked superseded. Where
a board and a ruling still differ, the ruling wins.

**Board refinement, 2026-09-08.** Three further rulings (45–47) came from reviewing the redrawn
boards: the report stays linear, with one verdict strip per option and the comparison table as the
shortlist view after assessment (new board 6c); the Sources tab is the Evidence search's Sources
component with scoping's read-depth and set-aside statuses; and after a full evidence search there is
one document, the child task's report shown in place as the profile, with the child task adding its
plan, Sources and History. Boards 6, 6b, 7b and 7c were redrawn to match.
