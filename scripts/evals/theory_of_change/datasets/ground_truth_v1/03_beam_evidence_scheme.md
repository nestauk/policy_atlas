# Evidence scheme: adopting a simplified BEAM in Policy Atlas

**Source method:** Christie, A. P. et al. (2023). *Assessing diverse evidence to improve conservation decision-making.* Conservation Science and Practice, 5(10), e13024. https://doi.org/10.1111/csp2.13024 (CC BY).

**Status:** proposal. This file replaces the evidence-rating rules in `01_ground_truth_pack.md` §4.2. Thresholds marked *(calibrate)* are starting points, not validated values.

---

## 1. What BEAM is

The Balance Evidence Assessment Method (BEAM) weighs diverse evidence for or against a single, specific **assumption**, such as a link in a theory of change. It pictures this as a seesaw: each piece of evidence is a block placed on the balance.

- **Position on the balance** is the block's *strength of support*. There are four ordinal categories:
  - **Refutes**: the evidence refutes the assumption. BEAM has only one refutes category, because refuting evidence is rare and hard to grade.
  - **Mixed support**: the evidence neither supports nor refutes it, or both supports and refutes it to roughly the same extent.
  - **Weakly supports**.
  - **Strongly supports**.
- **Size of the block** is its *weight*, the product of three criteria, each scored 0–3 (none, low, moderate, high):
  - **Information reliability (I):** how validly the information was produced or collected.
  - **Source reliability (S):** how credible and trustworthy the source is.
  - **Relevance (R):** how well the evidence applies to this assumption and context. The guiding test is how many additional assumptions you would need to relate the finding to the assumption of interest; the more you need, the lower the relevance.
- **Weight** = I × S × R ÷ 27. A "perfect" block (3|3|3) weighs 1. If any criterion scores 0, the block weighs nothing and disappears.
- **Aggregation.** Support categories get numeric values: refutes −2, mixed 0, weakly supports +1, strongly supports +2. BEAM then computes a weighted average strength of support with a bootstrapped 95% confidence interval, and displays it as a **Ziggurat plot**: blocks stacked by weight within each category.
- **Verdict.** Three confidence levels: *Confident*, *Not sure (further investigation required)* or *Not confident*. Each comes with decision implications, judged from three things: the average support, the variability in support, and the total weight of evidence.
- **Optional required level of proof.** For implausible or high-risk assumptions, refuting evidence is given more influence, for example −4 instead of −2.
- **Sets of assumptions.** Use the **critical weakest link** rule (Salafsky et al., 2022): overall confidence equals the lowest confidence among the assumptions rated critical.
- **Reliability.** In a pilot with 15–20 raters per assumption, the authors found strong agreement (Finn coefficient above 0.7) for 10 of 12 ratings and satisfactory agreement (0.5–0.7) for the other two.
- **Principles.** No a priori hierarchy of evidence types: local, practitioner and Indigenous knowledge can all score highly. Assessors should be as representative of the evidence sources as possible. Scoring should be documented and transparent.

## 2. Why it fits Policy Atlas

| Problem from user research or the Magenta Book | How BEAM addresses it |
|---|---|
| Users couldn't tell "weak" (no evidence) from "weak" (evidence against) | Direction (where a block sits) is separate from weight (block size). No evidence means an empty balance. Evidence against means blocks on the refutes side. |
| "How are low, medium and high ratings derived?" | The verdict is computed from visible evidence pieces, each with its own scores and rationale |
| Evidence skews UK-based or generic | Relevance is scored explicitly using the "additional assumptions needed" test |
| The Magenta Book asks for the strength of evidence behind each assumption, and for AI use to be transparent and verifiable | Every link has an auditable evidence list, and the scores can be edited by a human |
| ToC-level confidence and prioritisation | Critical weakest link highlights the weakest critical links in the summary |
| Earlier anti-pattern: EPPS's single scale mixing direction and strength | Replaced by two independent dimensions |

## 3. The simplified version (PA-BEAM)

There are three simplifications compared with the full BEAM:

1. **Two weight factors, not three.** Information reliability and source reliability are merged into **Quality (Q)**. Relevance (R) stays separate. This is because LLM judgements of source credibility are weak and drift towards prestige bias, while relevance matters most for context-specific policy questions.
2. **No bootstrapped confidence interval.** A simple conflict indicator (the share of weight on refutes) is used instead.
3. **No required level of proof in version 1.** It comes later as a "high-stakes decision" toggle that doubles the refutes value to −4.

### 3.1 Scoring each evidence piece

| Field | Values | Anchors |
|---|---|---|
| `support` | `refutes` (−2) · `mixed` (0) · `weak` (+1) · `strong` (+2) | As in BEAM Table 1 |
| `quality` (Q) | 0–3 | **3:** well-designed evaluation, systematic review, or official statistics with clear methods. **2:** sound study or credible report with some limitations. **1:** weak design, unclear methods, or a source with a possible conflict of interest. **0:** unverifiable or misleading. |
| `relevance` (R) | 0–3 | **3:** same intervention type, population and UK-comparable context, so no extra assumptions are needed. **2:** a few small extra assumptions (e.g. different UK region, similar intervention). **1:** several small or a few large leaps (e.g. different country *and* sector). **0:** not applicable. |
| `rationale_q`, `rationale_r`, `rationale_support` | One line each | Must cite the specific feature of the source that drove the score |
| `finding` | Short paraphrase plus location in the source | The claim the score is based on |

**Weight** = Q × R ÷ 9. This runs from 0 to 1, and a weight of 1 is one "perfect" block.

**Equity rule.** The quality anchors must not equate "not peer-reviewed" with low quality. Lived experience, practitioner reports and local monitoring data can score 2–3 if the information was gathered robustly. The same scheme applies to evidence uploaded by users.

### 3.2 Aggregating to a link verdict

```text
W   = Σ weight(e)                                  total weight of evidence
S̄   = Σ weight(e) · support(e) / W                 weighted average support, −2 … +2
R%  = Σ weight(e | refutes) / W                    conflict indicator
```

| Verdict | Rule *(calibrate)* | Canvas line | Meaning for the user |
|---|---|---|---|
| **Confident** | S̄ ≥ 1.0 and W ≥ 1.0 and R% < 15% | Solid | Proceed; monitor |
| **Not sure: mixed or conflicting** | W ≥ 1.0, and neither the Confident nor the Not confident rule is met | Two-tone | Look for moderators or context-dependence; consider Test and Learn |
| **Not sure: too little evidence** | W < 1.0 (including no evidence at all) | Dashed | Evidence gap; consider new research or a pilot |
| **Not confident: evidence against** | S̄ ≤ −0.5 and W ≥ 1.0 | Dotted, warning colour | Reconsider or modify this step |

The two "Not sure" labels split BEAM's single "Not sure" level by its cause, which is what users need in order to know what to do next.

### 3.3 Aggregating to the ToC

- Users (or Policy Atlas, as a default for them to review) mark links and assumptions as **critical**. A sensible default is every link that crosses the accountability ceiling, plus every link on the main chain.
- **ToC confidence** is the lowest verdict among the critical links. Ordered from lowest to highest: Not confident < Not sure: too little evidence < Not sure: mixed < Confident.
- The summary section names the 2–3 weakest critical links and explains why.

## 4. Worked example

**Assumption** (EPPS A13, sharpened): *"In UK central government, applying the five environmental principles when making policy leads to policy changes that reduce environmental harm."*

| # | Evidence (illustrative) | Support | Q | R | Weight |
|---|---|---|---|---|---|
| 1 | Process evaluation of the EPPS duty: interviewees report no policy changed yet | mixed (0) | 2 | 3 | 0.67 |
| 2 | Review of environmental-integration duties in other countries: modest effects on policy content | weak (+1) | 2 | 1 | 0.22 |
| 3 | UK impact assessment where the principles were used to justify the preferred option after the fact | refutes (−2) | 2 | 2 | 0.44 |

The rows are illustrative, loosely based on the OEP evaluation; they are not a real scoring.

W = 1.33, S̄ = (0 + 0.22 − 0.89) ÷ 1.33 ≈ −0.50, R% ≈ 33%.

Verdict: **Not confident: evidence against**, because S̄ ≤ −0.5 and W ≥ 1.0. The score is right on the boundary, so with slightly different scores this would be *Not sure: mixed*. Close-to-threshold cases like this should be flagged in the UI as sensitive.

## 5. What adoption entails

1. **Sharpening assumptions.** BEAM only works on specific, directional assumptions that name the action, the outcome and the context. Add a step that rewrites vague node or link labels into testable statements before any scoring. For example, "protecting nests is beneficial" becomes "fencing nests on Island X from mammalian predators increases breeding success".
2. **Data model.** Add evidence-piece objects to each link and assumption (see §6). Verdicts are always *computed*, never written directly by the model.
3. **Scoring prompts.** Score all evidence pieces for one assumption in a single call; this is cheaper and keeps scores more consistent with each other. Show the anchors from §3.1 verbatim and require the rationales.
4. **Deduplication.** A systematic review replaces the primary studies it includes, and multiple reports of the same study count once. Without this, a well-studied topic would be over-weighted.
5. **UI.**
   - Each link tooltip shows a mini ziggurat (blocks stacked by weight in each support category), the verdict and the evidence list with Q/R chips and rationales.
   - Scores are editable, and the verdict recomputes live.
   - Links near a verdict threshold get a "sensitive" flag.
6. **Validation before launch.**
   - Have 2–3 people score about 40 evidence–assumption pairs, and compare with the LLM. Use weighted kappa or the Finn coefficient, and aim for at least 0.7 (the paper's threshold for strong agreement).
   - Repeat the LLM scoring 3 times per pair to check reproducibility, which the Magenta Book 2026 flags as a risk of AI.
   - Run the ground-truth cases (`02_evaluation_protocol.md`) and check that verdicts reproduce the expected fall in confidence towards impact.
7. **Cost.** Roughly one call per assumption once pieces are batched, so about 25 calls for a typical ToC, plus one sharpening call per assumption.
8. **Later additions:**
   - The required-level-of-proof toggle.
   - Splitting Quality back into information reliability and source reliability, if testing shows value.
   - Confidence intervals once links routinely have five or more pieces of evidence.
   - Applying the same scheme to user-uploaded stakeholder evidence.

## 6. Schema additions

These extend `01_ground_truth_pack.md` §8. Each `edge` and each `assumption` gains:

```json
"assumption_statement": "Specific, directional, context-bound statement",
"critical": true,
"evidence_pieces": [
  {
    "id": "EV1",
    "source_id": "S3",
    "finding": "Short paraphrase + page/section",
    "support": "refutes|mixed|weak|strong",
    "quality": 0,
    "relevance": 0,
    "rationale_support": "string",
    "rationale_quality": "string",
    "rationale_relevance": "string",
    "context_fit": "uk|comparable_international|generic",
    "scored_by": "model|user",
    "duplicate_of": null
  }
],
"evidence_summary": {
  "total_weight": 0.0,
  "mean_support": 0.0,
  "refute_share": 0.0,
  "verdict": "confident|not_sure_mixed|not_sure_insufficient|not_confident",
  "near_threshold": false
}
```

The ToC object gains:

```json
"toc_confidence": {
  "verdict": "lowest verdict among critical links",
  "weakest_links": ["L7", "A13"]
}
```

## 7. Mapping to the earlier scheme and to the ground-truth sources

| Earlier pack (§4.2) | PA-BEAM |
|---|---|
| direction = supports / mixed / contradicts / none_found | Support category per piece; "none_found" = no pieces, so W = 0 |
| strength = high / medium / low | Replaced by weight (Q × R) and the computed verdict |
| EPPS Strong / Good | Most likely Confident |
| EPPS Some | Most likely Not sure: mixed |
| EPPS Limited (evidence against) | Not confident |
| EPPS No evidence | Not sure: too little evidence |
| Changing Futures solid / dashed / dotted | Confident / Not sure (either) / Not confident |

Treat these correspondences as approximate. EPPS and Changing Futures judgements are ex-post evaluations of the intervention itself, while Policy Atlas scores prior literature.

## 8. Risks and limits

- **The model scores its own retrieved evidence.** Mitigations: visible rationales, editable scores, validation against human raters, and reproducibility checks.
- **Quality anchors can encode bias against non-academic knowledge.** Mitigations: the equity rule in §3.1, and testing scores across source types.
- **Thresholds are uncalibrated.** Tune them on the validation set and the ground-truth cases before release.
- **Narrow searches inflate "too little evidence".** Always show the search scope next to that verdict.
