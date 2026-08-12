---
type: Invariant
title: Every screening consumer resolves the effective row — including write paths
description: A doc can hold several screening rows (stages, generations, failed retries); the effective result is the highest-generation-then-highest-stage non-failed row, read via screen.effective_screen_rows(). The rule binds write paths too — any component whose rows imply "this doc is in" (classify, appraise) must join through it, not just the audit counts.
tags: [screening, stage-2, effective-row, screen-generation, reader-sweep, appraise, invariant]
timestamp: 2026-07-16
---

# Rule

Since task 014 a document can legitimately hold multiple `source_screening_result`
rows per scope: one per stage (1 = envelope, 2 = full-text confirmation) plus any
number of `status='failed'` retry-history rows. Task 024 (ADR 0022) added a third
axis: `screen_generation` — a criteria-changed re-screen writes fresh rows at
`generation = max+1`, prior rows immutable (`uq_ssr_scope_source_stage` is partial
on scope/doc/stage/generation, excluding failed). **No consumer may join
`status='relevant'` raw.** The effective result — **highest generation first, then
highest stage, non-failed** — comes from `screen.effective_screen_rows()`;
stage-1→stage-2 flow and demote-only hold *within* a generation. Select reads it
wholesale (status + confidence + `screen_stage` carried into the rationale). The
one deliberate exception is `ingest_full_text`, which reads stage-1 inline: demoted
docs *stay* fetch-eligible by design (the demotion needed the text; the text stays
ingested). Known edge (deferred): a failed gen-N re-screen row is excluded, so that
doc silently keeps its gen-N−1 verdict — an unflagged criteria mix; and
classification/appraisal rows are not generation-aware yet (their collapse
triggers can read a stale picture post-re-screen).

The rule binds **write paths, not just counts**: any component that inserts rows
implying "this doc is in the corpus" must prove an effective-relevant row first —
classify does, and appraise's `appraisable_rows` joins through the helper with the
exclusion counted (`skipped_demoted`), never silent.

# Why

Stage-2 demotion makes stale stage-1 `relevant` rows a standing hazard: a raw join
re-admits demoted docs downstream. The 014 build swept every *reader* (characterise,
select, synthesise, synthesis_tools, skeleton, appraise's audit counts), but the
review stack's Codex adversarial lane found `appraise.appraisable_rows` still joined
classifications straight to snapshots — a doc classified while relevant, then
demoted, would gain an appraisal on any appraise rerun. Grep-for-`status='relevant'`
audits miss this shape: the join was classification-driven and never mentioned
screening at all.

# Watch out

When adding a screening-adjacent consumer, check three things: it resolves stage AND
status through the helper; a doc with both stage rows is read once, not twice; and
failed-then-retried attempt history doesn't inflate its counts. The per-reader
regression suites (four row-shapes: demoted / confirmed / failed-stage-2 /
failed-then-retried) are the template.

029 addenda: the helper now takes an optional creating-run snapshot
(`effective_screen_rows(run_ids=…)`) — chat's terminal-run readers bound the
effective choice to the resolved run set before ranking. And
`screening_by_doc`'s doc-id resolution is deliberately **project-wide** (022
rider 16 — a screened-out doc's history stays readable); snapshot binding
applies to its ROWS, not its resolution, so leak tests must assert empty
row lists for a newer-walk doc, never an unknown-doc error.
