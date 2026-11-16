# Ground truth: Implementation and application of the Environmental Principles Policy Statement (EPPS)

- **Case ID:** `epps`
- **Level:** policy / implementation of a statutory duty
- **Source:** RPA for the Office for Environmental Protection (2024, rev. Feb 2025), Figure A3-1 and Tables 1, 2-1, 2-3
- **URL:** https://www.theoep.org.uk/sites/default/files/investigations-files/Evaluation%20of%20the%20Implementation%20of%20the%20Environmental%20Principles%20Policy%20Statement_0.pdf
- **Evidence basis in source:** Ex-post: process tracing of 30 civil-servant interviews (8 departments + 1 ALB), departmental documents and 40 impact assessments.
- **Evidence/rating scheme in source:** No evidence < Limited < Some < Good < Strong (Table 2-3). NB 'Limited' = evidence identifies information AGAINST the assumption; 'No evidence' = nothing gathered either way.

## Task briefs for Policy Atlas

Use these as the *only* input to Policy Atlas. Do not give it any other text from the source.

**Outcome-first brief**

> Ministers in England must now have 'due regard' to a new policy statement on five environmental principles (integration, prevention, rectification at source, polluter pays, precaution) when making policy. The long-term aim is that this improves environmental protection and sustainable development. Build a theory of change for how this duty would achieve that aim across central government.

**Intervention-first brief**

> Environment Act 2021 s.19 requires ministers to have due regard to the Environmental Principles Policy Statement when making policy (in force 1 Nov 2023). To support implementation, Defra produced a non-statutory toolkit (assessment template, case studies), a Civil Service Learning module and a cross-departmental working group; departments added an EPPS section to ministerial submission templates and produced their own guidance, with comms and legal support. Build a theory of change from these inputs to long-term environmental impact.

## Shape summary

| Metric | Value |
|---|---|
| Nodes | 26 |
| Containers (groups) | 4 |
| Nodes by layer | input: 6, activity: 5, output: 2, outcome_short: 5, outcome_long: 4, impact: 3, vision: 1 |
| Edges (as drawn) | 27 |
| of which bidirectional | 2 |
| of which group-level (to/from a container) | 9 |
| Edges by evidence status | unrated: 27 |
| Edges carrying located assumptions | 17 |
| Assumptions / risks listed | 13 |
| Feedback loops (directed cycles, containers contracted, two-way links excluded) | 0 |
| Longest causal chain (units, containers contracted) | 8 |
| Unconnected nodes | none |

Longest chain (containers contracted): `I1` → `G_ACT` → `G_OUT` → `OC0` → `G_HOW` → `G_INF` → `IM1` → `V1`


## Containers

| ID | Layer | Label | Members |
|---|---|---|---|
| G_ACT | activity | Departments put in place and apply their systems and practices to give effect to EPPS | AC1, AC2, AC3, AC4, AC5 |
| G_OUT | output | Clear and effective systems to support the consideration of the EPPS in policymaking, with relevant principles considered where appropriate | OP1, OP2 |
| G_HOW | outcome_short | How policy could be affected by consideration of the EPPS | OC1, OC2, OC3, OC4 |
| G_INF | outcome_long | Consideration of EPPS influences approach to, and outcomes from, policymaking | OC5, OC6, OC7, OC8 |

## Nodes

| ID | Layer | Container | Label (as in source) |
|---|---|---|---|
| I1 | input |  | Cross-departmental working group on EPPS |
| I2 | input |  | Comms and legal support for implementation |
| I3 | input |  | Other (non-toolkit) departmental guidance and templates |
| I4 | input |  | Civil Service Learning module |
| I5 | input |  | Defra toolkit |
| I6 | input |  | Environmental Principles Policy Statement (EPPS) and explanatory memorandum |
| AC1 | activity | G_ACT | Govt departments use toolkit and civil service learning as a starting point for developing their own systems and processes |
| AC2 | activity | G_ACT | Govt departments develop their awareness and understanding of EPPS |
| AC3 | activity | G_ACT | Departmental record-keeping of how processes have been applied |
| AC4 | activity | G_ACT | Knowledge and best-practice sharing across departments, including working group meetings |
| AC5 | activity | G_ACT | Policymakers consider potential unintended consequences |
| OP1 | output | G_OUT | Ministerial policy |
| OP2 | output | G_OUT | Departmental records on how EPPS has been considered that show how processes have been applied |
| OC0 | outcome_short |  | Policies consider the relevant principles, with considerations taken on board where appropriate |
| OC1 | outcome_short | G_HOW | Policy options amended or new ones suggested |
| OC2 | outcome_short | G_HOW | Reframing the policy to accommodate the principle(s) |
| OC3 | outcome_short | G_HOW | Embedding a principle in law or guidance |
| OC4 | outcome_short | G_HOW | Postponing a policy until further evidence is gained |
| OC5 | outcome_long | G_INF | Changed attitudes by drawing attention to environmental issues and the five principles |
| OC6 | outcome_long | G_INF | Secured procedural change through dialogue on five principles and new processes |
| OC7 | outcome_long | G_INF | Affected policy content through consideration of the principles |
| OC8 | outcome_long | G_INF | Influenced behaviour change by ensuring meaningful and sustainable delivery of the principles |
| IM1 | impact |  | Identified opportunities to prevent environmental damage |
| IM2 | impact |  | Identified opportunities to enhance the environment |
| IM3 | impact |  | Identified opportunities to promote sustainable development |
| V1 | vision |  | Principles guide ministers and policymakers towards opportunities to prevent environmental damage and enhance the environment (Environment Act s.17(4)); application enhances environmental protection and promotes sustainable development |

## Edges

`status`: evidence judgement shown in the source. `confidence`: our confidence in the transcription of the arrow.

| # | From | To | Dir | Status | Assumptions on link | Confidence | Note |
|---|---|---|---|---|---|---|---|
| 1 | I1 | AC1 | → | unrated |  | high | direct line bypassing assumptions |
| 2 | I1 | AC1 | → | unrated | A6 | high | via A6 box |
| 3 | I2 | AC1 | → | unrated | A6 | medium | I2 feeds A6 box, which points to AC1 |
| 4 | I2 | G_ACT | → | unrated | A5 | medium | A5 box has no explicit outgoing arrow; sits above activity group |
| 5 | I3 | G_ACT | → | unrated | A5 | medium | I3 left line feeds A5 |
| 6 | I3 | AC1 | → | unrated | A3, A4 | high |  |
| 7 | I4 | AC1 | → | unrated | A3, A4 | high |  |
| 8 | I5 | AC1 | → | unrated | A1, A3, A4 | medium | toolkit and EPPS both feed A1; A1 points left into A3 |
| 9 | I6 | AC1 | → | unrated | A1, A3, A4 | medium |  |
| 10 | I6 | AC2 | → | unrated | A1, A2 | high |  |
| 11 | I5 | AC2 | → | unrated | A1, A2 | medium |  |
| 12 | AC2 | AC1 | → | unrated |  | high |  |
| 13 | AC2 | AC5 | → | unrated |  | high |  |
| 14 | AC1 | AC3 | → | unrated | A7, A8 | high |  |
| 15 | AC1 | AC4 | → | unrated | A7, A8 | high |  |
| 16 | AC3 | AC4 | ↔ | unrated |  | high |  |
| 17 | AC4 | AC5 | ↔ | unrated |  | high |  |
| 18 | G_ACT | G_OUT | → | unrated | A9, A10, A11 | high | three activity arrows pass through stacked A11/A10/A9 bars |
| 19 | G_OUT | OC0 | → | unrated | A12 | high |  |
| 20 | OC0 | G_HOW | → | unrated |  | high |  |
| 21 | G_HOW | G_INF | → | unrated |  | high |  |
| 22 | G_INF | IM1 | → | unrated | A13 | high |  |
| 23 | G_INF | IM2 | → | unrated | A13 | high |  |
| 24 | G_INF | IM3 | → | unrated | A13 | high |  |
| 25 | IM1 | V1 | → | unrated |  | high |  |
| 26 | IM2 | V1 | → | unrated |  | high |  |
| 27 | IM3 | V1 | → | unrated |  | high |  |

## Assumptions and risks

| ID | Statement | Location in chain | Rating in source | Justification |
|---|---|---|---|---|
| A1 | Government's frameworks for application of the principles are clear and transparent | Inputs to Activities | Strong | All departments interviewed stated how important awareness-raising of the EPPS was |
| A2 | Government officials and ministers understand the requirement to have due regard to EPPS and look at the EPPS | Inputs to Activities | Good | Information produced and used across all departments; one legal challenge suggests further work needed |
| A3 | Toolkit and training contain the necessary guidance to help policymakers apply the EPPS appropriately | Inputs to Activities | Strong | Feedback on uptake and usefulness of processes; departments able to tailor them |
| A4 | Toolkit is considered and used as intended | Inputs to Activities | Strong | Toolkit an important resource; feedback incorporated over time |
| A5 | Government puts in place effective framework of tools and processes | Inputs to Activities | Strong | Legal teams and comms enabled guidance to be developed effectively |
| A6 | Effective governance across government | Inputs to Activities | Strong | Value of the cross-governmental group for collaboration, feedback and sharing practice |
| A7 | Framework is applied effectively and meaningfully | Activities | Strong | Processes and additional support enable effective application |
| A8 | Environmental principles have been proportionately applied in accordance with the EPPS when making policy | Activities | Good | Frequent concerns over resource needs, expected to reduce over time |
| A9 | Application and interpretation of principles are robust, objective and consistent with intended meaning | Activities to Outputs | Some | Feedback on application, but questions over comprehensiveness |
| A10 | Application and interpretation of principles have usefully informed policymaking (where appropriate) | Activities to Outputs | Some | Examples show principles used to inform policymaking |
| A11 | Application and interpretation in individual cases is clear and transparent | Activities to Outputs | Some | Based on examples provided |
| A12 | Principles make a demonstrable and positive difference (where appropriate) to the substance/content of policies | Outputs to Outcomes | Good | Change in attitudes reported; more time needed for behaviour change |
| A13 | Application and interpretation of principles result in opportunities for positive effects in terms of environmental outcomes | Outcomes to Impacts | Limited | General discussion of changes indicates possible positive outcomes; more evidence needed |

## Machine-readable

```json
{
 "case": "epps",
 "title": "Implementation and application of the Environmental Principles Policy Statement (EPPS)",
 "nodes": [
  {
   "id": "I1",
   "layer": "input",
   "group": null,
   "label": "Cross-departmental working group on EPPS"
  },
  {
   "id": "I2",
   "layer": "input",
   "group": null,
   "label": "Comms and legal support for implementation"
  },
  {
   "id": "I3",
   "layer": "input",
   "group": null,
   "label": "Other (non-toolkit) departmental guidance and templates"
  },
  {
   "id": "I4",
   "layer": "input",
   "group": null,
   "label": "Civil Service Learning module"
  },
  {
   "id": "I5",
   "layer": "input",
   "group": null,
   "label": "Defra toolkit"
  },
  {
   "id": "I6",
   "layer": "input",
   "group": null,
   "label": "Environmental Principles Policy Statement (EPPS) and explanatory memorandum"
  },
  {
   "id": "AC1",
   "layer": "activity",
   "group": "G_ACT",
   "label": "Govt departments use toolkit and civil service learning as a starting point for developing their own systems and processes"
  },
  {
   "id": "AC2",
   "layer": "activity",
   "group": "G_ACT",
   "label": "Govt departments develop their awareness and understanding of EPPS"
  },
  {
   "id": "AC3",
   "layer": "activity",
   "group": "G_ACT",
   "label": "Departmental record-keeping of how processes have been applied"
  },
  {
   "id": "AC4",
   "layer": "activity",
   "group": "G_ACT",
   "label": "Knowledge and best-practice sharing across departments, including working group meetings"
  },
  {
   "id": "AC5",
   "layer": "activity",
   "group": "G_ACT",
   "label": "Policymakers consider potential unintended consequences"
  },
  {
   "id": "OP1",
   "layer": "output",
   "group": "G_OUT",
   "label": "Ministerial policy"
  },
  {
   "id": "OP2",
   "layer": "output",
   "group": "G_OUT",
   "label": "Departmental records on how EPPS has been considered that show how processes have been applied"
  },
  {
   "id": "OC0",
   "layer": "outcome_short",
   "group": null,
   "label": "Policies consider the relevant principles, with considerations taken on board where appropriate"
  },
  {
   "id": "OC1",
   "layer": "outcome_short",
   "group": "G_HOW",
   "label": "Policy options amended or new ones suggested"
  },
  {
   "id": "OC2",
   "layer": "outcome_short",
   "group": "G_HOW",
   "label": "Reframing the policy to accommodate the principle(s)"
  },
  {
   "id": "OC3",
   "layer": "outcome_short",
   "group": "G_HOW",
   "label": "Embedding a principle in law or guidance"
  },
  {
   "id": "OC4",
   "layer": "outcome_short",
   "group": "G_HOW",
   "label": "Postponing a policy until further evidence is gained"
  },
  {
   "id": "OC5",
   "layer": "outcome_long",
   "group": "G_INF",
   "label": "Changed attitudes by drawing attention to environmental issues and the five principles"
  },
  {
   "id": "OC6",
   "layer": "outcome_long",
   "group": "G_INF",
   "label": "Secured procedural change through dialogue on five principles and new processes"
  },
  {
   "id": "OC7",
   "layer": "outcome_long",
   "group": "G_INF",
   "label": "Affected policy content through consideration of the principles"
  },
  {
   "id": "OC8",
   "layer": "outcome_long",
   "group": "G_INF",
   "label": "Influenced behaviour change by ensuring meaningful and sustainable delivery of the principles"
  },
  {
   "id": "IM1",
   "layer": "impact",
   "group": null,
   "label": "Identified opportunities to prevent environmental damage"
  },
  {
   "id": "IM2",
   "layer": "impact",
   "group": null,
   "label": "Identified opportunities to enhance the environment"
  },
  {
   "id": "IM3",
   "layer": "impact",
   "group": null,
   "label": "Identified opportunities to promote sustainable development"
  },
  {
   "id": "V1",
   "layer": "vision",
   "group": null,
   "label": "Principles guide ministers and policymakers towards opportunities to prevent environmental damage and enhance the environment (Environment Act s.17(4)); application enhances environmental protection and promotes sustainable development"
  }
 ],
 "groups": [
  {
   "id": "G_ACT",
   "layer": "activity",
   "label": "Departments put in place and apply their systems and practices to give effect to EPPS"
  },
  {
   "id": "G_OUT",
   "layer": "output",
   "label": "Clear and effective systems to support the consideration of the EPPS in policymaking, with relevant principles considered where appropriate"
  },
  {
   "id": "G_HOW",
   "layer": "outcome_short",
   "label": "How policy could be affected by consideration of the EPPS"
  },
  {
   "id": "G_INF",
   "layer": "outcome_long",
   "label": "Consideration of EPPS influences approach to, and outcomes from, policymaking"
  }
 ],
 "edges": [
  {
   "source": "I1",
   "target": "AC1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "I1",
   "target": "AC1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A6"
   ],
   "confidence": "high"
  },
  {
   "source": "I2",
   "target": "AC1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A6"
   ],
   "confidence": "medium"
  },
  {
   "source": "I2",
   "target": "G_ACT",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A5"
   ],
   "confidence": "medium"
  },
  {
   "source": "I3",
   "target": "G_ACT",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A5"
   ],
   "confidence": "medium"
  },
  {
   "source": "I3",
   "target": "AC1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A3",
    "A4"
   ],
   "confidence": "high"
  },
  {
   "source": "I4",
   "target": "AC1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A3",
    "A4"
   ],
   "confidence": "high"
  },
  {
   "source": "I5",
   "target": "AC1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A1",
    "A3",
    "A4"
   ],
   "confidence": "medium"
  },
  {
   "source": "I6",
   "target": "AC1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A1",
    "A3",
    "A4"
   ],
   "confidence": "medium"
  },
  {
   "source": "I6",
   "target": "AC2",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A1",
    "A2"
   ],
   "confidence": "high"
  },
  {
   "source": "I5",
   "target": "AC2",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A1",
    "A2"
   ],
   "confidence": "medium"
  },
  {
   "source": "AC2",
   "target": "AC1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "AC2",
   "target": "AC5",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "AC1",
   "target": "AC3",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A7",
    "A8"
   ],
   "confidence": "high"
  },
  {
   "source": "AC1",
   "target": "AC4",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A7",
    "A8"
   ],
   "confidence": "high"
  },
  {
   "source": "AC3",
   "target": "AC4",
   "bidirectional": true,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "AC4",
   "target": "AC5",
   "bidirectional": true,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_ACT",
   "target": "G_OUT",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A9",
    "A10",
    "A11"
   ],
   "confidence": "high"
  },
  {
   "source": "G_OUT",
   "target": "OC0",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A12"
   ],
   "confidence": "high"
  },
  {
   "source": "OC0",
   "target": "G_HOW",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_HOW",
   "target": "G_INF",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_INF",
   "target": "IM1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A13"
   ],
   "confidence": "high"
  },
  {
   "source": "G_INF",
   "target": "IM2",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A13"
   ],
   "confidence": "high"
  },
  {
   "source": "G_INF",
   "target": "IM3",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [
    "A13"
   ],
   "confidence": "high"
  },
  {
   "source": "IM1",
   "target": "V1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "IM2",
   "target": "V1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "IM3",
   "target": "V1",
   "bidirectional": false,
   "status": "unrated",
   "assumptions": [],
   "confidence": "high"
  }
 ],
 "assumptions": [
  {
   "id": "A1",
   "text": "Government's frameworks for application of the principles are clear and transparent",
   "location": "Inputs to Activities",
   "rating": "Strong"
  },
  {
   "id": "A2",
   "text": "Government officials and ministers understand the requirement to have due regard to EPPS and look at the EPPS",
   "location": "Inputs to Activities",
   "rating": "Good"
  },
  {
   "id": "A3",
   "text": "Toolkit and training contain the necessary guidance to help policymakers apply the EPPS appropriately",
   "location": "Inputs to Activities",
   "rating": "Strong"
  },
  {
   "id": "A4",
   "text": "Toolkit is considered and used as intended",
   "location": "Inputs to Activities",
   "rating": "Strong"
  },
  {
   "id": "A5",
   "text": "Government puts in place effective framework of tools and processes",
   "location": "Inputs to Activities",
   "rating": "Strong"
  },
  {
   "id": "A6",
   "text": "Effective governance across government",
   "location": "Inputs to Activities",
   "rating": "Strong"
  },
  {
   "id": "A7",
   "text": "Framework is applied effectively and meaningfully",
   "location": "Activities",
   "rating": "Strong"
  },
  {
   "id": "A8",
   "text": "Environmental principles have been proportionately applied in accordance with the EPPS when making policy",
   "location": "Activities",
   "rating": "Good"
  },
  {
   "id": "A9",
   "text": "Application and interpretation of principles are robust, objective and consistent with intended meaning",
   "location": "Activities to Outputs",
   "rating": "Some"
  },
  {
   "id": "A10",
   "text": "Application and interpretation of principles have usefully informed policymaking (where appropriate)",
   "location": "Activities to Outputs",
   "rating": "Some"
  },
  {
   "id": "A11",
   "text": "Application and interpretation in individual cases is clear and transparent",
   "location": "Activities to Outputs",
   "rating": "Some"
  },
  {
   "id": "A12",
   "text": "Principles make a demonstrable and positive difference (where appropriate) to the substance/content of policies",
   "location": "Outputs to Outcomes",
   "rating": "Good"
  },
  {
   "id": "A13",
   "text": "Application and interpretation of principles result in opportunities for positive effects in terms of environmental outcomes",
   "location": "Outcomes to Impacts",
   "rating": "Limited"
  }
 ],
 "shape": {
  "n_nodes": 26,
  "n_groups": 4,
  "n_edges": 27,
  "n_bidirectional": 2,
  "n_group_level_edges": 9,
  "nodes_by_layer": {
   "input": 6,
   "activity": 5,
   "output": 2,
   "outcome_short": 5,
   "outcome_long": 4,
   "impact": 3,
   "vision": 1
  },
  "edges_by_status": {
   "unrated": 27
  },
  "edges_with_assumptions": 17,
  "n_assumptions": 13,
  "n_feedback_loops": 0,
  "longest_directed_path": [
   "I1",
   "G_ACT",
   "G_OUT",
   "OC0",
   "G_HOW",
   "G_INF",
   "IM1",
   "V1"
  ],
  "longest_path_len": 8,
  "orphan_nodes": []
 }
}
```
