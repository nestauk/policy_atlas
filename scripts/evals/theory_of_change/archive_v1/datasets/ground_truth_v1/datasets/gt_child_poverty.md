# Ground truth: UK Child Poverty Strategy: theory of change (Dec 2025 version)

- **Case ID:** `child_poverty`
- **Level:** cross-government strategy (nested: strategy / driver / policy levels)
- **Source:** Cabinet Office, Child Poverty Strategy: Monitoring and Evaluation Framework (5 Dec 2025); indicators from DWP Baseline Report (9 Jul 2026), Table 1
- **URL:** https://www.gov.uk/government/publications/child-poverty-strategy-monitoring-and-evaluation-framework/child-poverty-strategy-monitoring-and-evaluation-framework
- **Evidence basis in source:** Ex-ante: Evidence Pack plus engagement with children, families and organisations.
- **Evidence/rating scheme in source:** None on links. Evidence base held in separate Evidence Pack.

## Task briefs for Policy Atlas

Use these as the *only* input to Policy Atlas. Do not give it any other text from the source.

**Outcome-first brief**

> The UK Government wants to reduce child poverty (relative low income after housing costs, and deep material poverty) and reduce its impact on children over ten years. Build a strategy-level theory of change covering the drivers of child poverty and the outcomes needed.

**Intervention-first brief**

> UK Child Poverty Strategy 'Our Children, Our Future' (Dec 2025): removal of the Universal Credit two-child limit, expansion of free school meals to all UC households, childcare expansion, employment support (Jobs and Careers Service, Youth Guarantee), Renters' Rights Act and Decent Homes Standard, Crisis and Resilience Fund, Best Start Family Hubs. Build a strategy-level theory of change.

## Shape summary

| Metric | Value |
|---|---|
| Nodes | 15 |
| Containers (groups) | 3 |
| Nodes by layer | context: 1, input: 1, driver: 7, outcome_long: 4, impact: 2 |
| Edges (as drawn) | 5 |
| of which bidirectional | 0 |
| of which group-level (to/from a container) | 5 |
| Edges by evidence status | unrated: 5 |
| Edges carrying located assumptions | 0 |
| Assumptions / risks listed | 0 |
| Feedback loops (directed cycles, containers contracted, two-way links excluded) | 0 |
| Longest causal chain (units, containers contracted) | 4 |
| Unconnected nodes | none |

Longest chain (containers contracted): `CPS` → `G_DRV` → `G_OCM` → `G_IMP`


## Containers

| ID | Layer | Label | Members |
|---|---|---|---|
| G_DRV | driver | Drivers of poverty | D1, D2, D3, D4, D5, D6, D7 |
| G_OCM | outcome_long | Outcomes | O1, O2, O3, O4 |
| G_IMP | impact | Impact | IM1, IM2 |

## Nodes

| ID | Layer | Container | Label (as in source) |
|---|---|---|---|
| CPS | input |  | Child Poverty Strategy (measures across government) |
| D1 | driver | G_DRV | Social security and child maintenance |
| D2 | driver | G_DRV | Employment |
| D3 | driver | G_DRV | Childcare |
| D4 | driver | G_DRV | Housing |
| D5 | driver | G_DRV | Essential costs |
| D6 | driver | G_DRV | Savings and financial shocks |
| D7 | driver | G_DRV | Barriers to services |
| O1 | outcome_long | G_OCM | Boost families' incomes |
| O2 | outcome_long | G_OCM | Save families money |
| O3 | outcome_long | G_OCM | Secure family finances |
| O4 | outcome_long | G_OCM | Strengthened local support |
| IM1 | impact | G_IMP | Reduce child poverty |
| IM2 | impact | G_IMP | Reduce the impact of child poverty |
| CTX | context |  | Wider context: other policy changes; changes in social, economic or environmental factors (frame around whole model, arrows into Drivers and Outcomes) |

## Edges

`status`: evidence judgement shown in the source. `confidence`: our confidence in the transcription of the arrow.

| # | From | To | Dir | Status | Assumptions on link | Confidence | Note |
|---|---|---|---|---|---|---|---|
| 1 | CPS | G_DRV | → | unrated |  | high | column-level arrows only; no driver-specific links |
| 2 | G_DRV | G_OCM | → | unrated |  | high | column-level arrows only; driver->outcome mapping not specified |
| 3 | G_OCM | G_IMP | → | unrated |  | high | column-level arrows only |
| 4 | CTX | G_DRV | → | unrated |  | high | context frame arrow into Drivers |
| 5 | CTX | G_OCM | → | unrated |  | high | context frame arrow into Outcomes |

## Context factors

- Other policy changes
- Social, economic, environmental change
- Devolved powers and regional variation
- Place-based context (added in July 2026 revision)

## Indicators linked to the ToC

| Indicator | Direct link to relative low income | Direct link to deep material poverty |
|---|---|---|
| Net income before housing costs for children in the bottom two income quintiles | Yes | Yes |
| Employment rates for parents in the bottom two income quintiles | Yes | Yes |
| Median weekly earnings for employed parents in the bottom two income quintiles | Yes | Yes |
| Real value of the Universal Credit standard allowance | Yes | Yes |
| Household savings over £850 for children in the bottom two income quintiles | No | Yes |
| Household arrears on bills for children in the bottom two income quintiles | No | Yes |
| Household spending on essentials for low-income households with children | Yes | Yes |
| Children in relative low income living in homes not meeting the Decent Homes Standard | No | Yes |

## Known gaps in this dataset

- July 2026 revised ToC (three pillars, seven priority areas, delivery partners) is an SVG not transcribed; this dataset uses the Dec 2025 version
- Driver-to-outcome arrows are column-level only; specific driver->outcome mapping is not given in the source

## Machine-readable

```json
{
 "case": "child_poverty",
 "title": "UK Child Poverty Strategy: theory of change (Dec 2025 version)",
 "nodes": [
  {
   "id": "CPS",
   "layer": "input",
   "group": null,
   "label": "Child Poverty Strategy (measures across government)"
  },
  {
   "id": "D1",
   "layer": "driver",
   "group": "G_DRV",
   "label": "Social security and child maintenance"
  },
  {
   "id": "D2",
   "layer": "driver",
   "group": "G_DRV",
   "label": "Employment"
  },
  {
   "id": "D3",
   "layer": "driver",
   "group": "G_DRV",
   "label": "Childcare"
  },
  {
   "id": "D4",
   "layer": "driver",
   "group": "G_DRV",
   "label": "Housing"
  },
  {
   "id": "D5",
   "layer": "driver",
   "group": "G_DRV",
   "label": "Essential costs"
  },
  {
   "id": "D6",
   "layer": "driver",
   "group": "G_DRV",
   "label": "Savings and financial shocks"
  },
  {
   "id": "D7",
   "layer": "driver",
   "group": "G_DRV",
   "label": "Barriers to services"
  },
  {
   "id": "O1",
   "layer": "outcome_long",
   "group": "G_OCM",
   "label": "Boost families' incomes"
  },
  {
   "id": "O2",
   "layer": "outcome_long",
   "group": "G_OCM",
   "label": "Save families money"
  },
  {
   "id": "O3",
   "layer": "outcome_long",
   "group": "G_OCM",
   "label": "Secure family finances"
  },
  {
   "id": "O4",
   "layer": "outcome_long",
   "group": "G_OCM",
   "label": "Strengthened local support"
  },
  {
   "id": "IM1",
   "layer": "impact",
   "group": "G_IMP",
   "label": "Reduce child poverty"
  },
  {
   "id": "IM2",
   "layer": "impact",
   "group": "G_IMP",
   "label": "Reduce the impact of child poverty"
  },
  {
   "id": "CTX",
   "layer": "context",
   "group": null,
   "label": "Wider context: other policy changes; changes in social, economic or environmental factors (frame around whole model, arrows into Drivers and Outcomes)"
  }
 ],
 "groups": [
  {
   "id": "G_DRV",
   "layer": "driver",
   "label": "Drivers of poverty"
  },
  {
   "id": "G_OCM",
   "layer": "outcome_long",
   "label": "Outcomes"
  },
  {
   "id": "G_IMP",
   "layer": "impact",
   "label": "Impact"
  }
 ],
 "edges": [
  {
   "source": "CPS",
   "target": "G_DRV",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_DRV",
   "target": "G_OCM",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_OCM",
   "target": "G_IMP",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "CTX",
   "target": "G_DRV",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "CTX",
   "target": "G_OCM",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  }
 ],
 "assumptions": [],
 "shape": {
  "n_nodes": 15,
  "n_groups": 3,
  "n_edges": 5,
  "n_bidirectional": 0,
  "n_group_level_edges": 5,
  "nodes_by_layer": {
   "context": 1,
   "input": 1,
   "driver": 7,
   "outcome_long": 4,
   "impact": 2
  },
  "edges_by_status": {
   "unrated": 5
  },
  "edges_with_assumptions": 0,
  "n_assumptions": 0,
  "n_feedback_loops": 0,
  "longest_directed_path": [
   "CPS",
   "G_DRV",
   "G_OCM",
   "G_IMP"
  ],
  "longest_path_len": 4,
  "orphan_nodes": []
 }
}
```
