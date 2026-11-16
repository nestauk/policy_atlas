# Ground truth: Changing Futures: system-level theory of change

- **Case ID:** `cf_system`
- **Level:** programme, system level (3 of 3 linked maps)
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
| Nodes | 32 |
| Containers (groups) | 4 |
| Nodes by layer | context: 1, activity: 15, outcome_short: 5, outcome_long: 5, impact: 6 |
| Edges (as drawn) | 28 |
| of which bidirectional | 3 |
| of which group-level (to/from a container) | 11 |
| Edges by evidence status | progressing: 8, insufficient: 19, not_leading: 1 |
| Edges carrying located assumptions | 0 |
| Assumptions / risks listed | 0 |
| Feedback loops (directed cycles, containers contracted, two-way links excluded) | 0 |
| Longest causal chain (units, containers contracted) | 8 |
| Unconnected nodes | none |

Longest chain (containers contracted): `RES` → `LEAD` → `LOC` → `G_DATA` → `DUSE` → `G_NEW` → `JOIN` → `SVC_FLEX`


## Containers

| ID | Layer | Label | Members |
|---|---|---|---|
| G_OPS | activity | Operational and strategic activity supporting service improvement | OPS1, OPS2, OPS3, OPS4, OPS5 |
| G_STAFF | impact | Changes in staff capabilities, motivations, and working conditions | ST1, ST2, ST3 |
| G_DATA | activity | (unlabelled container) Data activity | DA1, DA2 |
| G_NEW | outcome_long | New services or service specifications | N1, N2 |

## Nodes

| ID | Layer | Container | Label (as in source) |
|---|---|---|---|
| OPS1 | activity | G_OPS | Programme activity influences service priorities and targets, putting in place agreements and clear escalation routes |
| OPS2 | activity | G_OPS | Programme works to improve services based on local priorities, including housing, substance misuse and other health services |
| OPS3 | activity | G_OPS | Programme produces evidence about levers/enablers to improve individual, service and system outcomes |
| OPS4 | activity | G_OPS | Training and awareness-raising activity promoting trauma-informed approaches to other services |
| OPS5 | activity | G_OPS | Programme engages services needed to meet the needs of the cohort, including services not working in a trauma-informed way |
| ST1 | outcome_short | G_STAFF | Wider system staff have the capabilities and motivation for trauma-informed working |
| ST2 | impact | G_STAFF | Wider service system staff have access to support, feel valued, and have reduced burnout across services |
| ST3 | impact | G_STAFF | Wider system service conditions (flexibility, autonomy) and capacity enable staff to respond to multiple disadvantage |
| SVC_FLEX | impact |  | Services across the system provide flexible, person-centred, trauma-informed support that is effective in addressing multiple disadvantage |
| SVC_CAP | impact |  | Services needed by people experiencing multiple disadvantage have sufficient capacity to enable timely, trauma-informed treatment |
| GOVJ | activity |  | Government supports areas to join up different programmes, including frontline caseworker and multidisciplinary team activity and multiagency governance structures |
| EXIST | context |  | Existing interventions and conditions supporting increased service capacity |
| REL | activity |  | Programme staff build relationships with other services and participate in multiagency meetings |
| FOR | activity |  | Strategic multiagency forums are established (by programme or others) and work effectively |
| RES | activity |  | Programme resources strategic roles with the right skills and position to advocate on multiple disadvantage |
| LEAD | activity |  | Skilled strategic Changing Futures leadership communicates evidence of what works to existing strategy owners and fora |
| LOC | activity |  | Local leadership (e.g. local strategic leaders, commissioners) are engaged by the programme |
| DA1 | activity | G_DATA | Changing Futures areas identify existing data that enables better responses to multiple disadvantage |
| DA2 | activity | G_DATA | Changing Futures influences data owners to increase the availability and awareness of data relating to multiple disadvantage |
| LEG | activity |  | Lived experience groups and activity (co-design and delivery) |
| WF | activity |  | Strategic workforce activity focused on multiple disadvantage |
| PATHW | outcome_short |  | Clear cross-service referral pathways |
| ALIGN | outcome_short |  | Strategic alignment across local strategies (local policies, processes, funding, delivery) |
| DUSE | outcome_short |  | Better use of data at a strategic level, enabling a better response to multiple disadvantage |
| DUND | outcome_short |  | Increased understanding of the impact of multiple disadvantage on demand and the effects of the Changing Futures programme on this |
| LEC | outcome_long |  | Lived experience involvement embedded and guiding commissioning |
| COCO | outcome_long |  | Co-commissioning, pooled budgets and KPIs joined across services |
| N1 | outcome_long | G_NEW | Outcomes-driven commissioning to appropriately reflect the needs of the cohort |
| N2 | outcome_long | G_NEW | Commissioners buy services that work flexibly around individuals rather than within service or activity boundaries |
| EID | outcome_long |  | Early identification of people at risk |
| JOIN | impact |  | Joined-up system aligned to respond to and prevent multiple disadvantage |
| STRUCT | impact |  | The structures, knowledge, skills and expertise needed to meet the needs of the cohort are recognised and strived for |

## Edges

`status`: evidence judgement shown in the source. `confidence`: our confidence in the transcription of the arrow.

| # | From | To | Dir | Status | Assumptions on link | Confidence | Note |
|---|---|---|---|---|---|---|---|
| 1 | REL | PATHW | ↔ | progressing |  | high |  |
| 2 | REL | ALIGN | → | progressing |  | high |  |
| 3 | FOR | ALIGN | → | progressing |  | high |  |
| 4 | RES | LEAD | → | progressing |  | high |  |
| 5 | LEAD | ALIGN | → | progressing |  | high |  |
| 6 | LEAD | LOC | → | progressing |  | high |  |
| 7 | LOC | G_DATA | → | insufficient |  | high |  |
| 8 | G_DATA | DUSE | → | insufficient |  | high |  |
| 9 | G_DATA | DUND | → | insufficient |  | high |  |
| 10 | DUSE | G_NEW | → | insufficient |  | high |  |
| 11 | DUND | G_NEW | → | insufficient |  | high |  |
| 12 | DUSE | EID | → | insufficient |  | medium | two dashed lines leave DUSE; one ends at EID |
| 13 | LEG | LEC | → | progressing |  | high |  |
| 14 | LEC | G_NEW | → | insufficient |  | high |  |
| 15 | ALIGN | COCO | → | insufficient |  | high |  |
| 16 | GOVJ | COCO | → | insufficient |  | high | system map version of GOVJ is worded 'including funded frontline work and governance (multiagency structures)' |
| 17 | COCO | JOIN | → | insufficient |  | high |  |
| 18 | G_NEW | JOIN | → | insufficient |  | high |  |
| 19 | WF | STRUCT | → | insufficient |  | high |  |
| 20 | STRUCT | G_OPS | → | insufficient |  | medium | dashed return arrow; forms a loop with the two-way WF<->G_OPS link |
| 21 | WF | G_OPS | ↔ | insufficient |  | high |  |
| 22 | JOIN | SVC_FLEX | → | progressing |  | high |  |
| 23 | G_OPS | G_STAFF | → | insufficient |  | high |  |
| 24 | G_STAFF | SVC_FLEX | → | insufficient |  | high |  |
| 25 | SVC_CAP | ST3 | → | insufficient |  | high |  |
| 26 | SVC_FLEX | SVC_CAP | ↔ | insufficient |  | high |  |
| 27 | GOVJ | SVC_CAP | → | insufficient |  | high | second instance of GOVJ box at bottom of map |
| 28 | EXIST | SVC_CAP | → | not_leading |  | high |  |

## Context factors

- Accountability ceiling: vertical dotted line marking the threshold of what the programme can directly influence

## Machine-readable

```json
{
 "case": "cf_system",
 "title": "Changing Futures: system-level theory of change",
 "nodes": [
  {
   "id": "OPS1",
   "layer": "activity",
   "group": "G_OPS",
   "label": "Programme activity influences service priorities and targets, putting in place agreements and clear escalation routes"
  },
  {
   "id": "OPS2",
   "layer": "activity",
   "group": "G_OPS",
   "label": "Programme works to improve services based on local priorities, including housing, substance misuse and other health services"
  },
  {
   "id": "OPS3",
   "layer": "activity",
   "group": "G_OPS",
   "label": "Programme produces evidence about levers/enablers to improve individual, service and system outcomes"
  },
  {
   "id": "OPS4",
   "layer": "activity",
   "group": "G_OPS",
   "label": "Training and awareness-raising activity promoting trauma-informed approaches to other services"
  },
  {
   "id": "OPS5",
   "layer": "activity",
   "group": "G_OPS",
   "label": "Programme engages services needed to meet the needs of the cohort, including services not working in a trauma-informed way"
  },
  {
   "id": "ST1",
   "layer": "outcome_short",
   "group": "G_STAFF",
   "label": "Wider system staff have the capabilities and motivation for trauma-informed working"
  },
  {
   "id": "ST2",
   "layer": "impact",
   "group": "G_STAFF",
   "label": "Wider service system staff have access to support, feel valued, and have reduced burnout across services"
  },
  {
   "id": "ST3",
   "layer": "impact",
   "group": "G_STAFF",
   "label": "Wider system service conditions (flexibility, autonomy) and capacity enable staff to respond to multiple disadvantage"
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
  },
  {
   "id": "GOVJ",
   "layer": "activity",
   "group": null,
   "label": "Government supports areas to join up different programmes, including frontline caseworker and multidisciplinary team activity and multiagency governance structures"
  },
  {
   "id": "EXIST",
   "layer": "context",
   "group": null,
   "label": "Existing interventions and conditions supporting increased service capacity"
  },
  {
   "id": "REL",
   "layer": "activity",
   "group": null,
   "label": "Programme staff build relationships with other services and participate in multiagency meetings"
  },
  {
   "id": "FOR",
   "layer": "activity",
   "group": null,
   "label": "Strategic multiagency forums are established (by programme or others) and work effectively"
  },
  {
   "id": "RES",
   "layer": "activity",
   "group": null,
   "label": "Programme resources strategic roles with the right skills and position to advocate on multiple disadvantage"
  },
  {
   "id": "LEAD",
   "layer": "activity",
   "group": null,
   "label": "Skilled strategic Changing Futures leadership communicates evidence of what works to existing strategy owners and fora"
  },
  {
   "id": "LOC",
   "layer": "activity",
   "group": null,
   "label": "Local leadership (e.g. local strategic leaders, commissioners) are engaged by the programme"
  },
  {
   "id": "DA1",
   "layer": "activity",
   "group": "G_DATA",
   "label": "Changing Futures areas identify existing data that enables better responses to multiple disadvantage"
  },
  {
   "id": "DA2",
   "layer": "activity",
   "group": "G_DATA",
   "label": "Changing Futures influences data owners to increase the availability and awareness of data relating to multiple disadvantage"
  },
  {
   "id": "LEG",
   "layer": "activity",
   "group": null,
   "label": "Lived experience groups and activity (co-design and delivery)"
  },
  {
   "id": "WF",
   "layer": "activity",
   "group": null,
   "label": "Strategic workforce activity focused on multiple disadvantage"
  },
  {
   "id": "PATHW",
   "layer": "outcome_short",
   "group": null,
   "label": "Clear cross-service referral pathways"
  },
  {
   "id": "ALIGN",
   "layer": "outcome_short",
   "group": null,
   "label": "Strategic alignment across local strategies (local policies, processes, funding, delivery)"
  },
  {
   "id": "DUSE",
   "layer": "outcome_short",
   "group": null,
   "label": "Better use of data at a strategic level, enabling a better response to multiple disadvantage"
  },
  {
   "id": "DUND",
   "layer": "outcome_short",
   "group": null,
   "label": "Increased understanding of the impact of multiple disadvantage on demand and the effects of the Changing Futures programme on this"
  },
  {
   "id": "LEC",
   "layer": "outcome_long",
   "group": null,
   "label": "Lived experience involvement embedded and guiding commissioning"
  },
  {
   "id": "COCO",
   "layer": "outcome_long",
   "group": null,
   "label": "Co-commissioning, pooled budgets and KPIs joined across services"
  },
  {
   "id": "N1",
   "layer": "outcome_long",
   "group": "G_NEW",
   "label": "Outcomes-driven commissioning to appropriately reflect the needs of the cohort"
  },
  {
   "id": "N2",
   "layer": "outcome_long",
   "group": "G_NEW",
   "label": "Commissioners buy services that work flexibly around individuals rather than within service or activity boundaries"
  },
  {
   "id": "EID",
   "layer": "outcome_long",
   "group": null,
   "label": "Early identification of people at risk"
  },
  {
   "id": "JOIN",
   "layer": "impact",
   "group": null,
   "label": "Joined-up system aligned to respond to and prevent multiple disadvantage"
  },
  {
   "id": "STRUCT",
   "layer": "impact",
   "group": null,
   "label": "The structures, knowledge, skills and expertise needed to meet the needs of the cohort are recognised and strived for"
  }
 ],
 "groups": [
  {
   "id": "G_OPS",
   "layer": "activity",
   "label": "Operational and strategic activity supporting service improvement"
  },
  {
   "id": "G_STAFF",
   "layer": "impact",
   "label": "Changes in staff capabilities, motivations, and working conditions"
  },
  {
   "id": "G_DATA",
   "layer": "activity",
   "label": "(unlabelled container) Data activity"
  },
  {
   "id": "G_NEW",
   "layer": "outcome_long",
   "label": "New services or service specifications"
  }
 ],
 "edges": [
  {
   "source": "REL",
   "target": "PATHW",
   "bidirectional": true,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "REL",
   "target": "ALIGN",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "FOR",
   "target": "ALIGN",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "RES",
   "target": "LEAD",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "LEAD",
   "target": "ALIGN",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "LEAD",
   "target": "LOC",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "LOC",
   "target": "G_DATA",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_DATA",
   "target": "DUSE",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_DATA",
   "target": "DUND",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "DUSE",
   "target": "G_NEW",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "DUND",
   "target": "G_NEW",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "DUSE",
   "target": "EID",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "medium"
  },
  {
   "source": "LEG",
   "target": "LEC",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "LEC",
   "target": "G_NEW",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "ALIGN",
   "target": "COCO",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "GOVJ",
   "target": "COCO",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "COCO",
   "target": "JOIN",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_NEW",
   "target": "JOIN",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "WF",
   "target": "STRUCT",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "STRUCT",
   "target": "G_OPS",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "medium"
  },
  {
   "source": "WF",
   "target": "G_OPS",
   "bidirectional": true,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "JOIN",
   "target": "SVC_FLEX",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_OPS",
   "target": "G_STAFF",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_STAFF",
   "target": "SVC_FLEX",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "SVC_CAP",
   "target": "ST3",
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
   "source": "GOVJ",
   "target": "SVC_CAP",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "EXIST",
   "target": "SVC_CAP",
   "bidirectional": false,
   "status": "not_leading",
   "assumptions": [],
   "confidence": "high"
  }
 ],
 "assumptions": [],
 "shape": {
  "n_nodes": 32,
  "n_groups": 4,
  "n_edges": 28,
  "n_bidirectional": 3,
  "n_group_level_edges": 11,
  "nodes_by_layer": {
   "context": 1,
   "activity": 15,
   "outcome_short": 5,
   "outcome_long": 5,
   "impact": 6
  },
  "edges_by_status": {
   "progressing": 8,
   "insufficient": 19,
   "not_leading": 1
  },
  "edges_with_assumptions": 0,
  "n_assumptions": 0,
  "n_feedback_loops": 0,
  "longest_directed_path": [
   "RES",
   "LEAD",
   "LOC",
   "G_DATA",
   "DUSE",
   "G_NEW",
   "JOIN",
   "SVC_FLEX"
  ],
  "longest_path_len": 8,
  "orphan_nodes": []
 }
}
```
