# Theory of change ground truth pack

Reference material for work on the Theory of change Capability. It is built from four published
UK theories of change, read against the HM Treasury Magenta Book (the UK government guide to
evaluation) and Nesta's theory of change guidance. `../../gt_eval.py` reads the datasets in
`datasets/`.

## Files

| File | What it is | Use it when you change… |
|---|---|---|
| `01_ground_truth_pack.md` | Summary; how the text is structured; the typical shape; how to judge evidence; how to show assumptions and evidence; the pattern library (P1 to P13); anti-patterns; the output schema | The theory of change prompts, the output schema, the canvas or the text template |
| `02_evaluation_protocol.md` | How to run Policy Atlas on the cases and score the overlap (nodes, links, shape, assumptions, weak links, checklist) | The evaluation harness |
| `03_beam_evidence_scheme.md` | A simplified Balance Evidence Assessment Method (BEAM) for scoring the evidence on links: scoring anchors, aggregation rules, verdicts, a worked example, schema additions and a validation plan. It replaces §4.2 of the pack. The source method is cited in the file | Evidence scoring and the canvas evidence display |
| `datasets/gt_epps.md` | The Office for Environmental Protection (OEP) theory of change for the Environmental Principles Policy Statement (EPPS): 26 nodes, 27 links, 13 assumptions and risks | Ground truth |
| `datasets/gt_cf_individual.md`, `gt_cf_service.md`, `gt_cf_system.md` | The Changing Futures theory of change at three levels, with the evidence status of each link | Ground truth |
| `datasets/gt_wales.md` | The Climate Action Wales public engagement theory of change: COM-B (capability, opportunity, motivation, behaviour) outcomes and risks | Ground truth (links at container level) |
| `datasets/gt_child_poverty.md` | The Child Poverty Strategy theory of change, with its indicator table | Ground truth (links at container level) |
| `tools/gt_data.py`, `tools/gen.py` | The source data and the generator. Edit `gt_data.py`, then run `python3 tools/gen.py` from this folder to remake the datasets and their shape metrics. `gen.py` needs the `networkx` package, which is not in the backend's dependencies | Adding cases or fixing transcriptions |

Each dataset has: Task briefs (outcome first and intervention first), a shape summary,
containers, nodes, links (with evidence status, assumptions and transcription confidence),
assumptions and risks, context factors, known gaps, and a JSON block for machine use.

## Sources and licences

The four theories are transcribed from published documents. `tools/gt_data.py` cites each by
its address: the Changing Futures theory of change (GOV.UK), the Child Poverty Strategy
monitoring and evaluation framework (GOV.UK), the Climate Action Wales public engagement
strategy theory of change (gov.wales), and the OEP's evaluation of the Environmental Principles
Policy Statement (theoep.org.uk). GOV.UK and gov.wales publications are under the Open
Government Licence v3.0 unless the page says otherwise. The OEP page states no licence: its
figure is transcribed as a short factual record of nodes and links, with a citation, and is
not reproduced. The repository stores no PDF of a source.

## Open items

- Wales: transcribe the behaviour outcomes B1 to B3 from the full report.
- Child Poverty: transcribe the revised theory of change (Figure 2 of the baseline report). The
  dataset uses the earlier version; its known gaps say so.
- EPPS: the links I2 and I3 to A5, and the link from A5 to the activities, have medium
  confidence (A5 has no explicit outgoing arrow in the figure).
