# V2 screen + classify methodology autopsy (design-phase recon, 2026-07-08)

Fourth V2 recon leg (theming autopsied in task 009, extraction in 011, synthesis
in 013). Deep-reasoner, read-only, over `../discovery_policy_atlas`
(backend + frontend + repo-root comparison artifacts). Written to adjudicate
task 014 (`contract.md` rev 1.4). All anchors are V2 paths. Structure mirrors the
013 synthesis autopsy.

---

## Scope & sources read

- **Screening (relevance):** `backend/app/services/analysis/relevance.py`,
  `RELEVANCE_SYSTEM_PROMPT` in `backend/app/services/analysis/prompts.py:70-128`.
- **Classification (evidence type):**
  `backend/app/services/analysis/evidence/category.py`,
  `EVIDENCE_CLASSIFICATION_SYSTEM_PROMPT` +
  `EVIDENCE_CATEGORIES_DEFINITION` in `prompts.py:581-723`.
- **Shared batch engine:** `backend/app/utils/llm/batch_check.py` (`LLMProcessor`).
- **Orchestration:** `backend/app/services/analysis/service.py:113-193` (pipeline
  steps 1.5 relevance / 1.75 categorisation).
- **Models/config:** `backend/app/core/config.py:113-146`.
- **Persistence + serialisation:** `service.py:486-540`, `storage.py:1110-1139`,
  CSV export `backend/app/api/projects.py:1820-1875`.
- **Downstream confidence teeth:** `evidence/strength.py:456-461`.
- **Display path:** `frontend/components/documents/PapersTable.tsx:261-289`,
  `frontend/app/(main)/projects/[projectId]/page.tsx:885-919`.
- **Measured evals:** `backend/testing/evals/screening/` (results
  `results/20251120_135440/`), `backend/testing/evals/blueprint_comparison/screening/`,
  `backend/testing/r_and_d/evidence_categorisation/EVIDENCE_CATEGORISATION_PLAN.md`.
- **Comparison study:** repo-root `heat_pump_*.csv/json` + `heat pumps literature.md`.

Two sub-recon agents supplied the eval-harness numbers and the comparison-study
numbers; frontend + backend paths were read directly.

---

## V2 screening methodology (as-built)

**Generative, single-pass, boolean + confidence + reason.** `RelevanceService`
(`relevance.py:28-93`) is not retrieval/embedding-based — it is one LLM call per
document over the metadata envelope. Input is `f"Title: {title}\n\nAbstract:
{abstract}"` (`relevance.py:126`); abstract defaults to the string
`"No abstract available"` when absent (`relevance.py:123`) — **there is no
structural fail-open basis flag**; a missing abstract is just weaker prose fed to
the same prompt.

The model returns four fields via `with_structured_output` (Pydantic dynamic
schema, `batch_check.py:100-109`): `is_relevant` (bool), `relevance_confidence`
(float 0-1), `relevance_reason` (str), `top_line` (str) — `relevance.py:72-93`.

**Model + params:** `SCREENING_MODEL = "gpt-4.1-mini"` (`config.py:135`),
temperature 0.0 (LLMProcessor default, `batch_check.py:50-61`; RelevanceService
never overrides it).

**"Batch" is bounded concurrency, not multi-doc-per-call.** `processor.run(...,
batch_size=25)` (`relevance.py:301`) chunks docs into windows of 25, and
`_process_batch` fires one independent `_invoke_llm` per doc via
`asyncio.gather` (`batch_check.py:187-192`). So each screen decision is already
an isolated per-doc call — **V2 is per-doc fan-out**, matching V3 decision 2. The
"batch" word is a concurrency window, not a shared prompt.

**Confidence is an additive coverage rubric, not a probability.** The prompt
tells the model to build confidence as `+0.2` each for research question,
population, outcome, screening factors, and geography match
(`prompts.py:122-124`), and to "not penalize" for unspecified facets. So
`relevance_confidence` conflates *how relevant* with *how many facets were
specified-and-matched* — a structurally miscalibrated score (borne out by the
eval, below).

**Intent enters as interpolated prompt text, not id-keyed data.** Research
question, population, outcome, screening factors, geography are string-formatted
straight into the system prompt (`prompts.py:88-102`) — the pre-injection-posture
pattern V3 decision 7 closes.

**Recall-leaning by instruction** ("Be inclusive rather than overly
restrictive", `prompts.py:113`) — but **geography is a hard exclusion
instruction** ("mark documents outside those geographies as not relevant",
`prompts.py:117`), a recall risk when geography is set.

**Threshold: none on relevance_confidence.** The downstream filter is the
`is_relevant` boolean alone (`category.py:291`, `service.py:163-173`); confidence
is display/sort-only (`projects.py:1850`, `PapersTable.tsx:266`). This matches
V3's "confidence never a hard exclusion cutoff". (Contrast: classify confidence
*does* have teeth — see below.)

**No consensus / no repeated sampling on the product path.** Single call, single
sample. (The eval *harness* does 5 runs — see comparison-study section — but
production screens once.)

**Failure = silent recall loss.** `_invoke_llm` retries twice
(`batch_check.py:126-179`), then returns `None`; failed docs are dropped from the
JSONL and the merge **defaults them to `is_relevant=False,
relevance_confidence=0.0, relevance_reason="Not processed"`**
(`relevance.py:194-197`). A transient API error therefore silently *excludes* a
document. A whole-batch exception returns the CSV unchanged and only logs
(`relevance.py:157-159`). This is exactly the failure mode V3 decision 5 replaces
with `status='failed'` + retry.

**Cascade:** a false-negative (or failed) screen is terminal — non-relevant docs
are never classified (`category.py:291`) and never acquired (`service.py:438-443`
sets `acquisition_status='not_attempted'`, `error="Document not relevant"`). One
missed screen removes the doc from every later stage.

---

## V2 classification methodology (as-built)

**Same engine, separate service, richer model.** `EvidenceCategoryService`
(`category.py:207-415`) runs *after* relevance, **only over `is_relevant==True`
docs** (`category.py:291`), one LLM call per doc (same `LLMProcessor`, same
per-doc fan-out, `batch_size=25`, `category.py:225,414`).

**The 9 closed categories are V2's, carried verbatim into V3.** Single source of
truth `_EVIDENCE_CATEGORY_DATA` (`category.py:47-130`): Systematic Review/MA · RCT
& Quasi-Exp · Observational · Modelling & Simulation · Policy Syntheses & Guidance
· Qualitative & Contextual · Expert Opinion & Commentary · Other (Non-evidence) ·
Unknown/Insufficient information. Each carries a score, rank, short name, colours,
and explanation. `Other` is the exclusion sink (`is_non_evidence_document`,
`category.py:39-41`; dropped from evidence counts `service.py:160-173`);
`Unknown` is the honest-abstain sink.

**It is prompt-based, closed single-label, with a definitions block.**
`EVIDENCE_CLASSIFICATION_SYSTEM_PROMPT` (`prompts.py:691-723`) embeds a ~100-line
`EVIDENCE_CATEGORIES_DEFINITION` (`prompts.py:581-689`) with per-category
definition + examples + keyword lists, then instructs: pick the SINGLE BEST-FIT,
give reasoning + a confidence band (High 0.8-1.0 / Medium 0.5-0.79 / Low
0.0-0.49, `prompts.py:703-706`). Output fields: `evidence_category` (closed
9-value string enumerated in the field description, `category.py:239-252`),
`evidence_confidence` (float), `evidence_category_reasoning` (str).

**Intent-free** — classification uses only title + abstract + metadata (source,
type, year; `category.py:334-346`), never the research question. Matches V3
decision 4 (and the 011 extract precedent).

**Provider priors are fed, but only as thin free text.** `_format_document`
passes `Source`, `Type`, `Year` inline (`category.py:342-346`) — a precursor to
V3's structured-priors-as-data-fields (decision 4) but unstructured and minimal
(no `record_type`, no Overton `source.type`/`organisation_type`).

**Model: `gpt-5.2`** (`config.py:136-138`), explicitly "needs higher accuracy" —
a *deliberately stronger* model than screening's gpt-4.1-mini. This is the single
most load-bearing tension with V3 (decision 8 uses `gpt-5-mini` for both). See
adjudication.

**Explicit Unknown-vs-Other discipline** (`prompts.py:708-713`): missing info →
`Unknown`, never `Other`; `Other` only for clearly non-evidence docs. This is a
prompt-design win worth carrying.

**Classify confidence HAS downstream teeth** (unlike screen confidence):
`evidence/strength.py:456-461` filters to docs with `evidence_confidence >=
EVIDENCE_CONFIDENCE_THRESHOLD` (0.5, `category.py:158`) before computing the
evidence-strength star rating. A low-confidence classification is dropped from
the strength calculation — a hard, calibration-dependent cutoff.

**Failure semantics differ from screen and are also silent.** Failed classify
calls are dropped from the merge (`category.py:348-364` maps only returned ids),
leaving `evidence_category = NaN` — **not** defaulted to `Unknown`. A whole-batch
failure logs "0/N succeeded" and returns the CSV unchanged
(`category.py:304-310,326-332`). V3 decision 5 formalises the no-row-on-failure
posture (and rejects the stub-era Unknown fallback for the same reason: a failure
is not a classification claim).

**No open methodological/structural tags.** V2 emits only the closed label. The
open-tag output V3 adds (decision 6) has no V2 precedent here.

---

## The comparison-study evidence

Two distinct bodies of measured evidence. **The committed eval harness is the
real screening-accuracy signal; the heat_pump files are a document-identity
recall study, not a screening study.**

### A. Committed screening eval — `evals/screening/results/20251120_135440/`

Harness `evals/screening/run_eval.py` screens with the production
`RelevanceService` (gpt-4.1-mini) against gold labels from CSMeD, SYNERGY, and
3ie EGM datasets; `calculate_metrics` (`run_eval.py:156-217`) emits recall,
precision, F_β2, confusion counts, and **avg confidence per outcome**.

`summary_overall_20251120_135440.json` (30 targets, **13,740 docs**):
- **recall 0.836 · precision 0.634 · F_β2 0.740 · WSS@95 0.187**;
  confusion tp 7025 / fp 674 / fn 3720 / tn 2321 → derived **specificity 0.775**.

Per dataset — **the recall/specificity split is severe and dataset-dependent**:

| dataset | recall | precision | derived specificity | failure mode |
|---|---|---|---|---|
| CSMeD (10) | 0.853 | 0.445 | **0.287** | over-includes |
| SYNERGY (10) | 0.927 | 0.531 | 0.615 | over-includes |
| 3ie (10) | 0.727 | 0.926 | 0.883 | **under-includes** |

Worst individual cases: `Health_AnaemiaReduction` **recall 0.400** (1352 FN);
several CSMeD/SYNERGY topics hit recall 1.0 at precision ~0.25-0.41
(`Systems_TelemonitoringHF` 1.0/0.275; `Family_ParentInfantPsych` 1.0/0.25).

**Calibration is poor — confidence does not separate right from wrong
positives.** Overall `avg_conf_tp 0.904` vs `avg_conf_fp 0.880`: false positives
are asserted with almost the same high confidence as true positives (same pattern
every dataset: SYNERGY tp0.918/fp0.879; 3ie tp0.882/fp0.862). `avg_conf_fn 0.611`
/ `avg_conf_tn 0.540`. This empirically validates the additive-rubric weakness and
V3's "confidence stored-never-trusted" posture. A stray token-logprob calibration
probe exists (`results/logprob_*.csv`, 26-41 rows) but is tiny and unsummarised.

**Blueprint screening harness** (`blueprint_comparison/screening/evaluate_screening.py:386-418`)
computes accuracy/precision/recall/specificity/f1 with **`SCREENING_RUNS=5`** and
cross-run variance against manual `title_abstract_screen`/`full_text_screen`
labels — i.e. V2 already tooled multi-run screening consensus at eval time — but
**no results are committed** (no results dir).

### B. Evidence-classifier eval — the gpt-5.2 vs gpt-5-mini number

Harness `r_and_d/evidence_categorisation/validate_classifier.py:168-186` computes
accuracy, macro/weighted P/R/F1, a full 9×9 confusion matrix, confidence-by-
correctness, and accuracy-by-difficulty, against **human labels captured via
Argilla** (`validation_set.csv`, `ground_truth_category`).

**All numeric outputs are gitignored** (`outputs/`, `experiments/*.csv`). The only
surviving figures are narrative, in
`EVIDENCE_CATEGORISATION_PLAN.md` §"R&D Findings" (**L396-431**):
- **3 validation sets:** child_obesity, home_heating, intervention_home_learning.
- **gpt-5.2 ≈ 76% accuracy** across datasets; **gpt-5-mini ≈ 50%**; gpt-5 also
  tested. (Metric = top-1 accuracy vs human gold on the 9-category task.)
- Prompt variant_b only "strengthened the Unknown category definition" and ≈
  variant_a → implies **Unknown/Insufficient was the weak/confused category**
  (confusion-matrix numbers not committed to confirm the confused pairs).
- **Classifier confidence correlates *positively* with correctness here** — the
  opposite of the screening calibration failure. This is why V2 could justify the
  0.5 `evidence_confidence` threshold in strength scoring.

This is the direct, measured basis to challenge V3 decision 8's choice of
gpt-5-mini for classify: on V2's own human-labelled 9-category test, mini scored
~50% vs ~76% for the gpt-5.2-class model — a ~26-point accuracy gap on the exact
taxonomy V3 inherits.

### C. Heat_pump study — document-identity recall, NOT screening accuracy

The repo-root `heat_pump_*` files measure **whether the pipeline surfaced the same
documents as a 20-item hand-curated reading list** (`heat pumps literature.md`),
via URL/DOI/gov-slug exact + title-similarity fuzzy matching. Key corrections:
- **The "088"/"09"/"093" in filenames are title-similarity THRESHOLDS, not
  achieved sensitivity.** Every strict-threshold run matched **0/11**
  (`heat_pump_sensitivity_title_088_first_section.json:2-7`;
  `..._non_relevant_overlap_sensitivity_088...json:2-10`, 105 docs, 0/11;
  `heat_pump_manual_vs_policy_atlas.csv` all 20 rows `matched=False`). There is
  **no 0.88 achieved-sensitivity number** anywhere; strict-identity sensitivity ≈
  **0%**.
- Dropping to a loose scorer recovers candidates for **10/11** items (7/11 at
  "high confidence"), but with weak title similarity (e.g. score 1.03 at
  title_similarity 0.43) — the pipeline surfaces *conceptually related but
  different* documents than an expert would hand-pick.
- The per-project relevance export
  (`heat_pump_policy_atlas_docs_with_relevance.json`) carried **only
  `is_relevant` (bool) + `relevance_reason` (text), no confidence field** — 189
  relevant / 105 not across 294 rows. (A different, thinner export than the app's
  CSV path; confirms confidence is not universally exported.)

Net: this study is mostly a **search/coverage** signal (015/016 territory), not a
screen-accuracy signal, and its numbers should not be read as screening
sensitivity. The eval harness (§A) is the screening-accuracy source of truth.

---

## The confidence-display failure mode (user-reported)

**Confirmed, fully resolved, in both the app table and the CSV export.**

Frontend documents table `PapersTable.tsx:261-289`:
- Column **`title: 'Relevance'`** with **`dataIndex: 'confidence'`**
  (`:262-264`), default-sorted **descending** by that number (`:266-267`).
- Render (`:268-278`): `{record.confidence ? (record.confidence * 100).toFixed(1)
  : 'N/A'}` followed by a green `Check` if `is_relevant` else a red `X`. **One
  unconditional numeric rendering for every row** — relevant and non-relevant rows
  share the identical confidence display; the only differentiator is the tiny
  check/X icon. Tooltip shows `relevance_reason` (`:281-284`).

The number is `relevance_confidence`, mapped at
`page.tsx:896` (`confidence: doc.relevance_confidence`) — also on the public page
`app/public/projects/[projectId]/page.tsx:376`.

Why users misread it: the column is literally headed **"Relevance"** and shows a
0-100 score for *excluded* docs too. Because `is_relevant` (a boolean the model
emits) and `relevance_confidence` (a separately-emitted additive score) are
produced independently and can diverge, a red-X row can display a high number
(e.g. "70.0 ✗"), and a kept row a low one — the number reads as a per-doc
"relevance score" across the whole table regardless of the include/exclude
decision. The same conflation is in the CSV export: `projects.py:1848-1850` writes
`"Relevance": Yes/No` and a single `"Confidence": relevance_confidence` column
side by side.

This is precisely the failure V3 contract decision 3(iii) records as a front-end
seam. Note V3 makes it *worse if naively displayed*: V3's persisted
`screen_decision_confidence` is confidence-in-the-recorded-decision (1−p flip for
`not_relevant` rows), so an excluded row's stored number is
confidence-in-exclusion — high when the doc is confidently rejected — which in a
"Relevance" column would invert the meaning entirely. The seam must never render
decision confidence for not_relevant rows in the same column as relevant rows'
relevance confidence.

---

## What worked (validated by use)

1. **The 9-category taxonomy held up** and is carried into V3 verbatim
   (`category.py:47-130`; contract carries `EVIDENCE_TYPES` for parity). The
   single-source-of-truth table (name/key/score/rank/colour/explanation) is a
   clean pattern.
2. **Closed single-label classify with an honest `Unknown` sink** and an explicit
   Unknown-vs-Other discipline (`prompts.py:708-713`) — matches V3 decision 4 and
   the field literature (PMC12407223).
3. **Per-doc fan-out with isolated calls** (`batch_check.py:187-192`) — V2 already
   did what V3 decision 2 mandates; no batching-into-one-prompt coupling.
4. **Definitions-rich classify prompt** (per-category definition + examples +
   keywords, `prompts.py:581-689`) — a strong template for `classify_v1`.
5. **Classifier confidence was measurably calibrated** (positive
   confidence↔correctness in the R&D eval), which is what let V2's 0.5 strength
   threshold be meaningful — evidence that classify confidence is worth storing.
6. **Screening recall was decent overall (0.836)** at mini-class cost — supports a
   mini-class screen model *if* recall (not accuracy) is the target.
7. **Real eval harnesses exist** (screening confusion matrix + confidence-by-
   outcome; 9×9 classifier confusion; blueprint 5-run variance) — reusable
   scaffolding for V3's eval slice, including the LLM4SCREENLIT-style metrics the
   contract defers.

## What failed / was fragile

1. **Silent failure → silent exclusion (screen).** Failed calls default to
   `is_relevant=False` (`relevance.py:194-197`); a transient error drops a doc
   from the corpus with no trace. Directly motivates V3 decision 5.
2. **Silent failure → silent NaN category (classify).** Failed calls leave
   `evidence_category` blank, not `Unknown` (`category.py:348-364`) — invisible
   coverage loss.
3. **Screening confidence is poorly calibrated** — FP confidence 0.88 ≈ TP 0.90
   (§A). The additive `+0.2`-per-facet rubric (`prompts.py:122-124`) produces a
   coverage score, not a probability. Never trust it as a threshold.
4. **Recall collapses on hard corpora** — 3ie recall 0.727 overall, **0.400** on
   Anaemia (§A). Single-pass mini screening is not uniformly recall-safe; the
   corpus determines whether it over- or under-includes.
5. **gpt-5-mini measured ~50% on the 9-category classify task vs ~76% for
   gpt-5.2** (§B). V2 chose the stronger model for classify *on purpose*.
6. **Dead config.** `BATCH_SIZE_SCREENING=5` (`config.py:144`) is never used;
   `relevance.py:301` hardcodes `batch_size=25` (mirrors the 013 dead-caps
   lesson). The configured budget surface lies.
7. **Missing abstract has no structural fail-open.** `"No abstract available"` is
   just weaker prose into the same prompt (`relevance.py:123`); no
   `title_only`/`title_abstract` basis, so title-only docs silently degrade
   toward exclusion. V3 decision 3 makes this structural.
8. **Intent is interpolated as prompt text** (`prompts.py:88-102`) — no injection
   posture; closed by V3 decision 7.
9. **Geography is a hard exclusion instruction** (`prompts.py:117`) — a recall
   risk contradicting the "be inclusive" line two paragraphs up.
10. **Display conflation** (`PapersTable.tsx:261-278`) — see failure-mode section.

---

## V3 adjudication table (recommendation → covered-by / new / seam)

| # | V2 lesson / recommendation | Verdict |
|---|---|---|
| 1 | Screen failure must not silently exclude (`relevance.py:194-197`) | **Covered** — decision 5 (`status='failed'`, partial unique index, retry as new row). |
| 2 | Classify failure must not silently blank the category | **Covered** — decision 5 (no row on failure; NOT-EXISTS retries). Do **not** reinstate the Unknown fallback. |
| 3 | Screening confidence is poorly calibrated (FP≈TP conf) | **Covered** — decision 3 (confidence stored as-is, calibration to eval seam) + consensus probability. Adds empirical weight: V3 should not gate on raw screen confidence. |
| 4 | Single-pass screen has real decision variance / recall collapse on hard corpora | **Covered** — decisions 3/10 (`SCREEN_REPS=3` consensus, agreement stats, borderline review). V2's blueprint harness `SCREENING_RUNS=5` is precedent. |
| 5 | Missing abstract needs structural fail-open, not weaker prose | **Covered** — decision 3 (`screen_basis` computed in code; fail-open structural). |
| 6 | Intent must be id-keyed data, not interpolated prompt text | **Covered** — decisions 3 & 7 (intent-as-data; injection posture). |
| 7 | 9-category closed taxonomy + honest Unknown + Unknown≠Other discipline | **Covered** — decision 4 + `EVIDENCE_TYPES` parity. Carry the `prompts.py:708-713` Unknown-vs-Other wording into `classify_v1`. |
| 8 | Per-doc fan-out, isolated calls | **Covered** — decision 2 (V2 already did this). |
| 9 | **gpt-5-mini ≈ 50% vs gpt-5.2 ≈ 76% on the exact 9-category classify task (human-labelled, 3 sets)** | **NEW / CONTRADICTS decision 8.** V3 runs classify on `gpt-5-mini`; V2's own eval says that ~halves classify accuracy vs the model V2 deliberately reserved for classification (`config.py:136-138`). The contract's "not all-Unknown" acceptance check is necessary but insufficient — a coherent-looking wrong label passes it. **Adjudicate:** either (a) accept mini + rely on the live-check by-type distribution and defer accuracy to the eval slice, or (b) split the model route so classify runs a stronger model. At minimum record the measured gap and add a classify-accuracy line to the eval-slice dataset. Note mitigations partly close it (structured provider priors, decision 4, which V2 lacked; classify-consensus is a recorded eval-gated seam). |
| 10 | Classify confidence *is* calibrated and had a hard 0.5 threshold in strength scoring (`strength.py:456-461`) | **Seam.** V3 stores confidence as-is and does no strength scoring off it yet; when appraise/strength consumes classify confidence, the 0.5-threshold precedent and its calibration dependence should be revisited (eval seam). |
| 11 | Provider metadata should feed classify as *structured* fields (V2 fed only thin `Source/Type/Year` text, `category.py:342-346`) | **Covered / strengthened** — decision 4 (structured priors: `record_type`, Overton `source.type`/`organisation_type`, topic labels). V3 improves on V2 here. |
| 12 | Confidence-display conflation: one "Relevance" number column across kept + excluded rows (`PapersTable.tsx:261-278`, `projects.py:1848-1850`) | **Covered as seam** — decision 3(iii). Reinforce: V3's 1−p decision-confidence for not_relevant rows would *invert* meaning if shown in a "Relevance" column; the front-end seam must separate relevance-confidence (relevant rows) from decision-confidence and never co-render them. |
| 13 | Dead config (`BATCH_SIZE_SCREENING` unused; hardcoded 25) | **Seam / discipline** — task-cycle "configured == binding" check (013 precedent). Ensure V3's concurrency bound is the real one and tested. |
| 14 | Open methodological/structural tags | **NEW (already in contract)** — decision 6 adds what V2 never had; no V2 precedent to carry, but no V2 contradiction either. |
| 15 | Heat_pump "sensitivity_088" numbers | **Not a screen signal.** Document-identity recall study (≈0% strict), search/coverage territory (015/016). Do not treat as screening sensitivity; the eval harness (`evals/screening/`) is the real screen-accuracy source and should seed the eval slice. |
