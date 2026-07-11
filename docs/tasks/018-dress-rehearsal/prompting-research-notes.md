# Prompting-strategy research notes (018 inputs: B-B2 voice · C2 loop · A1 models)

Two tracks, 2026-07-10: a deep primary-source sweep (vendor guides/cookbooks, papers)
and a last-30-days community sweep (Reddit/X/HN/GitHub/YouTube; raw file in the lead's
`~/Documents/Last30Days/`). Framed to generalize across frontier families + mini tiers
(Bedrock swap pending) — provider-specific items are quarantined at the bottom.

## Family-general rules (the 12 that converge across OpenAI / Anthropic / Google)

1. **One instruction, one place, zero conflicts.** Current frontier models follow
   instructions near-literally; contradictions are the #1 prompt bug and burn reasoning
   tokens. Conflict audit precedes any other tuning.
2. **Fence by type**: delimited sections (XML tags or MD headers) for instructions /
   context / examples / input. **JSON performs particularly poorly as a document
   wrapper** in long context (GPT-4.1 empirics) — independent support for A4's
   planner-history fix (JSON-blob → message array).
3. **Layout**: stable instructions first → tagged data blocks → task restated last.
   Serves long-context accuracy AND cache-prefix stability at once.
4. **Outcomes + success criteria, not procedures** ("describe the destination");
   prompt at heuristic altitude, never if-else rule piles.
5. **Give the reason behind every hard rule** — models generalize from motivation;
   bare prohibitions get lawyered. (Supports the environment-context preamble's
   "motivate the rule" framing for the extractor.)
6. **Positive framing by default; ALWAYS/NEVER reserved for true invariants** (citation
   integrity, schema, safety). Emphatic-language accretions ("CRITICAL: you MUST")
   are prior-generation tech debt that overtriggers on current models — strip at swaps.
7. **Specify verbosity/format numerically** ("≤5 bullets", "flowing prose") — current
   models are terse-but-prompt-sensitive; never rely on defaults.
8. **Few-shot = 1–5 canonical, diverse, format-pinning examples**; never edge-case
   laundry lists; never reasoning demonstrations for reasoning-enabled models.
9. **Native reasoning ON → delete CoT scaffolding** ("think step by step" is
   unnecessary-to-counterproductive); reasoning OFF/minimal → explicit plan-then-act
   returns. Prompts are written per effort-mode, not per model.
10. **Quote/anchor before synthesizing; uncertainty in structured form** (labelled
    assumptions, null-rather-than-guess fields) instead of prose hedging. Vendors
    document quote-grounding explicitly — external validation of our
    gather-then-author Option B shape and the claims machinery generally.
11. **Untrusted text in labelled data containers + standing contents-are-never-
    instructions rule — assumed breachable**, backed by architectural controls
    (matches our existing injection posture; delimiters are mitigation, not boundary).
12. **Prompts are versioned code**: paired replay set (50–200 cases at maturity —
    eval-slice scale; 018's pinned-substrate replays are the v1), regression-gated
    changes, and **fresh-minimal-prompt rebuild on every model-family swap** — never
    port the inherited stack. The single most important finding for the Bedrock plan,
    and it reframes C2: accumulated ritual in our prompts is suspect by default.

## Mini-tier adjustments (screen / extract / judge surfaces on 5.4-mini)

- One narrow, fully-specified job per call — minis degrade on multi-concern prompts
  fastest (moderate confidence: assembled from academic brittleness work, not vendor
  doctrine).
- Worked examples matter MORE at mini tier but saturate at 1–3; formatting consistency
  across examples is critical.
- Never trust prompted schema adherence — constrained decoding (structured outputs)
  everywhere, plus null-rather-than-guess field rules (we already do the former).
- Format/behaviour rules measurably work better in the SYSTEM message at small scale.
- **Reasoning effort is not monotonic on judgment tasks** — one eval found mini at
  *medium* effort beating its own *high* on judging accuracy per dollar; high effort
  narrows but never closes the size gap. → **Direct 018 consequence: classify@xhigh is
  a hypothesis to verify against baseline-1, not a settled setting** (plan A1 amended).
- Keep mini prompts short and blunt; motivation-prose pays off less than at frontier.

## Research/report-writer specifics

- OpenAI deep-research cookbook prompt language worth stealing: "focus on data-rich
  insights: specific figures, trends, statistics, measurable outcomes" · "be
  analytical, avoid generalities" · inline citations + full source metadata · write so
  tables could be extracted.
- Two-stage pattern: cheap model clarifies → rewrites the ask into a fully-specified
  brief before the expensive run (matches our planner → composed-run shape).
- Effort-scaling rules must be IN the prompt for agents (they can't judge effort
  otherwise — Anthropic multi-agent research blog).
- Kill meta-commentary in artifact-producing surfaces ("Respond directly without
  preamble; never 'Here is…' / 'Based on…'"); keep brief status preambles only in
  conversational surfaces (planner).
- **Answer-first/BLUF ordering has NO vendor-eval evidence** — practitioner convention
  only. The evidenced substitutes: be-analytical-avoid-generalities, structured
  uncertainty, quote-grounding. (Bears on the key-findings block: its value case is
  product design, not prompting literature.)
- Community pulse (last-30-days): the live debate has moved prompting → verification
  ("model returns something that looks perfect, then…" — r/PromptEngineering,
  2026-07-09); our judge/validator machinery IS that verification half. Also field
  evidence that system prompts steer *conclusions*, not just style (same data + two
  system prompts → opposite, equally-plausible-looking analyses) — the writer's
  framing rules are epistemically load-bearing; anti-overfit pins matter.

## Provider-specific — never bake in (Bedrock constraint)

Knob names/semantics (`reasoning_effort`/`verbosity` vs `effort`/adaptive-thinking vs
`thinkingLevel`) — config-abstracted only · OpenAI developer-role / "Formatting
re-enabled" / `prompt_cache_key` · Anthropic `cache_control` breakpoints / prefill
migration / XML-tag load-bearing-ness · Gemini PTCF / bridge idioms · any tuning that
fixed a previous generation's failure mode.

## Honestly thin/absent

No dedicated mini-tier prompting guide from any vendor · no vendor-eval evidence for
BLUF/answer-first in report writers · "Claude weights user messages more" is
secondary-blog lore, don't build on it · no Anthropic long-form-report prompting guide
(their material is orchestration-focused).
