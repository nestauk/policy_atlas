---
type: Review lens
title: The unmarked-default naming smell — the first-built variant hoards the generic names
description: When a second variant of a thing lands, the first one keeps the generic module/symbol names (extraction_records, extract_prompt) and only the newcomer gets marked names (implementation_context_*) — making the pair read as "the real one and the add-on" instead of two peers. Repeatable review lens; the IOF/ICF rename set (023) was the instance.
tags: [naming, review-lens, refactoring]
timestamp: 2026-07-14
---

# Rule

When a codebase grows a **second variant** of something, check whether the first variant
is still squatting on the *generic* names. The smell: variant A (built first) owns
`extraction_records` / `extract_prompt`, variant B (built later) gets
`implementation_context_records` / `implementation_context_prompt` — so the names say
"the extraction system, plus an add-on" when the truth is "two peer finding kinds (IOF
and ICF)". Fix by renaming to **symmetric marked names** (`iof_records`/`icf_records`,
`iof_prompt`/`icf_prompt`); a shared module that genuinely serves both kinds keeps the
generic name (`extraction_backend` serves both — its stale IOF-only docstring, not its
name, was the defect).

# Why

Asymmetric names misdirect readers and reviewers: they imply a primacy or a dependency
that doesn't exist, hide the peer relationship grep would otherwise show, and each new
variant compounds the asymmetry. The 023 instance was caught by the owner, not the
lanes — which is why it's recorded as a lens: it is cheap to check ("does the older
sibling have the generic name?") and invisible unless you ask.

# Watch out

Renames of this class are cheap **before** anything external pins the import paths
(trace shapes, eval baselines, published APIs) and expensive after — sequence them
early, as 023 did (its rationale: "renames/moves are cheap now and expensive after eval
baselines pin trace shapes").

# Citations

- docs/tasks/023-codebase-health/review-findings.md § "The unmarked-default family"
- [src/policy_atlas/evidence_base/extract/](../../src/policy_atlas/evidence_base/extract/) — the symmetric result (`iof_records.py`/`icf_records.py`, `iof_prompt.py`/`icf_prompt.py`)
