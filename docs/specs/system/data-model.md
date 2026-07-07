---
type: System contract
title: Core data model
description: Entity hierarchy, blocks and addressable units, the annotation layer, findings, versioning and staleness.
tags: [system, data-model, schema, annotations]
timestamp: 2026-07-06
---

# System contract — Core data model

**Distils** [backend-architecture-reference.md](../sources/backend/backend-architecture-reference.md) §3
(+ the findings layer from §4). Decision-level status is preserved. This spec + `docs/adr/` are canonical; the source is frozen
origin ([ADR 0002](../../adr/0002-spec-governance.md)).

## Entity hierarchy

`tools → components → capabilities → artefacts`, all **within a project**, drawing on a
**corpus** of sources, surfaced through a shared **information layer** (holds the corpus
*and* the artefacts; the unit-level annotation layer cross-cuts both). No separate collective
name for the derived side ("the artefacts" suffices — a symmetry-only term would be inert,
Principle 10).

Whole-item organisation is **just columns + tags + scoping** — no special container between
project and artefact.
- **Structured columns** — single-valued, closed/known vocabulary on the item record:
  `origin`, document type, date/year, format, plus derived columns (appraisal **quality
  tier**, and on uploads an inferred **function**). Queried directly; behavioural hooks read
  columns (appraisal reads document type; egress reads `origin`).
- **Tag layer** — item × tag, many-to-many, open/emergent vocabulary, mostly inferred. Each
  tag carries a **type** (topic/theme · methodological/structural · scoping/line-of-work · …,
  an open/extensible type-set). **Nothing hangs off a tag** (no owner, status, lifecycle —
  just a label). Clarified (task 009, decision 10): that rule governs the tag **label**; the
  **assignment row carries assertion provenance** like every other assertion in the system —
  **`asserted_by`** + the creating run, so every assertion is dateable and attributable.
  Provider topical signals (e.g. OpenAlex topics/SDGs, Overton topics/classifications/LLM
  themes) materialise at acquire as **provenance-classed tag rows**; provider-curated,
  provider-LLM and own-capability assertions **never mix** — the same tag from two asserters
  is two rows (corroboration, not duplication). **Created by the capabilities that read
  documents** (`classify` → methodological/structural; characterise → topic/theme), **never
  by the orchestrator**, which only **keeps the namespace consistent**. Vocabulary is
  open-but-seeded and namespace-consolidated (consolidation buys *precision*; *recall* rides
  the soft-prior widening over hybrid retrieval).
- **Scoping** is the behaviour of pointing an agent at a subset (queries over columns + tags
  alike). A **soft retrieval prior, not a hard boundary** — "look here first," then widen
  when thin (the evidence escape-hatch). Agents are never penned in.

⏸ **Sensitivity/classification column — deferred, not built** (no v3.0 behaviour reads it, so
it would be an inert security label, Principle 10). Egress is handled at deployment / route /
tool-governance level instead (see [security/egress — not yet drafted]; arch §11).

## The atomic units

- **Artefact** = unit of value (what the user sees; recursive — a meta-synthesis is also an
  artefact).
- **Block** = unit of **storage, versioning, interaction, commenting, regeneration**. Holds
  prose **or** structured content (an options table is *one* block). Carries a **co-versioned
  summary column** (parallel representation of the same version, hash-excluded; see
  [provenance-grounding.md](provenance-grounding.md)). A **chart is a ⏸ deferred view-type**
  over a structured-content block, not a new primitive.
- **Addressable unit** = a text-span (prose) or cell/row (table). Citations, comments, claims
  and (later) cross-artefact links all hang off **units**, uniformly. Each unit carries a
  **stable ID strictly bound to its block version** — IDs are **not** mapped across a
  substantive regeneration; immutable versioning keeps historical units addressable instead.
  One deterministic exception: a **`same_content_as` link** on exact normalised-content-hash
  match (no semantic matching, no false anchors) — read by the staleness check.
- **Annotations** (claims, citations, comments, gaps, patterns, and later eval results /
  cross-artefact links) live in a **separate structured annotation layer keyed by `(block,
  unit, type)`** — not inlined in prose, not on the block record. Rationale: almost everything
  we do with provenance is a **cross-unit query**. A claim is conceptually not a first-class
  entity (you never open/version one alone) but is *physically* its own addressable row.
  - The walk across annotation/provenance/dependency layers to assemble claim-/unit-/
    source-centred views is a **named-but-light projection** — **Postgres views over existing
    tables, not a new store and not a graph DB**.
- **Provenance/support vs amendment** are **two separate facets of a unit version**:
  *provenance* = what the text rests on (grounded tier / reasoning / pattern / gap, or
  **human-authored**); *amendment* = whether this version was human-amended vs its
  predecessor. They never collapse — an evidence-grounded unit later human-amended keeps its
  original provenance in history while the current version is **human-amended, verification
  flagged stale**. (Editing UX ⏸ deferred; the representation is not.)
- **User feedback signals** (`USER_VALIDATION` / `USER_CHALLENGE`) are review/sampling inputs,
  **not tier-level ground truth** — judge calibration is owned by the eval workstream.

## Corpus & source snapshots

- **One project corpus; source classes collapsed to `origin`** (`uploaded` | `acquired`).
  Wireframe source classes have no distinct v3.0 lifecycle → not modelled (inert). `Library`
  (curated cross-project) and `Connected` (auth'd departmental ingest) are ⏸ deferred seams.
- **Immutable source snapshots; no original bytes retained.** The raw file is fetched
  transiently to parse; **frozen parsed chunks are the content-of-record** for citation,
  grounding and audit. **A source whose full text can't be fetched (paywall, dead link) is
  snapshotted on the text in hand** (abstract + metadata), **not dropped** — each snapshot carries
  a **`text_basis`** (`full_text` | `abstract_only`) so grounding and coverage know what a finding
  rests on. Identity rests on **content hash (at ingest) + the §9 search-governance
  event + source locator**. A corrected re-upload is a **new snapshot**, optionally carrying a
  human-asserted `supersedes(source_snapshot_id)` edge (a link only — no diffing, no
  monitoring).
- **Acquired snapshots are a shared, content-addressed, cross-project substrate** (key =
  content hash × parse-profile × segmentation-policy × embedding-model version); derived
  substrate computed **once per unique key**; reference-counted GC; reference edges
  project-private (no cross-project enumeration). **Uploaded snapshots stay per-project, never
  shared.** Sharpens a cross-tenant boundary flag → carry to security/egress (arch §11). ⚠️
- **Origin drives classification richness & default priority, not appraisal** — an uploaded
  SR is appraised the same as an acquired one; priority is handled by **scoping** (soft prior),
  not a hidden re-weight. Uploaded docs get an **inferred `function`** (never user-entered;
  user-confirmable on a misroute) routing each to a treatment lane. 🟡 The lane set is
  **illustrative — to be specced** (examples: *evidence* → the evidence pool; *framing/subject* →
  orchestrator task-definition; *directive* → execution-shaping; *contextual* → a context lane;
  *prior work* → build-on); refined against real upload patterns closer to implementation.
- **Segmentation is trust-relevant, not a hidden detail.** Structure-aware parse first
  (pages/headings/tables/captions/footnotes), semantic splitting only as a layer over it; a
  named, versioned **segmentation policy**. **One parse, one segmentation per snapshot** —
  re-chunking/re-embedding/re-parsing in a project's life is not designed for; a policy/parser
  upgrade applies to **newly ingested snapshots only** (re-parse-without-refetch is impossible
  by construction since no bytes are retained). **The provenance anchor is `(source, verbatim
  quote, recorded location)`** — location is the recorded by-product of the verify step, not a
  designed coordinate system.

## The findings layer (reusable extracted evidence)

Structured extraction writes **reusable finding records into the information layer**, not
opaque tool-cache payloads. A capability **commit** declares an **extraction profile**
(requirements over its selected source set); the extraction service resolves it against
existing records and creates per-source tasks only for what's missing. Reuse happens
**through the findings layer**; exact results memoised by `(source snapshot, extraction-task
fingerprint)`. Capabilities consume via pinned **evidence dataset snapshots** (point-in-time).
**Model/prompt upgrades set future defaults; they never invalidate existing findings or
historical state.**

- **Where a finding is multidimensional, preserve it as one coherent typed record with its
  dimensions intact and queryable** — never flattened to disconnected fields or prose.
- **First reusable schema: `intervention_outcome_finding`**. **Grain:** one *(intervention,
  outcome, effect, stratum)* claim grounded in a **single source**; `intervention`, `outcome`,
  **study population** and **comparator** are **source-named references** (groupable/
  canonicalisable downstream, not baked-in canonical entities). **Base fields** = what the
  source reports: effect direction; effect size + type; uncertainty (CI/SE); p-value;
  study-design/sample metadata (design, N, k, I², τ²); source-named **population**;
  source-named nullable **comparator** (an effect direction is *versus something* — reported
  by the source, so a base field); the **estimate-level discriminator** (`study` | `pooled` |
  `claim` — a review's pooled estimate and a primary study's own estimate are different
  evidence shapes sharing one schema); **stratum qualifiers** (timepoint/subgroup/setting as
  structured qualifiers on the finding — the outcome reference stays the **base measure only**,
  "BMI", never "BMI at 12 months", which keeps outcome references groupable); descriptive
  **causality-by-design** label; primacy/prevalence flags. *(Comparator, estimate level,
  stratum qualifiers and τ² made explicit by the task-011 flow-back — all inside the
  source-groundability line, surfaced by the V2 extraction autopsy.)* **Question-relative
  judgements** (normalised magnitude, causal *weighting*, is-beneficial) are **analysis
  enrichment** layered by Impact/VfM — **not base fields** (keeps the record reusable, not
  pre-committed to one analysis).
- ⏸ **`implementation_context_finding`** (mechanisms/barriers/conditions — the "how/why") —
  named, not built. Carries the **same source-named reference vocabulary** so cross-schema
  linkage is **reference-mediated** via `group` (no explicit link objects).
- **Coverage states are gap provenance**: `searched_and_absent` · `not_applicable` ·
  `not_selected` (doc-level — screened-in but not chosen) · `not_extracted` (field-level) ·
  `unclear` · `extraction_failed`. A source that **reports** a null is a **finding**; a source
  that **doesn't mention** an outcome is **coverage**. (Consumed by the gap-provenance rule in
  [provenance-grounding.md](provenance-grounding.md) and the EB
  [provenance.md](../capabilities/evidence-base/provenance.md).)
- **Hybrid-queryable dimensions**: `intervention` and `outcome` are hybrid-indexed in v3.0
  (committed). Other dimensions are stored and filterable; hybrid-indexing is gated on the
  **dimension-promotion gate** (🟡 — driven by observed query behaviour, not declared upfront).
  Dimension search reuses the `retrieve` adapter with a second index target.
- ⏸ **Graph-structured synthesis** is a live seam over the findings graph at *query time*
  (run-local → project-scoped persistent → graph datastore, gated on an entity-resolution-
  quality bar) — **never** an ingestion-time global KG (rejected: re-creates the v2 monolith).

## Versioning, multiplicity & propagation

*(Folded here for the first pass; may split into its own contract when reruns-with-dependencies
land. arch §3.5–§3.6.)*

- **Three grains:** **block** = capture grain (own version chain; summary co-versions);
  **artefact** = snapshot grain (lock-on-advance freezes a named immutable binding of block
  versions; supersede-by-rerun mints the next, prior retained); **project** = living
  aggregate, never frozen.
- **History is linear per artefact** (no branchable tree). Branching lives in the
  cross-artefact **derivation DAG**, not in any one chain.
- **Capability → artefact is one-to-many** (sibling artefacts of the same capability).
  **Supersede is the quiet default** (keeps work in the existing instance); creating a **new
  sibling is the only path requiring an explicit orchestration-plan act** — the
  overwrite-vs-proliferate inference is designed out. The **plan is the registry of artefact
  instances**; dependencies resolve to a **specific instance**, not a capability type.
- **Annotation fate across regeneration**: new version → entirely new unit IDs; **no
  semantic re-anchoring**. Unresolved comments are carried forward as a **block-level
  resolution checklist** (flag-don't-drop). `same_content_as` auto-resolves unchanged units.
- **Edit propagation = two distinct mechanisms**: **staleness** (traverse derivation edges;
  cheap head-version query; **flag, don't auto-run**; `same_content_as` auto-downgrades to
  informational) and **coherence** (a semantic pass within an artefact — no edges to traverse;
  flags what no longer hangs together; orchestrator-mediated, augment-not-replace). Two entry
  points (artefact supersession via traversal; source supersession via provenance
  back-reference), one behaviour. ⏸ Body-level coherence across artefacts is a deferred seam.
  🟡 the magnitude threshold is open (eval territory).

## Meta-synthesis & cross-artefact derivation

*(arch §3.4.)*

- **v3.0 granularity = block + source-document.** A meta-synthesis combines artefacts and
  uploaded docs and declares *"this section draws on these blocks and these sources"*; a
  downstream artefact's dependencies are **plain foreign keys to a specific `(block, version,
  [unit])`** — so the staleness check is a deterministic head-version query, no LLM matching.
  Reuses the to-source provenance the core artefacts already need — no new machinery.
- ⏸ **Deferred behind the addressable-span seam:** statement-to-statement cross-artefact tracing;
  composing chain-strength across a multi-hop chain; how to display a chain to a reviewer;
  version-pinned cross-artefact staleness; deeper cross-project reconciliation. Buildable later
  *because* spans are addressable from day one.
- ❓ **Inherited-artefact edit — open.** When a meta-synthesis builds on an inherited artefact and
  the user then edits it: **copy-on-write** (fork a local copy) vs **in-place** (edit the shared
  original, propagating to all consumers) is unresolved — provenance cleanliness vs
  single-source-of-truth. Parked.
