# Fork probe — synthesise replay results (018 Phase B gate evidence)

Run 2026-07-10, per the plan's § Fork probe: two live synthesise replays on the 017
heat-pump substrate (project `91d2d684…`, scope `308bb287…`, grouping reference
`e2178624…` — identical substrate to the recorded 017 run). Scratch driver
monkeypatching in memory; no code changed. Artefact text stays in the dev DB per the
contract's private boundary — pointers below, register described not quoted at length.

## The three cells

| Cell | Run / artefact | Writer | Section prompt |
|---|---|---|---|
| Baseline-0 | `ed5feaf1…` / `079f30a1…` (the 017 run) | gpt-5-mini | as-built |
| Arm A | `02983547…` / `1e84bb28…` | gpt-5.5 | as-built |
| Arm B | `3c869ffd…` / `7f23ca1c…` | gpt-5.5 | as-built + demo voice rules |

## Annotation-layer stats (`component.completed` counts)

| | Baseline-0 | Arm A | Arm B |
|---|---|---|---|
| claims_total | 56 | 94 | 91 |
| chunk claims | 0 | 42 | 46 |
| tool_calls_total | 5 | 37 | 31 |
| tier_1 / tier_2 / tier_3 / tier_4 | 18 / 1 / 11 / 5 | 49 / 5 / 10 / 0 | 49 / 0 / 17 / 0 |
| unsupported_mis_cited | 7 | 2 | **0** |
| citations verified / unverified | 82 / 9 | 166 / 6 | 126 / 2 |
| citations_from_unselected | 0 | 1 | 0 |
| sections / blocks | 7 | 8 | 8 |

## Reading

1. **The model upgrade transforms grounding behaviour, not register.** gpt-5.5
   actually *works the evidence*: ~6× the tool calls, dozens of verbatim-verified
   chunk claims where mini made none, tier_1 up 18→49, unsupported 7→2/0. But arm A's
   prose still recites internals — "a reported direction spread of 11 positive, 4
   negative…", "the characterisation clustering reads the screened corpus as…" — and
   repeats the same spread twice in one section (independent claims can't see each
   other: the OmniThink redundancy failure, live).
2. **The voice rules fix register at zero annotation-layer cost.** Arm B's prose is
   clean analyst register (no internal vocabulary, numbers restated the way an analyst
   would, takeaway-leaning openings) and its verification stats are the *healthiest of
   the three* (0 unsupported, 2 unverified citations). Prompt rules do not trade
   grounding for prose. This also confirms the environment-context hypothesis at the
   writer surface (the voice block is a crude context-not-content preamble).
3. **What prompt rules do NOT fix (the residual, structural):** arm B still reads as a
   polished sequence of standalone observational paragraphs — one claim, one
   paragraph, pseudo-connective openers ("The same source reports…", "On upfront
   cost…") but no developed argument across claims, no section thesis, no answer-shaped
   narrative arc. The user's stated bar — "an actual report which answers the user's
   question" — is the part the wire cannot express: connective tissue between claims
   has no home, and block text remains the join of independently validated texts.

## Implication for the fork

- **Option A's ceiling is now measured, not theorised**: voice rules + the strong
  writer get to "well-written evidence briefing in bullet-paragraph form" with a
  healthy annotation layer. If that clears the demo bar, A is cheap and proven.
- **Option B's risk is now smaller than modelled**: the register transfers (the same
  voice rules become part of B's prose prompt), the writer demonstrably grounds well
  at 5.5, and B's remaining novelty is the span-binding mechanics + repair v2 +
  unspanned-prose check — machinery, not model behaviour.
- **Lead recommendation: Option B**, carrying arm B's voice rules into the prose
  prompt. Grounds: the residual gap is exactly the contract's core complaint
  (answer-shaped authored prose), it is structural by construction and now by
  observation, and the probe has de-risked the model-behaviour half of B. Option A
  survives as the recorded fallback if B's build hits its stop condition (the
  invariants must re-prove or we ship A's proven shape).

**Decision: owner call at the plan 🛑.** Probe caveats: judge model was still
gpt-5-mini in all three cells (same judge, so cross-cell comparison is fair; absolute
verdicts shift when the judge refreshes); one probe substrate (intervention-shaped
question) — taxonomy breadth is the loop's job, not the probe's.
