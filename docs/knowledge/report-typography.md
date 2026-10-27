---
type: Frontend rule
title: Report-style pages use the Evidence search report's four text styles and nothing else
description: Any page people read like a report (the ES report, the theory-of-change Result page and its Detailed information, the PDF print) uses the four classes in artefactPresentation.ts — part heading, section heading, body, label — on a white card. One body size, bold only for lead-ins and grades, grey only for metadata and labels. Panels and sheets use the smaller panel scale.
tags: [frontend, typography, report, theory-of-change, task-054, design-system]
timestamp: 2026-10-27
---

# Rule

A page that people read like a report sits on a white card (`bg-paper shadow-sm ring-1
ring-line`, as `ArtefactView`'s `main`) and uses exactly four text styles, all exported from
`frontend/src/views/artefactPresentation.ts`:

| Use | Class | Rendered |
|---|---|---|
| Part heading ("Executive summary", "Full report", "Detailed information") | `REPORT_PART_HEADING_CLASS` | 28px, extra bold, uppercase |
| Section heading ("Key findings", a pathway, "Assumptions") | `REPORT_SECTION_HEADING_CLASS` | 24px, bold |
| All reading text: paragraphs, list items, sentences, conditions, questions | `REPORT_BODY_CLASS` | 19px, regular |
| A short label above content ("REPORT", "SOURCES", "INPUT", an assumption type) | `REPORT_LABEL_CLASS` | 14px, bold, uppercase, grey |

Within body text:

- **Bold** only for a lead-in at the start of an item and for an evidence grade ("Weak evidence it
  holds here."). Same size as the body.
- **Grey** only for metadata (a source's authors, year and type) and labels. Never for a
  sentence someone is meant to read.
- No other sizes. No small grey caption under a paragraph: if it is worth saying, it is a body
  sentence; if not, drop it.

Panels and sheets beside a report (the detail panel, the citation sidebar) use the panel scale:
16px body (`text-body`) and 14px metadata (`text-meta`), as `ClaimPanel` does.

# Why

The owner reviewed the theory-of-change Result page twice for mixed type (2026-10-26 wireframes,
2026-10-27 build: "your fonts on assumptions are all over the place … please follow the standard
set by evidence search typography"). Each fix had been made item by item against a brief, with no
written standard, so new sections drifted to 14px, 16px and semibold variants. The ES report was
already consistent; writing its four styles down makes it the reference.

# How to apply

- Before styling any reading surface, import the four classes; do not write `text-body`,
  `text-meta` or `font-semibold` on report text.
- Check a new section by measuring it in the running app against the ES report (Playwright
  `getComputedStyle`): only 28, 24, 19 and 14 should appear, and 14 only on labels and metadata.
- The canvas is a diagram, not reading text: its box text follows the canvas's own size.
