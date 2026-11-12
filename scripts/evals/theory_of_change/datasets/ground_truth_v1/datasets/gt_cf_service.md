# Ground truth: Changing Futures: service-level theory of change

- **Case ID:** `cf_service`
- **Level:** programme, service level (2 of 3 linked maps)
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
| Nodes | 21 |
| Containers (groups) | 3 |
| Nodes by layer | context: 1, activity: 9, outcome_short: 5, outcome_long: 2, impact: 4 |
| Edges (as drawn) | 16 |
| of which bidirectional | 2 |
| of which group-level (to/from a container) | 6 |
| Edges by evidence status | insufficient: 6, progressing: 9, not_leading: 1 |
| Edges carrying located assumptions | 0 |
| Assumptions / risks listed | 0 |
| Feedback loops (directed cycles, containers contracted, two-way links excluded) | 0 |
| Longest causal chain (units, containers contracted) | 5 |
| Unconnected nodes | none |

Longest chain (containers contracted): `REC` → `MAF` → `KNOW` → `REF` → `SVC_FLEX`


## Containers

| ID | Layer | Label | Members |
|---|---|---|---|
| G_OPS | activity | Operational and strategic activity supporting service improvement | OPS1, OPS2, OPS3, OPS4, OPS5 |
| G_STAFF | impact | Changes in staff capabilities, motivations, and working conditions | ST1, ST2, ST3 |
| G_DEMO | outcome_short | (unlabelled container) Changing Futures project outcomes | D1, D2 |

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
| REC | activity |  | Recruitment of specialist keyworkers/staff with low caseloads, the right skills and knowledge, and personal budgets/resources |
| D1 | outcome_short | G_DEMO | Changing Futures projects demonstrate different ways of working, including reduced staff burnout |
| D2 | outcome_short | G_DEMO | Flexible, responsive, additional support for people experiencing multiple disadvantage |
| MAF | activity |  | Participation in operational-level multiagency forums and/or colocation of services |
| KNOW | outcome_short |  | Staff have the appropriate knowledge of, and contacts across, the system |
| REF | outcome_long |  | Improved facilitation of referrals and joint case working across services; service coordination |
| LER | activity |  | Creation of lived experience roles or teams; connection of existing lived experience and involvement groups to share learning and collaborate |
| LEP | outcome_short |  | Improved processes for recruiting and supporting people with lived experience to co-design and deliver services |
| LEE | outcome_long |  | Lived experience co-design and delivery is embedded |

## Edges

`status`: evidence judgement shown in the source. `confidence`: our confidence in the transcription of the arrow.

| # | From | To | Dir | Status | Assumptions on link | Confidence | Note |
|---|---|---|---|---|---|---|---|
| 1 | G_OPS | G_STAFF | → | insufficient |  | high |  |
| 2 | REC | G_DEMO | → | progressing |  | high |  |
| 3 | G_DEMO | G_STAFF | → | insufficient |  | high |  |
| 4 | G_DEMO | SVC_FLEX | → | progressing |  | high |  |
| 5 | REC | MAF | → | progressing |  | high |  |
| 6 | MAF | KNOW | → | progressing |  | high |  |
| 7 | KNOW | REF | → | progressing |  | high |  |
| 8 | REF | SVC_FLEX | → | progressing |  | high |  |
| 9 | LER | LEP | → | progressing |  | high |  |
| 10 | LEP | LEE | → | progressing |  | high |  |
| 11 | LEE | SVC_FLEX | → | progressing |  | high |  |
| 12 | SVC_FLEX | G_STAFF | ↔ | insufficient |  | high |  |
| 13 | SVC_CAP | G_STAFF | → | insufficient |  | high |  |
| 14 | SVC_FLEX | SVC_CAP | ↔ | insufficient |  | high |  |
| 15 | GOVJ | SVC_CAP | → | insufficient |  | high |  |
| 16 | EXIST | SVC_CAP | → | not_leading |  | high |  |

## Context factors

- Accountability ceiling: vertical dotted line marking the threshold of what the programme can directly influence

## Machine-readable

```json
{
 "case": "cf_service",
 "title": "Changing Futures: service-level theory of change",
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
   "id": "REC",
   "layer": "activity",
   "group": null,
   "label": "Recruitment of specialist keyworkers/staff with low caseloads, the right skills and knowledge, and personal budgets/resources"
  },
  {
   "id": "D1",
   "layer": "outcome_short",
   "group": "G_DEMO",
   "label": "Changing Futures projects demonstrate different ways of working, including reduced staff burnout"
  },
  {
   "id": "D2",
   "layer": "outcome_short",
   "group": "G_DEMO",
   "label": "Flexible, responsive, additional support for people experiencing multiple disadvantage"
  },
  {
   "id": "MAF",
   "layer": "activity",
   "group": null,
   "label": "Participation in operational-level multiagency forums and/or colocation of services"
  },
  {
   "id": "KNOW",
   "layer": "outcome_short",
   "group": null,
   "label": "Staff have the appropriate knowledge of, and contacts across, the system"
  },
  {
   "id": "REF",
   "layer": "outcome_long",
   "group": null,
   "label": "Improved facilitation of referrals and joint case working across services; service coordination"
  },
  {
   "id": "LER",
   "layer": "activity",
   "group": null,
   "label": "Creation of lived experience roles or teams; connection of existing lived experience and involvement groups to share learning and collaborate"
  },
  {
   "id": "LEP",
   "layer": "outcome_short",
   "group": null,
   "label": "Improved processes for recruiting and supporting people with lived experience to co-design and deliver services"
  },
  {
   "id": "LEE",
   "layer": "outcome_long",
   "group": null,
   "label": "Lived experience co-design and delivery is embedded"
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
   "id": "G_DEMO",
   "layer": "outcome_short",
   "label": "(unlabelled container) Changing Futures project outcomes"
  }
 ],
 "edges": [
  {
   "source": "G_OPS",
   "target": "G_STAFF",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "REC",
   "target": "G_DEMO",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_DEMO",
   "target": "G_STAFF",
   "bidirectional": false,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "G_DEMO",
   "target": "SVC_FLEX",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "REC",
   "target": "MAF",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "MAF",
   "target": "KNOW",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "KNOW",
   "target": "REF",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "REF",
   "target": "SVC_FLEX",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "LER",
   "target": "LEP",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "LEP",
   "target": "LEE",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "LEE",
   "target": "SVC_FLEX",
   "bidirectional": false,
   "status": "progressing",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "SVC_FLEX",
   "target": "G_STAFF",
   "bidirectional": true,
   "status": "insufficient",
   "assumptions": [],
   "confidence": "high"
  },
  {
   "source": "SVC_CAP",
   "target": "G_STAFF",
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
  "n_nodes": 21,
  "n_groups": 3,
  "n_edges": 16,
  "n_bidirectional": 2,
  "n_group_level_edges": 6,
  "nodes_by_layer": {
   "context": 1,
   "activity": 9,
   "outcome_short": 5,
   "outcome_long": 2,
   "impact": 4
  },
  "edges_by_status": {
   "insufficient": 6,
   "progressing": 9,
   "not_leading": 1
  },
  "edges_with_assumptions": 0,
  "n_assumptions": 0,
  "n_feedback_loops": 0,
  "longest_directed_path": [
   "REC",
   "MAF",
   "KNOW",
   "REF",
   "SVC_FLEX"
  ],
  "longest_path_len": 5,
  "orphan_nodes": []
 }
}
```
