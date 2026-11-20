---
type: Live behaviour
title: Study geography read from abstracts is mostly absent — "where tried" reads unknown until full text is read
description: The longlist's where-tried label comes from the scoping profile's study_geography, and the profile reads abstracts (text_basis abstract_only). On the live NEET longlists most option cards read "unknown"; where abstracts do name a place, England/UK and OECD countries appear. The label is honest but thin — a property of the input, not a bug.
tags: [options-scoping, longlist, geography, where-tried, abstracts, live-behaviour, task-045]
generated:
  by: process:okf-migrate
  at: 2026-09-24
sources:
  - resource: "backend/src/policy_atlas/options_scoping/longlist/where_tried.py"
    title: "`backend/src/policy_atlas/options_scoping/longlist/where_tried.py`"
  - resource: "../tasks/045-scoping-longlist/verification.md"
    title: "[045 verification.md](../tasks/045-scoping-longlist/verification.md) \u00a7 Phase 8 (c); \u00a7 Review handoff (knowledge candidates); \u00a7 Review findings (L1)"
---

# Rule

Expect *unknown* to dominate `WhereTriedOut` on a longlist built from abstracts. Abstracts rarely
state where a study was run; the scoping profile never loads chunks, so it cannot find the
setting in a methods section. Treat a mostly-unknown where-tried facet as the expected state, not
an extraction defect.

# Why

045 Phase 8 (c), the live NEET longlist: "Where tried on the cards is mostly *unknown*:
abstracts rarely state the study geography; where they do, England/UK and OECD countries appear
(e.g. the procurement-clauses option: comparable 4)." The same absence shows in provider metadata
for the ES landscape chart (`test_landscape_geography_residual_makes_every_scope_add_up`).

# Watch out

- Transferability is "checked at assessment" on the card — task 3 (full text) is where geography
  can become informative; don't read the longlist's facet as evidence of where an option works.
- Country matching over free text needs longest-phrase-first rules ("North Korea" was grouped as
  comparable via "korea" until 045 L1).
