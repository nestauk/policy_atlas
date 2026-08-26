# Contract-stage adversarial review: 034-synthesis-report

Reviewer: Codex (`codex-rescue`, read-only brief), 2026-08-26. Target:
contract.md + rubric.md as drafted at contract approval. Adjudicated by the
lead the same day; every remedy folded into the contract before planning.

| # | Sev | Finding | Adjudication |
|---|---|---|---|
| F1 | BLOCKER | Gap bullets need a coverage base the key-findings seed does not carry (no coverage records, no tools) | **Adopted** — gap bullets by re-statement of verified section gap claims only (grade/base copied verbatim, validator-matched against the seed ledger); deterministic ≤2 post-check; never derived fresh |
| F2 | BLOCKER | Case-study public/persistence shape unspecified; repository ignores unknown roll-up fields | **Adopted** — explicit `CaseStudyCardOut` (`card_id`, `title`, `prose`, `claims`, nullable `result_claim_id`/`strength`/`design`/`since_year`); additive `SectionOut.cards` defaulting `[]`; blocks payload mirrors it; repository projection named |
| F3 | BLOCKER | "Wire marks its claim id" impossible — `ClaimWire` has no id; public `claim_id` is the minted unit UUID | **Adopted** — wire carries `result_ordinal` (index into the card's claims); projection resolves it to the persisted `claim_id`; absent/dup/unresolvable degrades to null, renders unbolded |
| F4 | MAJOR | Card authoring/grounding protocol under-specified ("modelled on key findings" doesn't cover structured cards) | **Adopted** — dedicated `CaseStudyWire`; per-card prose/claim containment; exactly-one-result invariant; failing card dropped, survivors stand; <2 survivors ⇒ recorded absence |
| F5 | MAJOR | S5's venue/year fields exceed the granted public gate; title-joins non-deterministic | **Adopted (trim remedy)** — S5 restyles with existing projection fields only (title, appraisal, evidence type, citation count, cited-in); venue/year dropped |
| F6 | MAJOR | SSE/live-render contract unaddressed for a conditionally absent front-matter block | **Adopted (no-change path)** — stream untouched; cards appear only in the committed artefact read model; pinned with a stream-shape test |
| F7 | MAJOR | Programme identity/distinctness/absence-reason undefined | **Adopted** — identity = normalised card title; validator rejects duplicate titles and shared result claims; absence reason distinguishes `insufficient_programmes` from `cards_failed_validation` |
| F8 | MAJOR | Prompt-surface counts contradictory (4+1 vs six vs five+1) | **Adopted** — swept to "five surfaces (four bumps + one new)" everywhere; hash-pin modules named (`synthesis_backend.py`, `summary_prompts.py`; judges untouched) |
| F9 | MINOR | "Last updated" source undefined | **Adopted** — pinned to `latest_run.ended_at` (today's source, no new read field) |
| F10 | MINOR | Title ≤60 reject-vs-clamp unspecified (today clamps at 200) | **Adopted** — rejects at the proposal validator, like `nav_label`; `SECTION_TITLE_MAX` 200 stays on the read path; behaviour test required |

**Verdict handling:** the reviewer's "do not approve for planning yet" was
satisfied by folding all ten remedies before the plan was finalised; the
owner's contract approval stands (specification completions within the
approved scope — the one narrowing, F5's venue/year trim, is flagged at the
plan gate).
