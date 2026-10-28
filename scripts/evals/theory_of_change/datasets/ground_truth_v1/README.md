# Theory of Change ground truth pack — Policy Atlas

Reference material for iterating on Policy Atlas's Theory of Change capability, built from four published UK theories of change and read against the HM Treasury Magenta Book (May 2026 update) and Nesta's ToC guidance.

## Files

| File | What it is | Give to Claude Code when… |
|---|---|---|
| `01_ground_truth_pack.md` | Summary; Q1 text structure; Q2 typical shape; Q3 judging evidence; Q4 presenting assumptions and evidence; pattern library (P1–P13); anti-patterns; output schema | Changing ToC generation prompts, the output schema, the canvas rendering or the text template |
| `02_evaluation_protocol.md` | How to run Policy Atlas on the cases and score overlap (nodes, links, shape, assumptions, weak links, checklist) | Building the evaluation harness |
| `03_beam_evidence_scheme.md` | Simplified Balance Evidence Assessment Method (Christie et al. 2023) for scoring evidence on links: scoring anchors, aggregation rules, verdicts, worked example, schema additions, validation plan. Supersedes §4.2 of the pack | Implementing evidence scoring and the canvas evidence display |
| `datasets/gt_epps.md` | OEP Environmental Principles ToC: 26 nodes, 27 links, 13 rated assumptions | Ground truth |
| `datasets/gt_cf_individual.md`, `gt_cf_service.md`, `gt_cf_system.md` | Changing Futures three-level ToC with evidence status for each link | Ground truth |
| `datasets/gt_wales.md` | Climate Action Wales engagement ToC: COM-B outcomes, risks | Ground truth (container-level links) |
| `datasets/gt_child_poverty.md` | Child Poverty Strategy ToC (Dec 2025) plus indicator table | Ground truth (container-level links) |
| `tools/gt_data.py`, `tools/gen.py` | Source data and generator; edit `gt_data.py` and rerun `python3 tools/gen.py` to regenerate the datasets and shape metrics | Adding cases or fixing transcriptions |

Each dataset contains: task briefs (outcome-first and intervention-first), a shape summary, containers, nodes, links (with evidence status, assumptions and transcription confidence), assumptions and risks, context factors, known gaps, and a JSON block for machine use.

## Open items
- Wales: transcribe behaviour outcomes B1–B3 from the full report.
- Child Poverty: transcribe the July 2026 revised ToC (Figure 2 of the baseline report).
- EPPS: links I2/I3 → A5 and the A5 → activities link are medium-confidence (A5 has no explicit outgoing arrow in the figure).
