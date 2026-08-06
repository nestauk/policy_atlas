---
type: Frontend rule
title: Server-key→label maps live in one presentation module, and fixtures use RAW keys
description: Three 028 defects were the same class — a durable server key ("openalex", reason codes, backend names) rendered raw on a NEW surface while a perfectly good label map sat unused elsewhere, and the miss was invisible because the test fixture was written in display case. One shared map per vocabulary, imported everywhere it renders; fixtures carry the server's actual keys.
tags: [frontend, vocabulary, presentation, fixtures, task-028, review-lesson]
timestamp: 2026-08-05
---

# Rule

For every server-supplied key vocabulary the UI humanises (search backend
names, reason codes, status enums):

1. **One map, one home** — the key→label map lives in a presentation module
   (`checkInPresentation.ts`, `sourcesPresentation.ts`,
   `planVocabulary.ts`) and every surface imports it. A second surface
   hand-rolling or skipping the map is the defect vector.
2. **Fixtures use RAW server keys** — a fixture written in display case
   ("OpenAlex" where the wire carries "openalex") makes the raw-key render
   pass its test; the test then guards nothing. The fixture must be shaped
   like the wire, with the assertion on the label.
3. Lookups are **case-insensitive** where the server has ever varied casing
   (durable read models serve public names, stream keys are lowercase —
   028 batch 10).

# Why

The same defect shipped three times in one slice: batch 10 ("Where I
looked" empty — map keyed on stream keys, server sent public names), and
the review stack's F10 (P1 check-in card rendering `openalex 12` raw while
`BACKEND_LABELS` sat unused in JourneyPane, masked by a display-cased
fixture). Class-level fix: `backendLabel` moved to the shared presentation
module, both consumers import it, fixture re-keyed raw.

# Watch out

- Closed UI vocabularies omit unknown keys (vocabulary honesty); open
  diagnostic sets (ingest-failure reason codes) may de-snake as a fallback
  — that split is deliberate (028 review F17), record which kind a new
  vocabulary is when adding its map.

# Citations

- `frontend/src/views/workspace/checkInPresentation.ts` (`backendLabel`)
- 028 verification.md § Review findings (F10, batch-10 note)
