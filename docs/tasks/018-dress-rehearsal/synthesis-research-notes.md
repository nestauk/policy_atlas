# Synthesis output-shape research notes (018 Phase B fork input)

Web research, 2026-07-10 (delegated sweep; all sources public). Feeds the Phase B fork
(contract § Phase B): Option A = prompt-first on the claims-are-the-prose structure;
Option B = authored prose with typed claims anchored as char-offset spans.

## Headline

**The external evidence leans clearly toward Option B.** No production deep-research /
report-writing system found concatenates validated claim objects into the report
surface. The three shapes that exist at scale: (a) prose-first + post-hoc attribution
pass (Anthropic's multi-agent research system: a dedicated CitationAgent locates
citations in the finished report); (b) span-anchored citations emitted with the prose
(Anthropic Citations API — `cited_text` + start/end char indices, reported +15% recall
vs prompted citing; OpenAI Deep Research; LongCite); (c) prose composed *over*
pre-attributed evidence units (PaperQA2, scite, Attribute-First-then-Generate).
Option B + our existing verbatim/judge machinery re-pointed at spans is pattern (b).

## Measured results that bear on the fork

- **Post-hoc / two-pass attribution ≥ generation-time citing**: coverage and human-rated
  answer correctness higher (78% vs 69%), citation hallucination comparable-or-lower
  (arXiv 2509.21557, 2025).
- **Format-restricted emission taxes writing**: JSON-schema output costs ~10–15%
  generation/reasoning quality vs free-form; the cost disappears when writing is
  decoupled from format emission ("Let Me Speak Freely?", arXiv 2408.02442) — direct
  mechanistic support that emit-the-report-as-a-claims-list taxes the writer.
- **Atomized/extractive register costs utility**: perceived utility rises up to 200%
  moving extractive → abstractive, while cited-sentence rate falls — span-anchoring is
  how the abstractive end claws verifiability back (Extractive–Abstractive Spectrum,
  arXiv 2411.17375).
- **Our exact symptom is a documented failure mode**: OmniThink (arXiv 2501.09751)
  diagnoses write-sections-from-evidence-snippets pipelines as producing redundant,
  disjointed, shallow prose — and STORM's editors still flagged residual issues *after*
  its dedicated polish stage, i.e. prompt polish alone did not fully fix it.
- **Coherence levers with measured gains**: outline-guided generation (STORM: +25%
  "organized"); iterative self-feedback/revision loops (OpenScholar, Nature 2025 —
  citation accuracy at human-expert level); RARR-style targeted revision preserves text
  while fixing support (fits our existing bounded repair lane).
- **Caveat for Option A's side**: Attribute-First-then-Generate (ACL 2024) shows a
  claim-decomposed pipeline *can* maintain quality — but its final step still authors
  each sentence conditioned on the previously written text. It is evidence for
  "evidence-selection-first + authored prose", i.e. B-compatible, not for concatenated
  independent claims.
- **No paper tests our exact architecture** (claim objects concatenated = report).
  The A-vs-B inference is from adjacent evidence, which is why the contract's cheap
  probe (demo-prompt approach replayed on a 017 substrate with the new models) still
  runs before the fork is decided.

## Writer-envelope metadata (the noise question)

- **For**: PaperQA2 feeds citation counts / journal quality / retraction status to its
  agent and credits metadata-awareness in its superhuman-benchmark result — the
  strongest production precedent. Retrieval-side ablations (Anthropic contextual
  retrieval −49% retrieval failures; arXiv 2601.11863 metadata-in-chunk ablations) show
  source/year fields carry real signal.
- **Against**: irrelevant-context degradation (Shi 2023 — accuracy below 30% with
  distractors) and lost-in-the-middle (Liu 2023) — bulk mid-context additions are the
  hazard shape.
- **Direct evidence gap, explicitly**: no controlled study of writer-side (vs
  retriever-side) metadata benefit exists. Design consequence adopted in the contract:
  fields are terse, structured, and attached *adjacent to the evidence unit they
  describe* (never a mid-context metadata bulk), and each field earns its place via the
  contract's A/B replay — an experiment to run, not settled science.

## Prompt-surface takeaways (Phase C loop input)

- The battle-tested open writer prompt (gpt-researcher) converges on: forced concrete
  opinion ("Do NOT defer to general and meaningless conclusions"), citations at
  sentence/paragraph end, explicit structure directives, recency/trust preferences.
- Voice/answer-first/no-recitation rules are practitioner lore with no controlled
  studies; nearest measured support is the extractive-register utility cost above. Our
  loop's before/after replay is therefore the evidence mechanism, not the literature.

## What we keep regardless of fork outcome

Independent claim validation + the grounding judge are the part of the current design
the literature *endorses* (verification-guided revision beats unverified generation
everywhere it's measured — Self-RAG, OpenScholar, RARR). The fork is only about where
the prose surface lives, never about weakening validation.

## Owner adjudication of the patterns (2026-07-10, post-research)

- **Write-then-attribute (pattern a) is disfavoured as our primary mechanism.** Anthropic
  et al. are frontier, but their research products aren't robust research tools with
  citations as a core product feature — for Policy Atlas grounding IS the product, and a
  claim authored before its evidence is located is the `unsupported_mis_cited` class by
  construction. Post-hoc revision survives only as the repair loop's shape (RARR-like),
  which it already is.
- **PaperQA2's gather-then-author (pattern c) is the closest architectural analogue** —
  and the section loop is already half of it: evidence units are gathered by tool turns
  before emission. Option B's pinned form: keep the gather phase, author prose over the
  gathered units, span-anchor claims as written (pattern b's anchoring), validation
  machinery unchanged in authority.
- **Envelope metadata**: default-adopt the PaperQA2-precedented set + own quality ladder
  (year · evidence type · appraisal label · venue · cited-by · `is_retracted` flag);
  A/B the rest (author institution first). Terse, adjacent to the evidence unit.
- **Judge envelope changes get a verification-grade test** (verdict-distribution diff +
  flipped-verdict inspection), not an output-taste A/B; full calibration stays with the
  eval workstream.

## Thin/absent evidence flags

Perplexity internals (secondary sources only) · ledger/state-tracking value in
isolation · any direct claims-as-prose vs prose-with-anchored-claims comparison ·
controlled studies of voice rules · writer-side metadata benefit.
