# ADR 0010 — Intent-led synthesis sections and substrate-conditional grounding

- **Status:** Accepted — 2026-07-08 (Shabeer Rauf, task-013 contract gate).
- **Date:** 2026-07-07/08 (consolidated record — the decisions here were
  settled across the task-013 contract-gate rounds, several user-driven;
  the round-by-round trail lives in the
  [task 013 contract's revision history](../tasks/013-synthesise/contract.md)).
- **Context doc:** [task 013 contract](../tasks/013-synthesise/contract.md) ·
  [ADR 0009](0009-capability-composes-synthesise-terminus.md) (the terminus
  architecture this realises) ·
  [EB capability § Output structure](../specs/capabilities/evidence-base/capability.md)
  ("a single section mixes grounding modes freely … composed from intent") ·
  [provenance-grounding](../specs/system/provenance-grounding.md) ·
  [v2-synthesis-autopsy](../tasks/013-synthesise/v2-synthesis-autopsy.md) ·
  [spec log, 2026-07-07/08 entries](../specs/log.md).

## Context

The first contracted realisation of synthesise rendered **one grounded
block per facet group**, with intent absent from the synthesis prompts
(inherited from task 012's deliberate intent-exclusion) and all direct
chunk-grounded narrative deferred behind `retrieve`. The user challenged
this as producing an artefact shaped by what-was-studied rather than by
what-was-asked — against v3's founding principles (modularity,
flexibility, collaboration) — and directed an independent, detached design
interrogation (deep-reasoner, fresh context,
contract-as-proposal-not-authority), which confirmed the challenge:
group-per-block contradicted ADR 0009's own plan-shapes-sections
authority; 012's intent-exclusion rationale does not transfer (a facet
partition should be question-independent; synthesis's entire job is
serving the question); and the deliberately narrow IOF findings schema
means findings-only prose can never carry mechanisms, implementation
context, caveats or qualitative texture.

Subsequent gate rounds — each user-driven — removed the remaining
artificial constraints (mode splits, mandatory upstream references, a
hard selection reading-boundary), completed the claim vocabulary to the
spec's full honest-assertion set, adopted the spec's own agent-loop
realisation, and folded in the lessons of a V2 synthesis autopsy and a
30-day field scan (which independently validated
retrieval-as-a-controlled-loop and verification-centric design as the
2026 consensus, and flagged the eval harness as the field's named
project-killer → recommended as the next slice after 013).

## Decision

1. **One substrate-conditional flow, never mode-forked.** Synthesise
   takes explicit fail-closed run references — **all optional**
   (`characterisation_run_id`, `selection_run_id`, `extraction_run_id`,
   `grouping_run_id`; the deepest given resolves the rest transitively
   from the referenced rows' own provenance, explicit mismatches
   structural failures). The requirement is **≥ 1 groundable substrate**
   (zero → structural failure, no artefact). Claim types, tools and
   sectioning inputs are gated by what the referenced runs actually
   produced; a characterise-only run is the landscape degenerate case, a
   rapid run (no characterise, no deep chain) a grounded answer over
   appraised screened evidence. The orchestrator's registry
   freedom (ADR 0009) is preserved by construction — e.g. a question
   outside the intervention–outcome schema is served by
   characterise → select → synthesise with **no extract**.
2. **The artefact is structured as intent-led sections.** The section
   set derives from the user's intent via one bounded schema-constrained
   proposal call (`synthesise_sections_v1` — intent + available
   substrate summaries in, a validated capped section list out; an
   answer-shaped lead section is explicitly legal, verdict-sections are
   not), overridable by a fail-closed `context["synthesis"]` directive —
   the compile target of the plan-shaped-sections seam. Intent also
   enters the writer prompts as emphasis-shaping **data** (id-keyed,
   never instructions). Intent is orthogonal to grounding: no claim
   passes verify because of intent ("topical relevance ≠ support"). The
   recomputable unit is `(config-including-intent, evidence)` — 012's
   intent-exclusion was grouping-specific and does not bind synthesis.
3. **The section loop — the repo's first agent loop, exactly one such
   surface.** Per section, `synthesise_section_v1` (system prompt + tool
   schemas, one versioned unit) runs a capped tool-calling loop — the
   realisation execution-orchestration declares for synthesise, running
   *inside* the component per the facade principle (the capability
   sub-agent invokes synthesise as one tool; there is no second agent) —
   over **three read-only, code-scoped tools**:
   - **`search_chunks`** — a staged pipeline: content-only hybrid
     relevance (embedding cosine + lexical, rank-fused; metadata never
     feeds the relevance leg — 010's signal-attributability rule) →
     arithmetic soft priors (the selection look-here-first boost where
     referenced + the directive's `retrieval_boosts`: select's
     vocabulary, clamped multiplicative weights over columns / tags /
     appraisal tier, re-weight-never-exclude, malformed fails closed,
     unknown keys surface via `unmatched_boosts`; the surface the future
     source/evidence policy compiles into, honouring plan-as-object's
     steerable-never-baked quality-prior ruling) → a **cross-encoder
     reranker stage** (`ChunkRerankerBackend` protocol, pass-through v1
     recorded as `reranker: "none"`; the live Bedrock Rerank backend and
     its public injection point land with the Bedrock slice — no public
     kwarg while nothing live exists) → caps. Scope = the **screened-in
     corpus** always, each returned chunk carrying its origin
     (`selected` | `unselected_screened`); guarded by the fail-closed
     `RETRIEVAL_UNIT_CAP`. The 009 unit vectors' first reader; the
     `retrieve` seam's first increment.
   - **`query_findings`** (with an extraction) — the findings-layer
     read; discharges task 012's recorded deferral with its named
     deliberative consumer.
   - **`lookup`** (always) — the universal-core canonical-state read:
     appraisals, classifications, selection rationale, coverage records,
     characterisation/grouping rows, and the tag layer; closed query
     vocabulary, project-guarded.
   Hard bounds, enforced in code: `SECTION_TURN_CAP` (exhaustion forces
   emission with whatever was gathered, flagged `turn_cap_hit` — never
   an unbounded loop), per-call and gathered-context budgets, closed
   tool set, no egress verb. Budgets are pre-run **maxima**: generation
   calls ≤ 2 + `SECTION_CAP` × (`SECTION_TURN_CAP` + 3) — loop turns
   incl. the claims emission, the initial judge call, and the bounded
   repair pair.
4. **Six typed claims, substrate-gated, each with its own deterministic
   validation** — the spec's full honest-assertion vocabulary:
   **finding** (cite finding ids → extract-verified anchors; the model
   never authors these quotes) · **chunk** (verbatim quotes from
   tool-returned frozen text only; the claimed location is untrusted —
   verified spans become the citation rows) · **pattern** (counts must
   equal computed values) · **theme** (the interpretive clustering
   shape — characterise themes / facet groups — validated against the
   referenced clustering row; softest grade, base-labelled; named
   "theme" for the policy-maker audience, matching the spec's own
   "thematic clustering"/"facet-level theming"; `cluster` remains the
   internal tool verb) · **gap** (graded, coverage-base-carrying;
   corpus-level absence fail-closed on a non-`inadequate`
   `search_coverage_record`, else degraded and counted;
   `not_selected`/`not_extracted` never license absence) · **reasoning**
   (uncited, visibly Tier-4-labelled, bounded per block, judge
   strict-routed, never in strength roll-ups). No silent uncited path.
   Two invariants from the V2 autopsy: **renderings never escape
   verification** (structured/tabular renderings decompose into these
   same typed claims — V2's deterministically-rendered table bypassed
   grounding entirely) and **citation-bearing evidence is verbatim**
   (frozen-chunk text / verified anchors only; model-authored summaries
   never serve as citation evidence — V2 primed its writer on
   re-summarised truncated chunks).
5. **Verification is non-agentic and rewrites down.** Two parts, neither
   the writer: the **deterministic legs** (quote-presence via
   `QuoteMatcher` against frozen chunks; the per-type validators) are
   pure code, and the **judge** (`grounding_judge_v1`) is a separate,
   single-call, schema-constrained surface — single lane (exactly one of
   Tier 1–4 / Unsupported-mis-cited), orthogonal weakly-grounded flag,
   required rationale, input including the cited chunks' full frozen
   text (`synthesis_envelope_v1`). **Maker ≠ checker at the surface
   level**; the seam permits a heterogeneous judge model at the Bedrock
   swap; judge calibration is the eval workstream's. The judge's
   rationales drive **one loop-free reword-down regeneration + one
   re-judge** (`REPAIR_ROUND_CAP` = 1; no new tool calls on repair; a
   passing claim survives a sibling's repair verbatim — the V2
   whole-section-regeneration lesson). Exhaustion → soft-flagged, never
   dropped, never silently promoted — with one hard exception: a chunk
   claim whose quote fails presence after repair is **excluded and
   counted** (fabrication is the hard-fail class; V2 persisted
   hallucinated quotes with support intact). Judgements persist
   eval-ready (judge model + prompt version + envelope version on the
   annotation; full I/O on telemetry; no `calibration_status` anywhere).
6. **Groups are input, not structure — pure intent-led.** Group
   summaries inform sectioning and emphasis as data; no descriptive
   backbone blocks are rendered (user choice; the hybrid backbone was
   offered and declined). Recorded trade: the always-visible rendered
   full-shape check on intent-shaped prose is given up; the remaining
   guards are pattern-claim validation, the judge lane, the disciplined
   gap machinery, and honest `groups_unsectioned` accounting (sections
   need not cover every group — uncovered groups are counted, never
   silently dropped).
7. **Sections are written serially with a rolling claim ledger.**
   Proposal order; each loop is seeded with prior sections' typed claims
   marked **context-never-evidence** (block content is the claims' texts
   joined, so the ledger *is* the sections as written, plus structure);
   ledger records are structurally uncitable — cited ids must be
   finding/chunk ids, so sibling-content citation is impossible by
   construction (the citation-scope rule).
8. **The consensus boundary stands** (user-confirmed as the intended
   v3.0 line): the artefact describes the direction-spread, never "the
   evidence supports X", until the ⏸ weighted-consensus seam lands.

## Consequences

- Task 013 implements one substrate-conditional flow of intent-led
  sections: **three prompt surfaces** (`synthesise_sections_v1` ·
  `synthesise_section_v1` — the section loop, multi-turn ·
  `grounding_judge_v1`), with tool-retrieved screened-corpus frozen text
  entering the writer turns (the 011 source-text egress class).
- `synthesis_result` carries the substrate profile, retrieval scope +
  priors + reranker mode, section provenance (the section set, its
  derivation source, unassigned groups) and per-section block entries
  with claim counts by type — a run roll-up pointing at its artefact,
  never the artefact store (the 001 substrate is).
- Budgets stay pre-run-known as maxima; all caps plan-pinned and
  binding (configured == enforced — the V2 dead-config lesson,
  test-asserted).
- The eval harness (synthesis/judge/retrieval quality; judge
  calibration) is the recommended next slice after 013, per the field
  scan's no-evals-sinks-projects warning; 013's eval-ready persistence
  is what makes it cheap.

## Rejected

- **Group-per-block as the artefact structure** — an evidence
  *organisation* mistaken for an artefact *structure*; intent-blind and
  thin by IOF-schema construction (the founding challenge of this ADR).
- **Hybrid with a rendered group-spread backbone** (the interrogation's
  and the lead's recommendation) — declined by the user in favour of
  pure intent-led sections; the trade is recorded in decision 6.
- **Mode splits** (landscape path / deep path; later landscape
  synthesis / findings-grounded synthesis) — every split artificially
  constrained the orchestrator's registry freedom; dissolved into
  decision 1's substrate-conditional gating. A separate landscape
  prompt died with them (four surfaces → three).
- **Mandatory upstream references** (grouping, then characterisation) —
  each was an unprincipled residue; all references are optional under
  decision 1.
- **Whole-document windowing as writer context** — crowds context with
  irrelevant text and scales cost with length, not relevance; replaced
  by the staged retrieval pipeline (decision 3).
- **A hard selection reading-boundary** — inverted the data-model's
  soft-prior scoping principle; the selection is a rank boost, never a
  filter.
- **Evidence pre-allocation at the proposal** — inverts relevance-driven
  selection; rejected outright.
- **A write-time coherence pass** — the data-model's coherence mechanism
  belongs to its original regeneration-time home; the rolling ledger
  owns write-time coherence.
- **Structure discovery in-slice** (recon-informed proposal,
  structure-mismatch signals, bounded revision checkpoint) — deferred
  with a trigger: revisit as a seam with evidence if one-shot structure
  proves a real problem after the slice lands.
- **Model-authored quotes for finding claims** — finding claims cite ids
  resolved to extract-verified anchors; only chunk claims carry
  model-emitted quotes, and those face the same deterministic presence
  check extract's own quotes face.
