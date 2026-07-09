# External validation — LLM search/research-agent research + practice (2026-07-09)

The 014 rev-1.2 precedent applied to 015's search design: three parallel
streams at the user's direction — (1) a deep-reasoner survey of the
**published research literature** (iterative retrieval, SR search
automation, stopping, snowballing, grounding), (2) a deep-reasoner survey
of **shipped-system engineering practice** (Undermind, PaperQA2,
OpenScholar, Asta, Elicit, Consensus, the general deep-research agents,
OSS frameworks, benchmarks), and (3) a **/last30days field scan** (raw
file `~/Documents/Last30Days/deep-research-agents-literature-search-raw-v3.md`).
Lead adjudication folded into contract rev 3.10.

## Adjudication summary

| Finding (streams) | Call |
|---|---|
| **Screen-as-loop-judge unification is convergent practice AND the measured bottleneck** — PaperQA2's one relevance score ranks + seeds traversal + gates stopping; Undermind's one classifier scores + drives convergence; MetaSyn (arXiv 2606.17041): 90.9% retrieval ceiling but ≤52.7% recovered — the failure stage is eligibility screening; SatIR's "is this actually possible?" framing | **Validated as designed** (rev 3's strongest call); citations recorded |
| **No shipped system uses a bandit for expansion allocation**; cold-start arithmetic kills it here (1–2 min wall-clock − 15–45 s/round screening ⇒ ~2–4 rounds = 2–4 pulls for a 3-arm bandit) | **ADOPTED: Thompson sampling CUT** — fixed round-robin/proportional allocation across the three arms; TS (sliding-window variant, for arm depletion) recorded as an eval-gated seam that must beat round-robin. Side benefit: the seeded-RNG test machinery drops out entirely |
| **Diminishing returns are measured**: ADORE (2606.13905) plateaus at round 2–3; reformulation *harms* after ~3–4 (2605.00560); CMU quality window 3–7 turns with context collapse past ~7 | **ADOPTED: round cap pinned at 3** (plan constant), aligned with the wall-clock arithmetic |
| **Positives-only exemplars drift** (PRF drift; "Jaguar→car"); ADORE's fix: graded exemplars incl. suppressed false-positive attractors, **grades anchored to the ORIGINAL query** | **ADOPTED: reformulation context = graded exemplars** — top confident-relevants AND a bounded set of high-confidence not_relevants (negative exemplars), all id-keyed, with the original intent record riding every reformulation prompt as the fixed anchor (never the evolving exemplar centroid). Screen's persisted rows already carry the grades — zero new judging |
| **Screener-as-reward self-reinforcement** (reward-hacking amplified in feedback loops; loop starves novel-vocabulary relevants the screener is least confident on) — the design's highest-severity un-named risk | **ADOPTED: diversity reserve** — a fixed fraction of each round's acquisition budget runs exploration NOT steered by screen results (fresh intent-derived queries); named in the contract's risk framing with the mitigation triple (fixed-intent anchoring · negative exemplars · reserve) |
| **Context accumulation re-creates the ceiling by round 3–4** (CMU) | **ADOPTED: reformulation context is strictly per-round, non-accumulating** (top-k this round; pinned in contract wording) |
| **Zero-shot boolean query generation is low-recall and validation is decisive**: SIGIR 2025 reproduction 0.26–0.58 vs 0.84 manual (earlier ~0.5 claims reproduce at ~0.15 best); skipping result-validation collapses recall to 0.08–0.15; multi-query OR-combining recovers 0.64–0.73; AutoBool (EACL 2026) needs RL to hit 0.70 | **ADOPTED: generated-query validation** — zero-result generated queries are counted and dropped; if ALL generated queries zero-out, fall back to the verbatim-intent query with an honest note. Multi-query fan-out re-validated as necessary-but-not-sufficient (deep escalation carries the recall load) |
| **Single NL query = single point of failure for the dense arm** (mirror of the boolean fragility) | **ADOPTED: Overton gets up to 2 generated NL paraphrases beside the verbatim intent** (same `search_queries_v1` call; 2 extra rate-limited calls) — rapid and deep |
| **Marginal-yield stopping is the naive baseline the SR field benchmarks against**; a raw per-round count is fragile to round-size variance; AstaBench: the documented failure mode is over-search (cost 2× for less) | **ADOPTED: `short_circuit` = discovery-RATE floor** (new confident-relevant per docs-evaluated), with marginal-yield the PRIMARY stop and budgets the backstop ("stop when it's not worth it, not only when we run out"). **SEAM: calibrated recall estimate** (Chao capture-recapture / Undermind's exponential-saturation fit f=1−e^(−n/τ), τ≈80 — ~150 papers→85%, 300→98%) → a user-facing "estimated % of relevant found" on the coverage record; eval-slice-gated product surface |
| **"Adequate" must never read as a recall guarantee** (SR convention: ≥95% recall floors; our verdict is a target-hit) | **ADOPTED (framing)**: contract discipline line — the coverage verdict is coverage-adequacy, never a completeness claim; downstream honesty machinery already carries it |
| **Suggestion grounding**: hallucination 3–20% (deep-research agents worse, 10.7% vs 4.8%); tool verification cuts bad refs 6.4–79×; title-lookup verifies existence not identity/relevance and can false-drop variants | **Validated + ADOPTED refinements**: prefer OpenAlex ID/DOI resolution over fuzzy title match where resolvable; grounded suggestions still screen (existence ≠ relevance — already true); **log grounded-but-screened-out rate** as the suggest-arm quality signal |
| **Snowballing is a complement, not a recall engine**: one-hop median 35.8% recall (27 reviews, OpenAlex/S2); framework/consensus articles are the best seeds; precision better than DB search | **Validated as designed** ("complement" was already the posture); seed-selection note (prefer central/high-confidence relevants) folded into decision 15 wording |
| **Token-bounded reformulation is universal practice** (LangChain briefs; PaperQA2 RCS 2,250→200–400 tokens; Undermind relevants-only); the R&D's 6-min driver is the documented context-pollution failure | **Validated as designed** (the user's rev-2 latency diagnosis is field-confirmed) |
| **1–2 min wall-clock sits between Asta-fast (30 s) and Asta-diligent (2–3 min)**, faster than every general agent (OpenAI DR 5–30 min, Gemini ≤60 min); the 2–4-round budget lands inside CMU's quality window | **Validated as designed**; the decision-11 requirement to measure in-loop screening latency separately is what determines round count |
| **3-rep consensus screen is a calibration asset** (BrowseComp: browsing agents 82–91% calibration error) BUT **mini-class judges have a comprehension threshold** (PaperQA2: small judge models can be net-negative) — the deep loop's single biggest un-eval'd dependency | **ADOPTED (framing + eval gate)**: consensus screen named as the calibration control; **mini-class judge quality = eval-slice must-measure** before "adequate" is trusted; joins the eval seam |
| **Eval metrics stance**: AstaBench cost-normalized estimated-recall+nDCG Pareto; MetaSyn stage-attributed metrics (retrieval vs screening failures diagnosed separately) | **SEAM (eval)**: joins the existing eval-reuse pointers |
| Structural strengths confirmed by contrast: curated backends dodge the SEO/content-farm source-quality collapse (Anthropic's postmortem); the fan-out has a real selector (screen) where parallel best-of-N without a selector is the benchmarked failure; per-call `search.executed` events answer the field's reproducibility criticism of Undermind | Recorded as validation, no action |
| PaSa (2501.10120): iterative paper-search agent with search+snowball loop and selector judge, +37.8%/+39.9% recall@20/50 over Google+GPT-4o | Recorded — the closest published analog to the whole DEEP design |

**Declined/deferred**: RCS-style abstract compression before screen (only if the plan shows screen tokens bind the wall-clock — seam) · best-of-N query selection (screen already selects; revisit only if instability survives the fan-out — seam) · adopting a target-recall stopping rule in-slice (needs the recall estimator; seam with the coverage-estimate entry).

---

## Stream 1 — published research literature (deep-reasoner; ✓ = opened and verified, listing-only = medium confidence)

[Condensed; full detail preserved in the agent transcript]

- **PaSa** (arXiv:2501.10120 ✓, ByteDance): iterative paper-search agent — search + read + reference-follow loop with a "selector" relevance judge; +37.8% recall@20 / +39.9% recall@50 vs Google+GPT-4o. Near-exact DEEP analog.
- **ADORE** (arXiv:2606.13905 ✓): feedback-informed retrieval — +24.5% nDCG@10 over BM25; gains land at round 2, **plateau by round 3** (TREC DL20: 0.480→0.648→0.706→flat); exemplars are **graded 0–3** (reinforce 3s, actively suppress 2–1 false-positive attractors); grading **anchored to the original query**.
- **Query drift** (arXiv:2605.00560 ✓): reformulation *hurts* after ~3–4 iterations.
- **Boolean-SR reassessment** (arXiv:2505.07155, SIGIR 2025 ✓): LLM boolean recall 0.26–0.58 vs 0.84 manual, high run variance; **omitting query validation → 0.08–0.15**; multi-query OR-combining → 0.64–0.73. AutoBool (arXiv:2602.00005/EACL 2026): RL-trained 0.70 avg recall vs 0.35 zero-shot.
- **Reward-hacking/self-reinforcement** (agentic-search RL survey 2510.16724; ReSeek 2510.00568; 2606.04923 — listing): "model-based rewards inevitably lead to reward hacking and bias," amplified in feedback loops; PRF drift is the mechanism; mitigations = fixed-anchor grading, negative exemplars, non-reward exploration.
- **Stopping** (Syst Rev 2024 DOI 10.1186/s13643-024-02699-7; Confidence-Based Stopping arXiv:2606.15380 ✓; Chao estimator 2404.01176 listing): good rules = target recall + calibrated confidence; marginal-yield/knee/target-count are the naive baselines; capture-recapture is the cheap statistical upgrade; marginal-yield alone yields no achieved-recall estimate — a credibility gap for evidence synthesis.
- **Snowballing** (Research Synthesis Methods 2025 ✓): 27 reviews, OpenAlex/S2 — median **35.8% one-hop recall**, 37% of reviews >50%; precision 2.6% vs 0.8% DB search; best seeds = framework/consensus articles.
- **Suggestion hallucination** (arXiv:2604.03173 ✓): reference hallucination 3–20%; deep-research agents 10.7% vs search-augmented 4.8%; callable-tool verification cuts bad refs **6.4–79×**. Title-lookup verifies existence, not identity — prefer ID/DOI resolution.
- **Bandits**: no direct retrieval-arm TS precedent; cold-start + non-stationary (depleting arms); sliding-window TS (2409.05181 listing) exists; round-robin/fixed schedules are the standard baselines.
- **Latency**: parallel tool calls ~36% cost / ~41% wall-clock reduction at ~3/turn (medium confidence); judge batching standard; token-bounded context standard. Per-index idiom: BM25 optimal ~32 tokens, dense ~64 (listing, medium confidence) — supports keyword-for-lexical/NL-for-dense.

## Stream 2 — engineering practice (deep-reasoner)

[Condensed; the system-by-system table preserved verbatim below]

| System | Loop | Judge | Expansion | Stopping / budgets | Latency |
|---|---|---|---|---|---|
| Undermind | search→classify→adapt→estimate | GPT-4 3-way, ~98% at extremes | citation trails + re-search from relevants | exponential convergence f=1−e^(−n/τ), τ≈80 | minutes |
| PaperQA2 | agentic RAG, 4 tools | RCS 0–10/chunk, top-k 30 | citation traversal fwd+back, seed ≥8 | "≥5 evidence or a few tries" | $1–3/query |
| OpenScholar | retrieve→generate→self-feedback | bi-encoder → cross-encoder | new query per unmet feedback | ≤3 iterations | — |
| Asta Paper Finder | intent-routed workflows | per-doc sub-criteria, 89% "perfect" | keyword→S2→citation tracking | enough-papers OR scanned-too-many; fast 30 s / diligent 2–3 min | 30 s–3 min |
| Consensus | single-shot funnel | hybrid → rerank 1,500 → top-20 | none | fixed funnel | ~sub-second |
| Elicit | staged PRISMA pipeline | per-paper screen + explanation | none | staged; 97%/99% screening recall | product-paced |
| Anthropic multi-agent | orchestrator-worker parallel | LLM rubric 0–1 | subagent-decided | effort-by-complexity (1/2–4/10+ agents) | −90% time via parallelism |
| OpenAI DR | RL-trained browse loop | learned | learned | model-internal | 5–30 min |
| Perplexity DR | successive rounds | hybrid + cross-encoder | reformulate per insight | no-new-insight | 2–4 min |
| Gemini DR | plan(approved)→execute | model-internal | learned | 60-min cap; ~80–160 queries | minutes, async |
| LangChain ODR | supervisor-worker | compression briefs | spawn on gaps | iterations 6 / concurrent 5 / tool-calls 10 | ~15× chat tokens |
| gpt-researcher/dzhng | recursive breadth×depth | "learnings" extraction | follow-ups per node | breadth 3–4, depth 2 | knob-scaled |
| STORM/Co-STORM | perspective conversation | grounded QA | perspective/mind-map expansion | turn budgets (12/20) | — |

Convergent patterns (we match): loop-not-single-shot · two-tier funnel · per-doc scored judging · threshold-seeded snowballing · 3–5 query fan-out · compressed reformulation context · hard budget stopping · effort-by-difficulty. Divergences: TS (nobody), 3-rep judge (heavier than practice — deliberate calibration/governance trade), no convergence model (Undermind's is strictly more principled — seam).

Benchmarks: AstaBench (2510.21652) — over-search is the failure mode; Pareto cost-normalized scoring. BrowseComp (2504.12516) — 82–91% calibration error. CMU test-time ceiling (2602.18998) — 3–7-turn peak, collapse past ~7–11. DeepResearcher (2504.03160) honesty behaviors. SR screening (JAMIA 32(5):893) — ≥95% recall convention.

## Stream 3 — /last30days field scan (30-day window)

- **MetaSyn** (arXiv 2606.17041, Tsinghua): 442 Nature Portfolio meta-analyses; 12 pipelines; retrieval ceiling 90.9% recall@200; **no system >52.7% of ground-truth included literature — screening is the bottleneck**, not retrieval.
- **SatIR** (COLM 2026, Stanford+Mayo, @cyruszzhou): high-stakes retrieval judged by eligibility ("is this actually possible?"), not vibes-relevance.
- **Undermind whitepaper** + Katina: convergence numbers above; the community's chief criticism — no reproducible search strategy — is structurally answered by our `search.executed` events + coverage records.
- **JMIR viewpoint** (2026/1/e88195): deep research agents for evidence synthesis — iterative clarify-then-search dialog as the emerging shape.
- Practitioner pulse: "loop engineering" as the emerging discipline (@panda_liyin); open-source deep-research loops (dzhng et al.) now standard stack items.
- Raw evidence file: `~/Documents/Last30Days/deep-research-agents-literature-search-raw-v3.md`.
