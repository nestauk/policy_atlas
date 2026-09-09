# Implementation plan: 034-synthesis-report

> **Status:** Contract approved 2026-08-26 · owner. Plan approved 2026-08-26 ·
> owner. **Owner amendment 2026-08-26:** D9 — default writer `gpt-5.6-terra`,
> env-overridable (`POLICY_ATLAS_SYNTHESIS_MODEL` restores `gpt-5.5`).
> ADR: 0033 expected (case-studies pass; S6 reversal of 028's overview lead).
>
> Terms, S1–S9 and P1–P10 live in [contract.md](contract.md). This plan cites
> them. Adversarial reviews (contract-stage, plan-stage) run via
> `codex-rescue` — Codex is installed this slice. Contract-stage: 10/10
> adopted ([adversarial-review-contract.md](adversarial-review-contract.md)).
> Plan-stage: two cheap facts folded in (gap-ledger seed, route-at-baseline);
> remaining wire details parked for the build
> ([adversarial-review-plan.md](adversarial-review-plan.md)). S5 venue/year
> trim flagged for this gate.

## Context

The report's substance is right; its surface is not. Four prompt bumps and a
new case-studies pass change what the model writes; the page reorder,
hierarchy and card work change how it reads. One slice, one PR, stacked on
033. Remaining synthesis-wire details (card JSON, gap-ledger fields beyond
grade/base) land in the build — reopen the contract only if a granted gate
is exceeded. Owner 2026-08-26: **D9** switches the synthesis default to
`gpt-5.6-terra` (cheaper live experiments) and adds
`POLICY_ATLAS_SYNTHESIS_MODEL` so 5.5 is an env flip, not a code edit.
Langfuse autopsy and a calibrated cheaper-model ladder stay **out of this
slice**.

## Decisions

| # | Decision | Choice |
|---|---|---|
| **D1** | Gap bullets' coverage base | Key findings **re-states** verified section gap claims. Phase A **extends `_key_findings_ledger` with each surviving gap's `payload["gap"]`** (grade + coverage base) — today the ledger omits it. No new tool plumbing, no fresh gap derivation. Validator matches restated grade/base against that record; post-check caps at 2. |
| **D2** | Result-claim marking (S8) | Wire carries `result_ordinal` (index into the card's own claims); the repository projection resolves it to the persisted public `claim_id` after the write (adversarial F3). No `ClaimOut` change. Absent/dup/unresolvable ⇒ `result_claim_id: null`, renders unbolded, never errors. |
| **D3** | Case-study seed | Verified claims + cited chunk text (the key-findings seed shape) **plus** the cited documents' appraisal label, evidence type and year — deterministic DB fields, so strength/meta lines are sourced, never invented. Missing fields ⇒ the line is omitted. |
| **D4** | Card storage + shape | One `role: "case_studies"` entry in `synthesis_result.blocks`; payload mirrors the public `CaseStudyCardOut` (contract § S4, adversarial F2). Additive `SectionRole` + `SectionOut.cards` defaulting `[]`. Dedicated `CaseStudyWire` + validator: exactly-one-result, title-uniqueness, drop-failing-card, absence reasons (`insufficient_programmes` vs `cards_failed_validation`) (F4/F7). SSE untouched — cards appear only in the committed read model (F6). No migration. |
| **D5** | Callout label | **"In brief"** (owner: softer label). One string, contract § Reading the prototype item 3. |
| **D6** | Title bound (S6) | Proposal validator: title ≤ 60 chars (rejects, like `nav_label`); prompt instructs the short form. `SECTION_TITLE_MAX` stays 200 for old-artefact reads — the bound is enforced at the proposal validator, not the read path. |
| **D7** | Review | Full Tier 3 stack: contract- and plan-stage adversarial (codex-rescue) + step-7 contract verifier, `/code-review`, `/security-review`, `/simplify`, human deep review. |
| **D8** | Live route | **Phase 0** confirms a working model route (or the build does not open). Phase E is the replay/live-evidence gate, not the first route check. If quota dies mid-build, Phase E halts and escalates — deterministic work already landed stays. |
| **D9** | Synthesis model | Default **`gpt-5.6-terra`** (owner 2026-08-26 — cheaper experiments). Env `POLICY_ATLAS_SYNTHESIS_MODEL` restores `gpt-5.5` (or any listed model). Tool-bearing and structured-parse synthesis calls pin `reasoning_effort="none"` **only when the resolved model is `gpt-5.6-terra`** (029 — terra 400s on function tools otherwise). 5.5 omits the field (provider default). Judge stays `gpt-5.4-mini`. Terra-as-writer is unmeasured vs 5.5; pin 5.5 via env if grounding regresses. Do not treat one 034 live check as a clean A/B (prompts also move). |

## Gates

Three full `make verify` runs (033 shape):

| # | When | Class |
|---|---|---|
| 1 | Phase 0 | build-open baseline |
| 2 | End of Phase B | public API (OpenAPI/`SectionRole`) |
| 3 | End of Phase F | step-6 exit |

Phase A gates on `make verify-fast` (includes prompt-guard) plus the full
synthesis test files; frontend phases (C, D) gate on `make frontend-verify`;
Phase E gates on prompt-guard + replay notes, not a suite run.

## Phases

Each phase ends in a commit on `task/034-synthesis-report`.

### Phase 0 — Baseline

Confirm a working model route (D8) — halt here if it is down. Then
`make verify` + `make frontend-verify` on the branch. Record counts.
**Also D9 (inline, cheaper than a phase):** `POLICY_ATLAS_SYNTHESIS_MODEL`
env read with default `gpt-5.6-terra`; terra `reasoning_effort="none"` pin
on every tool-bearing (and terra `parse`) synthesis call; kwargs pin test
in the synthesis backend suite; `infra/DEPLOYMENT.md` row, omitted /
development-tuning. Env restores `gpt-5.5`.
**Gate:** live route + full `make verify`.

### Phase A — Prompt surfaces (S3 prompt, S6 prompt, S7) — lead

Lead throughout: prompt-bearing work is never delegated.

1. Shared voice block (P1–P8, P10) as one module constant; rendered into
   each surface. P9 stays on the sections proposer.
2. `synthesise_section_v9` — voice block + corpus-touring ban; conclusions
   focus one-liner. v6 baseline module untouched.
3. `synthesise_key_findings_v3` — lead-colon form, gap bullets per D1 (≤2),
   claim-type widening + validator.
4. `synthesise_sections_v5` — short titles (P9), D6 bound, overview-lead
   guidance dropped (the named 028 reversal).
5. `summariser_v2` — P1–P2, P10.
6. Hash re-pins; prompt pin tests updated; existing synthesis suite green.

**Gate:** `make verify-fast` + synthesis test files.

### Phase B — Case-studies pass (S4 backend) — codex

Seam designed here (D1–D4 are the spec); implementation delegated.

1. `synthesise_case_studies_v1` prompt text — **lead** (prompt-bearing);
   `CaseStudyWire` + validator + composition — **codex**: pass runs after
   key findings, seed per D3, emits 0 or 2–4 cards, judged and verified
   (failing cards dropped — no `repair_section` reuse), validation per D4 (exactly-one-result, title uniqueness,
   drop-failing-card), absence reasons recorded in
   `counts["case_studies"]`.
2. Roll-up: `role: "case_studies"` block per D4; production-order test
   (after key findings), presentation-order test (front matter);
   `result_ordinal` → `claim_id` projection resolution (D2).
3. Public shape: `SectionRole` + `SectionOut.cards` + `CaseStudyCardOut`
   additive; `make openapi-sync`; `web-api.md` flow-back. Readers swept:
   `chat_context.py`, read-model repository role filters.
4. Tests: composition/absence-reason/role/result-binding-degrade/
   meta-omission; old-artefact read unaffected; **SSE stream shape
   untouched** (F6 pin).
5. Plumbing the new lane needs: bump `generation_budget_max` and record
   the pass in provenance / `call_counts`. Do **not** reuse
   `_section_claims`'s `repair_section` path — failing cards are dropped.
   Card-to-claim mapping rides the block payload (exact JSON shape is a
   Phase B call, not pre-specified here).

**Gate:** full `make verify`.

### Phase C — Front matter + hierarchy (S1, S2, S5) — codex

Prototype-pinned layout; contract § S1/S2 is the spec.

1. Page reorder: front matter → body → back matter; "In brief" callout
   label (D5); metadata strip (031 wording, Published relabel, study types
   out, no Authors).
2. Heading levels h1/h2/h3 per contract; contents grouped + "Method"
   relabel; old-artefact fallback (long titles, no cards) tested.
3. Most relevant sources: move above body, card restyle **within the
   existing projection fields** (title, appraisal, evidence type, citation
   count, cited-in — venue/year stay out, adversarial F5); ranking test
   pinned unchanged (**fast-worker**: mechanical against the existing
   `mostRelevantSources` contract).

**Gate:** `make frontend-verify`.

### Phase D — Bullets, cards, download (S3 render, S4 render, S8, S9)

1. Key-findings renderer: first-`: ` split, bold lead, no-colon degrade,
   gap marker; span-anchoring tests incl. boundary-crossing degrade —
   **fast-worker** (exact spec, existing 028 bullet machinery).
2. Case-study cards component + result-span bolding (D2) — **codex**.
3. `artefactMarkdown` + print parity (order, headings, bold leads, cards) —
   **fast-worker** with pinned expected-output tests.

**Gate:** `make frontend-verify`.

### Phase E — Replay evidence + live check — lead

1. Refine-replay per bumped surface (≤3 rounds each) on pinned inputs;
   before/after excerpts tagged P1–P10 into `verification.md`.
2. One live run on a known question; front matter, hierarchy, bullets,
   cards, markdown download eyeballed against the page; artefact id,
   **`SYNTHESIS_MODEL` actually used**, and screenshots recorded. Owner may
   point this run at terra via the D9 env var; if so, say so — it is not a
   5.5 baseline.

**Gate:** prompt-guard green + replay notes complete. Requires the live
model route (D8).

### Phase F — Flow-back + step-6 exit — lead

1. ADR 0033; `web-api.md` confirmed; deferred.md: case-studies seam
   discharged, "why this source matters" left standing; AGENTS.md pointer.
   If 033 has merged, rebase onto `dev` before this slice's review (contract
   branching rule — not a separate phase).
2. `verification.md` complete.

**Gate:** full `make verify` + `make frontend-verify`.

## Executor summary

- **lead** — Phases A, E, F and every prompt text in B: prompt-bearing and
  adjudication (doctrine: never delegated); D1–D6 seam design (this plan).
- **codex** — B's implementation, C's layout build, D's card component:
  judgment-bearing execution against machine-verifiable dones (contract
  § Acceptance checks + the phase test lists).
- **fast-worker** — C3 restyle, D1 renderer split, D3 markdown parity:
  mechanical transcription of exact specs with pinned tests.
- Inline lead: OpenAPI/type regen, hash re-pins, pointer edits, D9 env
  knob (cheaper than delegation).

## Out of this slice (follow-on)

A Langfuse cost-and-clarity autopsy, a calibrated clarity judge, and a
controlled cheaper-model ladder (5.4 writer · gather/writer split · mini
summaries) are **not** 034. D9 is the only 034 deliverable that unblocks
them: set `POLICY_ATLAS_SYNTHESIS_MODEL`, confirm `LANGFUSE_HOST` + keys
in the agent environment, then inspect `run:synthesise:<run_id>`
observations. Do not paste keys into chat. Shipping a new default writer
still wants the deferred eval slice.
