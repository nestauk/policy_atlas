# Verification: 034-synthesis-report

Evidence for the 034 build (S1–S9 + the 2026-09-01 owner iterate pins), plus
the in-branch code-review pass of 2026-09-02 that fixed the issues listed
under § Review findings. Public-safe: all evidence below is from fixtures and
deterministic tests; no raw source text, secrets or unredacted traces.

## Commands run

All run on `task/034-synthesis-report` at the reviewed state (2026-09-02,
after the review-pass fixes).

| Command | Result | Notes |
|---|---:|---|
| `make verify` (backend: pytest + mypy + lint + guards) | pass | 2,414 backend tests green. Was **red at review open** — see findings F-1 |
| `cd frontend && pnpm typecheck` | pass | Was **red at review open** — findings F-2/F-3 |
| `cd frontend && pnpm lint` | pass | Was **red at review open** — finding F-4 |
| `cd frontend && pnpm test` | pass | 499 tests, 68 files |
| `cd frontend && pnpm build` | pass | Production build |
| `make drift-check` | pass | `frontend/openapi.json` matches the schema export; `types.ts` regenerated, not hand-edited |

## Checks beyond the build

- **Deterministic tests (S1–S9 coverage)** — all green in the suites above:
  - S1/S2: `orderSections` places `case_studies` between `key_findings` and
    `standard`; outline entries group as Executive summary / Full report;
    "Method" relabel in the contents; part-heading scroll tests
    (`ArtefactOutline.test.tsx`, `ArtefactView.test.tsx`).
  - S3: lead-colon bold split incl. no-colon bullets; colon-crossing citation
    renders exactly one `[n]` marker; gap bullets get the distinct (gold)
    marker; backend gap-restatement validator tests (match accepted, forged
    grade rejected `gap_not_restated`, cap at 2 `gap_restatement_cap`);
    `_key_findings_ledger` carries the gap payload.
  - S4: composition test (stub emits 2 cards → `role: "case_studies"` block
    directly after key findings, `counts["case_studies"] = {present: true}`,
    prompt version + call counts in provenance); absence test
    (`stubnocasestudies` → no block, `present: false` + reason);
    `CaseStudyWire` strict-schema and bad-`result_ordinal` drop tests;
    SSE surface unchanged (`test_progress_emitter_has_no_case_studies_stream_surface`).
  - S5: ranking-unchanged tests; card claims counted without double-counting
    (regression test added this pass, see F-5); note merge by `source_id`
    (backend `pss_id` = `CitationOut.source_id`, verified consistent).
  - S6: proposal validator **rejects** titles over 60 chars
    (`title_too_long`, no truncation) and accepts at the bound;
    `SECTION_TITLE_MAX` 200 kept on the read path.
  - S7: prompt pin tests for `synthesise_sections_v5`,
    `synthesise_section_v10`, `synthesise_key_findings_v3`, `summariser_v2`,
    `synthesise_case_studies_v1`, `most_relevant_note_v1`,
    `full_report_intro_v1`; `VOICE_PRINCIPLES` asserted present in the
    section, key-findings, case-studies and summariser surfaces;
    corpus-touring ban strings asserted; overview-lead guidance asserted gone.
  - S9: markdown export tests — part labels (`## Executive summary`,
    `## Full report`), `###` section headings, bold lead-colon bullets,
    case-study cards with bolded result span and metadata line, MRS block
    position (after KF, before body), notes included, empty case-studies
    section omitted (parity with the page, fixed this pass — F-6).
  - Budget: `generation_budget_max` covers the case-studies pass
    (1 + `CASE_STUDIES_MAX_CARDS` judge lanes), `MRS_NOTE_MAX` note calls and
    the intro call; asserted in two suites.
- **AI evals** — none this slice (per contract: judged behaviour beyond the
  deterministic checks is eval territory).
- **Manual / browser** — NOT run in this review pass (see § Known unverified).

## End-to-end command

Not run here. The declared manual check is: one live run on a known question
(`Reducing NEETs` substrate per the iterate plan), eyeball the front matter /
hierarchy / bullets / cards, and download the markdown for comparison —
requires the live OpenAI route (`POLICY_ATLAS_SYNTHESIS_MODEL`, default
`gpt-5.6-terra`).

## Diff summary

One PR on `task/034-synthesis-report` (≈6,000 added lines vs `dev`):

- **Backend synthesis** (`synthesis_backend.py`, `synthesise.py`,
  `summary_prompts.py`, new `voice_prompt.py`): shared voice block
  (P1–P8, P10); prompt bumps `sections_v5` / `section_v10` (bridge clause) /
  `key_findings_v3` (lead-colon + gap restatement) / `summariser_v2`; new
  `synthesise_case_studies_v1` pass (own `CaseStudyWire`, validate → judge →
  drop-failing-card, block on `synthesis_result.blocks`, `result_ordinal` →
  `claim_id` at projection); `most_relevant_note_v1` mini-pass (fail-soft,
  stored in `counts["most_relevant_notes"]`); `full_report_intro_v1`
  mini-pass (fail-soft, stored in `counts["full_report_intro"]`) — **see
  deviation D-1**; `SYNTHESIS_MODEL` env-overridable with the terra
  `reasoning_effort="none"` pin; proposal titles rejected over 60 chars.
- **API read models / repository**: additive `SectionRole` value
  `"case_studies"`, `SectionOut.cards` (`CaseStudyCardOut`),
  `ArtefactOut.most_relevant_notes`, `ArtefactOut.full_report_intro`;
  card/notes/intro projection from the rollup JSONB; OpenAPI + `types.ts`
  regenerated.
- **Frontend** (`ArtefactView`, `ArtefactOutline`, `artefactPresentation`,
  `AppShell`): two-part report chrome with grouped contents sidebar and
  part headings; Expand all / Collapse all for the full report; case-study
  cards with bolded result span and strength/design/since chips; full-width
  MRS cards (cited-in lists removed, authors placeholder, grounded note
  line); lead-colon bullet bolding with single-`[n]` suppression; gap-bullet
  marker; metadata strip (Sources / Published / Last updated, study types
  moved to Method); markdown export parity; footer moved into the task
  scroll pane.
- **Docs**: ADR 0034; contract iterate pins; deferred.md case-studies seam
  discharged, "why this source matters" narrowed; `web-api.md` flow-back;
  prompt hashes re-pinned (`summary_prompts.py`, new `voice_prompt.py`).

## Review findings

In-branch code review, 2026-09-02 (this pass; the formal Tier-3 step-7 stack
is still owed — see rubric 15). **Fixed in this pass:**

- **F-1 (blocker) — backend mypy red.** `_case_studies_pass` reused the name
  `claim` (bound to `ClaimDraft`) for `CaseStudyClaimWire` in the metadata
  loop. Renamed to `wire_claim`; `mypy src tests` green (294 files).
- **F-2 (blocker) — frontend typecheck red.** `artefactMarkdown` fed
  `MarkdownSection`/`MarkdownCard` (nullable `claims`/`blocks`) into
  `mostRelevantSources`/`cardEvidenceChipLabels`, whose structural types
  did not admit `null`. Widened the structural types
  (`ClaimSourceLike`/`ClaimBearerLike`) instead of casting.
- **F-3 (blocker) — new `ArtefactView.load.test.tsx` typecheck red.** Mock
  return values needed `as unknown as` conversions.
- **F-4 (blocker) — frontend lint red.** The committed
  `eslint-disable-next-line react-hooks/exhaustive-deps` in `ContentsSidebar`
  made the React Compiler skip the component. Fixed at cause: `navEntries`
  memoised on `entries` and the effect depends on it; disable removed.
- **F-5 (major, logic) — MRS citation double-count.** For a case-studies
  section the API returns the same claims in `section.blocks` **and** as
  re-projections in `section.cards`; `mostRelevantSources` counted both,
  inflating counts and potentially changing the top-3 (and diverging from
  the backend's note ranking). Fixed: claims deduped by `claim_id` across
  blocks + cards; regression test added.
- **F-6 (minor, S9 parity) — markdown emitted an empty `### Case studies`
  heading** when a case-studies section had no cards, while the page renders
  nothing. Markdown now skips it; test updated to assert the omission.
- **F-7 (cleanup) — dead code.** `AnswerCallout` was unreferenced after the
  "In brief" owner steer (see D-3) — removed. The deprecated-on-arrival
  `reportRoadmap` stub removed with its test. The duplicated note-merge
  logic in `ArtefactView` replaced by the exported `mergeMostRelevantNotes`.
- **F-8 (defensive) — repository card-claim fallback could emit duplicates**
  (`block_claim_by_id` holds each claim under its UUID and its synthesis
  alias; `.values()` yields both). Deduped by claim identity.
- **F-9 (blocker) — backend lint red** (masked at review open because mypy
  failed first): 14 ruff errors in branch-touched files, including a loop
  variable shadowing the imported `citation` table in
  `_card_evidence_fields` (F402), `zip()` without `strict=` in the card
  projection (B905, now `strict=True` — the two lists are built in
  lockstep), unsorted imports and long lines. One long line sat inside
  `FULL_REPORT_INTRO_SYSTEM_PROMPT` and was re-wrapped (whitespace-only
  prompt change; the surface is not hash-pinned — see D-5).

**Recorded, not fixed (adjudication items for the review conversation):**

- **D-1 — `full_report_intro` deviates from the approved contract and
  ADR 0034 § 3.** Both pin a *deterministic, presentation-only* roadmap
  sentence built from body titles; the implementation ships an **LLM
  mini-pass** (`full_report_intro_v1` on `gpt-5.4-mini`, env
  `POLICY_ATLAS_FULL_REPORT_INTRO_MODEL`), a new prompt surface and an
  additive public field `ArtefactOut.full_report_intro` — none named in the
  contract's approval gates. There is **no deterministic fallback**: when
  the pass fails (fail-soft), no roadmap renders. Landed in commit
  `2a79c64` ("improved formatting and connecting sentences"), i.e.
  owner-authored, but the contract/ADR were not amended. **Needs owner
  ratification and a contract/ADR amendment before merge.** `web-api.md`
  now documents the field (flow-back done this pass).
- **D-2 — extra env override** `POLICY_ATLAS_CASE_STUDIES_MODEL` (case-studies
  pass only) is additive and follows the gated pattern but is not one of the
  two named gated vars. Same ratification bucket as D-1.
- **D-3 — the "In brief" answer callout is hidden** on the page and absent
  from the markdown (code comment: "034 owner steer: overlaps key
  findings"), while contract S1 keeps the labelled callout in the front
  matter. The summariser still runs (its output feeds chat context), and
  `summariser_v2`'s prompt still says the summary "is labelled 'In brief'
  on the page" — stale if the steer stands. Record the steer in the
  contract or restore the callout.
- **D-4 — heading levels differ from contract S2's letter** (h3 for Case
  studies / MRS): the shipped two-part chrome renders part headings and all
  section headings as `h2` on the page; markdown uses `##` parts / `###`
  sections. The two-level *grouping* the iterate pins asked for is there;
  the exact h-levels are not. Presentation-only; flag for the owner.
- **D-5 — prompt-hash guard does not pin `synthesis_backend.py`** (the guard
  pins files whose *name* contains "prompt"; the four bumped surfaces live in
  `synthesis_backend.py`). Pre-existing gap — v8 was never pinned either —
  but the contract's "pins re-recorded for … `synthesis_backend.py`" wording
  is unimplementable as written. `voice_prompt.py` and `summary_prompts.py`
  are pinned.
- **D-6 — validator gap vs contract S4:** duplicate card **titles** are
  rejected; "cards sharing a result claim" is not explicitly checked
  (low risk — `result_ordinal` indexes each card's own claims, which must be
  substrings of that card's own prose).
- **D-7 (pre-existing) — frontend appraisal tie-break vocabulary**
  (`["high","moderate","low","very_low"]`) does not match the labels the API
  emits (`Very strong`/`Strong`/`Moderate`/`Limited`/`Weak`), so the MRS
  tie-break mostly falls through to title order; the backend note ranking
  uses the real labels. Tie-break only; ranking by count agrees. Predates
  034 and S5 pins ranking as unchanged — left for a later slice.
- **Formal review lanes** (contract verifier, `/code-review`,
  `/security-review`, adversarial/Codex, `/simplify`): **not run in this
  conversation** — Tier 3 requires the step-7 stack in a fresh conversation.

## Rubric status

| # | Status | Note |
|---|---|---|
| 1 | partial | Prototype departures all hold (no authors, no confidence, no invented metadata); D-1/D-3/D-4 are deviations awaiting owner ratification |
| 2 | partial | `make verify` + frontend verify + build green (this pass); **manual live check not run** — escalated here, not skipped silently |
| 3 | **not satisfied as written** | Two ungated additions: `full_report_intro_v1` + public field (D-1), `POLICY_ATLAS_CASE_STUDIES_MODEL` (D-2). No schema migration, no new dependency, no new egress (both mini-passes ride the existing OpenAI route) |
| 4 | holds | `types.ts`/`openapi.json` regenerated; `make drift-check` green |
| 5 | holds | No tests deleted/skipped; one test assertion corrected to match its own name (empty case-studies markdown omission, F-6) |
| 6 | holds on fixtures | Order + grouping + relabel tested; old artefacts: `cards` defaults `[]`, fallback ladder untouched |
| 7 | holds | v3 pin, split/degrade/no-colon/single-marker, gap re-statement validator + cap + marker, never forced |
| 8 | holds | Composition/absence/role/binding/SSE tests green; metadata omitted when unsourced; chat context tolerates the role (role-agnostic iteration) |
| 9 | holds | Restyle + move; ranking unchanged (F-5 restored count parity); no importance prose — note is grounded-restatement only |
| 10 | holds | v5 pin; 60-char reject; forbidden titles kept; overview-lead removal asserted; consumers swept (anchors, markdown, chat) |
| 11 | **not satisfied** | Per-surface refine-replay notes with P-tagged before/after excerpts not recorded in this repo; voice block is one module constant; v6 baseline untouched; guard re-pinned for the two pinnable modules (D-5) |
| 12 | partial | Markdown export tests green; the live download-vs-page comparison is part of the outstanding manual check |
| 13 | holds | `web-api.md` updated (incl. `full_report_intro` this pass); ADR 0034 written (needs D-1 amendment); deferred.md discharged/narrowed |
| 14 | partial | This file; **live-run artefact id missing** (manual check outstanding); OpenAPI diff = the committed `frontend/openapi.json` delta, drift-check green |
| 15 | **not satisfied** | Step-7 review stack not yet run — must run in a fresh conversation |

## Intent & assumptions

- Commit `2a79c64` is owner-authored and treated as the latest intent where
  it conflicts with the contract (D-1/D-3); the docs, not the code, are
  assumed stale — flagged rather than reverted.
- The case-studies block stores per-card `claim_ids`/`claim_spans` in the
  rollup; the repository's substring-matching fallback exists only for
  rollups written before that (defensive, deduped in F-8).

## Known unverified items

- **Manual live run** (rubric 2/12/14): needs the live model route; produces
  the artefact id, front-matter screenshots and the download comparison.
- **Refine-replay evidence per surface** (rubric 11): ≤3 rounds each with
  P-numbered before/after excerpts; the private replay driver
  (`docs/verification/private/034/replay_034_lanes.py`, referenced from
  `.env.example`) is not in the repo.
- **Live behaviour of the two mini-passes** (note quality, intro quality,
  terra `reasoning_effort` pin against the real API) — deterministic tests
  cover wiring and fail-soft paths only.

## Public safety

Yes. All test evidence is fixture-based (Finland/Sweden stub cards, invented
prose). Prompts and specs are public by design. No live traces, artefact
excerpts or source text appear in this file.

## Review handoff (step-7/8 inputs)

- **Adjudication items:** D-1 through D-6 above; D-1 is the gate-shaped one
  (new prompt surface + public field beyond the granted gates).
- **Executor provenance:** build commits authored in Cursor chats by the
  owner; this review pass (fixes F-1…F-8) by the lead agent, 2026-09-02.
  The heterogeneous (Codex) lane has not read this slice yet.
- **Diff-scoping:** `.cursor/plans/*` and `docs/tasks/034-*/` are
  process artefacts; `frontend/openapi.json` + `frontend/src/api/gen/types.ts`
  are generated.
- **Knowledge candidates:**
  - The prompt-hash guard's filename convention silently exempts the largest
    prompt surface (`synthesis_backend.py`) — pinning by content marker or an
    explicit list would close D-5 for good.
  - A section that re-projects its block claims into a second public shape
    (cards) creates double-count traps for every claims-walking consumer;
    dedupe by `claim_id` at the walker, not the producer.
  - React Compiler treats a single `eslint-disable` of a hooks rule as
    "skip this component" — memoise instead of disabling.
  - OpenAI strict structured output rejects the full `ClaimWire` (nested
    optional payloads); the slim per-pass wire (`CaseStudyClaimWire`) is the
    pattern for future bounded passes.

## Deferred work

- "Why this source matters" free-form prose stays out (narrowed, not
  discharged — grounded notes only): `docs/deferred.md`.
- Paper authors acquire/projection (placeholder only), venue/year on MRS
  cards, mobile/narrow-viewport work: unchanged seams.
- Frontend appraisal tie-break vocabulary alignment (D-7).
