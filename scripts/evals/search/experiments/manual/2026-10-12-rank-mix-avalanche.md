# Pool orderings: How are avalanche criticality and edge-of-chaos criticality related in neural networks, conceptually, mathematically and empirically?

Run 2026-10-12T14:06:44+00:00. Depth `rapid`, cap 100. Pool 591 papers (573 distinct papers) from 23 query calls. No ground truth; this compares orderings of one pool.

## Where the probe papers rank

| paper | baseline | reserve | hits | rrf | blend | mix_c | mix_q | mix_f1 | mix |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Avalanche and edge-of-chaos criticality do not necessarily co-occur in | 104 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| Neuronal Avalanches in Neocortical Circuits | 1 | 51 | 72 | 75 | 3 | 2 | 2 | 2 | 2 |
| Being Critical of Criticality in the Brain | 39 | 87 | 48 | 45 | 28 | 46 | 103 | 106 | 73 |
| Avalanches and edge-of-chaos learning in neuromorphic nanowire network | 389 | 7 | 57 | 54 | 113 | 102 | 42 | 33 | 60 |
| Neuronal Avalanches Imply Maximum Dynamic Range in Cortical Networks a | 18 | 66 | 213 | 213 | 52 | 35 | 35 | 35 | 35 |

A number at or under 100 means the paper survives the cut at this scope.

## What the top 100 looks like

| ordering | overlap with baseline | median_year | share_from_2020 | median_cited_by | share_two_plus_queries | share_no_query | origins |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline | 100 | 2018.0 | 0.36 | 29.5 | 0.17 | 0.69 | {'semantic': 17, 'generated': 9, 'snowball_backward': 30, 'snowball_forward': 44} |
| reserve | 59 | 2018.5 | 0.49 | 11.0 | 0.3 | 0.37 | {'generated': 45, 'variant_sr': 4, 'semantic': 12, 'snowball_backward': 19, 'snowball_forward': 20} |
| hits | 31 | 2017.0 | 0.35 | 8.5 | 0.71 | 0.0 | {'generated': 26, 'semantic': 61, 'variant_sr': 4, 'snowball_forward': 8, 'snowball_backward': 1} |
| rrf | 23 | 2017.0 | 0.36 | 5.0 | 0.71 | 0.0 | {'generated': 34, 'semantic': 61, 'variant_sr': 4, 'snowball_forward': 1} |
| blend | 64 | 2016.0 | 0.28 | 14.0 | 0.5 | 0.35 | {'generated': 15, 'semantic': 47, 'snowball_backward': 19, 'snowball_forward': 19} |
| mix_c | 71 | 2017.0 | 0.33 | 32.0 | 0.32 | 0.56 | {'generated': 14, 'semantic': 27, 'snowball_backward': 28, 'snowball_forward': 31} |
| mix_q | 42 | 2016.0 | 0.33 | 16.5 | 0.6 | 0.28 | {'generated': 25, 'semantic': 44, 'snowball_backward': 28, 'variant_sr': 2, 'snowball_forward': 1} |
| mix_f1 | 46 | 2016.0 | 0.33 | 16.5 | 0.6 | 0.28 | {'generated': 22, 'semantic': 47, 'snowball_backward': 28, 'variant_sr': 2, 'snowball_forward': 1} |
| mix | 62 | 2016.0 | 0.33 | 33.5 | 0.48 | 0.44 | {'generated': 15, 'semantic': 39, 'snowball_backward': 28, 'snowball_forward': 17, 'variant_sr': 1} |

## Top 15 under `baseline`

1. 2003 · Neuronal Avalanches in Neocortical Circuits · cited 2304 · queries 1 · inset 72 · wcoup 2.585 · spec 21.698 · semantic
2. 2007 · Dynamical synapses causing self-organized criticality in neural networks · cited 546 · queries 4 · inset 44 · wcoup 11.36 · spec 16.757 · semantic
3. 2005 · Critical Branching Captures Activity in Living Neural Networks and Maximizes the Number of Metastable States · cited 478 · queries 1 · inset 35 · wcoup 10.097 · spec 13.763 · semantic
4. 2021 · Criticality and sampling in neural networks · cited 1 · queries 2 · inset 0 · wcoup 50.966 · spec 13.444 · generated
5. 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · cited 506 · queries 3 · inset 35 · wcoup 5.17 · spec 13.271 · generated
6. 2006 · Optimal dynamical range of excitable networks at criticality · cited 838 · queries 0 · inset 38 · wcoup 0.0 · spec 12.976 · snowball_backward
7. 2023 · Spreading Processes in Complex Networks of Cultured Neurons and Society · cited 0 · queries 0 · inset 0 · wcoup 41.567 · spec 12.0 · snowball_forward
8. 2020 · Mechanisms of self-organized quasicriticality in neuronal networks models · cited 3 · queries 0 · inset 0 · wcoup 44.281 · spec 11.67 · snowball_forward
9. 2009 · Spontaneous cortical activity in awake monkeys composed of neuronal avalanches · cited 576 · queries 0 · inset 32 · wcoup 0.0 · spec 11.561 · snowball_backward
10. 2020 · Mechanisms of Self-Organized Quasicriticality in Neuronal Network Models · cited 31 · queries 0 · inset 3 · wcoup 49.188 · spec 11.161 · snowball_forward
11. 2010 · Neuronal Avalanches in Spontaneous Activity In Vivo · cited 207 · queries 0 · inset 26 · wcoup 0.0 · spec 11.128 · snowball_backward
12. 2004 · Neuronal Avalanches Are Diverse and Precise Activity Patterns That Are Stable for Many Hours in Cortical Slice Cultures · cited 587 · queries 0 · inset 30 · wcoup 0.0 · spec 10.807 · snowball_backward
13. 2011 · Information Capacity and Transmission Are Maximized in Balanced Cortical Networks with Neuronal Avalanches · cited 604 · queries 0 · inset 30 · wcoup 0.0 · spec 10.76 · snowball_backward
14. 2022 · Neuronal Avalanches · cited 1 · queries 0 · inset 0 · wcoup 31.973 · spec 9.603 · snowball_forward
15. 2002 · Finite-size effects of avalanche dynamics · cited 118 · queries 0 · inset 20 · wcoup 0.0 · spec 9.491 · snowball_backward

## Top 15 under `reserve`

1. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · queries 9 · inset 3 · wcoup 30.005 · spec 5.413 · generated
2. 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · cited 506 · queries 3 · inset 35 · wcoup 5.17 · spec 13.271 · generated
3. 2004 · At the Edge of Chaos: Real-time Computations and Self-Organized Criticality in Recurrent Neural Networks · cited 59 · queries 2 · inset 1 · wcoup 3.907 · spec 1.088 · generated
4. 2010 · Critical branching neural computation · cited 13 · queries 1 · inset 2 · wcoup 19.691 · spec 5.141 · generated
5. 2020 · CORR Insights®: Does Artificial Intelligence Outperform Natural Intelligence in Interpretation of Musculoskeletal Radiological Studies? A Systematic Review · cited 0 · queries 3 · inset 0 · wcoup 0 · spec 0.0 · variant_sr
6. 2024 · ACTIVATION FUNCTIONS IN NEURAL NETWORKS: OVERVIEW AND COMPARISON · cited 5 · queries 1 · inset 0 · wcoup 0 · spec 0.0 · generated
7. 2021 · Avalanches and edge-of-chaos learning in neuromorphic nanowire networks · cited 179 · queries 2 · inset 1 · wcoup 18.53 · spec 2.196 · generated
8. 2010 · Self-organization without conservation: are neuronal avalanches generically critical? · cited 96 · queries 6 · inset 9 · wcoup 24.183 · spec 6.913 · generated
9. 2022 · Managing Self-organized Criticality in Neural Networks on the Edge of Stability and Chaos · cited 0 · queries 2 · inset 0 · wcoup 0 · spec 0.0 · generated
10. 2026 · Sovereign Cybernetic Architectures: An Exhaustive Analysis of CollectiveOS, Fixed-Time Convergence Control, and Topological LLM Hijacking · cited 0 · queries 1 · inset 0 · wcoup 0 · spec 0.0 · generated
11. 2004 · Data mining in health and medical information · cited 29 · queries 2 · inset 0 · wcoup 0 · spec 0.0 · variant_sr
12. 2022 · Artificial Neural Networks for COVID-19 Forecasting in Mexico: An Empirical Study · cited 0 · queries 1 · inset 0 · wcoup 0 · spec 0.0 · generated
13. 2016 · Neural avalanches at the edge-of-chaos? · cited 0 · queries 9 · inset 0 · wcoup 11.36 · spec 2.0 · generated
14. 2017 · Biological modelling of a computational spiking neural network with neuronal avalanches · cited 15 · queries 1 · inset 3 · wcoup 22.633 · spec 5.723 · generated
15. 2022 · A toy model for brain criticality: self-organized excitation/inhibition ratio and the role of network clustering · cited 0 · queries 2 · inset 0 · wcoup 0 · spec 0.0 · generated

## Top 15 under `hits`

1. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · queries 9 · inset 3 · wcoup 30.005 · spec 5.413 · generated
2. 2016 · Neural avalanches at the edge-of-chaos? · cited 0 · queries 9 · inset 0 · wcoup 11.36 · spec 2.0 · generated
3. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 0 · queries 8 · inset 0 · wcoup 0 · spec 0.0 · semantic
4. 2016 · Is cortical criticality unique? · cited 0 · queries 7 · inset 0 · wcoup 26.545 · spec 5.0 · generated
5. 2014 · Criticality in Neural Systems · cited 192 · queries 7 · inset 8 · wcoup 0 · spec 3.47 · semantic
6. 2016 · Neuronal avalanches in complex networks · cited 9 · queries 6 · inset 1 · wcoup 35.359 · spec 7.038 · generated
7. 2010 · Self-organization without conservation: are neuronal avalanches generically critical? · cited 96 · queries 6 · inset 9 · wcoup 24.183 · spec 6.913 · generated
8. 2013 · Criticality and avalanches in neural networks · cited 50 · queries 6 · inset 2 · wcoup 22.96 · spec 3.937 · semantic
9. 2024 · A general description of criticality in neural network models · cited 2 · queries 6 · inset 0 · wcoup 18.852 · spec 3.707 · semantic
10. 2014 · Self‐Organized Criticality in Neural Network Models · cited 5 · queries 6 · inset 0 · wcoup 20.758 · spec 3.401 · semantic
11. 2014 · Identification of Criticality in Neuronal Avalanches: II. A Theoretical and Empirical Investigation of the Driven Case · cited 13 · queries 6 · inset 0 · wcoup 17.852 · spec 2.937 · generated
12. 2016 · Journal of Mathematical Neuroscience (2013) 3:5 DOI 10.1186/2190-8567-3-5 RESEARCH Open Access Identification of Criticality in Neuronal Avalanches: I. A Theoretical Investigation · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
13. 2023 · A General Description of Criticality in Neural Network Models · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
14. 2018 · Criticality hypothesis in the brain: from neutral theory to self-organisation and synchronisation · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
15. 2016 · Criticality in neural networks: a study of the interplay between experimental tools and theoretical models · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic

## Top 15 under `rrf`

1. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · queries 9 · inset 3 · wcoup 30.005 · spec 5.413 · generated
2. 2016 · Neural avalanches at the edge-of-chaos? · cited 0 · queries 9 · inset 0 · wcoup 11.36 · spec 2.0 · generated
3. 2014 · Criticality in Neural Systems · cited 192 · queries 7 · inset 8 · wcoup 0 · spec 3.47 · semantic
4. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 0 · queries 8 · inset 0 · wcoup 0 · spec 0.0 · semantic
5. 2010 · Self-organization without conservation: are neuronal avalanches generically critical? · cited 96 · queries 6 · inset 9 · wcoup 24.183 · spec 6.913 · generated
6. 2016 · Is cortical criticality unique? · cited 0 · queries 7 · inset 0 · wcoup 26.545 · spec 5.0 · generated
7. 2013 · Criticality and avalanches in neural networks · cited 50 · queries 6 · inset 2 · wcoup 22.96 · spec 3.937 · semantic
8. 2014 · Identification of Criticality in Neuronal Avalanches: II. A Theoretical and Empirical Investigation of the Driven Case · cited 13 · queries 6 · inset 0 · wcoup 17.852 · spec 2.937 · generated
9. 2016 · Neuronal avalanches in complex networks · cited 9 · queries 6 · inset 1 · wcoup 35.359 · spec 7.038 · generated
10. 2014 · Self‐Organized Criticality in Neural Network Models · cited 5 · queries 6 · inset 0 · wcoup 20.758 · spec 3.401 · semantic
11. 2006 · Criticality of avalanche dynamics in adaptive recurrent networks · cited 24 · queries 5 · inset 6 · wcoup 6.19 · spec 4.571 · semantic
12. 2016 · Journal of Mathematical Neuroscience (2013) 3:5 DOI 10.1186/2190-8567-3-5 RESEARCH Open Access Identification of Criticality in Neuronal Avalanches: I. A Theoretical Investigation · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
13. 2021 · Self-organized criticality in neural networks from activity-based rewiring · cited 19 · queries 5 · inset 2 · wcoup 36.728 · spec 7.522 · semantic
14. 2009 · Scaling properties of neuronal avalanches are consistent with critical dynamics · cited 18 · queries 5 · inset 1 · wcoup 8.775 · spec 2.073 · semantic
15. 2024 · A general description of criticality in neural network models · cited 2 · queries 6 · inset 0 · wcoup 18.852 · spec 3.707 · semantic

## Top 15 under `blend`

1. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · queries 9 · inset 3 · wcoup 30.005 · spec 5.413 · generated
2. 2007 · Dynamical synapses causing self-organized criticality in neural networks · cited 546 · queries 4 · inset 44 · wcoup 11.36 · spec 16.757 · semantic
3. 2003 · Neuronal Avalanches in Neocortical Circuits · cited 2304 · queries 1 · inset 72 · wcoup 2.585 · spec 21.698 · semantic
4. 2010 · Self-organization without conservation: are neuronal avalanches generically critical? · cited 96 · queries 6 · inset 9 · wcoup 24.183 · spec 6.913 · generated
5. 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · cited 506 · queries 3 · inset 35 · wcoup 5.17 · spec 13.271 · generated
6. 2014 · Criticality in Neural Systems · cited 192 · queries 7 · inset 8 · wcoup 0 · spec 3.47 · semantic
7. 2016 · Neural avalanches at the edge-of-chaos? · cited 0 · queries 9 · inset 0 · wcoup 11.36 · spec 2.0 · generated
8. 2016 · Neuronal avalanches in complex networks · cited 9 · queries 6 · inset 1 · wcoup 35.359 · spec 7.038 · generated
9. 2016 · Is cortical criticality unique? · cited 0 · queries 7 · inset 0 · wcoup 26.545 · spec 5.0 · generated
10. 2021 · Self-organized criticality in neural networks from activity-based rewiring · cited 19 · queries 5 · inset 2 · wcoup 36.728 · spec 7.522 · semantic
11. 2013 · Criticality and avalanches in neural networks · cited 50 · queries 6 · inset 2 · wcoup 22.96 · spec 3.937 · semantic
12. 2021 · Criticality and sampling in neural networks · cited 1 · queries 2 · inset 0 · wcoup 50.966 · spec 13.444 · generated
13. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 0 · queries 8 · inset 0 · wcoup 0 · spec 0.0 · semantic
14. 2005 · Critical Branching Captures Activity in Living Neural Networks and Maximizes the Number of Metastable States · cited 478 · queries 1 · inset 35 · wcoup 10.097 · spec 13.763 · semantic
15. 2006 · Criticality of avalanche dynamics in adaptive recurrent networks · cited 24 · queries 5 · inset 6 · wcoup 6.19 · spec 4.571 · semantic

## Top 15 under `mix_c`

1. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · queries 9 · inset 3 · wcoup 30.005 · spec 5.413 · generated
2. 2003 · Neuronal Avalanches in Neocortical Circuits · cited 2304 · queries 1 · inset 72 · wcoup 2.585 · spec 21.698 · semantic
3. 2021 · Self-organized criticality in neural networks from activity-based rewiring · cited 19 · queries 5 · inset 2 · wcoup 36.728 · spec 7.522 · semantic
4. 2016 · Neuronal avalanches in complex networks · cited 9 · queries 6 · inset 1 · wcoup 35.359 · spec 7.038 · generated
5. 2007 · Dynamical synapses causing self-organized criticality in neural networks · cited 546 · queries 4 · inset 44 · wcoup 11.36 · spec 16.757 · semantic
6. 2021 · Criticality, Connectivity, and Neural Disorder: A Multifaceted Approach to Neural Computation · cited 60 · queries 3 · inset 0 · wcoup 48.211 · spec 7.046 · semantic
7. 2016 · Is cortical criticality unique? · cited 0 · queries 7 · inset 0 · wcoup 26.545 · spec 5.0 · generated
8. 2006 · Optimal dynamical range of excitable networks at criticality · cited 838 · queries 0 · inset 38 · wcoup 0.0 · spec 12.976 · snowball_backward
9. 2021 · Criticality and sampling in neural networks · cited 1 · queries 2 · inset 0 · wcoup 50.966 · spec 13.444 · generated
10. 2010 · Self-organization without conservation: are neuronal avalanches generically critical? · cited 96 · queries 6 · inset 9 · wcoup 24.183 · spec 6.913 · generated
11. 1987 · Self-organized criticality: An explanation of the 1/ f noise · cited 7644 · queries 0 · inset 35 · wcoup 0.0 · spec 9.012 · snowball_backward
12. 2020 · Avalanche size distribution of an integrate-and-fire neural model on complex networks · cited 11 · queries 5 · inset 0 · wcoup 24.928 · spec 5.294 · semantic
13. 2013 · Criticality and avalanches in neural networks · cited 50 · queries 6 · inset 2 · wcoup 22.96 · spec 3.937 · semantic
14. 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · cited 506 · queries 3 · inset 35 · wcoup 5.17 · spec 13.271 · generated
15. 2021 · Self-Organization Toward Criticality by Synaptic Plasticity · cited 76 · queries 0 · inset 1 · wcoup 49.205 · spec 9.305 · snowball_forward

## Top 15 under `mix_q`

1. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · queries 9 · inset 3 · wcoup 30.005 · spec 5.413 · generated
2. 2003 · Neuronal Avalanches in Neocortical Circuits · cited 2304 · queries 1 · inset 72 · wcoup 2.585 · spec 21.698 · semantic
3. 2021 · Self-organized criticality in neural networks from activity-based rewiring · cited 19 · queries 5 · inset 2 · wcoup 36.728 · spec 7.522 · semantic
4. 2016 · Neural avalanches at the edge-of-chaos? · cited 0 · queries 9 · inset 0 · wcoup 11.36 · spec 2.0 · generated
5. 2007 · Dynamical synapses causing self-organized criticality in neural networks · cited 546 · queries 4 · inset 44 · wcoup 11.36 · spec 16.757 · semantic
6. 2024 · A general description of criticality in neural network models · cited 2 · queries 6 · inset 0 · wcoup 18.852 · spec 3.707 · semantic
7. 2014 · Criticality in Neural Systems · cited 192 · queries 7 · inset 8 · wcoup 0 · spec 3.47 · semantic
8. 2006 · Optimal dynamical range of excitable networks at criticality · cited 838 · queries 0 · inset 38 · wcoup 0.0 · spec 12.976 · snowball_backward
9. 2020 · Avalanche size distribution of an integrate-and-fire neural model on complex networks · cited 11 · queries 5 · inset 0 · wcoup 24.928 · spec 5.294 · semantic
10. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 0 · queries 8 · inset 0 · wcoup 0 · spec 0.0 · semantic
11. 1987 · Self-organized criticality: An explanation of the 1/ f noise · cited 7644 · queries 0 · inset 35 · wcoup 0.0 · spec 9.012 · snowball_backward
12. 2023 · A General Description of Criticality in Neural Network Models · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
13. 2010 · Self-organization without conservation: are neuronal avalanches generically critical? · cited 96 · queries 6 · inset 9 · wcoup 24.183 · spec 6.913 · generated
14. 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · cited 506 · queries 3 · inset 35 · wcoup 5.17 · spec 13.271 · generated
15. 2025 · How balance, chaos and Criticality jointly shape computation in neural networks · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · semantic

## Top 15 under `mix_f1`

1. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · queries 9 · inset 3 · wcoup 30.005 · spec 5.413 · generated
2. 2003 · Neuronal Avalanches in Neocortical Circuits · cited 2304 · queries 1 · inset 72 · wcoup 2.585 · spec 21.698 · semantic
3. 2021 · Self-organized criticality in neural networks from activity-based rewiring · cited 19 · queries 5 · inset 2 · wcoup 36.728 · spec 7.522 · semantic
4. 2016 · Neural avalanches at the edge-of-chaos? · cited 0 · queries 9 · inset 0 · wcoup 11.36 · spec 2.0 · generated
5. 2007 · Dynamical synapses causing self-organized criticality in neural networks · cited 546 · queries 4 · inset 44 · wcoup 11.36 · spec 16.757 · semantic
6. 2020 · Avalanche size distribution of an integrate-and-fire neural model on complex networks · cited 11 · queries 5 · inset 0 · wcoup 24.928 · spec 5.294 · semantic
7. 2014 · Criticality in Neural Systems · cited 192 · queries 7 · inset 8 · wcoup 0 · spec 3.47 · semantic
8. 2006 · Optimal dynamical range of excitable networks at criticality · cited 838 · queries 0 · inset 38 · wcoup 0.0 · spec 12.976 · snowball_backward
9. 2024 · A general description of criticality in neural network models · cited 2 · queries 6 · inset 0 · wcoup 18.852 · spec 3.707 · semantic
10. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 0 · queries 8 · inset 0 · wcoup 0 · spec 0.0 · semantic
11. 1987 · Self-organized criticality: An explanation of the 1/ f noise · cited 7644 · queries 0 · inset 35 · wcoup 0.0 · spec 9.012 · snowball_backward
12. 2023 · A General Description of Criticality in Neural Network Models · cited 0 · queries 6 · inset 0 · wcoup 0 · spec 0.0 · semantic
13. 2010 · Self-organization without conservation: are neuronal avalanches generically critical? · cited 96 · queries 6 · inset 9 · wcoup 24.183 · spec 6.913 · generated
14. 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · cited 506 · queries 3 · inset 35 · wcoup 5.17 · spec 13.271 · generated
15. 2025 · How balance, chaos and Criticality jointly shape computation in neural networks · cited 0 · queries 5 · inset 0 · wcoup 0 · spec 0.0 · semantic

## Top 15 under `mix`

1. 2017 · Avalanche and edge-of-chaos criticality do not necessarily co-occur in neural networks · cited 36 · queries 9 · inset 3 · wcoup 30.005 · spec 5.413 · generated
2. 2003 · Neuronal Avalanches in Neocortical Circuits · cited 2304 · queries 1 · inset 72 · wcoup 2.585 · spec 21.698 · semantic
3. 2021 · Self-organized criticality in neural networks from activity-based rewiring · cited 19 · queries 5 · inset 2 · wcoup 36.728 · spec 7.522 · semantic
4. 2016 · Neural avalanches at the edge-of-chaos? · cited 0 · queries 9 · inset 0 · wcoup 11.36 · spec 2.0 · generated
5. 2007 · Dynamical synapses causing self-organized criticality in neural networks · cited 546 · queries 4 · inset 44 · wcoup 11.36 · spec 16.757 · semantic
6. 2020 · Avalanche size distribution of an integrate-and-fire neural model on complex networks · cited 11 · queries 5 · inset 0 · wcoup 24.928 · spec 5.294 · semantic
7. 2016 · Neuronal avalanches in complex networks · cited 9 · queries 6 · inset 1 · wcoup 35.359 · spec 7.038 · generated
8. 2006 · Optimal dynamical range of excitable networks at criticality · cited 838 · queries 0 · inset 38 · wcoup 0.0 · spec 12.976 · snowball_backward
9. 2021 · Criticality, Connectivity, and Neural Disorder: A Multifaceted Approach to Neural Computation · cited 60 · queries 3 · inset 0 · wcoup 48.211 · spec 7.046 · semantic
10. 2016 · Is cortical criticality unique? · cited 0 · queries 7 · inset 0 · wcoup 26.545 · spec 5.0 · generated
11. 1987 · Self-organized criticality: An explanation of the 1/ f noise · cited 7644 · queries 0 · inset 35 · wcoup 0.0 · spec 9.012 · snowball_backward
12. 2024 · A general description of criticality in neural network models · cited 2 · queries 6 · inset 0 · wcoup 18.852 · spec 3.707 · semantic
13. 2010 · Self-organization without conservation: are neuronal avalanches generically critical? · cited 96 · queries 6 · inset 9 · wcoup 24.183 · spec 6.913 · generated
14. 2012 · Universal Critical Dynamics in High Resolution Neuronal Avalanche Data · cited 506 · queries 3 · inset 35 · wcoup 5.17 · spec 13.271 · generated
15. 2021 · Criticality and sampling in neural networks · cited 1 · queries 2 · inset 0 · wcoup 50.966 · spec 13.444 · generated
