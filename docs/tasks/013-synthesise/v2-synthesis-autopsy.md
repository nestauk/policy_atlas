# V2 synthesis/generation/verification autopsy (design-phase recon, 2026-07-07)

Third V2 recon leg (theming was autopsied in task 009, extraction in task 011).
Deep-reasoner, read-only, over `../discovery_policy_atlas`; corroborated against
V2's own `V2_EVIDENCE_PIPELINE_CONTEXTUAL_REPORT.md` (§H, §M). Adjudicated into
contract rev 7.3. Preserved verbatim below as the build-phase reference.

---

## How V2's synthesis actually worked

A LangGraph pipeline (`agent.py:91-213`) runs 18 nodes: load → canonical
concepts → parallel theme discovery (issue/intervention/outcome/risk) →
deterministic aggregation → RAG retrieval → RCS (Ranked Contextual
Summarisation) → `generate_briefing`. It runs **synchronously in-request**, no
checkpointer, no worker tier (report §J; `projects.py:814`).

Generation (`nodes/briefing.py:146`) is a **fixed template**, not intent-led.
`SECTION_CONFIGS` (`briefing.py:60-143`) hardcodes four sections — Background,
Interventions table, Core Findings, Recommendations — plus **1-2 LLM-proposed
"synthesis" sections** (`briefing.py:845-893`, `_decide_synthesis_sections`),
the only intent-shaped structural element. Order is fixed; generation order
differs from frontend display order (`briefing.py:650`).

Per section, `BriefingOrchestrator.generate_section` (`orchestrator.py:349-447`)
runs **gather → generate → ground → regenerate**:

1. **Gather**: agentic tool loop, orchestrator LLM `gpt-5.2` emitting a
   structured `OrchestratorDecision`, calling read-only evidence tools until
   `done` or the cap `MAX_TOOL_CALLS_PER_SECTION=10` (`orchestrator.py:155`;
   bumped to 25 for the table, `:765`). Tools read RCS-scored evidence,
   aggregated intervention outcomes, top studies, document quality.
2. **Generate**: `gpt-5-mini` writes markdown prose with `[N]` markers
   (`orchestrator.py:862-906`). Recommendations and the interventions table use
   **Pydantic structured output** (`orchestrator.py:919-922, 1686-1704`) and
   the table is **rendered deterministically** from typed rows
   (`orchestrator.py:976-1002`).
3. **Ground** (`_ground_and_extract_quotes`, `orchestrator.py:1186-1425`):
   regex-extract `(claim,[N])` pairs, then per citation ask `gpt-5-mini`
   (structured `GroundingResult`) whether each claim is supported, returning a
   model-authored "verbatim" quote + attribution label
   (`direct`/`synthesised`/`inferred`).
4. **Repair**: if any claim unsupported, re-gather via `retrieve_evidence` and
   **regenerate the whole section**, max 2 retries. Then return content
   regardless — "verification is informational only"
   (`orchestrator.py:436-447`).

Intent (`research_question`, `target_population`, `target_outcomes`,
`user_context`) enters via **prompt injection** into section instructions
(`briefing.py:242-277`) and — the one real retrieval hook — into RCS
theme-question generation (`contextual_summarisation.py:294-307`).
`target_geography` is ignored (hardcoded UK; report §I). Models: `gpt-5.2`
orchestrator, `gpt-5-mini` generation+verification, `gpt-4.1-mini` RCS
(`tools/models.py:10-22`).

The secondary answer path (`services/chatbot/`) consumes the briefing's
citation map but does no independent grounding — it strips/renumbers synthesis
citations (`chat_service.py:771-812`).

## Defect autopsy — NEW findings (beyond the known list)

1. **The interventions table entirely escapes grounding.**
   `_extract_claim_citation_pairs` strips every markdown table row before
   finding claims (`orchestrator.py:1067`). The richest, most quantitative
   section — effect sizes, key studies, outcomes — is **never verified against
   sources**. Any prose claim lacking a `[N]` bracket is likewise never
   grounded. → v3 fix binds only if structured/tabular renderings decompose
   into the same typed-claim/verification pipeline (contract rev 7.3).
2. **A failed quote-presence check does not fail the claim.** When the
   model-authored `supporting_quote` cannot be found in any candidate chunk,
   the code blanks `chunk_id` and appends a note — `is_supported` stays
   whatever the model said (`orchestrator.py:1329-1342`). A **fabricated quote
   still counts as a supported claim** and is persisted to
   `synthesis_citations.supporting_quote` (`briefing.py:480-495`). The quote is
   model-authored, never deterministically extracted. → proves 013's
   deterministic presence gate + excluded-and-counted rule is necessary.
3. **Mis-citation (right fact, wrong source) is invisible.** Grounding fetches
   only the cited document's chunks (`orchestrator.py:1247-1259`); a claim
   citing the wrong doc fails to match → anchor blanked, support retained. →
   013's judge carrying an explicit Unsupported/mis-cited state is the fix.
4. **`overall_supported = all(...)` makes repair all-or-nothing**
   (`orchestrator.py:1412`). One unsupported claim regenerates the *entire
   section* (≤2×), risking regression of good claims; combined with a
   permissive judge biased to `True` (`orchestrator.py:1284-1291`), repair
   rarely fires and is blunt when it does. → 013's per-claim loop-free
   reword-down is strictly better; prove good claims survive sibling repair.
5. **Dead config caps — the budget surface lies.**
   `BriefingConfig.max_tool_calls_per_section=5` and
   `min_evidence_per_section=3` (`briefing.py:44-56`) are **never passed** to
   `generate_section`; the real cap is the module constant. The evidence floor
   is never enforced — a section can be written on **zero gathered evidence**,
   silently falling back to precomputed contexts or "No evidence available."
   (`orchestrator.py:1581-1605`). → 013 tests must assert configured cap ==
   binding cap on the live path; uncited sections flagged.
6. **447 lines of dead verification** (`tools/verification.py`), while
   docstrings advertise "mandatory verification for all claims" — the tools
   are excluded from the tool list and hard-blocked if called
   (`orchestrator.py:661-665, 1435-1441`). Docs say one thing, code does
   another. → the step-7 contract-verifier's documented-vs-built check exists
   for exactly this.
7. **Fourth silent truncation.** RCS truncates each chunk to 2500 chars before
   scoring/summarising (`contextual_summarisation.py:176`); the writer's
   primary evidence is a **model-authored RCS summary of a truncated chunk**
   (paraphrase-priming). Grounding re-fetches raw text, but generation is
   primed on summaries. → 013's verbatim-evidence invariant (rev 7.3).
8. **`effect_consensus` propagates into user prose** — fed directly into the
   table prompt as `effect={consensus}` (`orchestrator.py:1521,1538`).

## What V2 did well — adoption candidates

- **Deterministic table rendering from typed rows** (`orchestrator.py:976-1002`)
  — low effort, high value; 013's block-assembly-from-claims is the same
  principle; any future comparison table must keep it AND decompose to claims.
- **Structured output (Pydantic function-calling) for rows/recommendations** —
  already 013's typed-claim posture; keep.
- **Citation renumber-by-first-appearance** (`briefing.py:643-719`) — clean
  reader-facing `[1..N]`; a composition-conventions seam note.
- **Per-claim `claim_quotes` persisted with `chunk_id`** → click-to-highlight
  source-pane UX; 013's verified-span citation rows preserve the affordance.
- **`_decide_synthesis_sections`** — curated menu + custom-title escape + safe
  default; mirror the "menu + default" robustness pattern in
  `synthesise_sections_v1`'s prompt design (build-phase note).
- **Parallel per-row gather+generate, per-citation parallel grounding** —
  sound latency posture (v3.0 is serial by spec; note for later).
- **Rolling prior-sections summary** (`briefing.py:222-240`) — precursor to
  013's claim ledger, but passed as citable context; 013's
  context-never-evidence guard is the correction.

## Verdict — top 5 lessons encoded into 013

1. Structured/tabular renderings decompose into typed claims — no verification
   escape hatch (contract rev 7.3, decision 7).
2. Quote-presence gates the claim deterministically; fabricated quotes are
   never persisted, and are counted (already designed; test named).
3. Prove the caps bind: configured == enforced on the live path; evidence
   floors honest (`uncited_sections` flag; test named).
4. Repair per-claim, loop-free; a passing claim survives a sibling's repair
   verbatim (test named).
5. No dead capabilities on the live path; docs match execution (step-7
   contract-verifier's existing check; verification.md must exercise the judge
   on the live path).

**Contract-level gap adopted (rev 7.3):** the writer's citation-bearing
evidence context must be verbatim frozen-chunk text / extract-verified anchors
— model-authored summaries never serve as citation evidence (V2's
paraphrase-of-paraphrase drift cannot re-enter).
