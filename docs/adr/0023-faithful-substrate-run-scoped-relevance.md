# ADR 0023 — Faithful extraction substrate; relevance is run-scoped annotation

**Status:** Accepted — 2026-07-16 (Shabeer Rauf; task 024 review rounds
3–4 — the owner first challenged extraction-prompt guidance, then chose to
ship the fenced alternative). Revisitable at the eval slice (the recorded
trigger: evidence that doc/artefact-grain emphasis under-serves user
priorities, or that the annotator's fencing leaks).

## Context

024's guidance channels raise the question: should user emphasis ("I care
most about cost-effectiveness") steer the extraction prompt? Two facts
say no. The findings layer's contract is *faithfulness* — downstream
treats it as the complete substrate, and emphasis inside a bounded token
budget tilts recall (over-X, silently under-Y). And extraction is
memoised by fingerprint with cross-question reuse (the multi-question
project model): guidance in the prompt means guidance in the fingerprint,
fragmenting reuse. The vetter is likewise closed — users must not
instruct the quality judge on their own findings.

## Decisions

1. **Extraction and vetting prompts never carry user-authored text.**
   Byte-untouched by emphasis guidance, test-pinned. The only
   what-to-extract levers stay schema-grain (the profile set) and
   corpus-grain (screen criteria, selection).
2. **User emphasis reaches the findings grain as run-scoped annotation
   (B2′).** `extraction.relevance_emphasis` (bounded prose-as-data) feeds
   a **sibling annotator pass** (`finding_relevance_v1`, mini-class) that
   runs post-vetting, only when emphasis is present, marking surviving
   findings `priority | normal` — coverage-validated, fail-open with a
   flag. **Verdict fencing is by construction**: the guidance never
   enters the extraction or vetter calls at all.
3. **Relevance is question-relative, so it persists run-scoped** —
   `relevance_annotations: {finding_id: …}` in that run's
   `extraction_result` JSONB — never on the shared finding rows and never
   in the memo fingerprint. The same finding can be priority for question
   A and normal for question B; reuse is preserved.
4. **The consumer ships with the annotation** ("model only what
   behaves"): findings surfaced to synthesis carry the marks; the section
   prompt (additive optional block, `synthesise_section_v7 → v8`, frozen
   cost baseline handled explicitly) foregrounds priority findings where
   relevant; the P4 proposal shows priority counts per group.

## Consequences

- The faithful-substrate rule generalises: any future per-question shaping
  of shared, memoised layers lands as run-scoped annotation, not prompt
  guidance.
- Deferred with named triggers: finding-grain relevance feeding grouping
  or retrieval (needs a consumer + eval evidence); vetter-adjacent
  single-call designs (rejected here for prompt-bleed risk).
