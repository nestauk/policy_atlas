# 021-icf design research (2026-07-12, owner-commissioned)

Two streams, run at contract stage before adjudicating the field set: (A) web research
into what transferability assessment and options appraisal need as structured inputs
from primary evidence; (B) a survey of the V2 alpha repo (`../discovery_policy_atlas`)
— what it extracted, how it was consumed, and the transferability forecast feature.
Condensed here as the durable design provenance; the contract's field set and gate
decisions 1–3 were amended against it.

## A. Frameworks research — the converging design line

Every framework examined separates three provenance layers, consistently:

1. **Source-extractable** — what the document states: what was delivered, to whom,
   where, how, with what fidelity, what helped/hindered, what it consumed. The entire
   legitimate ICF territory.
2. **Analyst/target-supplied** — properties of the decision context no document can
   contain: local acceptability, budget, objectives, MCDA weights/criteria, target
   population, receiving-organisation readiness, the transfer/adaptation plan.
3. **Comparative judgments** — the load-bearing transferability calls (GRADE
   indirectness, Wang, TRANSFER stages 4–5, PIET-T P/E) are all
   `distance(source_value, target_value)`. **Extraction captures the source side of
   each pair; the comparison operator and target value live in the future capability.**
   GRADE EtD makes this architectural (research-evidence column vs
   additional-considerations column).

Frameworks covered: TRANSFER (NIPH, Munthe-Kaas 2020, PMC6967089) · PIET-T
(Schloemer & Schröder-Bäck 2018, PMC6019740) · Wang/Moss/Hiller 2006 applicability/
transferability · CICI (Pfadenhauer 2017, PMC5312531) · RE-AIM (Glasgow; Gaglio 2013)
· PRECIS-2 (Loudon 2015, BMJ h2147) · GRADE indirectness (Guyatt 2011) + EtD
(Alonso-Coello 2016, BMJ i2016; Moberg 2018) · HM Treasury Green Book (2026 edn) +
DESNZ MCDA guidance · CFIR 2.0 (Damschroder 2022) · FRAME (Wiltsey Stirman 2019) ·
Carroll 2007 fidelity · TIDieR (Hoffmann 2014; the 39%-adequacy statistic Hoffmann
2013).

**Top source-extractable demands** (multi-framework, both consumers):
1. Finding as construct + valence + socio-ecological level (CFIR coding practice;
   EtD feasibility/acceptability).
2. Setting/population/geography at finding grain — the source side of every
   comparative judgment.
3. Intervention-as-delivered facets (TIDieR dose/mode/provider/training) — most
   demanded AND worst reported (39% adequacy) → recorded as the
   `intervention_specification` schema candidate, not ICF cargo.
4. Adaptations (FRAME: what/planned-vs-reactive/why/core-preserved) — chronically
   undocumented, hence high-value when present.
5. Fidelity delivered-vs-planned (Carroll; TIDieR 11–12) — "intervention failed" vs
   "implementation failed".
6. Resource/cost + workforce observations (EtD resources; Green Book benchmarks) —
   the only economic input a primary document supplies; repricing needs setting/year.
7. Reach/uptake/acceptability observations (RE-AIM; EtD acceptability) — qualitative
   side expressible as barrier/enabler; numeric side is `reported_statistic` territory.
8. Sustainability/maintenance observations — weakest-reported RE-AIM dimension.

**Cross-cutting rules adopted:** extraction never emits transferability verdicts;
context fields are expected-missing with "not reported" distinct from "absent"
(validates `field_coverage`); no universal closed factor list (stable spine + free
claim text beats a giant enum — Atkins); mechanism claims are usually stated-as-theory
not demonstrated (realist/RAMESES practice) → record the stated basis, never force CMO
completeness. **Process evaluations publish separately from trial results 76% of the
time (median 15.5 months, PMC7650157)** → implementation and effect findings for one
intervention routinely live in different documents: validates reference-mediated
cross-document linkage; recorded as a companion-document retrieval seam for the future
transferability capability.

## B. V2 survey — what to pull through, what to drop

V2 had three independent transferability surfaces over one extraction:
(a) a document-level score (context-fit × constraint veto vs user tolerances) that
**dampened the impact ranking**; (b) an intervention-theme rating
(Excellent→Poor + implementation-requirements = max of cost/staffing/complexity);
(c) the **forecast chatbot** — a realist CMO engine with hard verdict ceilings
(Strong/Conditional/Weak/Insufficient). None of the extracted profile ever reached
briefing narrative text. No evals existed for any surface.

**Pull through (into the 021 design):**
- The forecast's `EvidenceBasis` provenance tag (`empirical | author_hypothesis |
  theory_background`) → ICF's three-way `claim_basis`.
- The inner-setting rule (near-verbatim into `extract_icf_v1`): the setting where
  recipients EXPERIENCE the intervention, not the mandating institution.
- The forecast's CMO decomposition maps onto `context_type` (mechanism ✓; support
  factors ≈ implementation_condition; moderators/dealbreakers ≈ barrier/enabler) —
  independent confirmation of the vocabulary cut.
- Downgrade-only critic philosophy ≈ flag-not-drop vetter.

**Drop, with the lesson recorded:**
- High/Moderate/Low ordinals under "**Infer from context if not explicit**" (null
  reserved for "truly unknowable") — extraction-time judgment, unanchored; the
  recorded anti-pattern behind the contract's never-infer/never-grade prompt line.
  (`complexity` fails source-groundability entirely and does not carry.)
- Prompt-only "enums" (schema was free-text `Optional[str]`) → strict Literals +
  CHECKs.
- Judgment coupling at extraction (transferability dampening impact scores ×
  `transferability**0.3`) — V2's own carve-out doc flags removal; V3 keeps judgment
  downstream of extraction by architecture.
- Document-level `StudyContext` fallback → superseded by finding-grain references.
- Hardcoded `["UK"]` target geography → target context is analyst-supplied at
  analysis time, per every framework.
- The forecast **re-extracted from chunks because it didn't trust the analysis-layer
  extraction** — the pathology the findings layer exists to cure; ICF's bar is that
  the future transferability capability reads it instead of rebuilding it.

Key V2 files: `backend/app/services/analysis/schemas_langchain.py` (models),
`analysis/prompts.py:204-229` (profile prompt), `analysis/scoring.py:225-318` +
`storage.py` (doc-level score), `synthesis/nodes/impact_synthesis.py:1040-1314`
(theme rating), `chatbot/prompts.py` + `chatbot/extraction_models.py` (forecast CMO),
`docs/backend/impact_assessment.md` + `V2_EVIDENCE_PIPELINE_CONTEXTUAL_REPORT.md`
(V2's own carve-out analysis).

## Resulting contract amendments (folded 2026-07-12)

`context_type` + `adaptation` + `fidelity` (7 values) · `level` enum
(system·organisation·provider·recipient) rides gate decision 2 · `claim_basis`
three-way · inner-setting rule + never-infer/never-grade lines in the prompt ·
`intervention_specification` joins the schema-candidate ladder · companion-document
retrieval seam recorded · replay probe set extended (adaptation/fidelity-bearing
process evaluation; dual-kind document).
