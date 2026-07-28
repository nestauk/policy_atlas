---
type: Invariant
title: Every EB run terminates in synthesise; every other component is a plan choice
description: Synthesise mints the capability's artefact, so no valid run shape ends before it; characterise and the rest of the composition run at the orchestrator/sub-agent's discretion per intent.
tags: [architecture, run-shape, orchestration, synthesise, invariant]
timestamp: 2026-07-09
---

# Rule

Every Evidence Base run — rapid, deep, or anything the plan composes — **ends in
`synthesise`**, because synthesise is the component that mints the capability's
artefact. A chain described (in a contract, a smoke test, a skeleton profile, a
doc) as ending at characterise or any other component is not a valid run shape:
it produces no artefact, so nothing of value was delivered. Every component
*between* the front edge and the terminus — characterise especially — is a
**plan choice**: the orchestrator / EB sub-agent composes which registry
components run for a given intent.

# Why

The spec makes both halves explicit (EB components.md §9): a rapid run is
`acquire → screen → classify → appraise → ingest → synthesise`, and "a run
without characterise yields an artefact with no landscape — a grounded answer,
not an evidence report; the plan's legitimate choice." As-built agrees:
`skeleton.py` calls synthesise "EB's terminal component" and ships a
no-reference rapid synthesise profile, so the terminus holds even when no
grouping/selection/characterisation references exist.

Getting this wrong has real consequences beyond wording: task 015's contract
briefly pinned a live-check smoke chain ending at characterise, and a design
argument ("synthesise isn't in the smoke") was built on the error before being
caught. The mistake recurred across multiple slices before being captured here
(user correction, 2026-07-09).

# Watch out

- When writing a live check, demo profile, or fixture chain, the cheap
  cost-control move is trimming *mid-chain* components (select/extract/group
  legs), never the terminus — a smoke that skips synthesise validates a
  pipeline that can't exist.
- "Characterise runs" is never an assumption a reader/consumer may bake in:
  code consuming characterisation output must tolerate its absence (the
  artefact is then a grounded answer without a landscape, by design).
- **The terminus has a substrate precondition** (013 as-built, hit live at the
  015 chain smoke): synthesise refuses an envelope-only corpus with an honest
  structural `no_groundable_substrate` — its citable substrate is full-text
  chunks. Until live fetch (016) lands, no chain running purely on acquired
  metadata envelopes can mint; a demo/smoke must seed at least one full-text
  document. A spec/contract line saying a chain "synthesises over metadata
  envelopes" is written against intent, not the as-built rule.
- **UI/spec assertions must target always-present stages** (026 smoke spec, the
  pitfall's first bite in a committed spec): a browser test asserting the
  characterise stage label ("Mapping the landscape") races orchestrator
  discretion; assert the acquire stage ("Searching sources"), which every chain
  contains and which persists in the timeline.
