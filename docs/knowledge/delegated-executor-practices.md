---
type: Runbook
title: Delegated-executor practices — Codex sandbox has no localhost DB; shared worktrees need ownership lists; killed workers resume by message
description: Codex jobs cannot reach localhost Postgres, so delegated backend phases say "tests run lead-side" in the brief and the lead actually runs them before the gate; two codex jobs plus the lead can share one worktree when every brief carries an explicit file-ownership list; a fast-worker killed by a transient API stall resumes losslessly via SendMessage to the same agent id.
tags: [codex, delegation, worktree, subagents, testing]
timestamp: 2026-07-29
---

# Rules

- **Codex jobs cannot reach localhost Postgres** (sandbox network). A delegated
  backend phase whose gate includes DB-backed tests must say **"tests run
  lead-side"** in the brief, and the lead must actually run them before
  declaring the gate — a green Codex report cannot include them (027 phases
  A–C).
- **One worktree, several executors** works when every brief carries an
  explicit **file-ownership list**; the only overlap in 027 (E.5 extending the
  lead's minutes-old dossier wiring) was intentional and clean. No list → merge
  archaeology.
- **A fast-worker killed mid-task** (transient API stall) resumes losslessly
  via `SendMessage` to the same agent id — its transcript survives; don't
  re-brief from scratch (027 build).
- **Codex-authored tests are the dominant delegated-defect surface** —
  confirmed a third time in 028: the build's 15-test fallout plus one
  invalid fixture were all test bugs (product code survived adjudication
  unchanged), and the review stack's one shipped MAJOR (dead
  finding-groups regroup) was masked by a Codex-authored matrix that
  asserted ids/compilation instead of answering the pause (see
  [tested-in-isolation-is-not-wired](tested-in-isolation-is-not-wired.md)).
  Weight review budget toward delegated tests, not delegated product code.
- **Two families editing one working tree concurrently** is safe when the
  briefs carry disjoint file lists AND each names the sibling's files;
  string-anchored edits on one SHARED file from two agents also merged
  cleanly in 028 — but a mid-flight `pnpm typecheck` sees the union and
  cross-fires (one agent's regenerated types transiently broke the
  other's check). Gate on typecheck only after both land.

# Why

All three were paid for once in the 027 build: a Codex phase gate that silently
skipped DB tests until the lead re-ran them, and a worker stall that would have
cost a full re-run without the resume.
