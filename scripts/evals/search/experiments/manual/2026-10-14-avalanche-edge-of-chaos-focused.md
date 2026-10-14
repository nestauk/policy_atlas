# Manual check: 2026-10-14-avalanche-edge-of-chaos-focused

Run 2026-10-14T14:29:36+00:00. Question: "What is relationship between avalanche criticality and edge of chaos". Depth `rapid`, caps {'papers_cap': 100, 'policy_cap': 50, 'call_budget': {'openalex': 45, 'overton': 30}}. No geography filter, no screening criteria. Rolled back, nothing kept in the database. Raw data: `2026-10-14-avalanche-edge-of-chaos-focused.json` (no abstracts stored).

## Numbers

| | value |
|---|---:|
| search wall clock | 43 s |
| screening wall clock | 45 s |
| provider calls | OpenAlex 35, Overton 18 |
| records returned | OpenAlex 2133, Overton 417 |
| duplicate paper copies dropped | 11 |
| kept at the cap | papers 100, policy 50 |
| screened relevant | papers 99 of 100, policy 13 of 50 |
| query generation tokens | 813 |
| failed provider calls | 1 |

## How the kept documents were found and screened

| backend | found by | relevant | not relevant |
|---|---|---:|---:|
| openalex | generated | 13 | 1 |
| openalex | semantic | 26 | 0 |
| openalex | snowball_backward | 30 | 0 |
| openalex | snowball_forward | 30 | 0 |
| overton | landmark | 1 | 14 |
| overton | paraphrase | 10 | 19 |
| overton | verbatim | 2 | 4 |

## Probe papers

| paper | pool rank | kept | screen |
|---|---:|---|---|
| Avalanche and edge-of-chaos criticality do not necessarily co-occur | 4 | yes | relevant (0.99) |
| Neuronal Avalanches in Neocortical Circuits | 8 | yes | relevant (0.92) |
| Being Critical of Criticality in the Brain | — | no | not returned by any call |

## Generated queries

- `openalex` search: "(avalanche criticality edge of chaos) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "(avalanche criticality edge of chaos) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 0
- `openalex` search: "avalanche criticality edge of chaos" → 39
- `openalex` search: "self-organized criticality avalanche dynamics chaos transition" → 8
- `openalex` search: "(self-organized criticality avalanche dynamics chaos transition) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 0
- `openalex` search: "(self-organized criticality avalanche dynamics chaos transition) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "(avalanche size distributions criticality complex systems) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "(avalanche size distributions criticality complex systems) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 1
- `openalex` search: "critical branching avalanches edge-of-chaos dynamics" → 0
- `openalex` search: "(critical branching avalanches edge-of-chaos dynamics) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "(neural avalanches criticality chaotic dynamics) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 0
- `openalex` search: "(critical branching avalanches edge-of-chaos dynamics) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 0
- `openalex` search: "neural avalanches criticality chaotic dynamics" → 12
- `openalex` search: "(neural avalanches criticality chaotic dynamics) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "avalanche size distributions criticality complex systems" → 96
- `overton` search: "What is relationship between avalanche criticality and edge of chaos" → 134
- `openalex` search_semantic: "Examine how avalanche criticality, including critical avalanche dynamics and scaling behavior, relates to systems operating at the edge of chaos." → 47
- `openalex` search_semantic: "Investigate whether avalanche-like cascades and self-organized critical behavior are associated with, caused by, or indicative of edge-of-chaos regimes in complex systems." → 49
- `overton` search: "Examine how avalanche criticality, including critical avalanche dynamics and scaling behavior, relates to systems operating at the edge of chaos." → 134
- `openalex` search_semantic: "critical branching avalanches edge-of-chaos dynamics" → 46
- `openalex` search_semantic: "What is relationship between avalanche criticality and edge of chaos" → 47
- `overton` search: "Investigate whether avalanche-like cascades and self-organized critical behavior are associated with, caused by, or indicative of edge-of-chaos regimes in complex systems." → 134
- `openalex` search_semantic: "avalanche criticality edge of chaos" → 47
- `openalex` search_semantic: "self-organized criticality avalanche dynamics chaos transition" → 49
- `openalex` search_semantic: "neural avalanches criticality chaotic dynamics" → 49
- `openalex` search_semantic: "avalanche size distributions criticality complex systems" → 0 (error: search transport error host=api.openalex.org status_code=429)

## Papers kept as relevant (top 25 by confidence)

- 1994 · Anomalous approach to the self-organized critical state in a model for ‘‘life at the edge of chaos’’ · 99% · found by generated · pool rank 1
- 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · 99% · found by generated · pool rank 4
- 2021 · Avalanches and edge-of-chaos learning in neuromorphic nanowire networks · 99% · found by generated · pool rank 6
- 2016 · Neural avalanches at the edge-of-chaos? · 99% · found by generated · pool rank 10
- 2022 · A toy model for brain criticality: self-organized excitation/inhibition ratio and the role of network clustering · 99% · found by generated · pool rank 21
- 1990 · Is the world at the border of chaos? · 99% · found by semantic · pool rank 25
- 2020 · Feedback Mechanisms for Self-Organization to the Edge of a Phase Transition · 99% · found by snowball_forward · pool rank 58
- 2021 · Self-organized criticality in neural networks from activity-based rewiring · 98% · found by generated · pool rank 3
- 1994 · Avalanches in the weakly driven Frenkel-Kontorova model · 98% · found by generated · pool rank 22
- 2021 · Integrating Various Neural Features Based on Mechanism of Intricate Balance and Ongoing Activity: Unified Neural Account Underlying and Correspondent to Mental Phenomena · 98% · found by generated · pool rank 33
- 2009 · Spontaneous cortical activity in awake monkeys composed of neuronal avalanches · 98% · found by snowball_backward · pool rank 44
- 2016 · Neuronal avalanches in complex networks · 98% · found by generated · pool rank 46
- 2005 · Critical Branching Captures Activity in Living Neural Networks and Maximizes the Number of Metastable States · 97% · found by snowball_backward · pool rank 23
- 2016 · Identification of Criticality in Neuronal Avalanches: II. A Theoretical and Empirical Investigation of the Driven · 97% · found by semantic · pool rank 31
- 2009 · Scaling properties of neuronal avalanches are consistent with critical dynamics · 97% · found by generated · pool rank 37
- 2009 · Neuronal Avalanches Imply Maximum Dynamic Range in Cortical Networks at Criticality · 97% · found by snowball_backward · pool rank 50
- 2022 · Sandpile Models · 97% · found by snowball_forward · pool rank 93
- 2025 · Transitions in the dynamics of recurrent neural networks · 97% · found by generated · pool rank 96
- 2002 · Multiscale dynamics and robust critical scaling in a continuum current sheet model · 96% · found by semantic · pool rank 19
- 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · 96% · found by semantic · pool rank 38
- 2013 · Shocks Generate Crossover Behavior in Lattice Avalanches · 96% · found by semantic · pool rank 43
- 2014 · Critical Dynamics in Complex Networks · 96% · found by semantic · pool rank 91
- 2021 · Criticality, Connectivity, and Neural Disorder: A Multifaceted Approach to Neural Computation · 94% · found by snowball_forward · pool rank 18
- 2011 · Information Capacity and Transmission Are Maximized in Balanced Cortical Networks with Neuronal Avalanches · 94% · found by snowball_backward · pool rank 35
- 1997 · How Nature Works: The Science of Self-Organized Criticality · 94% · found by snowball_backward · pool rank 56

## Papers screened out

- 2025 · Harnessing the Second Power of Anesthesia for Disorders of Consciousness: 2025 T. H. Seldon Memorial Lecture · found by generated · not_relevant · The document concerns anesthesia, neural consciousness markers, and disorders of consciousness, with no apparent discussion of avalanche criticality or the edge of chaos.

## Policy documents kept as relevant

- 2003 · Loss of Stability and Emergence of Chaos in Dynamical Systems · 82% · found by verbatim
- 2015 · Research Note No. 8 (2) · 78% · found by paraphrase
- 1987 · Research Briefings, 1987 · 77% · found by paraphrase
- 1983 · Simple Models, Catastrophes and Cycles · 74% · found by paraphrase
- 2005 · Multi-type Branching Processes and Adaptive Dynamics of Structured Populations · 72% · found by paraphrase
- 1990 · Impact of Mathematics: Nonlinear Mathematics, Chaos, and Fractals in Science: Proceedings of a Symposium · 68% · found by paraphrase
- 2016 · [THIS TITLE IS BROKEN AND HAS BEEN REMOVED] · 68% · found by paraphrase
- 2013 · Chaos Forgets and Remembers: Measuring Information Creation, Destruction, and Storage · 68% · found by paraphrase
- 2009 · From Complex Networks to Time Series Analysis and Viceversa: Application to Metabolic Networks · 66% · found by paraphrase
- 2002 · Bifurcation Analysis of a Prey-Predator Coevolution Model · 62% · found by paraphrase
- 1975 · How Likely are Catastrophes? Natura Non Facit Saltus · 62% · found by verbatim
- 2024 · Complex Systems – Benefit or Burden? TA Preliminary Study · 62% · found by paraphrase
- 1996 · Delayed Maturation in Temporally Structured Populations with Non-Equilibrium Dynamics · 50% · found by landmark
