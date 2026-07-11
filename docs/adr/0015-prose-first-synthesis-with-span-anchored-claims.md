# ADR 0015: Prose-first synthesis with span-anchored claims

**Status:** Accepted — 2026-07-10 (018 plan confirmation; owner decision at the plan
gate). Amends ADR 0009/0010's emission decision (claims-are-the-prose).

## Context

013 shipped synthesis as structured claim emission: the writer emits a validated list
of typed claims and the artefact block text is literally the `\n\n` join of their
texts (`synthesise.py:2182`). Free prose is forbidden by prompt; no field exists for
connective tissue. The owner's quality verdict on live output (2026-07-10): the
artefact "reads like a bunch of observational sentences and not an actual report which
answers the user's question."

Evidence assembled at the 018 design gate (all in `docs/tasks/018-dress-rehearsal/`):

- **Fork probe** (fork-probe.md, three cells on one live substrate): the model upgrade
  (gpt-5.5 writer) transforms grounding behaviour (6× tool use, 42–46 verified chunk
  claims vs 0, tier_1 18→49) but not register; demo voice rules fix register at ZERO
  grounding cost (0 unsupported, 2 unverified citations — healthiest of all cells);
  what neither fixes is structural: one-claim-one-paragraph, no argument across
  claims, no answer-shaped narrative — because claims are validated independently and
  the prose surface IS their concatenation.
- **External research** (synthesis-research-notes.md): no production deep-research
  system concatenates validated claim objects into the report surface; measured
  results show format-restricted emission taxes writing quality ~10–15%, atomized
  register costs perceived utility, and two-pass/span-anchored attribution does NOT
  trade attribution fidelity for prose (Citations-API-style anchoring, +15% recall).
- **Prompting research** (prompting-research-notes.md): quote/anchor-before-synthesize
  is documented vendor guidance — the gather phase is endorsed; the claims machinery
  is the verification half of the current best-practice shape.

## Decision

Synthesis output shape v2 = **gather-then-author with span-anchored claims**:

1. The section loop's **gather phase is unchanged** (tool turns collect evidence units
   before any writing) — PaperQA2-shaped, and the part the literature endorses.
2. The writer **authors section prose** answering the intent over the gathered units;
   typed claims anchor as **char-offset spans into that prose** as it is written
   (`addressable_unit` start/end locators — no DB migration). Span binding is
   validated deterministically (exact substring, fail-closed, salvage preserved).
3. **Write-then-attribute is rejected as the primary mechanism** (owner posture):
   grounding IS the product; a claim authored before its evidence is located is the
   `unsupported_mis_cited` class by construction. Post-hoc revision survives only as
   the bounded repair loop (RARR-shaped), which it already is.
4. **Repair lane v2**: repairing a failing claim rewrites its prose segment in place,
   re-binds its span, recomputes downstream offsets, and re-validates the section
   (claim-only repair is mechanically incompatible with spans).
5. **Unspanned-prose traceability**: the judge lane receives full section prose + span
   map and flags evidential assertions outside any claim span
   (`unspanned_assertion`, flag-not-drop). Connective tissue is what SURVIVES that
   check, not what avoids it — the spec's traceability rule covers all significant
   prose, not only emitted claims.
6. **Every 013 grounding invariant survives unweakened**: per-type deterministic
   validators, judge lanes, pattern-count recomputation, gap grading + coverage base,
   flag-not-drop, verified-verbatim citations.
7. **Annotation-layer purpose statement**: annotations are the epistemic layer
   (provenance, tiers, gaps, flags) rendered IN the prose (typed spans — the locked
   demo product decision); the prose is the answer to the intent. Neither substitutes
   for the other.
8. **Two new grounded block kinds, distinct and never merged** (owner refinement,
   riding as a spec flow-back to capability.md + provenance-grounding.md):
   the **key-findings block** (produced last, shown first, conditional-required —
   present iff headline claims are made, never forced) and the **conclusions block**
   (report foot; what this evidence amounts to against the question;
   evidence-descriptive — no recommendations, per EB scope).
9. **Voice**: the demo branch's voice rules are a validated LESSON (register ban,
   analyst number restatement, takeaway-first — proven grounding-neutral by the
   probe), never a copy source; the writer's voice is re-authored deliberately as one
   coherent design (audience, environment-context preamble with the
   context-not-content rule, register, argument structure) and validated against
   baseline-1 in the refine loop.

## Fallback

Option A (prompt-first on the claims-join structure, the probe's arm-B shape) is the
recorded fallback, firing only through Phase B's stop condition: a grounding invariant
that cannot survive the new wire without weakening. Arm B's measured health (0
unsupported claims) makes the fallback shippable if needed.

## Consequences

- More machinery: span-binding validator, repair v2 offset arithmetic, the
  unspanned-prose judge lane — each with named property tests (018 plan B-B1).
- The annotation layer must be re-proven on a replayed live substrate before Phase C.
- The judge becomes the guard of the connective-tissue line; its envelope v2 changes
  carry the verification-grade evidence protocol (verdict-shift diff +
  unchanged-sample inspection + self-certification fixture) inside Phase B.
- Emission wire and prompts version-bump; Langfuse traces distinguish v1/v2 by
  prompt-version fields as usual.
