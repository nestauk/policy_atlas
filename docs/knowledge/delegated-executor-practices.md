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

# Why

All three were paid for once in the 027 build: a Codex phase gate that silently
skipped DB tests until the lead re-ran them, and a worker stall that would have
cost a full re-run without the resume.
