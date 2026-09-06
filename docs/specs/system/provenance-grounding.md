---
type: System contract
title: Provenance & grounding
description: The trust invariant — claims, citations, grounding tiers, produce-grounded-block/verify, gaps, patterns and summaries.
tags: [system, provenance, grounding, citations, trust]
timestamp: 2026-07-05
---

# System contract — Provenance & grounding (the trust invariant)

**Distils** [backend-architecture-reference.md](../sources/backend/backend-architecture-reference.md)
§3.3 and §4 (grounding mechanism + progressive disclosure). This is the system's most
distinctive contract: the discipline that stops an ungrounded or mis-cited statement from
masquerading as grounded evidence. This spec + `docs/adr/` are canonical; the source is frozen
origin ([ADR 0002](../../adr/0002-spec-governance.md)).

## The traceability rule

**Every significant statement either traces to its source, is visibly flagged as reasoning,
or is a pattern grounded in a scan over the set — three honest categories.** A statement that
presents itself as source-supported but is not supported by its cited source(s) **as worded**
is **Unsupported / mis-cited**, whether empirical or interpretive. The cardinal sin is an
ungrounded/mis-cited statement masquerading as grounded evidence.

## Grounding tiers (claims)

Ordered by epistemic strength (inference distance from evidence):
1. **Direct quote** — chain bottoms out at a document span.
2. **Inferred from a single document.**
3. **Reasoning over synthesised evidence** (across sources). High-level "what this adds up to"
   synthesis is Tier 3 attributed at **block level** (the block declares the source set it
   "draws on").
4. **Pure LLM reasoning / background** — no evidential terminus; honest **only because visibly
   labelled**. **Not a common-knowledge safe harbour** — policy-specific, empirical, causal,
   comparative, evaluative or "the evidence suggests…" claims must be supported or classified
   Unsupported/mis-cited; they must not escape into Tier 4. Never counts toward
   evidence-strength roll-ups.

**Two non-tier outcomes, kept distinct**:
- **Unsupported / mis-cited** — a **failure state, not a tier**: cited source(s) don't support
  the claim as worded (fabricated support, quote-mining, omitted caveats, support-for-a-weaker-
  claim, contradiction, unwarranted synthesis). Remedy: *the cited evidence doesn't support
  this — the claim may not hold.*
- **Weakly grounded** — a **completeness flag orthogonal to the tier** (a thin or cut-short
  Tier 2/3), not a sixth lane. Remedy: *the claim stands but is under-evidenced — seek
  corroboration.* Both are **soft-flagged, never dropped** (flag-don't-drop). Where the
  clean/weak line falls is a judge-rubric question owned by the eval workstream. ❓

⏸ **Support-direction relations** (supports/caveats/contradicts) and user counter-evidence
search are a deferred seam; the free-form grounding rationale carries the per-citation *how*
in v3.0.

**Citation scope:** a citation always points to a **source/document, never to another block** —
within an artefact every block's claims ground out in evidence, not sibling blocks (a user never
sees a block "cite" a sibling; cross-block derivation is internal staleness wiring, owned by
[data-model.md](data-model.md), never a visible citation).

## Gaps — the dual of a claim

A gap asserts **absence** and is the structural mirror of a claim: a typed annotation in the
same layer (type = gap), but its provenance records the **attempted search**, not a supporting
source. Graded by how far the absence claim travels:
1. **Corpus/coverage gap** — grounded; the failed search is recorded.
2. **Acknowledged domain gap** — backed by an in-corpus sparsity signal.
3. **Inferred domain gap** — from silence + reasoning; weakest tier but often **highest value**
   (a true evidence frontier). A sparsity signal **raises a gap's tier but never gates it** —
   the most valuable gaps least often carry one.

Honesty rides on the **visible tier label**: a reasoned domain gap shows as an inference about
the field, never as proven absence (we searched our corpus, not the whole literature).

## The coverage base — what licenses an absence claim

Framework-level (arch §4, EB-prompted). The gap *tier* above grades how far an absence travels;
the **coverage base** grades what it rests on — orthogonal, both required.

- **Every gap / absence claim carries its coverage base** as a required structural field — the
  pipeline ladder **attempted-search → acquired → screened → selected → extracted**. Each rung
  narrows; each narrowing can manufacture a false absence.
- **Only `searched_and_absent` over an adequately-searched base licenses an absence claim.**
  `not_selected`, `not_extracted`, `extraction_failed` and `unclear` **never** do (the coverage
  states themselves are owned by [data-model.md](data-model.md)). A reported null is a **finding**;
  a silence is **coverage**.
- **Even `searched_and_absent` is bounded by acquisition scope** — absence is "absent from the
  *searched* space" (configured backends / trust classes), never absolute; a corpus-level absence
  carries a **search-adequacy caveat**.
- **Shallow vs deep base:** shallow coverage rests on the **screened** base (the whole relevant
  corpus); deep coverage rests on the **selected / extracted** base (a subset), must be
  **base-labelled**, and is **never promoted to corpus absence**.
- **`search_coverage_record` operationalises "adequately-searched"** — a corpus-level absence
  references a record with the **search-space boundary** (backends / trust classes), a **stop
  condition** (v3.0: *breadth-truncated* / *re-searched-still-thin* / *error* — `saturated` is a ⏸
  seam), an **adequacy verdict + origin** (model or human), plus by reference the queries/expansions
  (→ `search` governance events) and scope filters. **Fail closed:** absent a non-`inadequate`
  record, an absence degrades to "not found in extracted / selected material," never corpus-level.

The EB instance (and where this rule is most acute) is
[../capabilities/evidence-search/provenance.md](../capabilities/evidence-search/provenance.md).

## Patterns — the third assertion type

A pattern asserts the **shape of the corpus**, grounded in a **scan over the set** (a gap is the
hole; a pattern is the shape). Stored like the others (type = pattern; provenance = the
scan/query). **A strength ladder, never conflated** — two rungs:
1. **Metadata-grounded** — counts/distributions over Tier-0 columns/tags. **Strongest grounding
   in the system** (re-running the query *is* the verification); profile-independent.
2. **Content-scan** — a shape the agent reads *across* the corpus that the metadata doesn't
   capture (e.g. a recurring framing). No deterministic terminus, so — the pattern analogue of
   the inferred domain gap — it ships **soft and honestly labelled, never gated**.

Two further positions relative to the rungs:
- **Finding-query patterns** — counts/direction-spreads over extracted findings; deterministic
  *given the recorded (finding-set, coverage-state, extraction-profile)* but **inherit the
  extraction dependency**; not metadata-grade. Whether they grade as a labelled middle position
  between the rungs, and their roll-up relationship, ❓.
- **Thematic clustering** (`cluster`, LLM-labelled) — an **interpretive shape, not a count**;
  recomputable, never a deterministic fact; a **softer grade below both rungs** (facet grouping
  over findings also inherits the extraction dependency).

## `produce-grounded-block` — how verify works

Runs **synthesise → cite → verify → write**, with **cite and verify as mandatory internal
steps** (not optional tools). **Citations are co-emitted, never post-hoc** — a claim is
generated *from* its evidence; there is no "attach citation to written prose" path (that route
produces mis-attribution/citation theatre). "Re-grounding" means **regenerating from new
evidence**, not stapling a source onto fixed wording.

**Verify has two parts:**
- **Deterministic quote-presence check** — the verbatim supporting quote must occur in the
  cited source's **frozen chunks** (normalised string match over concatenated passage text so a
  boundary-spanning quote isn't a spurious miss). A fabricated quote on a real document is a
  **hard fail**. Matches against stored passage text (what the model could read), **not** a full
  snapshot reload.
- **LLM-as-judge grounding classifier** — reads claim + cited passage(s) + enough surrounding
  **evidence envelope**, assigns **exactly one** of Tier 1–4 / Unsupported-mis-cited (single
  lane — no separate `is_supported` field). **Permissive about legitimate inference, strict
  about attribution fidelity**: preserves scope, caveats, population, intervention, comparator,
  outcome, direction, magnitude, uncertainty, context. Topical relevance ≠ support. Empirical
  markers are **strict-routing heuristics, not the definition** of unsupportedness. Co-emits a
  **free-form grounding rationale** (the per-citation *how*; chosen over a fixed role
  vocabulary, which would re-tread the tier). Why LLM-judge over NLI: a strict entailment model
  flattens legitimate inference and its one reliable case is already the presence check.

**Verify is a bounded loop; its job is claim↔evidence convergence, not pass/fail.** Primary
repair = **reword the claim *down*** to what the evidence supports; alternative = re-gather
targeted evidence. On exhaustion the claim lands **weakly grounded** or **Unsupported/
mis-cited** — soft-flagged, never silently promoted to a clean tier.

**Grounding governs what is committed, not how the model reasons** — the harness sits at the
*commit* boundary; upstream exploratory reasoning is captured for eval but is not itself
grounded/shipped (distinct from Tier 4, which *does* ship, visibly labelled).

**Persistence for eval-readiness, not calibration** — each judgement persists judge
prompt/model id+version + I/O payload, plus **segmentation-policy and envelope-policy versions**
(else judge-drift and envelope-drift confound the SLIs). There is **no `calibration_status`
field**; whether/how the judge is calibrated is owned wholesale by the eval workstream.

## Appraisal — orthogonal to grounding

`appraise` measures **source quality**; the grounding tier measures **inference distance**.
**Two independent axes, never collapsed into one confidence score** (a direct quote from a weak
source is faithfully reported but weakly evidenced; the reverse for a careful inference from
strong sources). Document type (from `classify`) picks the yardstick. Modelled as **extensible
typed dimensions + a rubric version**; the **rubric travels with each appraisal**. The type→tier
rubric is **steerable, default-first** (Agent seeds a provisional default; user may
inspect/adjust but needn't). **v3.0 = a single light pass** (cheap tier, all screened-in,
document-type-based); ⏸ a fuller full-text second pass and ⏸ a relative-to-feasible tier are
deferred. The axes combine **only at an aggregate roll-up** — itself ⏸ **deferred**. One
canonical constraint ahead of any roll-up: **Unsupported/mis-cited and Tier-4 never contribute
positively; weakly-grounded contributes only at a discount.**

## Summaries — outside the grounding economy

Block- and artefact-level summaries are a **navigation device**, not a new evidential surface.
- **A summary is a condensed rendering of the detail beneath it, not independently grounded
  content.** It carries **no citations**; its integrity property is **faithfulness-to-detail**,
  not grounding-to-source; it sits **outside evidence-strength roll-ups**. Citation-free is
  acceptable only under a **display invariant**: *a summary never renders detached from its
  drill-down affordance* (export is a ⏸ seam).
- **Flat faithfulness** — every summary checks against **raw detail**, never another summary
  (**no summary-of-summaries**; distinct from the rejected RAPTOR-style citable hierarchical
  summaries). The faithfulness terminus is the prose **and its epistemic annotations** —
  flagged / Tier-4 / gap / soft-pattern content is **carried-with-status or excluded**, never
  silently promoted to plain assertion.
- **Mechanism = LLM judge alone, bounded regenerate-on-fail** (no deterministic leg — abstractive
  text has no verbatim anchor). Verdict keyed to `(block-or-artefact, version)`, **outside** the
  `(block, unit, type)` annotation layer. Exhausted retry → marked **`failed`**, surfaced as
  such (flag-don't-drop). Rubric: fidelity · epistemic-annotation awareness · conclusion-fidelity
  (artefact grain) · **emphasis inherited, never originated** (selective emphasis is a defect).
  Calibration owned by the eval workstream.
- **Block summary** = a co-versioned second column on the block record (trailing step of
  `produce-grounded-block`), **excluded from the content hash**, nullable with a `pending` /
  `verified` / `failed` marker, **no independent staleness**.
- **Artefact summary** = a **field on the artefact** (not a block — accrues no annotations,
  Principle 10), the **one stale-able summary object**, **flag-and-propose** on material
  block-composition change (never auto-run), **emphasis located structurally** (anchored on the
  declared conclusion-bearing component; falls back to structural-shape condensation for a
  horizon scan).
- **The "what did it conclude" front door is two distinct grounded blocks, never merged**
  (owner refinement 2026-07-10; task 018, ADR 0015): the **key-findings block** — headline
  evidence claims at their appropriate grade, **produced last, shown first**,
  conditional-required (present iff headline claims are made) — and the **conclusions block**
  at the report foot — what this evidence amounts to against the user's question,
  evidence-descriptive (no recommendations). Both sit inside the grounding economy (cited —
  **to sources, never to sibling blocks** — contestable, versioned, steerable) and are present
  only where the skeleton declares a conclusion-bearing component. The summary only *points
  at* them.
- ⏸ **Summaries may route, never substitute** — nothing load-bearing (grounding, synthesis,
  citation, extraction, agent context) is generated *from* a summary.
