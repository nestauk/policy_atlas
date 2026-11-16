# Evaluation protocol: Policy Atlas ToC vs ground truth

**Goal.** Measure how closely Policy Atlas reproduces the content, shape and weak-link judgements of published UK theories of change, using the six ground-truth maps in `datasets/`.

**Principle.** A published ToC is *one valid* theory, not the only one. Treat **recall** (did Policy Atlas find what experts found?) and **weak-link agreement** as the primary metrics. Treat precision as diagnostic only: an extra Policy Atlas node may be a legitimate addition, and that is judged qualitatively.

---

## 1. Cases and inputs

| Case | Dataset | Use for | Edge-level scoring? |
|---|---|---|---|
| `epps` | `gt_epps.md` | Content, shape, assumptions, weak links | Yes (most edges high-confidence) |
| `cf_individual` | `gt_cf_individual.md` | Content, shape, weak links | Yes |
| `cf_service` | `gt_cf_service.md` | Content, shape, weak links | Yes |
| `cf_system` | `gt_cf_system.md` | Content, shape, weak links | Yes |
| `wales` | `gt_wales.md` | Content, shape, assumptions/risks | Container-level only (source has column-level arrows) |
| `child_poverty` | `gt_child_poverty.md` | Content (drivers, outcomes), shape | Container-level only |

**Runs.**
- Each dataset has an *outcome-first* and an *intervention-first* brief. Run both, and use the brief text verbatim.
- Repeat each run 3 times to estimate variance. That gives 6 maps × 2 entry points × 3 repeats = 36 runs (the Changing Futures maps can share one run if Policy Atlas produces multi-level output; otherwise prompt each level separately by adding "Focus on the [individual / service / system] level.").
- Record the Policy Atlas version, model, search settings and date for every run.
- Save Policy Atlas output in the schema in `01_ground_truth_pack.md` §8, or convert to it.

## 2. Normalisation

1. **Map layers** to the canonical set: `input`, `activity`, `output`, `driver`, `outcome_short`, `outcome_long`, `impact`, `vision`, `context`.
   - Treat `input` and `activity` as one layer ("input/activity") when scoring, because the Magenta Book merges them.
   - Treat `driver` as equivalent to `output` / `outcome_short` for `child_poverty`.
2. **Expand containers.** An edge to or from a container counts as an edge to or from *any* member, for matching purposes.
3. **Two-way edges** match a Policy Atlas edge in either direction.

## 3. Node matching

Use an LLM judge (or embeddings plus a judge for borderline cases). For each ground-truth node, find the best Policy Atlas node and label the match:

- `exact`: same meaning.
- `broader`: the Policy Atlas node contains the ground-truth idea plus more, or the Policy Atlas node is a container that includes it.
- `narrower`: the Policy Atlas node covers part of the ground-truth idea.
- `none`.

One-to-many and many-to-one matches are allowed, because granularity differs.

**Judge prompt (use verbatim):**

```text
You compare two theories of change. For the GROUND TRUTH item below, decide whether any POLICY ATLAS item expresses the same causal idea (ignore wording, focus on meaning and actor).
Return JSON: {"gt_id": "...", "match_id": "...|null", "match_type": "exact|broader|narrower|none", "layer_agrees": true|false, "reason": "<20 words"}
Rules: "broader" if the PA item includes the GT idea plus more; "narrower" if it covers only part. Layer agrees if both are in the same canonical layer (input+activity count as one).
GROUND TRUTH: {gt_id} [{gt_layer}] {gt_label}
POLICY ATLAS ITEMS: {list of id [layer] label}
```

Score `exact` = 1.0, `broader` = 0.7, `narrower` = 0.5, `none` = 0.

## 4. Metrics

**Content**
- **Node recall:** mean match score over ground-truth nodes. Report it overall and by layer (input/activity, output, short-term outcome, long-term outcome, impact).
- **Layer agreement:** share of matched nodes where `layer_agrees` is true.
- **Novel node rate:** share of Policy Atlas nodes with no ground-truth match. Report it, then review a sample by hand and label each as *plausible addition* or *spurious*.

**Links** (for datasets marked Yes in §1)
- **Edge recall (strict):** share of ground-truth edges whose two endpoints are both matched and connected directly by a Policy Atlas edge.
- **Edge recall (soft):** as strict, but a Policy Atlas path of length ≤ 2 between the matched endpoints also counts, scored at 0.5.
- **Confidence weighting:** weight each ground-truth edge by transcription confidence (high = 1, medium = 0.7, low = 0.3). Report both weighted and unweighted results.

**Shape**
Compare against the "Shape summary" table in each dataset:
- Box count ratio (PA ÷ GT), overall and per layer.
- Container count.
- Longest chain (containers contracted): absolute difference.
- Share of container-level links.
- Number of impacts.
- Presence of each of: vision node, context factors, accountability ceiling.

Report a **shape score**: the mean, across five checks, of 1 if the Policy Atlas value lies within the ground-truth value ± 50% and 0 otherwise. The five checks are total boxes, boxes per layer (mean), containers, longest chain and number of impacts.

**Assumptions** (`epps`, `wales`)
- **Assumption recall:** semantic match of ground-truth assumptions and risks to Policy Atlas assumptions (same judge, applied to assumption text).
- **Location agreement:** for matched assumptions, whether the Policy Atlas location (from → to) sits in the same layer transition. For example, EPPS A13 is Outcomes → Impacts.

**Weak-link agreement** (the most important judgement metric)
- First define the ground-truth weak set for each case:
  - `epps`: A9, A10, A11 (Some) and A13 (Limited).
  - `cf_*`: all `insufficient` and `not_leading` edges, with `not_leading` as a critical subset.
  - `wales`: risks W-R2, W-R3, W-R5 (the Opportunity gap and the attribution and macroeconomic risks).
- Then take the Policy Atlas weak set: links or assumptions it rates `none_found`, `contradicts`, or `low` strength.
- **Report:**
  - recall of the ground-truth weak set;
  - whether Policy Atlas reproduces the **confidence gradient** (Spearman correlation between layer depth and Policy Atlas strength, where a negative value means confidence falls towards impact, as in the sources);
  - for `cf_*`, whether every `not_leading` edge is flagged as `contradicts` or `none_found`.
- **Interpretation:** ground-truth ratings for EPPS and Changing Futures are ex-post (evaluations of the intervention itself), while Policy Atlas is ex-ante. Disagreement is expected where an intervention's own results diverge from the prior literature. Review those cases by hand rather than counting them as failures.

**Quality checklist** (binary, per run)
Score 1 for each item present:
- every assumption is attached to a link;
- outputs and outcomes are distinguished correctly;
- risks or reasons the chain might fail are covered (Section 3 of the text);
- context factors are present;
- impacts are framed as contribution;
- sources are auditable;
- "weak" ratings say whether evidence is absent or against;
- the text references node IDs;
- a text version of the diagram is present;
- AI use is disclosed.

## 5. Reporting template

| Case | Entry | Run | Node recall | Layer agr. | Edge recall (strict / soft) | Shape score | Assump. recall | Weak-link recall | Gradient ρ | Checklist /10 | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| epps | outcome | 1 | | | | | | | | | |

Summarise each metric as mean ± SD across repeats, and compare outcome-first with intervention-first. Expect intervention-first to score higher on input/activity recall, and outcome-first to be the stronger test of reasoning.

## 6. Reference scoring pseudocode

```python
def edge_recall(gt, pa, matches, soft=False):
    # matches: gt_node_id -> set(pa_node_ids); containers expanded to members first
    hit = 0.0; total = 0.0
    for e in gt.edges:
        w = {"high": 1, "medium": .7, "low": .3}[e.confidence]; total += w
        S = expand(e.source, gt, matches); T = expand(e.target, gt, matches)
        if any(pa.has_edge(s, t) or (e.bidirectional and pa.has_edge(t, s)) for s in S for t in T):
            hit += w
        elif soft and any(pa.path_len(s, t) == 2 for s in S for t in T):
            hit += 0.5 * w
    return hit / total
```

## 7. Known limitations of the ground truth

- **Transcription.** Edges were transcribed from published diagrams; each carries a confidence rating.
- **Wales:** the behaviour outcomes B1–B3 are a placeholder. Transcribe them from the full report before scoring Wales long-term outcomes.
- **Child Poverty:** the dataset uses the Dec 2025 diagram. The July 2026 revision (three pillars, seven priority areas, delivery partners) is not yet transcribed.
- **Changing Futures:** link statuses reflect the evaluation's findings, not prior literature.
- **Small sample.** These are four ToCs. Treat the results as directional and add cases over time; the generator script makes that cheap.
