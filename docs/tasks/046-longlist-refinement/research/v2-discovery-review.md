# V2 review: how the previous Policy Atlas produced and assessed its output

- V2 commit read: `db3027a test(search-exp): skip query-set tests when queries.jsonl is absent` (repo `discovery_policy_atlas`)
- Date: 2026-09-29
- Input for the owner, not a decision. V2 is evidence of one way to do it, not authority.

All paths below are in the V2 repo unless marked "V3". "Inferred" marks what I reasoned but did not read. The code in `backend/app` changed very little between the commit that `V2_EVIDENCE_PIPELINE_CONTEXTUAL_REPORT.md` describes (`b7d1308`) and `db3027a`: 7 backend files, 73 lines, all in synthesis prompts and state. So that report's line numbers mostly still hold. I checked the ones I quote.

## Summary

- V2 ran everything on every relevant document: full-text extraction of issues, interventions, results and a conclusion, then scoring, then a global theming and briefing graph. It ran in one HTTP request.
- It judged many things. Each judgement was small and had its own scale. Deterministic code then combined them into verdicts, stars and 1–5 scores.
- Its implementation profile had three aspects (cost, staffing, complexity), each High / Moderate / Low, judged per intervention in one study, from full text. Bands were defined by words only. They were not anchored to numbers or compared across options.
- Its outcome handling was rich at the level of one result (direction, size, CI, comparator, population, stratum). It did not separate observed from modelled results. Its cross-study summary was a count of directions, weighted by evidence tier.
- No judgement was ever validated against expert labels. The team's own blog says "a structured evaluation of this methodology against expert judgement is still to come" (`docs/blog/impact_assessment.md:292`).

## 1. The pipeline

Order of steps (`backend/app/services/analysis/service.py`, then `backend/app/services/synthesis/agent.py`):

1. Search wizard: suggest populations, outcomes, settings, extra questions.
2. Query generation: 5 boolean queries for OpenAlex, 1 semantic query for Overton.
3. Search: up to 15 OpenAlex calls plus Overton; metadata and abstracts only.
4. Relevance screen: title and abstract, batches of 25.
5. Evidence category: title, abstract and metadata, batches of 25.
6. Acquire and parse full text (PDF or HTML) for relevant documents.
7. Extraction: a 5-stage chain per document on full text.
8. Document scoring: evidence stars, transferability, impact score, harm flag.
9. Chunk and embed for retrieval.
10. Synthesis: themes for issues, interventions, outcomes and risks.
11. Coverage, aggregated tables, impact synthesis (verdict, magnitude, fit).
12. Retrieval and contextual summarisation per theme.
13. Briefing: agentic gather, write, ground, per section.

| Step | Takes in | Produces | Model (tier) | Calls | Text |
|---|---|---|---|---|---|
| 1 Wizard | question | option lists | gpt-4.1-mini (`core/config.py:130`) | about 4 per run | none |
| 2 Queries | question, population, outcome, geography | 5 boolean + 1 semantic query | gpt-4.1 at temp 1.0, n=5 (`core/config.py:124-127`); gpt-4o-mini | 6 per run | none |
| 4 Screen | title, abstract | `is_relevant`, confidence, reason, `top_line` | gpt-4.1-mini (`core/config.py:135`) | 1 per 25 docs (`analysis/relevance.py:301`) | abstract |
| 5 Category | title, abstract, metadata | one of 9 categories, confidence 0–1 | gpt-5.2 (`core/config.py:136-138`) | 1 per 25 docs (`analysis/evidence/category.py:225`) | abstract |
| 7 Extraction | full text, capped at 75,000 chars (`core/config.py:149`) | issues, interventions, mappings, results, conclusion | gpt-4o-mini for 4 stages, gpt-5-mini for conclusions (`analysis/workflows/base.py:42-49`) | 4 + one per intervention (2–6) per doc; plus a yes/no check per SR "intervention variant" stratum (`analysis/workflows/sr.py:23-50`) | full text; abstract if no text |
| 8 Scoring | extracted fields, user target context | transferability 0.2–1.0, impact 1–5, stars 0–5, harm flag | scoring LLM (`analysis/storage.py:273`) | 3 per doc (geography, population, setting) + 1 per primary outcome, sequential (`analysis/scoring.py:244-263`, `:416-440`) | extracted fields |
| 10 Themes | "concept" strings built from extractions | named themes, assignments | gpt-5-mini discover; gpt-5-nano map, one call per concept (`synthesis/utils.py:22-23`, `synthesis/nodes/theme_discovery.py:164`) | 4 branches × (discover + critique) + 1 per concept | extracted fields |
| 11 Impact synthesis | outcome themes, result rows, doc scores | verdict, magnitude, fit rating, impact summary | gpt-4o-mini (`synthesis/nodes/impact_synthesis.py:81-83`) | 1 threshold call per outcome theme; about 6 fit calls + 1 summary per intervention theme, looped one theme at a time (`:331`, `:406-445`) | extracted fields |
| 12 RCS | chunks per theme | relevance 0–10 and a summary per chunk | gpt-4.1-mini (`synthesis/tools/models.py:22`) | 1 per chunk per theme; "over a hundred" per run (`docs/blog/synthesis.md:125`) | chunks |
| 13 Briefing | tool results | 5+ sections with citations | gpt-5.2 orchestrator, gpt-5-mini writer and grounder (`synthesis/tools/models.py:10-18`) | up to 10 tool calls per section + write + ground + 2 retries (`synthesis/tools/orchestrator.py:152`) | chunks |

Per document, steps 7 and 8 make roughly 10 to 15 calls, each re-reading the full text in step 7 (inferred from the counts above; `docs/backend/extraction-research-methodology.md:230` says "4 + number_of_interventions per document").

## 2. The output

The project page has two tabs, Summary and Evidence (`frontend/app/(main)/projects/[projectId]/page.tsx:1199-1210`).

**Summary tab.** Stat cards (Overton count, OpenAlex count, intervention themes, interventions), then the executive briefing (`frontend/app/(main)/results/ExecutiveBriefing.tsx`). The briefing object is `StructuredBriefing` (`backend/app/services/synthesis/schemas.py:437-446`):

- `core_answer: CoreAnswer` (`query`, `answer`, `directive`)
- `evidence_snapshot: List[EvidenceSnapshotRow]` (`metric`, `detail`) and `evidence_snapshot_summary: str`
- `background_section` (`title`, `paragraphs`, `citation_numbers_used`)
- `interventions_table: List[InterventionTableRow]`, 4 to 8 rows
- `synthesis_sections` (0–2 dynamic sections)
- `recommendations: List[RecommendationItem]` (`number`, `title`, `description`, `implementation_option`, `citation_numbers`)
- `follow_up_suggestions: List[str]`

`InterventionTableRow` (`schemas.py:301-359`): `intervention_name`, `context`, `key_study_description`, `key_study_citation`, `population_applicability`, `outcome_relevance`, `delivery_features: List[str]`, `subgroup_effects: List[str]`, `impact_narrative`, `outcome_effects: List[OutcomeEffect]`. The LLM wrote each cell as prose. Code rendered the table (`orchestrator.py:112-150`).

**Evidence tab, interventions.** A sortable table of interventions (`frontend/components/interventions/NavigatorInterventionsTable.tsx:283-304`): Intervention · Country · Type · Evidence Category · Evidence (stars) · Impact · Sample Size. Filters "Min Impact" and "Min Evidence" (`InterventionsNavigator.tsx:568-573`). A row expands into result cards: outcome, direction badge, k and N for reviews, effect size, p-value, CI, I², τ² (`NavigatorInterventionsTable.tsx:440-600`).

**Intervention theme detail** (`frontend/components/interventions/ThemeDetailView.tsx:420-545`), in order: name and description; "Impact" with a tier badge and an impact summary; "Evidence" with a tier badge and a sentence on the evidence mix; "Key outcomes" as one card per outcome theme with verdict, causality, magnitude and a consensus bar (`frontend/components/synthesis/ImpactProfileCard.tsx`, `ConsensusMeter.tsx`), with "insufficient evidence" outcomes folded away; "Context fit"; "Implementation requirements" (Cost, Staffing, Complexity, each a band plus one sentence, with an overall band); risk warnings.

The theme object is `PolicyIntervention` (`schemas.py:620-643`): `intervention_name`, `brief_description`, `impact_summary`, `frequency`, `supporting_doc_ids`, `effect_consensus`, `positive_count`, `negative_count`, `null_count`, `sample_effect_sizes`, `countries`, `study_types`, `related_outcomes`, `transferability_rating`, `transferability_note`, `transferability_breakdown`, `impact_score: float`, `impact_score_label`, `impact_score_breakdown`. The outcome object is `OutcomeTheme` (`schemas.py:559-581`), with `effect_consensus`, the three counts, `verdict_label`, `verdict_description`, `discord_flag`, `predicted_magnitude`, `magnitude_detail`, `primary_causal_mechanism`. The per-document records are `InterventionItem` and `ResultItem` (`backend/app/services/analysis/schemas_langchain.py:44-139`).

There were no maps. Consensus was a stacked bar of weighted positive, null and negative counts.

## 3. The assessments

| # | Assessment | Scale (verbatim) | Unit | Input | Prompt / code | Schema | Across the set? |
|---|---|---|---|---|---|---|---|
| 1 | Relevance | bool + confidence 0–1, "+0.2" for each of question, population, outcome, screening factors, geography | document | title + abstract | `analysis/prompts.py:104-128` | `analysis_documents.is_relevant` | one at a time (25 per call, judged alone) |
| 2 | Evidence category | 9 labels, "Systematic Review and Meta-Analysis" … "Unknown / Insufficient information"; confidence bands 0.8–1.0 / 0.5–0.79 / 0.0–0.49 | document | title + abstract + metadata | `analysis/prompts.py:581-722` | `analysis/evidence/category.py:47-130` | one at a time |
| 3 | Evidence stars | 0–5 from category base (5,4,3,2,2,2,1,0,0), −1 if causal N<100, caps: single SR 4, single RCT 3, single observational 2, density <2.5% → 3 | document, then intervention | category + extracted N | code only | `analysis/evidence/strength.py:362`, `:441-527`; `category.py:158-168` | yes: density cap uses the project's total |
| 4 | Implementation profile | `cost_level`, `staffing_level`, `implementation_complexity_level`: "High \| Moderate \| Low \| null (only if truly unknowable)", with word definitions (see § 5), plus 1–2 sentence justification | intervention in one study | full text | `analysis/prompts.py:204-229` | `schemas_langchain.py:62-68` | one at a time |
| 5 | Inner setting | free text, "the setting where recipients experience the intervention" | intervention | full text | `analysis/prompts.py:205-208` | `schemas_langchain.py:62` | one at a time |
| 6 | Study context fallback | same three bands, "Prefer the dominant or typical level" | document | full text | `analysis/prompts.py:349-356` | `schemas_langchain.py:161-175` | one at a time |
| 7 | Effect direction | `increase \| decrease \| null \| mixed \| inconclusive` | result row | full text | `analysis/prompts.py:284`, `:477` | `schemas_langchain.py:14` | one at a time |
| 8 | Beneficial | `is_beneficial` true/false, "BMI decrease is beneficial" | result row | full text | `analysis/prompts.py:296-297` | `schemas_langchain.py:135`, default `True` | one at a time |
| 9 | Causality claim | "attribution: Author claims intervention CAUSED", "contribution: … HELPED", "correlation: … association only" | result row | full text | `analysis/prompts.py:287-290` | `schemas_langchain.py:25` | one at a time |
| 10 | Magnitude (per result) | `substantial \| large \| moderate \| marginal \| unknown`; no definitions in the RCT prompt: "Semantic effect size bucket for this result" | result row | full text | `analysis/prompts.py:312`, `:500-501` | `schemas_langchain.py:17-24` | one at a time |
| 11 | Primary / prevalence-only / harm | booleans `is_primary`, `is_prevalence_only` ("If unsure, set is_prevalence_only=true"), `negative_impact_flag` | result row | full text | `analysis/prompts.py:292-310` | `schemas_langchain.py:132-138` | one at a time |
| 12 | Risks | `risks_identified: List[str]`, `unintended_consequences_detected: bool` | document | full text | `analysis/prompts.py:338-347` | `schemas_langchain.py:154-158` | one at a time |
| 13 | Outcome similarity | "1.0 = Directly measures … 0.7 = Established proxy … 0.4 = Contributing factor … 0.1 = Same broad domain … 0.0 = Unrelated" | result row vs user outcomes | outcome label | `analysis/scoring.py:336-362` | breakdown JSON | one at a time |
| 14 | Context match | `match \| similar \| comparable \| partial \| mismatch \| unknown`, scored 1.0 / 0.85 / 0.7 / 0.4 / 0.15 / 0.5 | document, per dimension | extracted country, population, setting | `analysis/scoring.py:196-212` | `scoring.py:11-18` | one at a time, UK hard-coded (`storage.py:259`) |
| 15 | Document impact | 1.0–5.0, "Very high" ≥4.5 … "Very low" <1.5 | document | #8–#14 | code | `analysis/scoring.py:372-500` | no |
| 16 | Intervention impact | same scale; max of best-tier docs, caps (1 doc → 4.0, ≤3 docs → 4.3, stars <3 → 3.0), discord penalty | intervention theme | #15 + #3 | code | `analysis/scoring.py:507-704` | within one intervention only |
| 17 | Effect consensus | `increase \| decrease \| mixed \| no change \| insufficient`; increase if pos > 2×neg | outcome/intervention theme | result rows weighted by stars/5 | code | `synthesis/nodes/aggregation.py:254-299` | within one theme |
| 18 | Verdict | 10 labels, `well_evidenced_positive` … `probable_contribution`; thresholds 3 / 8 / 15, contested if ratio > 0.4 | outcome theme | #17 counts | code | `synthesis/nodes/impact_synthesis.py:546-594` | within one theme |
| 19 | Calibrated magnitude | static scales (e.g. SMD 0.2/0.5/0.8/1.2; OR 1.2/1.5/2.0/3.0; percent 5/15/30/50) or LLM thresholds per outcome | outcome theme | extracted effect sizes | `impact_synthesis.py:35-72`, `:125-175` | `schemas.py:527-536` | yes: thresholds use all effects for the outcome |
| 20 | Context fit rating | "Excellent Fit" ≥0.85, "Good" ≥0.70, "Moderate" ≥0.50, "Limited" ≥0.30, "Poor"; any mismatch → Poor | intervention theme | #14 per dimension | `impact_synthesis.py:1277-1303` | `schemas.py:511-524` | no |
| 21 | Implementation requirements | per dimension: the most common band across studies; overall: the highest ("max rule"), shown High / Medium / Low | intervention theme | #4, #6 | `impact_synthesis.py:811-841` | `TransferabilityBreakdown` | across studies of one theme |
| 22 | Harm warning | true if any adverse result, or more than 2 risks | document | #11, #12 | `analysis/scoring.py:112-130` | `analysis_documents.has_harm_warning` | no |
| 23 | Coverage strength | "High" if ≥3 reviews or ≥5 RCTs; "Moderate" if ≥1 review or ≥2 RCTs; else "Low" | run | category counts | `synthesis/nodes/aggregation.py:101-106` | `schemas.py:455-481` | yes, whole run |
| 24 | Grounding | `direct \| synthesised \| inferred` per claim | briefing claim | chunks | `synthesis/tools/orchestrator.py:74`, `:1285` | `synthesis_citations.attribution` | no |
| 25 | Chat transfer view | "Strong / Conditional / Weak / Insufficient", with ceilings | intervention, in chat | chunks | `services/chatbot/prompts.py:11-72`, `:336` | none | no |

Only #3, #19 and #23 used the rest of the set. Every LLM band (#4, #7–#14) was judged on one item alone.

## 4. Outcomes

**Extraction.** One results call per intervention asks for "1–5 MECE RESULTS showing the intervention's effects" (`analysis/prompts.py:266`). Each `ResultItem` records `outcome_variable`, `effect_direction`, `effect_size_type`, `effect_size`, `uncertainty`, `p_value`, `population_measured`, `subgroup_or_dose`, `result_text` and a verbatim `supporting_quote` (`schemas_langchain.py:73-139`). The review prompt adds `n_studies`, `sample_size`, `heterogeneity_I2`, `tau2` and strata, and a good rule: "outcome_variable: The BASE outcome measure ONLY … WRONG: outcome_variable="BMI at 12 months" … CORRECT: … stratum_type="follow-up period"" (`analysis/prompts.py:453-459`). Size, units and CI were free strings.

**What it recorded.** Direction: yes. Size: yes, as a string. Units: only inside `effect_size_type`. Comparator: at intervention level (`InterventionItem.comparator`, `schemas_langchain.py:59`), but the RCT prompt's schema never asks for it (`analysis/prompts.py:181`), so it was likely empty for most studies (inferred). Time period: only as a review stratum. Population: yes (`population_measured`).

**Observed versus modelled.** Not separated. `estimate_level` is `study | pooled | claim`, set by code from the workflow, and "claim" was never produced (`V2_EVIDENCE_PIPELINE_CONTEXTUAL_REPORT.md:260-261`). "Modelling & Simulation" is an evidence category (`analysis/prompts.py:615-623`), but such documents go through the RCT workflow, the default (`analysis/workflows/routing.py:81-92`). So a projected effect became an ordinary result row with a causality label.

**Combining studies.** Code counted result rows by direction, each weighted by the document's stars / 5, and rounded up (`synthesis/nodes/aggregation.py:255-289`). It then applied the consensus rule (#17) and the verdict rule (#18). The weighted counts, not studies, crossed the 3 / 8 / 15 thresholds. The team noted: "Directional counts currently operate at the result-extraction level, not the document level" (`docs/blog/impact_assessment.md:272`). A gpt-4o-mini call then wrote a 2–3 sentence summary that must "Note the evidence strength (well-evidenced, evidenced, or suggested)" (`impact_synthesis.py:751-763`).

**Uncertainty labels.** Uncertainty was carried by the verdict words ("suggested", "contested", "insufficient_evidence") and by the causality downgrade to `probable_contribution` when no result claimed attribution (`impact_synthesis.py:591-592`). CIs were shown raw per result. One unused prompt pulled the other way: "Be direct: do not hedge or use phrases like 'the evidence suggests'" (`synthesis/prompts.py:517`; no caller found).

**A defect.** The docs say mixed and inconclusive results count in no bucket (`docs/backend/impact_assessment.md:467-476`). The code checks `is_beneficial` before direction, and `is_beneficial` defaults to `True` (`aggregation.py:262-266`; `schemas_langchain.py:135`). So a "mixed" or "inconclusive" result counts as positive whenever the model marked it beneficial. The verdicts lean positive (inferred from the code; not measured).

## 5. Bands and calibration

**Implementation bands (#4).** Words only, no numbers, no reference class (`analysis/prompts.py:210-228`):

- Cost. "High: significant capital investment, high ongoing operational costs, specialist equipment"; "Moderate: structured programme costs, ongoing consumables, facility requirements"; "Low: minimal financial outlay, uses existing resources, low-cost materials".
- Staffing. "High: specialist professionals required, intensive staffing ratios"; "Moderate: trained staff required, dedicated personnel"; "Low: minimal staffing, can be delivered by generalists, self-service possible".
- Complexity. "High: legislative/systemic change, multi-agency coordination, significant training required"; "Moderate: cross-team coordination, staff training, ongoing monitoring systems"; "Low: plug-and-play materials, single-session delivery, minimal coordination".

The prompt says "Infer from context if not explicit", which invites guesses. The review workflow's prompt has no profile fields at all (`analysis/prompts.py:407`), so reviews got a band only from the document-level fallback. The UI mixes "Moderate" (extraction) with "Medium" (overall rating, `impact_synthesis.py:838`). V2's complexity band fuses legislation, coordination and training in one scale; that is the composite the owner doubts.

**Anchored bands.** Where V2 anchored, it used numbers or fixed rubrics: the 0–1 outcome similarity rubric with worked examples (#13); fixed match levels with UK calibration examples, such as "Evidence='Germany' -> similar or comparable (NOT mismatch)" (`analysis/scoring.py:189-193`); static effect-size scales (#19); count thresholds for verdicts and coverage. None was anchored to the set of options being compared, except the LLM magnitude thresholds, which read all effect sizes for one outcome.

**Weak points in the anchors.**

- Unknown magnitude scores the same as marginal (both 0.25, `analysis/scoring.py:20-27`). Full-text failures made "unknown" common: "This leads to `magnitude_estimate: "unknown"` for many outcomes and systematically under-scores high-quality sources (e.g. Cochrane)" (`docs/backend/full_text_extraction_issue.md:5`).
- The static scale takes the first number in the string and uses `abs()`. An odds ratio of 0.5 falls below 1.2 and becomes "marginal". Any unknown unit falls back to "percentage". The test `"or" in lower` also matches words like "score" (`impact_synthesis.py:1671-1703`).
- Mismatch is 0.15 at document level (`scoring.py:16`) but 0.0 at theme level (`impact_synthesis.py:1272`).
- Impact is damped by transferability with exponent 0.3 (`scoring.py:478`), then rescaled with 0.4 (`impact_synthesis.py:1551`), and the second overwrites the first in the database.
- The UI's magnitude text calls "substantial" a "large effect size" and has no entry for "large" (`ImpactProfileCard.tsx:32-38`).

**Evidence of accuracy.** I found none for any judgement.

- The impact blog: "a structured evaluation of this methodology against expert judgement is still to come" (`docs/blog/impact_assessment.md:292`). It adds that small models do the threshold and fit calls and "We have not yet systematically evaluated how the outputs … vary across models" (`:282-284`).
- The synthesis blog: "We do not have a systematic evaluation framework for theme quality" (`docs/blog/synthesis.md:129`); RCS value "not yet tested rigorously" (`:125`).
- The categorisation experiment has scripts and an Argilla labelling setup, but no results file (`backend/testing/r_and_d/evidence_categorisation/experiments/`).
- `backend/test/test_evidence_strength.py` tests the star arithmetic, not whether the stars are right.
- The heat pump files at the repo root test search recall, not assessments. Six projects were compared with a manual list of about 20 sources. Exact matching found 0 of 20 (`heat_pump_policy_atlas_comparison.json`, summary). Loose title matching found candidates for 10 of 11 first-section items, 7 of 11 at high confidence (`heat_pump_loose_match_first_section*.json`). The questions were supply-chain questions, where V2's intervention-shaped extraction fits poorly (inferred).

The blog does report one qualitative finding. Rubrics with explicit anchor points "produced more stable and interpretable results than asking it to 'rate the relevance' in its own terms", and calibration examples "helped steer outputs away from known failure modes" (`docs/blog/impact_assessment.md:306-312`). That is a claim of stability across runs, not of accuracy.

## 6. Latency and cost

**Measurements and estimates in the repo.**

| What | Figure | Source |
|---|---|---|
| Extraction per paper | 15–25 s (issues 3–5, interventions 4–6, mappings 2–3, results 2–4 per intervention) | `docs/backend/extraction-research-methodology.md:237-244` |
| Extraction per paper | 15–30 s, sequential | `docs/backend/langraph-extraction-system.md:232` |
| ETA used in the product | 2 min retrieval + 15 s per relevant doc + synthesis 119 + 133 + 518 + 304 s (about 18 min) | `frontend/lib/analysisTimingHeuristic.ts:4-12` |
| Briefing | about 200–400+ LLM calls, 5–15 min | `docs/backend/architectural_suggestions.md:162-163` |
| Cost | "A typical search currently costs approximately £1.50"; "several hundred LLM calls" at 40+ docs | `docs/blog/synthesis.md:137` |

With the wizard default of 30 results per source (`frontend/components/search/SearchWizard.tsx:270`) and two sources, the product's own ETA is about 2 + 9 + 18 = 29 minutes (inferred from the heuristic). The longest synthesis step (518 s) is "Writing executive briefing" (`backend/app/services/analysis/progress.py:15-20`).

**What made it slow.**

1. Everything was extracted. The whole relevant set went through the full chain, with no selection first (`V2_EVIDENCE_PIPELINE_CONTEXTUAL_REPORT.md:291-296`).
2. Full text was re-read in every stage: 4 + k calls per document on up to 75,000 characters. The config says "smaller limits = faster processing" (`core/config.py:151`).
3. Calls ran in series inside a document: results one intervention at a time (`analysis/workflows/rct.py:128`), outcome similarity one primary outcome at a time (`scoring.py:416`), impact synthesis one theme at a time (`impact_synthesis.py:331`, `:406`). Across documents the concurrency was 5.
4. Per-item micro-calls: one nano call per concept to assign themes, one RCS call per chunk per theme, one threshold call per outcome, six small calls per intervention for fit notes.
5. The agentic briefing: up to 10 tool calls per section, then write, ground and up to 2 regenerations.
6. Full-text acquisition: downloads, scraping and parse timeouts of 30 s, with frequent fallbacks (`docs/backend/full_text_extraction_issue.md`).

The implementation profile itself was cheap. It rode inside the interventions call. What made V2's assessments expensive was their unit (every intervention in every document) and their input (full text).

## 7. What is worth bringing in

Costs assume V3's longlist of 25 options from abstracts, batched as in the V3 measurement (5 options per call, 6 calls at a time: 61–62 s, V3 `amendment-2-proposed.md` Part F).

| V2 idea | What it gives the V3 longlist | Cost for 25 options, abstracts | Weakness or risk | Verdict |
|---|---|---|---|---|
| Band + one-line reason per aspect (#4) | the shape of the implementation profile | inside the option profile pass, about 60 s | V2 bands were word-only, per study, "infer from context"; no check | bring in changed: add a basis field, anchor bands (below) |
| V2's band definitions for cost, staffing, complexity | a first draft of anchor text | none | they fuse aspects; complexity mixes legislation, coordination, training | bring in changed: split into V3's 7–8 aspects; reuse the phrases as examples |
| Judging implementation per study, then taking the mode | none for V3 | 1 call per record | ignores the option as a class; mode and max give odd results | leave |
| Anchored rubric with worked examples (#13, #14) | stable, readable bands | a few hundred prompt tokens | stability shown, accuracy not | bring in: put 2–3 reference options per band in the prompt |
| Rating the whole list in one call | bands comparable across options | 1–2 calls, or a second ranking pass of about 1 call | long output; V3 saw setting words drift across batches | bring in: one short pass to re-check bands across all 25 |
| "Cannot judge" as an allowed value (`null (only if truly unknowable)`) | honest gaps | none | V2 made it rare by asking the model to infer | bring in, and make it easy to choose |
| Direction vocabulary `increase/decrease/null/mixed/inconclusive` + `is_beneficial` | an early signal | about 2 fields per evaluated record | increase/decrease needs a second flag; the flag default caused the positive-lean bug | bring in changed: V3's `improved/no difference/mixed/worsened/not reported` is better; no default |
| `is_prevalence_only`, with "If unsure, set … true" | removes baseline statistics posing as effects | none | none found | bring in |
| Base outcome versus stratum rule | clean outcome labels to count against | none | none found | bring in |
| Causality claim (attribution/contribution/correlation) | a hint of study strength | 1 field per record | overlaps V3's evidence tiers; from abstracts, it reflects author wording | leave at longlist |
| Observed versus modelled | a real split V2 lacked | 1 field per record | abstracts may not say | bring in (V3 C1); V2 offers no model to copy |
| Effect size, CI, magnitude buckets | size of effect | 2–4 fields per record | V2 got "unknown" for many from abstracts; the parsing was fragile | leave at longlist |
| Weighted direction counts and verdict thresholds (#17, #18) | one word per outcome | code only | counts result rows, not studies; thresholds never tested; 3/8/15 means little with abstracts | bring in changed: count documents, show raw counts, withhold under a minimum (V3 C3) |
| Contested rule (ratio > 0.4) | flags split evidence | code | untested number | bring in changed: show "mixed" when both sides have 2+ documents; no score |
| 1–5 impact score, stars as sort key | a single rank | code | the blog admits "some users will anchor on it" (`docs/blog/impact_assessment.md:286-288`) | leave (agrees with V3 B6) |
| Transferability fit score | context fit | 3 calls per option | UK hard-coded; V3 keeps it for assessment | leave |
| Harm flag from "more than 2 risks" | a warning icon | code | the count of risks is not a measure of harm | leave |
| Presentation: one row with icons and a sortable table; detail on expand | scanning 25 options | none | V2's table showed 7 columns and hid the profile in the detail page | bring in changed |
| Presentation: one overall band with the three dimensions below it (max rule) | a condensed summary | code | a max rule hides which aspect drives it | bring in changed: name the harder aspects instead of a max band |
| Presentation: fold away "insufficient evidence" items | less noise | none | none found | bring in |
| Presentation: consensus bar (green/amber/red with counts) | outcomes at a glance | none | bars imply precision the counts lack | bring in changed: text counts, no bar, at longlist |

**How to show 8 aspects without overload** (my recommendation, drawn from V2's strengths and faults):

- On the card, show a single line of exceptions: only aspects at the harder end, and any "cannot judge". For example: "Harder: powers (primary legislation), workforce · Cannot judge: cost". An option with no harder aspects shows "No aspect stands out as hard".
- On expand, show all aspects in a fixed order, each as band · one line · basis. This is V2's Implementation requirements card (`ThemeDetailView.tsx:221-290`) with more rows.
- In the list, allow sort and filter by one aspect. V2 had "Min Impact" and "Min Evidence" filters; one per aspect is the same idea without a composite.
- Do not show a single overall band. Under V2's "max rule", one High aspect made the whole option High, and the card did not say which aspect.

**On the owner's question about bands.** V2 shows that unanchored word bands are hard to compare. It never tested them. The V3 finding that bands gather at medium and high matches V2's "Infer from context" design, which reads each item alone (inferred). Two changes answer the owner's point. First, anchor each band to named reference options in the prompt. Second, make one pass that reads the whole list and moves bands so that the list uses the scale. Keep the definition of each band fixed, so that a downstream AI can read "high cost" the same way in every run.

## 8. Known problems in V2's own sources

- Synchronous, in-request runs with no background job, checkpoint or resume (`V2_EVIDENCE_PIPELINE_CONTEXTUAL_REPORT.md:437-445`; `docs/Policy_Atlas_v3_Backend_Architecture.md:666-668`, ALB 60 s idle timeout).
- Full text often fell back to abstracts. This caused "unknown" magnitudes and lowered scores for strong sources (`docs/backend/full_text_extraction_issue.md:5`).
- Already covered above: result-row counting (`docs/blog/impact_assessment.md:272`), mixed evidence "invisible to the verdict system" (`:274-276`, and the code is worse, § 4), UK hard-coded (`:278-280`), users anchoring on scalar scores (`:286-288`), and the 0.3 / 0.4 exponent overwrite (§ 5).
- Theme quality has no evaluation (`docs/blog/synthesis.md:127-129`). The theme critique call's output is thrown away (`V2_EVIDENCE_PIPELINE_CONTEXTUAL_REPORT.md:330`).
- RCS is the most expensive phase and its value is untested (`docs/blog/synthesis.md:125`).
- Grounding is permissive: "Set is_supported=True whenever the source provides any relevant evidence … including reasonable paraphrase and inference" (`synthesis/tools/orchestrator.py:1285`).
- Dead config and code: `screening_enabled`, `BATCH_SIZE_SCREENING`, `ACQUISITION_CONCURRENCY`, the retry helper; each extraction is written twice to `extractions.json` (`V2_EVIDENCE_PIPELINE_CONTEXTUAL_REPORT.md:613-619`).
- Memory bank: the files are unfilled templates. `progress.md` lists only I1–I3 (Supabase credentials, OpenAI key fallback, tests needing keys) (`memory-bank/progress.md:15-18`).

## What remains uncertain

- I did not run V2 or read its database, so I have no real distribution of bands, verdicts or times. The ETA constants may come from measured runs; the commit that added them does not say (`a72afea`).
- The positive-lean bug in § 4 is read from code. Its size on real data is unknown.
- I read the result views by their schemas and headings, not every line (for example `ExecutiveBriefing.tsx`, 1,611 lines).
