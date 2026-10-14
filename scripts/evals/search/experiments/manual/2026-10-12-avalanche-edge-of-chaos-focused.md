# Manual check: avalanche criticality and edge of chaos (Focused)

Run 2026-10-12T11:31:28+00:00. Question: "What is relationship between avalanche criticality and edge of chaos". Depth `rapid`, caps {'papers_cap': 100, 'policy_cap': 50, 'call_budget': {'openalex': 45, 'overton': 30}}. No geography filter, no screening criteria. Rolled back, nothing kept in the database. Raw data: `2026-10-12-avalanche-edge-of-chaos-focused.json` (no abstracts stored).

## Numbers

| | value |
|---|---:|
| search wall clock | 44 s |
| screening wall clock | 36 s |
| provider calls | OpenAlex 35, Overton 18 |
| records returned | OpenAlex 2331, Overton 417 |
| kept at the cap | papers 100, policy 50 |
| screened relevant | papers 99 of 100, policy 23 of 50 |
| query generation tokens | 817 |

## How the kept documents were found and screened

| backend | found by | relevant | not relevant |
|---|---|---:|---:|
| openalex | generated | 1 | 0 |
| openalex | semantic | 7 | 0 |
| openalex | snowball_backward | 23 | 0 |
| openalex | snowball_forward | 68 | 1 |
| overton | landmark | 2 | 13 |
| overton | paraphrase | 18 | 5 |
| overton | verbatim | 3 | 9 |

## Generated queries

- `openalex` search: "(avalanche criticality AND edge of chaos) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "(avalanche criticality AND edge of chaos) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 1
- `openalex` search: "(self-organized criticality AND edge-of-chaos dynamics) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 0
- `openalex` search: "avalanche criticality AND edge of chaos" → 39
- `openalex` search: "(self-organized criticality AND edge-of-chaos dynamics) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "self-organized criticality AND edge-of-chaos dynamics" → 51
- `openalex` search: "(neuronal avalanches AND criticality AND chaos) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 0
- `openalex` search: "neuronal avalanches AND criticality AND chaos" → 8
- `openalex` search: "(neuronal avalanches AND criticality AND chaos) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "(avalanche dynamics AND critical state AND transition to chaos) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 0
- `openalex` search: "(avalanche dynamics AND critical state AND transition to chaos) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "avalanche dynamics AND critical state AND transition to chaos" → 11
- `openalex` search: "(critical phenomena AND complexity AND edge of chaos) AND ("systematic review" OR "meta-analysis" OR "narrative synthesis")" → 0
- `openalex` search: "(critical phenomena AND complexity AND edge of chaos) AND ("randomized controlled trial" OR "randomised controlled trial" OR "randomized control trial" OR "randomised control trial")" → 0
- `openalex` search: "critical phenomena AND complexity AND edge of chaos" → 36
- `overton` search: "What is relationship between avalanche criticality and edge of chaos" → 134
- `openalex` search_semantic: "What is relationship between avalanche criticality and edge of chaos" → 50
- `openalex` search_semantic: "Examine how avalanche criticality relates to the edge-of-chaos regime in complex systems, including whether critical avalanche behavior signals or produces a transition between ordered and chaotic dynamics." → 50
- `openalex` search_semantic: "avalanche criticality AND edge of chaos" → 50
- `openalex` search_semantic: "self-organized criticality AND edge-of-chaos dynamics" → 50
- `openalex` search_semantic: "neuronal avalanches AND criticality AND chaos" → 50
- `openalex` search_semantic: "avalanche dynamics AND critical state AND transition to chaos" → 50
- `overton` search: "Examine how avalanche criticality relates to the edge-of-chaos regime in complex systems, including whether critical avalanche behavior signals or produces a transition between ordered and chaotic dynamics." → 134
- `openalex` search_semantic: "Assess the connection between avalanche-like cascades at criticality and systems operating near the boundary between stability and chaos, focusing on shared mechanisms and measurable indicators." → 50
- `openalex` search_semantic: "critical phenomena AND complexity AND edge of chaos" → 50
- `overton` search: "Assess the connection between avalanche-like cascades at criticality and systems operating near the boundary between stability and chaos, focusing on shared mechanisms and measurable indicators." → 134

## Papers kept as relevant (top 25 by confidence)

- 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · 99% · found by generated
- 2021 · Single-cell Networks Reorganise to Facilitate Whole-brain Supercritical Dynamics During Epileptic Seizures · cited 5 · 98% · found by snowball_forward
- 2009 · Neuronal Avalanches Imply Maximum Dynamic Range in Cortical Networks at Criticality · cited 626 · 98% · found by snowball_backward
- 2020 · Feedback Mechanisms for Self-Organization to the Edge of a Phase Transition · cited 64 · 98% · found by snowball_forward
- 2021 · Self-organized criticality in neural networks from activity-based rewiring · cited 20 · 98% · found by snowball_forward
- 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · cited 506 · 96% · found by semantic
- 2021 · Criticality, Connectivity, and Neural Disorder: A Multifaceted Approach to Neural Computation · cited 60 · 96% · found by snowball_forward
- 2012 · Being Critical of Criticality in the Brain · cited 502 · 96% · found by snowball_backward
- 2009 · Spontaneous cortical activity in awake monkeys composed of neuronal avalanches · cited 576 · 96% · found by snowball_backward
- 2005 · Critical Branching Captures Activity in Living Neural Networks and Maximizes the Number of Metastable States · cited 478 · 95% · found by snowball_backward
- 2010 · Neuronal Avalanches in Spontaneous Activity In Vivo · cited 207 · 94% · found by snowball_backward
- 2020 · Punctuated equilibrium as the default mode of evolution of large populations on fitness landscapes dominated by saddle points in the weak-mutation limit · cited 3 · 94% · found by snowball_forward
- 2013 · Identification of Criticality in Neuronal Avalanches: I. A Theoretical Investigation of the Non-driven Case · cited 24 · 94% · found by semantic
- 1999 · Self-organized criticality · cited 616 · 93% · found by snowball_forward
- 2022 · Critical brain wave physics of neuronal avalanches without sandpiles of self organized criticality · cited 0 · 93% · found by snowball_forward
- 2017 · Criticality predicts maximum irregularity in recurrent networks of excitatory nodes · cited 7 · 93% · found by snowball_forward
- 2017 · Neuronal avalanches: Where temporal complexity and criticality meet · cited 6 · 93% · found by semantic
- 2009 · Subsampling effects in neuronal avalanche distributions recorded in vivo · cited 143 · 93% · found by snowball_backward
- 1997 · How Nature Works: The Science of Self-Organized Criticality · cited 2721 · 93% · found by snowball_backward
- 2022 · Theoretical foundations of studying criticality in the brain · cited 42 · 93% · found by snowball_forward
- 1995 · Self-Organized Branching Processes: Mean-Field Theory for Avalanches · cited 306 · 92% · found by snowball_backward
- 2006 · Self-organized Criticality in an Earthquake Model on Random Network · cited 1 · 91% · found by snowball_forward
- 1998 · Self-Organized Criticality · cited 1135 · 91% · found by snowball_backward
- 2003 · Neuronal Avalanches in Neocortical Circuits · cited 2328 · 91% · found by snowball_backward
- 1998 · Self-organized criticality in deterministic systems with disorder · cited 7 · 91% · found by snowball_forward

## Papers screened out

- 2022 · A Unified Genomic Mechanism of Cell-Fate Change · not_relevant · The title concerns a genomic mechanism of cell-fate change and does not address avalanche criticality or the edge of chaos.

## Policy documents (Overton)

- 2015 · Research Note No. 8 (2) · État de Vaud · relevant 82% · found by paraphrase · The report addresses chaos, bifurcations, Lyapunov exponents, and nonlinear dynamics, which could provide indirect evidence about edge-of-ch
- 2003 · Loss of Stability and Emergence of Chaos in Dynamical Systems · Institutet för Näringslivsforskning · relevant 80% · found by paraphrase · Discusses stability loss, bifurcations, chaos emergence, and Feigenbaum universality, which could inform the relationship between critical t
- 2006 · Mathematical Models of Catastrophes. Control of Catastrophic Processes · IIASA · relevant 78% · found by paraphrase · Its treatment of catastrophes, bifurcations, singularities, and abrupt transitions could inform relationships between avalanche criticality 
- 1990 · Impact of Mathematics: Nonlinear Mathematics, Chaos, and Fractals in Science: Proceedings of a Symposium · National Academies of Sciences, Engineering, and Medicine · relevant 78% · found by paraphrase · The symposium concerns nonlinear mathematics and chaos, which could provide indirect conceptual evidence about edge-of-chaos dynamics, thoug
- 1991 · Bifurcations and Chaos in a Periodic Predator-Prey Model · IIASA · relevant 74% · found by paraphrase · Although it does not address avalanches explicitly, its analysis of bifurcations and routes to chaos could inform understanding of chaos ons
- 1987 · Research Briefings, 1987 · National Academies of Sciences, Engineering, and Medicine · relevant 74% · found by paraphrase · The report addresses chaos and nonlinear phenomena broadly, which could provide indirect conceptual context for avalanche criticality and th
- 2003 · Stochastic Behaviour of Deterministic Systems · Institutet för Näringslivsforskning · relevant 74% · found by paraphrase · Discusses chaotic dynamics, parameter dependence, complexity, and Lyapunov exponents, which could inform the edge-of-chaos aspect, though av
- 2017 · The Origins of Computational Mechanics: A Brief Intellectual History and Several Clarifications · Santa Fe Institute · relevant 72% · found by paraphrase · The document addresses chaotic dynamics, complex systems, and emergent organization, which could provide indirect context for relating avala
- 2016 · the influence of the fractal properties of the information space on the process of generating a random signal with signs of accident · Government of Ukraine · relevant 72% · found by paraphrase · The document addresses fractal properties and chaotic or emergency-like random signals, which could indirectly inform relationships between 
- 2016 · entropy scale for evaluating the result of measurements · Government of Ukraine · relevant 72% · found by paraphrase · It addresses nonlinear systems, transitions into chaos, entropy, and dynamic criticality-related measurement concepts, which may indirectly 
- 2023 · Natural Hazard Process Fact Sheet · Government of Switzerland · relevant 70% · found by verbatim · Although primarily a descriptive avalanche fact sheet, it discusses critical snowpack conditions and triggering processes that could provide
- 2016 · [THIS TITLE IS BROKEN AND HAS BEEN REMOVED] · Helsingin kaupunki · relevant 70% · found by paraphrase · The report concerns nonlinear chaotic dynamics and stability, which could inform the edge-of-chaos aspect, though avalanche criticality is n
- 2014 · Asperities · State of North Carolina · relevant 68% · found by verbatim · The document discusses earthquake fault-rupture dynamics, which can provide indirect evidence about avalanche-like criticality, though it do
- 2009 · From Complex Networks to Time Series Analysis and Viceversa: Application to Metabolic Networks · Joint Research Centre · relevant 67% · found by paraphrase · The paper concerns chaotic dynamics and network robustness, which may indirectly inform edge-of-chaos behavior, although avalanche criticali
- 2013 · Chaos Forgets and Remembers: Measuring Information Creation, Destruction, and Storage · Santa Fe Institute · relevant 66% · found by paraphrase · It addresses chaos in dynamical systems and information dynamics, which could indirectly inform edge-of-chaos concepts, although avalanche c
- 2007 · Stochastic dynamics: Fundamentals and applications (STOCHDYN) · European Science Foundation · relevant 63% · found by paraphrase · Although it does not explicitly mention avalanches or the edge of chaos, its treatment of nonlinear stochastic systems, critical transitions
- 1975 · Stable Manifolds and Separatrices · IIASA · relevant 62% · found by paraphrase · Discusses dynamical-system resilience, attractor basins, separatrices, and parameter changes, which could indirectly inform transitions and 
- 2016 · model for measuring parameters of nonlinear dynamic systems · Government of Ukraine · relevant 58% · found by paraphrase · It addresses dynamic chaos and nonlinear systems using fractal analysis, which may offer indirect context for edge-of-chaos concepts, though
- 2012 · Invitation to the seminar · Government of the Czech Republic · relevant 50% · found by paraphrase · The seminar concerns general chaos theory, Lyapunov exponents, and fractals, but the envelope does not indicate coverage of avalanche critic
- 1975 · How Likely are Catastrophes? Natura Non Facit Saltus · IIASA · relevant 50% · found by verbatim · The document discusses catastrophe likelihood in general dynamical models but does not specify avalanches, criticality, or the edge of chaos
- 1996 · Delayed Maturation in Temporally Structured Populations with Non-Equilibrium Dynamics · IIASA · relevant 36% · found by landmark · The paper studies non-equilibrium population dynamics with cyclic and chaotic attractors, offering indirect evidence relevant to understandi
- 2017 · A Physics-Based Approach to Unsupervised Discovery of Coherent Structures in Spatiotemporal Systems · Santa Fe Institute · relevant 28% · found by paraphrase · The document focuses on causal-state discovery of coherent structures, including cellular automata, but does not clearly address avalanche c
- 1999 · Games on Grids · IIASA · relevant 28% · found by landmark · The document concerns complex adaptive systems and spatial evolutionary games, but the envelope does not clearly address avalanche criticali
- 2002 · Super- and Coinfection: The Two Extremes · IIASA · not_relevant 99% · found by landmark · The paper concerns superinfection, coinfection, and pathogen virulence, with no apparent focus on avalanche criticality or the edge of chaos
- 1999 · Ecology and Adaptation of Stunted Growth in Fish [Updated August 2000] · IIASA · not_relevant 99% · found by landmark · The document concerns fish growth, population ecology, and life-history adaptation, with no apparent subject matter involving avalanche crit
- 2019 · Watch out for avalanches! 2019-2020 · Generalitat de Catalunya · not_relevant 99% · found by verbatim · This document concerns snow avalanche types, warning systems, and skiing safety, not avalanche criticality or its relationship to the edge o
- 2000 · Evolution of Dispersal in Metapopulations with Local Density Dependence and Demographic Stochasticity · IIASA · not_relevant 99% · found by landmark · The document concerns evolution of dispersal in stochastic metapopulations and does not address avalanche criticality or the edge of chaos.
- 2000 · The Evolutionary Dynamics of Direct Phenotypic Overdominance: Emergence Possible, Loss Probable · IIASA · not_relevant 98% · found by landmark · The document concerns evolutionary genetics, genotype–phenotype dominance, and population ecology, with no apparent focus on avalanche criti
- 2017 · General Directorate of Combating Desertification and Erosion · Government of Turkey · not_relevant 98% · found by verbatim · The document concerns physical snow avalanches and hazard mitigation, with no discussion of criticality, complex systems, or the edge of cha
- 1998 · The Efficiency of Adapting Aspiration Levels · IIASA · not_relevant 98% · found by landmark · The document concerns aspiration-level adaptation and efficiency in repeated games, with no apparent focus on avalanche criticality or the e
- 2011 · Consequences and recommendations · Generalitat de Catalunya · not_relevant 98% · found by verbatim · The document concerns practical mountain-snow avalanche risk and safety recommendations, not avalanche criticality or its relationship to th
- 2018 · 3.4 Risk Assessment : Avalanche · State of Idaho · not_relevant 98% · found by verbatim · The document concerns physical snow-avalanche hazards and risk assessment, with no discussion of avalanche criticality or the edge of chaos.
- 2000 · Evolutionary Suicide and Evolution of Dispersal in Structured Metapopulations · IIASA · not_relevant 98% · found by landmark · The document concerns evolutionary dispersal, metapopulation viability, and extinction, with no apparent discussion of avalanche criticality
- 1998 · Best Response Adaptation for Role Games · IIASA · not_relevant 98% · found by landmark · The document concerns best-response dynamics and Nash equilibria in role-based games, with no apparent subject matter on avalanche criticali
- 2004 · The Dynamics of Public Goods · IIASA · not_relevant 98% · found by paraphrase · The document concerns evolutionary game dynamics and cooperation in public goods games, with no apparent focus on avalanche criticality or t
- 2012 · Assessment of secondary avalanches in cases of artificial avalanche triggering · Government of Switzerland · not_relevant 98% · found by verbatim · The document concerns operational risk assessment for secondary snow avalanches after artificial triggering, not avalanche criticality or it
- 1999 · Evolutionary Branching and Coexistence of Germination Strategies · IIASA · not_relevant 98% · found by landmark · The document concerns evolutionary branching and coexistence of plant germination strategies, with no apparent discussion of avalanche criti
- 2002 · The Evolution of Self-Fertilization in Density-Regulated Populations · IIASA · not_relevant 97% · found by landmark · The document concerns evolution of self-fertilization under demographic and chaotic population dynamics, with no apparent focus on avalanche
- 2016 · Avalanches - fact sheet · Government of Switzerland · not_relevant 97% · found by verbatim · The document concerns natural snow avalanches, their formation, impacts, and mitigation, with no apparent discussion of criticality or the e
- 2003 · Evolutionary Game Dynamics · IIASA · not_relevant 96% · found by landmark · The document surveys evolutionary game dynamics and equilibria, with no apparent discussion of avalanche criticality or the edge of chaos.
- 2002 · Ecological Bistability and Evolutionary Reversals under Asymmetrical Competition · IIASA · not_relevant 96% · found by landmark · The document concerns ecological bistability and evolutionary reversals in population dynamics, with no apparent focus on avalanche critical
- 2012 · Assessment of secondary avalanches in the case of artificial avalanche triggering · Government of Switzerland · not_relevant 96% · found by verbatim · The document concerns practical triggering and risk assessment of snow avalanches, with no apparent discussion of avalanche criticality or t
- 2023 · Dangerous Processes Fact Sheet · Government of Switzerland · not_relevant 96% · found by verbatim · The fact sheet describes snow avalanche types, formation, and hazard management but contains no discussion of criticality, self-organized cr
- 2003 · Metapopulation-Level Adaptation of Insect Host plant Preference and Extinction-Colonization Dynamics in Heterogenous Landscapes · IIASA · not_relevant 96% · found by paraphrase · The document concerns butterfly host-plant preference and metapopulation extinction-colonization dynamics, with no apparent focus on avalanc
- 2016 · Not All Fluctuations are Created Equal: Spontaneous Variations in Thermodynamic Function · Santa Fe Institute · not_relevant 95% · found by paraphrase · The document concerns thermodynamic fluctuations and information-processing Maxwellian demons, with no apparent discussion of avalanche crit
- 1965 · Avalanche Conference: 1965 : transcript · National Academies of Sciences, Engineering, and Medicine · not_relevant 94% · found by verbatim · The document concerns snow avalanches triggered by the 1965 Alaska earthquake, not avalanche criticality or its relationship to the edge of 
- 1998 · Complex Adaptive Systems and the Evolution of Reciprocation · IIASA · not_relevant 94% · found by landmark · The document concerns reciprocal altruism and cooperation in complex adaptive systems, with no apparent focus on avalanche criticality or th
- 1999 · Wave Patterns in Spatial Games and the Evolution of Cooperation · IIASA · not_relevant 91% · found by landmark · The document focuses on spatial evolutionary games and cooperation, with no apparent discussion of avalanche criticality or the edge of chao
- 2017 · Spectral Simplicity of Apparent Complexity, Part II: Exact Complexities and Complexity Spectra · Santa Fe Institute · not_relevant 90% · found by paraphrase · The document concerns information-theoretic complexity spectra and hidden dynamics, with no apparent treatment of avalanches, criticality, o
- 2006 · Synchronization and Peak-to-Peak Dynamics in Networks of Low-Dimensional Chaotic Oscillators · IIASA · not_relevant 87% · found by paraphrase · The paper concerns synchronization and collective dynamics in coupled chaotic oscillators, without addressing avalanche criticality or the e
