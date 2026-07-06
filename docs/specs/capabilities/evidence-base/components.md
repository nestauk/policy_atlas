---
type: Capability spec
title: Evidence Base — component skeleton
description: The nine EB components — declared I/O, tool wiring, realisation and gating.
tags: [capability, evidence-base, components]
timestamp: 2026-07-06
---

# Evidence Base — component skeleton

The nine components, their declared I/O, tool wiring, realisation and gating. Distilled from
[backend-evidence-base-build-spec.md](../../sources/backend/backend-evidence-base-build-spec.md) §2; the
shared tools and findings schema are owned by
[../../system/execution-orchestration.md](../../system/execution-orchestration.md) and
[../../system/data-model.md](../../system/data-model.md).

```
acquire → screen → classify → appraise → characterise (shallow terminus)
        → select → extract → group → synthesise (deep terminus)
```

## Tool wiring (consolidated)

**Universal core, ambient to every component:** `search`, `retrieve`, `lookup`, `appraise`,
`produce-grounded-block`, `escalate`, `clarify`.

| # | Component | Centres on | Declares (beyond core) | Realisation |
|---|---|---|---|---|
| 1 | acquire | `search` (only egress verb); ingestion follows | — | procedure |
| 2 | screen | `screen`; re-invokes `search` on the thin-base hatch | `screen` | per-doc fan-out |
| 3 | classify | `classify` (single-label doc type + open tags) | `classify` | per-doc fan-out |
| 4 | appraise | `appraise` (steerable rubric → quality tier) | — (core) | per-doc fan-out |
| 5 | characterise | `cluster` (topic) + deterministic metadata patterns | `cluster` | procedure + agent |
| 6 | select | `select` (strategy-parameterised) | `select` | procedure |
| 7 | extract | `extract` → `intervention_outcome_finding` | `extract` | per-source fan-out |
| 8 | group | `cluster` (facet, over findings) + `query-findings` | `cluster`, `query-findings` | agent |
| 9 | synthesise | `produce-grounded-block` (reads grouped findings) | `query-findings` | agent-loop |

## 1 — acquire (front edge)

Gather a **broad corpus** via `search` over configured backends (OpenAlex, Overton) + any
uploaded corpus — at this point **metadata only** (title, abstract, metadata), **no full text**.
Bounded by configured backends / trust classes (the acquisition constraint). Breadth is
**intent-derived**, not fixed. **Full-text fetch + Tier-0 ingestion does not happen here** — it
is gated by `screen`. Ingestion is *not* a tool; this component's verb is `search`.
In v3.0 acquire snapshots the metadata envelope itself as text-in-hand
(`text_basis="abstract_only"`); full-text fetch + Tier-0 ingestion remain post-screen.

## 2 — screen

A distinct **recall-oriented** relevance filter, **per-document fan-out**. The dangerous failure
for a broad scan is the **false negative**, so the screen is deliberately inclusive.
- **v3.0:** screens on **metadata** — title + abstract, **degrading to title-only** where no
  abstract — **fail-open** ("no abstract" must never behave like "not relevant").
- Emits `is_relevant` + relevance **`confidence`** + a **`screen_basis`** flag (`title_abstract` |
  `title_only`) + a retryable **`screen_failed`** state (distinct from not-relevant).
- **Confidence is load-bearing (light):** feeds the **thin-base re-search trigger** (thin = too
  few *sufficiently-confident* relevant docs) and flags/orders borderline inclusions — but is
  **never a hard exclusion cutoff** (preserves recall). Adds the escape hatch v2 lacked
  (re-search when the screened base is too thin) — may re-invoke `search`.
- ⏸ The richer **tiered content peek** (exec-summary / headings / passage scan for poor-metadata
  grey lit) is **deferred**.

## 3 — classify

Cheap classification on the screened-in set, **per-document fan-out**; distinct from appraisal
(*what kind* vs *how good*). Produces two things:
- a single-valued **`primary_evidence_type`** — a **closed column** (routing/appraisal key; a
  study has one primary design). **Carries v2's categories for parity** (rubric maps off them, no
  migration churn). The **`Non-evidence`** value is a landscape label that **excludes from
  `select`/`extract`**; **`Unknown`** is **kept-and-eligible** (label stays metadata-based; ⏸
  resolving Unknowns on full text mirrors the appraisal seam). ⏸ **grey-lit category granularity**
  (splitting v2's coarse Policy-Guidance / Expert-Opinion) is a deferred refinement (with
  policy-team input).
- proposed **methodological / structural tags** — **open, inferred tags, not a closed column**
  (LLM-inferred; grey-lit variety unbounded; job is scoping/description) → the open tag layer,
  seeded + namespace-consolidated. *Not* flat multi-label on the primary type.

## 4 — appraise

Cheap **document-level** quality tier, **per-document fan-out**, applying a **steerable,
default-first rubric** (document type + typed dimensions → quality tier — **not** a fixed global
hierarchy; the **rubric version travels with each appraisal**). **v3.0 = a single light pass**
from metadata + title/abstract, document-type-based, over all screened-in — coverage
clarification (task 006): the pass scores classified **evidence** types; Non-evidence and
Unknown are skipped-and-counted (Unknown re-enters via the deferred full-text resolution
seam). Deferred seams (see
[../../system/provenance-grounding.md](../../system/provenance-grounding.md)): ⏸ the full
full-text pass (methods quality / risk-of-bias, gated to the selected subset; two-stage with the
light tier) + modifier-tag-driven dimensions; ⏸ relative-to-feasible tier; the cross-document
roll-up stays **out of EB's appraise** (EB appraises per document).

**Full-text ingestion — gated by screen, built for all screened-in**. After screen/classify/
appraise (which run on the cheap envelope), full text is fetched and fully Tier-0-ingested
(snapshot → parse → segment → embed) for the **entire screened-in set** — the cheap, shared
substrate downstream capabilities/retrieval/Q&A reuse. Only Tier-1 extraction is further gated by
`select`. **When full text can't be fetched (paywall, dead link) the source is *not* dropped** —
it is snapshotted/ingested on the text in hand (abstract + metadata), carrying a per-source
**`text_basis`** (`full_text` | `abstract_only`) so grounding and coverage see which a finding
rests on. Full-text fetch is egress but mechanical execution of the governed `search` (telemetry
plane + run-record summary, *not* a per-document audit event). Vectorisation is **eager and
uniform** (lazy/on-demand rejected — biases retrieval toward what was vectorised early). In v3.0
Tier-0 ingestion lands as fetch → parse → segment → embed: the embed seam opened in task 009
**ahead of its first reader** (approved exception to "vectorise at the first vector reader" —
chunk vectors are certain retrieval/synthesis substrate, and landing them with the egress
gate beat relitigating egress in a third slice). Vectorisation is eager and uniform over all
ingested snapshot classes, at **embedding-unit grain** (a named, versioned unit policy over
the immutable canonical chunks — units attach alongside; chunks are never re-segmented), each
unit stamped with the embedding profile (the substrate-key leg for embedding-model version). ⏸
budget cap + lazy vectorisation for very large relevant sets is a possible later refinement.

## 5 — characterise (shallow terminus)

Produces the evidence-landscape **content, not presentation**: a run-scoped characterisation
record + topic/theme tags (task 009 clarification, decision 7). Characterise does **not** mint
an artefact or blocks — EB produces **one** artefact, composed once at the run terminus by the
orchestrator (see [capability.md](capability.md)); the artefact-composition step is a recorded
seam. Two parts:
- **Coverage / patterns over metadata** — deterministic distributions and gaps over Tier-0
  columns (study-type, geography, recency, population, category). **Source/evidence policy is
  flag-not-block here** — EB reads and counts *all* relevant in-corpus evidence, so coverage/gaps
  reflect what **exists**, with below-policy evidence present-but-flagged (no false gaps). When
  the user has supplied a policy, characterise computes **two coverage views** — the **overall**
  landscape and the **policy-filtered ("well-evidenced")** landscape — side by side, the **delta**
  showing where the base thins under the citable bar (descriptive **dual-view coverage**, cheap
  and deterministic — *not* the deferred weighted-strength roll-up). These shallow gaps rest on
  the **screened base** (never read `not_selected` / `not_extracted` as absence).
- **Thematic shape — graded by depth.** At the shallow landscape: a **bounded two-stage LLM
  grouping** (task 009 clarification, decision 4) — one judgment-model call discovers the
  scope's themes from all titles + abstracts, then batched cheap-model calls assign every
  screened-in document against the fixed theme list. Exhaustiveness is **code-enforced**
  (schema-constrained outputs, per-batch validation with targeted repair); a document may
  land explicitly in a counted **`unclustered`** bucket — never silently dropped, no
  placeholder themes representable. Call budget is known before the run
  (`1 + ceil(n/batch)`, retry-capped maximum enforced). Honest about being the softest
  grade — an interpretive shape, recomputable, never a deterministic fact. Per-theme labels
  persist as **topic/theme tags**; the run's grouping memberships stay **run-local** (in the
  run's characterisation record only). ⏸ Embedding-based clustering over the landed chunk
  vectors (and discovery-sampling) is the recorded very-large-corpus seam.

Facet-level thematic grouping is a **deeper product** (component 8 `group`), not part of the
shallow terminus.

## 6 — select (deep terminus opens)

Chooses the subset for Tier-1 extraction — a clean departure from v2 (which had **no** select
step and extracted the whole screened set). **Coverage-aware stratified selection over the
characterisation clusters**, breadth-adaptive (the landscape has already *measured* breadth, so
no separate broad/narrow mode — stratify across whatever clusters exist; depth sets how deep per
cluster). Guards against horizon scans collapsing onto a narrow top-k. Realised as the shared
**`select`** tool (strategy-parameterised: *(candidate set, cheap signals, strategy, budget) →
chosen subset + rationale*); EB's coverage-aware-stratified-over-clusters is one strategy.

**Selection signals (cheap, pre-extract only)**: cluster coverage (breadth skeleton) +
relevance to intent (embeddings/screening) + recency + origin/upload-priority + light appraisal
tier + **must-includes** (user-nominated / official docs as a **hard-include bypassing the
budget** — the one hard rule). The **source/evidence policy tilts but never gates** (soft prior;
a hard exclude would re-manufacture false gaps). Diversity is reliable only on cheaply-known
dimensions (topic clusters + clean metadata; publication country is cheap, but study geography /
population / intervention-type live in the text → cluster-approximated, properly post-extraction).
**Rationale is bidirectional** — records what was selected (why) and what was *not* (aggregate
exclusion reasons + notable flagged exclusions); this is exactly what the **deepening-selection
steer-point** reads (see [capability.md](capability.md)).

## 7 — extract (Tier-1)

Per selected document, extracts **`intervention_outcome_finding`** records (the framework schema —
see [../../system/data-model.md](../../system/data-model.md) for grain + base fields).
**EB's extraction profile** (the EB-specific part) = its commitment to extract those **base
fields** over the **selected** subset. Question-relative judgements (normalised magnitude, causal
weighting, is-beneficial) are **not** extracted by EB — they are analysis enrichment for
Impact/VfM.

⏸ **v3.0 deep-synthesis scope:** centred on **intervention–outcome(–population) evidence**. The
shallow landscape covers any facet (mechanisms, barriers, delivery models) via topic
clusters/tags/metadata, but **deep grounded synthesis is schema-bound**. The
**`implementation_context_finding`** second schema (mechanisms/barriers/conditions) is a deferred
seam (named, not built; cross-schema linkage reference-mediated via `group`).

## 8 — group (facet-level theming)

A distinct component between extract and synthesise (not folded into the write-up). Groups the
extracted findings on the **intent-derived facet** — in v3.0 the facets the schema supports
(**interventions / outcomes / populations** — the source-named references), *not* v2's fixed
four. Mechanisms/barriers/conditions stay **landscape-only** until the
`implementation_context_finding` seam lands. The **second clustering** in the chain (topic-level
at characterise; facet-level over extracted findings here) — via `cluster` over finding records /
dimension values + `query-findings`.

## 9 — synthesise (deep terminus)

Over the **grouped** findings, **per group produce a grounded block** reporting what the findings
show. **Descriptive**, surfacing the direction-spread ("5 of 7 findings positive on tenancy, two
null") — v2's `effect_consensus` counts as the descriptive steer. Each claim grounded via the
settled `produce-grounded-block` mechanism (deterministic quote-presence + LLM judge;
Unsupported/mis-cited a real state) — *not* v2's permissive post-hoc fuzzy matching. The
source/evidence policy's citable bar is applied **flag-not-block** (below-bar support flagged
weakly-grounded/below-policy, never hidden/dropped). Deep "gaps" rest on the **selected/extracted
base**, **base-labelled, never promoted to corpus absence** — the shallow landscape is the check
(see [provenance.md](provenance.md)). ⏸ **Consensus seam:** the *weighted* verdict
(strength-weighted "the evidence supports X at strength Y") is deferred to the same roll-up seam;
candidate mechanism = the deferred graph-structured synthesis.
