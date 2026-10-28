# Ground truth: Changing Futures: individual-level theory of change

- **Case ID:** `cf_individual`
- **Level:** programme, individual level (1 of 3 linked maps)
- **Source:** MHCLG / Changing Futures evaluation (CFE Research with University of Sheffield), theory of change map version (updated Dec 2025)
- **URL:** https://assets.publishing.service.gov.uk/media/67a221eaad556423b636ca1f/Changing_Futures_theory_of_change_-_map_version.pdf
- **Evidence basis in source:** Ex-post: theory-based, largely qualitative evaluation (longitudinal participant data, systems mapping, participatory methods, triangulation).
- **Evidence/rating scheme in source:** Edge line style: solid = evidence suggests progress towards intended outcome; dashed = not enough evidence to gauge; dotted = evidence suggests NOT leading to intended outcome.

## Task briefs for Policy Atlas

Use these as the *only* input to Policy Atlas. Do not give it any other text from the source.

**Outcome-first brief**

> Adults experiencing multiple disadvantage (combinations of homelessness, substance misuse, mental ill-health, domestic abuse, contact with criminal justice) are poorly served by fragmented services. The aim is sustained improvements in their health, wellbeing, financial stability and social inclusion, and reduced use of emergency services. Build a theory of change for a place-based programme to achieve this at individual, service and system levels.

**Intervention-first brief**

> Changing Futures (~£92m, MHCLG and The National Lottery Community Fund, delivered in local areas in England) funds keyworkers with low caseloads and personal budgets providing flexible, person-centred, trauma-informed support; lived experience roles and co-design; multiagency forums and strategic leadership roles; data and workforce activity to change local commissioning and services. Build a theory of change at individual, service and system levels.

## Shape summary

| Metric | Value |
|---|---|
| Nodes | 31 |
| Containers (groups) | 5 |
| Nodes by layer | activity: 7, outcome_short: 9, outcome_long: 7, impact: 8 |
| Edges (as drawn) | 14 |
| of which bidirectional | 1 |
| of which group-level (to/from a container) | 8 |
| Edges by evidence status | insufficient: 10, progressing: 3, not_leading: 1 |
| Edges carrying located assumptions | 0 |
| Assumptions / risks listed | 0 |
| Feedback loops (directed cycles, containers contracted, two-way links excluded) | 0 |
| Longest causal chain (units, containers contracted) | 8 |
| Unconnected nodes | none |

Longest chain (containers contracted): `DPC` → `IPC` → `G_ENG` → `AREAS` → `HR` → `G_EARLY` → `G_STAB` → `G_SUST`


## Containers

| ID | Layer | Label | Members |
|---|---|---|---|
| G_ENG | outcome_short | Participants are engaged by the programme | EN1, EN2, EN3 |
| G_EARLY | outcome_short | Early outcomes of programme support | E1, E2, E3, E4, E5 |
| G_STAB | outcome_long | Stabilisation of health and wellbeing reduces need for intensive caseworker support | S1, S2, S3, S4, S5 |
| G_PATH | outcome_long | Pathways of support for people who are stabilised | P1, P2, P3, P4, P5 |
| G_SUST | impact | Sustained improvements | SU1, SU2, SU3, SU4, SU5, SU6 |

## Nodes

| ID | Layer | Container | Label (as in source) |
|---|---|---|---|
| EN1 | outcome_short | G_ENG | People at key transition points (leaving care, prison) are engaged |
| EN2 | outcome_short | G_ENG | Participants with high levels of need and poor past engagement with services are engaged |
| EN3 | outcome_short | G_ENG | People with protected characteristics experiencing multiple disadvantage are engaged |
| DPC | activity |  | Data and evidence collected from local partners on participants with protected characteristics |
| IPC | activity |  | Increased evidence and insight on how people with protected characteristics experience multiple disadvantage |
| AREAS | activity |  | Areas provide flexible person-centred support; support people to engage more positively with family/community; coordinate care; build relationships with people experiencing multiple disadvantage |
| HR | activity |  | Provision of harm reduction pre-treatment support whilst participants await treatment |
| E1 | outcome_short | G_EARLY | Improved financial security |
| E2 | outcome_short | G_EARLY | People engage more positively with family and community and move away from negative relationships |
| E3 | outcome_short | G_EARLY | Individuals feel supported, trusted, valued, safe and in control |
| E4 | outcome_short | G_EARLY | Improved capability and motivation to access services |
| E5 | outcome_short | G_EARLY | Crisis prevention reduces need for emergency services or treatment |
| SENG | outcome_short |  | Individuals can sustain their engagement with the services and treatment they need and want |
| S1 | outcome_long | G_STAB | Improved connectivity to family/community |
| S2 | outcome_long | G_STAB | Better health, including mental health and addiction |
| S3 | outcome_long | G_STAB | Increased ownership of recovery |
| S4 | outcome_long | G_STAB | Individuals have increased trust in public services |
| S5 | outcome_long | G_STAB | Improved wellbeing |
| P1 | activity | G_PATH | Sustainable peer support in place as part of step-down support |
| P2 | activity | G_PATH | Participants who are stabilised receive step-down support (continuing casework or mainstream service, as appropriate) |
| P3 | activity | G_PATH | People who are at risk are re-linked to support |
| P4 | outcome_long | G_PATH | There is sustainable, holistic keyworker support in local systems |
| P5 | outcome_long | G_PATH | The local ecosystem of support can respond to the longer-term needs of people in recovery |
| SU1 | impact | G_SUST | Sustained greater financial stability |
| SU2 | impact | G_SUST | Progress towards social inclusion is sustained |
| SU3 | impact | G_SUST | Sustained improvements in health |
| SU4 | impact | G_SUST | Sustained improvements in wellbeing |
| SU5 | impact | G_SUST | Reduction in the use of emergency services, contact with criminal justice, rough sleeping |
| SU6 | impact | G_SUST | Reduced inequalities in outcomes for people with protected characteristics |
| SVC_FLEX | impact |  | Services across the system provide flexible, person-centred, trauma-informed support that is effective in addressing multiple disadvantage |
| SVC_CAP | impact |  | Services needed by people experiencing multiple disadvantage have sufficient capacity to enable timely, trauma-informed treatment |

## Edges

`status`: evidence judgement shown in the source. `confidence`: our confidence in the transcription of the arrow.

| # | From | To | Dir | Status | Assumptions on link | Confidence | Note |
|---|---|---|---|---|---|---|---|
| 1 | DPC | IPC | → | insufficient |  | high |  |
| 2 | IPC | G_ENG | → | insufficient |  | high |  |
| 3 | G_ENG | AREAS | → | progressing |  | high |  |
| 4 | AREAS | G_EARLY | → | progressing |  | high |  |
| 5 | AREAS | HR | → | insufficient |  | high |  |
| 6 | HR | G_EARLY | → | insufficient |  | high |  |
| 7 | AREAS | SENG | → | insufficient |  | high |  |
| 8 | SENG | G_STAB | → | insufficient |  | high |  |
| 9 | G_EARLY | G_STAB | → | progressing |  | high |  |
| 10 | G_STAB | G_SUST | → | insufficient |  | high |  |
| 11 | G_PATH | G_SUST | → | insufficient |  | medium | arrow leaves right edge of pathways group near P5 |
| 12 | SVC_FLEX | P5 | → | insufficient |  | high |  |
| 13 | SVC_FLEX | SVC_CAP | ↔ | insufficient |  | high |  |
| 14 | SVC_CAP | SENG | → | not_leading |  | high | the only 'not leading' link on this map |

## Context factors

- Accountability ceiling: vertical dotted line marking the threshold of what the programme can directly influence

## Machine-readable

```json
{
 "case": "cf_individual",
 "title": "Changing Futures: individual-level theory of change",
 "nodes": [
  {
   "id": "EN1",
   "layer": "outcome_short",
   "group": "G_ENG",
   "label": "People at key transition points (leaving care, prison) are engaged"
  },
  {
   "id": "EN2",
   "layer": "outcome_short",
   "group": "G_ENG",
   "label": "Participants with high levels of need and poor past engagement with services are engaged"
  },
  {
   "id": "EN3",
   "layer": "outcome_short",
   "group": "G_ENG",
   "label": "People with protected characteristics experiencing multiple disadvantage are engaged"
  },
  {
   "id": "DPC",
   "layer": "activity",
   "group": null,
   "label": "Data and evidence collected from local partners on participants with protected characteristics"
  },
  {
   "id": "IPC",
   "layer": "activity",
   "group": null,
   "label": "Increased evidence and insight on how people with protected characteristics experience multiple disadvantage"
  },
  {
   "id": "AREAS",
   "layer": "activity",
   "group": null,
   "label": "Areas provide flexible person-centred support; support people to engage more positively with family/community; coordinate care; build relationships with people experiencing multiple disadvantage"
  },
  {
   "id": "HR",
   "layer": "activity",
   "group": null,
   "label": "Provision of harm reduction pre-treatment support whilst participants await treatment"
  },
  {
   "id": "E1",
   "layer": "outcome_short",
   "group": "G_EARLY",
   "label": "Improved financial security"
  },
  {
   "id": "E2",
   "layer": "outcome_short",
   "group": "G_EARLY",
   "label": "People engage more positively with family and community and move away from negative relationships"
  },
  {
   "id": "E3",
   "layer": "outcome_short",
   "group": "G_EARLY",
   "label": "Individuals feel supported, trusted, valued, safe and in control"
  },
  {
   "id": "E4",
   "layer": "outcome_short",
   "group": "G_EARLY",
   "label": "Improved capability and motivation to access services"
  },
  {
   "id": "E5",
   "layer": "outcome_short",
   "group": "G_EARLY",
   "label": "Crisis prevention reduces need for emergency services or treatment"
  },
  {
   "id": "SENG",
   "layer": "outcome_short",
   "group": null,
   "label": "Individuals can sustain their engagement with the services and treatment they need and want"
  },
  {
   "id": "S1",
   "layer": "outcome_long",
   "group": "G_STAB",
   "label": "Improved connectivity to family/community"
  },
  {
   "id": "S2",
   "layer": "outcome_long",
   "group": "G_STAB",
   "label": "Better health, including mental health and addiction"
  },
  {
   "id": "S3",
   "layer": "outcome_long",
   "group": "G_STAB",
   "label": "Increased ownership of recovery"
  },
  {
   "id": "S4",
   "layer": "outcome_long",
   "group": "G_STAB",
   "label": "Individuals have increased trust in public services"
  },
  {
   "id": "S5",
   "layer": "outcome_long",
   "group": "G_STAB",
   "label": "Improved wellbeing"
  },
  {
   "id": "P1",
   "layer": "activity",
   "group": "G_PATH",
   "label": "Sustainable peer support in place as part of step-down support"
  },
  {
   "id": "P2",
   "layer": "activity",
   "group": "G_PATH",
   "label": "Participants who are stabilised receive step-down support (continuing casework or mainstream service, as appropriate)"
  },
  {
   "id": "P3",
   "layer": "activity",
   "group": "G_PATH",
   "label": "People who are at risk are re-linked to support"
  },
  {
   "id": "P4",
   "layer": "outcome_long",
   "group": "G_PATH",
   "label": "There is sustainable, holistic keyworker support in local systems"
  },
  {
   "id": "P5",
   "layer": "outcome_long",
   "group": "G_PATH",
   "label": "The local ecosystem of support can respond to the longer-term needs of people in recovery"
  },
  {
   "id": "SU1",
   "layer": "impact",
   "group": "G_SUST",
   "label": "Sustained greater financial stability"
  },
  {
   "id": "SU2",
   "layer": "impact",
   "group": "G_SUST",
   "label": "Progress towards social inclusion is sustained"
  },
  {
   "id": "SU3",
   "layer": "impact",
   "group": "G_SUST",
   "label": "Sustained improvements in health"
  },
  {
   "id": "SU4",
   "layer": "impact",
   "group": "G_SUST",
   "label": "Sustained improvements in wellbeing"
  },
  {
   "id": "SU5",
   "layer": "impact",
   "group": "G_SUST",
   "label": "Reduction in the use of emergency services, contact with criminal justice, rough sleeping"
  },
  {
   "id": "SU6",
   "layer": "impact",
   "group": "G_SUST",
   "label": "Reduced inequalities in outcomes for people with protected characteristics"
  },
  {
   "id": "SVC_FLEX",
   "layer": "impact",
   "group": null,
   "label": "Services across the system provide flexible, person-centred, trauma-informed support that is effective in addressing multiple disadvantage"
  },
  {
   "id": "SVC_CAP",
   "layer": "impact",
   "group": null,
   "label": "Services needed by people experiencing multiple disadvantage have sufficient capacity to enable timely, trauma-informed treatment"
  }
 ],
 "groups": [
  {
   "id": "G_ENG",
   "layer": "outcome_short",
   "label": "Participants are engaged by the programme"
  },
  {
   "id": "G_EARLY",
   "layer": "outcome_short",
   "label": "Early outcomes of programme support"
  },
  {
   "id": "G_STAB",
   "layer": "outcome_long",
   "label": "Stabilisation of health and wellbeing reduces need for intensive caseworker support"
  },
  {
   "id": "G_PATH",
   "layer": "outcome_long",
   "label": "Pathways of support for people who are stabilised"
  },
  {
   "id": "G_SUST",
   "layer": "impact",
   "label": "Sustained improvements"
  }
 ],
 "edges": [
  {
   "source": "DPC",
   "target": "IPC",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "IPC",
   "target": "G_ENG",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_ENG",
   "target": "AREAS",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "AREAS",
   "target": "G_EARLY",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "AREAS",
   "target": "HR",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "HR",
   "target": "G_EARLY",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "AREAS",
   "target": "SENG",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "SENG",
   "target": "G_STAB",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_EARLY",
   "target": "G_STAB",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_STAB",
   "target": "G_SUST",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_PATH",
   "target": "G_SUST",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "medium"
  },
  {
   "source": "SVC_FLEX",
   "target": "P5",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "SVC_FLEX",
   "target": "SVC_CAP",
   "bidirectional": true,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "SVC_CAP",
   "target": "SENG",
   "bidirectional": false,
   "status": "not_leading",
   "assumptions": [],
   "confidence": "high"
  }
 ],
 "assumptions": [],
 "shape": {
  "n_nodes": 31,
  "n_groups": 5,
  "n_edges": 14,
  "n_bidirectional": 1,
  "n_group_level_edges": 8,
  "nodes_by_layer": {
   "activity": 7,
   "outcome_short": 9,
   "outcome_long": 7,
   "impact": 8
  },
  "edges_by_status": {
   "insufficient": 10,
   "progressing": 3,
   "not_leading": 1
  },
  "edges_with_assumptions": 0,
  "n_assumptions": 0,
  "n_feedback_loops": 0,
  "longest_directed_path": [
   "DPC",
   "IPC",
   "G_ENG",
   "AREAS",
   "HR",
   "G_EARLY",
   "G_STAB",
   "G_SUST"
  ],
  "longest_path_len": 8,
  "orphan_nodes": []
 }
}
```
