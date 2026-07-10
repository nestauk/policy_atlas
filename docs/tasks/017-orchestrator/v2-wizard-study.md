# V2 search-wizard study (rev 2.2c evidence)

Read-only study of the V2 repo (`../discovery_policy_atlas`) commissioned at the 017
contract gate (2026-07-10, user direction) to inform the planner's question set,
defaults and suggested-answers behaviour. V2 context: rigid fixed-step wizard, biased
toward intervention-style questions, built for V2's fixed downstream analysis — shapes
are evidence, not design authority. File references are V2 paths.

## 1. The question set (fixed steps, in order)

Step machine in `frontend/components/search/SearchWizard.tsx` (~1900 lines):
USE_CASE → ASK → POPULATION → INNER_SETTING → OUTCOME → SCREENING → PARAMETERS →
(ADDITIONAL_QUESTIONS — dead, skipped by navigation) → SUMMARY.
**Required: only USE_CASE + ASK + ≥1 source.** Everything else defaulted.

- **USE_CASE** ("How can Policy Atlas help?"): 6 options (horizon_scan · rapid_brief ·
  policy_note · policy_blueprint · rapid_evidence_review · not_sure). **Analytics
  only** — schema comment: "does not affect search behavior in alpha".
- **ASK**: textarea, heading "What policy interventions are you exploring?" — the
  intervention bias hard-coded in copy. On Continue, fires the suggestion calls.
- **POPULATION / INNER_SETTING / OUTCOME**: each = "No preference" (default-selected)
  + LLM-suggested chips + free-text add. Fallback lists hard-coded so never empty.
- **SCREENING** ("Additional criteria", all optional): user context (role/audience,
  free text — fed only synthesis framing); implementation constraints (cost /
  staffing / complexity, each Any|Low|Moderate|High, default Any — fed only a
  transferability scoring veto, ×0.5 per exceeded dimension); free-text screening
  factors (e.g. "Only studies with children below 5").
- **PARAMETERS**: sources (academic/grey chips, both on); max results per source
  (5–200, default 30, with a processing-time tooltip); time window (presets, default
  LAST_10_YEARS); geography (multi-add, default "Anywhere"; special regions + ~190
  countries).
- **SUMMARY**: editable review cards deep-linking back to each step + estimated-time
  panel; Run gated on validity.

## 2. Suggested-answers machinery

- Trigger: once, on leaving ASK. Three parallel calls (population / outcome /
  inner-setting), each `.catch → []`, in-flight guard. **Never re-run when the
  question is later edited** (one-shot anti-pattern).
- Backend: `services/search_wizard.py`; `gpt-4.1-mini`, temperature 0.3,
  max_tokens 300; human message is just `Research question: {q}`; response = JSON
  array of strings; parse failure degrades to frontend fallbacks.
- Counts/ordering: population 3 (broad→narrow) · outcome 3 (broad→narrow) ·
  setting 3–5 (most-common→least). Prompts all framed "…about interventions…" —
  the bias baked in at prompt level.
- An additional-questions generator exists but is orphaned (endpoint never called).

## 3. What fed downstream (and what didn't)

Well-used: research_question (queries, relevance, synthesis) · population + outcome
(query construction, relevance prompt, scoring) · geography (relevance hard-exclude
unless transferability claimed; query name-variant OR-expansion; scoring) · sources ·
time window · max_results.
Weak/dead: use_case (analytics only) · additional_questions (deprecated, skipped) ·
inner_setting (transferability scoring only — not retrieval, not screening) ·
screening_factors (relevance prompt + semantic query, but explicitly commented out of
boolean query construction — inconsistent by invisible mode).

## 4. Screening criteria

No structured inclusion/exclusion object. One LLM relevance pass; criteria derived
implicitly from question + population + outcome + geography into one system prompt
with a +0.2-per-dimension confidence rubric, "inclusive rather than overly
restrictive" except geography (hard exclude). User's only lever: the free-text
screening factors. Users could not see or edit the effective criteria.

## 5. Adjudicated into the 017 contract (rev 2.2c)

**Adopted** — suggested answers on planner questions (2–5, broad→narrow, buttons +
free text, degrade-don't-block, re-derived as framing evolves); no-preference-style
visible defaults with a two-field-equivalent required core; pre-launch editable
review (the plan draft/proposal); cost transparency (time band).
**Named anti-patterns** — intervention-framed copy/prompts (planner prompt is
question-type-neutral; intent-fit decides when population/setting/outcome suggestions
are even relevant); dead collected fields (V3 rule: every plan field compiles or is
explicitly non-executing; ask nothing that nothing consumes — user-context/audience
deliberately not collected in v1); one-shot suggestions; opaque derived criteria
(confirms visible-defaults posture; the structured inclusion/exclusion criteria
directive remains the recorded 014 seam).
**Noted, not folded** — constraint-veto scoring (clean soft-preference → ranking
penalty pattern; V3 analogue belongs to the boost/policy surfaces, eval-gated);
geography name-variant query expansion (search-surface territory, not the planner's).
