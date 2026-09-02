# ADR 0034 — Case-studies late-produce / early-show, short titles, and report hierarchy

- **Status:** Accepted — 2026-09-01 (owner, with the 034 iterate pin)
- **Date:** 2026-09-01
- **Task:** 034-synthesis-report
- **Amends:** [ADR 0015](0015-prose-first-synthesis-with-span-anchored-claims.md)
  §8 key-findings production≠presentation pattern (extends it to case studies);
  records the 028 strand-12 overview-lead reversal from 034 S6.

## Context

The synthesis report's executive front matter needs programme-level case
studies and a readable two-level page (Executive summary / Full report).
Case studies are grounded content produced from the same verified-claim
substrate as key findings, but shown in front matter. Section titles must
be short contents-ready theme names; the answer-shaped overview lead added
in 028 is no longer needed once front matter frames the report.

## Decisions

1. **Case studies are produced after key findings and shown in front matter**
   (after Key findings, before Most relevant sources), riding
   `synthesis_result.blocks` as `role: "case_studies"` with an additive
   `SectionOut.cards` payload. Absence (`<2` valid cards) is normal.
   SSE gains no case-studies frames.

2. **Section titles are short (P9); the 028 overview lead is dropped.**
   Proposal titles reject above 60 characters. `SECTION_TITLE_MAX` stays
   200 for old-artefact reads.

3. **Page chrome is two-level:** Headline (title + stats) · Executive
   summary (In brief, Key findings, Case studies, Most relevant sources) ·
   Full report (deterministic roadmap sentence from body titles, then body
   sections with optional one-sentence bridges, Conclusions, References,
   Method). Roadmap is presentation-only; bridges live in section prose.

4. **Most relevant sources may carry a grounded cheap one-liner**
   (`most_relevant_note_v1` on `gpt-5.4-mini`), seeded only from that
   source's cited claim texts/quotes. Free-form “why this source matters”
   stays out. Paper authors stay parked (API/UI placeholder only).

## Consequences

- Public interface: additive `SectionRole` value, `CaseStudyCardOut`,
  `ArtefactOut.most_relevant_notes`.
- Prompt surfaces: `synthesise_case_studies_v1`, `synthesise_section_v10`
  (bridges), `most_relevant_note_v1`.
- Deferred.md: case-studies seam discharged; “why this source matters”
  narrowed to free-form-only.
