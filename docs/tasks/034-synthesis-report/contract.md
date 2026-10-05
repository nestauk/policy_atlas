# Task contract: 034-synthesis-report

One implementation slice. Keep it reviewable. Boundaries are in
[AGENTS.md](../../../AGENTS.md). Specs are in [docs/specs/](../../specs/index.md).

> **Status:** approved.
> Contract approved (before planning): **2026-08-26 · owner** (go-ahead to
> plan; forks A–C settled the same day) ·
> Plan approved (before implementation): **2026-08-26 · owner** ·
> ADR: **0034** (case-studies pass — a new grounded content form produced
> late, shown early; S6 reversal of 028's overview lead; two-level report
> hierarchy; grounded cheap MRS note). Note: ADR 0033 is organisations
> tenancy — 034's number moved.
>
> **Owner iterate pins (2026-09-01):** case studies implement now; MRS
> grounded one-liner **in** on `gpt-5.4-mini` (reverses the facts-only
> ruling for that narrow surface); paper authors **parked** with
> placeholders; KF double-cite is a display fix; Executive summary / Full
> report chrome + deterministic roadmap + optional section bridges.
>
> **Branching:** `task/034-synthesis-report` from `task/033-ux-snags`
> (stacked — 033's build is complete on its branch, review/PR pending). The
> PR re-targets `dev` once 033 merges; if 033's review changes files this
> slice touches, this branch rebases before its own review.
>
> **Owner fork rulings (2026-08-26, design conversation, recorded in
> [design-inputs.md](design-inputs.md)):** softer answer-callout label (the
> spec's citation-free-navigation rule stands); 031's included-based source
> count wording stays; gap bullets join key findings; no Authors line; no
> confidence rating; Most relevant sources is a restyle/move only; case
> studies land as a new synthesis pass.
>
> **Review stack (owner, 2026-08-26):** the Codex CLI is now installed —
> the Tier 3 standard applies in full: contract-stage and plan-stage
> adversarial review via `codex-rescue` (read-only briefs), plus the step-7
> stack. No waiver this slice; the first since 030 with a non-Claude
> reviewer.
>
> **Contract-stage adversarial review adjudicated 2026-08-26:** 10 findings
> (3 blockers · 5 majors · 2 minors), **10/10 adopted** — gap bullets by
> re-statement (F1), the explicit `CaseStudyCardOut` public/wire/persistence
> shape (F2), ordinal→`claim_id` result binding (F3), the card validation
> contract (F4), S5 trimmed to existing fields rather than widening the
> projection (F5), SSE deliberately unchanged (F6), programme-identity
> validator keys + absence reasons (F7), prompt-count sweep (F8),
> Last-updated source pinned (F9), title bound rejects (F10). Findings log:
> [adversarial-review-contract.md](adversarial-review-contract.md).

## Goal

Make the synthesis report parseable and plainly written: an executive front
matter a policy reader can absorb in a minute (answer, key findings, case
studies, key sources), a real heading hierarchy over short titles, and prose
that states and synthesises findings instead of touring the corpus. Nine
numbered defects, S1–S9.

## Deliverable

One PR on `task/034-synthesis-report` that:

- Reorders the report page into front matter → body → back matter (S1).
- Gives the page a heading hierarchy and grouped contents (S2).
- Renders key findings as bold-lead bullets with gap bullets (S3).
- Adds a case-studies synthesis pass and its cards (S4).
- Moves and restyles Most relevant sources ahead of the body (S5).
- Makes section titles short and contents-ready (S6).
- Re-voices the writer, key-findings, sections and summariser prompts to the
  language principles (S7).
- Bolds the case-study result span (S8).
- Keeps the markdown/print export faithful to all of the above (S9).

## Terms

| Term | Meaning |
|---|---|
| **Front matter** | Inside **Executive summary**: In brief · Key findings · Case studies · Most relevant sources. Preceded by the Headline (H1 + stats strip). |
| **Body** | Inside **Full report**: ordinary (`standard`) sections plus Conclusions, each collapsed on its one-line summary. Prefaced by a deterministic roadmap sentence from body titles. |
| **Back matter** | References and Method (today's "How the evidence was gathered", relabelled), still under Full report. |
| **Answer callout** | The existing verified artefact summary (`ArtefactOut.summary`), rendered as the labelled callout. Citation-free navigation per [capability.md](../../specs/capabilities/evidence-base/capability.md) § Output structure — the label must not crown it the evidential headline (owner ruling: not "The answer"). |
| **Lead-colon form** | A key-findings bullet shaped `Lead phrase: warrant.` The lead is a 4–8-word claim (not a topic label); the renderer bolds everything before the first `: `. |
| **Gap bullet** | A key-findings bullet carrying a gap-typed claim with its coverage base, rendered with a distinct marker. New in this slice (the pass today re-states only finding/chunk/pattern claims). |
| **Case study** | One named programme a policy reader can point at (place — instrument), carried as a card: title, short mechanism prose, one bolded result claim, citations, honest strength/design metadata. Grain = programmes, never papers (papers are S5's job) and never raw finding rows. |
| **Most relevant sources** | Deterministic top-3-by-citation-count block (`mostRelevantSources`), full-width cards. Ranking unchanged. May carry a **grounded** one-liner (`most_relevant_note_v1`) restating only that source's cited claims/quotes. Free-form importance prose stays out. Paper authors are placeholders only this slice. |
| **Corpus-touring** | Prose about the act of reading the corpus ("a high-level reading of the documents", "in the material read here", "this body of work", "Inference:") instead of about programmes, populations and outcomes. Banned by P2. |
| **P1–P10** | The language principles (§ Language principles). Prompt surfaces cite them by number. |
| **S1–S9** | Defect ids. Goal, deliverable, scope, invariants, plan phases and rubric items all cite these. |

## Read first

- [Frozen prototype](../../specs/sources/synthesis-report-ux/README.md) — the
  Results-tab design reference; read its README for the extraction recipe and
  the recorded departures.
- [design-inputs.md](design-inputs.md) — the language target and anti-target
  samples, the fork rulings, and the invented-content table.
- [capability.md](../../specs/capabilities/evidence-base/capability.md)
  § Output structure — artefact summary vs grounded key findings; production
  ≠ presentation (produced last, shown first) — the case-studies pass follows
  the same pattern.
- [web-api.md](../../specs/system/web-api.md) § Read models — `SectionOut`,
  `SectionRole`, the artefact shape this slice extends.
- [prompting.md](../../specs/system/prompting.md) — binds all prompt work:
  versioned bumps, refine-replay loop (≤3 rounds/surface), cache-prefix
  layout, cost on the cache-discounted curve.
- `docs/deferred.md` § Task lifecycle IA — the parked case-studies design
  this slice discharges, and the facts-only "why this source matters" seam it
  must NOT discharge.
- Code spine: `synthesis_backend.py` (all prompt surfaces + wire shapes),
  `synthesise.py` (key-findings/conclusions composition, roll-up),
  `summary_prompts.py` (summariser), `ArtefactView.tsx` / `ArtefactOutline.tsx`
  / `artefactPresentation.ts` (page, contents, markdown export).

## Reading the prototype

The prototype binds page order, card anatomy and the bullet form. It does
**not** bind (recorded departures, each owner-ruled 2026-08-26):

1. **No Authors line** — the backend has no author for an artefact.
2. **No confidence rating** — no such judgment exists; inventing one would
   have the report vouch for itself.
3. **Softer callout label** — "In brief" (final word confirmed at this gate),
   not "THE ANSWER".
4. **Source counts** — "M cited out of K included" (031's one-meaning-per-
   count ruling), not "N found · M cited".
5. **Heading hierarchy** — the prototype's headings are visually flat; S2
   goes past it.
6. **Reference format** — `title (year) · venue` stays; no author strings.
7. **"Why this study matters" prose** — stays out (032 facts-only ruling).

## Defects

### S1 — Page order

Today the report runs title → summary → snapshot → all sections → most-cited
sources → references → gathered. The front matter must come first as one
executive block.

- Order: header (title · answer callout · metadata strip) → Key findings →
  Case studies → Most relevant sources → body sections (collapsed) →
  Conclusions → References → Method.
- Metadata strip: Sources ("M cited out of K included", cited links to the
  filtered sources view — unchanged meaning) · Published (the cited years
  range, relabelled from "Years covered") · Last updated (**stays
  `latest_run.ended_at`**, today's source — no new read field; adversarial
  F9). Study types leave the strip (they remain under Method). No Authors.
- The answer callout keeps its verified-only/pending/absent behaviour
  unchanged; it gains the label and the prototype's callout styling.

### S2 — Heading hierarchy

Every section heading today is the same `h2` and the contents is one flat
list of long titles.

- On the page: `h1` = report title; `h2` = Key findings, each body section
  (short title), Conclusions, References, Method; `h3` = Case studies and
  Most relevant sources (subordinate front-matter blocks) and card titles.
- Contents: Executive summary (→ the answer callout anchor) first, then the
  body sections' short labels, Conclusions, References, Method. Renamed:
  "How the evidence was gathered" → "Method" in the contents (the page
  heading may keep the long name).
- Old artefacts (long titles, no short labels beyond `nav_label`) render
  without error — the fallback ladder stays `nav_label` → clipped title.

### S3 — Key-findings bullets

028 shipped `- ` bullets; they are still long single-sentence paragraphs.

- Prompt (`synthesise_key_findings_v2` → **v3**): every bullet in lead-colon
  form — a 4–8-word claim lead, a colon, then the warrant (P5); one headline
  per bullet (P3); 3–7 bullets, 60–180 words total (unchanged).
- **Gap bullets in** (owner ruling), by **re-statement only** (adversarial
  F1): the pass has no tools and derives no fresh gap. A gap bullet
  restates a verified section gap claim, copying that claim's grade and
  coverage base. Today's `_key_findings_ledger` serializes only text,
  type, verdict and citations — Phase A **adds the surviving gap's
  `payload["gap"]` (grade + coverage base)** so the validator has something
  to match. `KEY_FINDINGS_CLAIM_TYPES` gains `"gap"`; the validator rejects
  a gap bullet whose grade/base does not match a seed gap claim; a
  deterministic post-check caps gap bullets at **2**. Never forced — a
  report with no verified gap claims emits none.
- Renderer: split each bullet on the first `: `; bold the lead; a bullet with
  no colon renders whole and unbolded, never mis-split. Gap bullets get the
  distinct marker (prototype gold). Claim spans still anchor into the stored
  prose — the split is display-only; spans crossing the split degrade
  honestly per the 028 rule.

### S4 — Case studies

Discharges the parked 032 seam (`docs/deferred.md` § Task lifecycle IA), at
the **programme grain** — the 032 parked design's IOF-shortlist detail is
superseded by this contract.

- New synthesis pass `synthesise_case_studies_v1`, modelled on the
  key-findings pass's position (single bounded call, after key findings) but
  on its **own constrained wire** (adversarial F4): `CaseStudyWire` — a list
  of cards, each `{title, prose, claims, result_ordinal}`. Seed = the
  surviving verified claims + cited chunk text (the key-findings seed shape)
  **plus** the cited documents' appraisal label, evidence type and year
  (deterministic DB fields). Emits 0 or 2–4 cards; judged and verified like
  any grounded block.
- **Card validation contract** (F4/F7): claims anchor into the card's own
  prose (exact substrings, no overlap — the standing rule); uncited
  evidential prose is flagged unverified exactly as in sections; **exactly
  one result claim** per card, named by `result_ordinal` (an index into the
  card's claims — F3); programme identity = the normalised card title, and
  the validator rejects duplicate titles and cards sharing a result claim.
  A failing card is **dropped, not repaired**; survivors stand. Fewer than
  2 survivors ⇒ no block, with the absence reason recorded in
  `counts["case_studies"]` distinguishing `insufficient_programmes` from
  `cards_failed_validation`. Absence is a normal state, never an error.
- **Public shape** (F2): `SectionRole` gains `"case_studies"` (additive);
  `SectionOut` gains additive `cards: list[CaseStudyCardOut]` defaulting to
  `[]` (old artefacts and non-case-study sections read `[]`).
  `CaseStudyCardOut` = `{card_id (stable), title, prose,
  claims (standard ClaimOut list), result_claim_id (nullable),
  strength (nullable), design (nullable), since_year (nullable)}`. The
  nullable metadata comes from the cited sources' appraisal/classification/
  year where present and is omitted where not — never invented.
- **Result-claim binding** (F3): the wire's `result_ordinal` is resolved to
  the persisted public `claim_id` (the minted unit UUID) by the repository
  projection after the write; an absent, duplicated or unresolvable ordinal
  degrades to `result_claim_id: null` (card renders with no bold span,
  never errors).
- Storage: one block with `role: "case_studies"` riding
  `synthesis_result.blocks`, its payload carrying the card list mirroring
  the public shape — **no new table**. Produced last, shown in front matter
  (the key-findings production ≠ presentation pattern; ADR 0033 records it).
- **SSE / live render unchanged** (F6): the run's stream gains no
  case-studies frames; cards appear only when the committed artefact read
  model replaces the live view (the same behaviour as the artefact summary
  today). Recorded as a deliberate path, with a test that the stream shape
  is untouched.
- Chat context and any other `blocks` readers must tolerate the new role
  (they already filter by role).

### S5 — Most relevant sources

- Moves into Executive summary (after Case studies) and restyles as
  **full-width** cards: title, appraisal chip (with hover), evidence type,
  citation count. Cited-in section lists are **removed** from the card.
  Venue and year are **not** added. Paper authors: API/UI placeholder only
  (null/omitted until a later acquire/projection slice).
- Ranking (citation count, appraisal tie-break) is **unchanged**.
- **Grounded cheap note (owner 2026-09-01):** after the artefact is written,
  a mini pass (`most_relevant_note_v1` on `gpt-5.4-mini`, env-overridable)
  may emit one sentence per top source, seeded only from that source's
  cited claim texts and quotes. Fail-soft (omit note). Stored under
  `synthesis_result.counts["most_relevant_notes"]` and exposed as additive
  `ArtefactOut.most_relevant_notes`. Free-form “why this source matters”
  remains out — the deferred seam narrows to ungated importance theatre.

### S6 — Short section titles

Body titles today restate the question ("What the evidence shows about
effectiveness for preventing or reducing childhood obesity…").

- Prompt (`synthesise_sections_v4` → **v5**): `title` is the short,
  parallel, contents-ready theme name (P9), bounded tighter — the proposal
  validator **rejects** a title over 60 chars, like `nav_label` and unlike
  today's clamp-at-200 (adversarial F10; a contents-ready title the writer
  was told to keep short is a proposal defect, and clipping one mid-word
  helps nobody). `SECTION_TITLE_MAX` stays 200 on the read path for old
  artefacts. `focus` keeps the full writing brief; `nav_label` may equal
  the title. `FORBIDDEN_SECTION_TITLES` still applies — one-word titles
  must dodge the banned generics ("Findings", "Summary" …).
- **Named reversal of 028 strand 12:** the answer-shaped overview lead
  section is dropped from the proposal guidance — the front matter (answer
  callout + key findings) now does its framing job. Recorded in the ADR.
- Old artefacts keep long titles and render fine (no backfill; the S2
  fallback ladder covers them). Title consumers swept: anchors,
  duplicate-title rejection, chat context, markdown export.

### S7 — Voice

The report tours the corpus and stacks findings. Four prompt surfaces adopt
the language principles (§ below); all lead-authored, each version-bumped,
each refine-replay-evidenced per prompting doctrine:

| Surface | Bump | Changes |
|---|---|---|
| `synthesise_section_v8` → **v9** → **v10** | body + conclusions writer | v9: P1–P4, P6–P8, P10 + corpus-touring ban. v10 (2026-09-01): optional one bridging sentence when not the first body section; still takeaway-first after the bridge; no mid-section headers |
| `synthesise_key_findings_v2` → **v3** | S3's home | P3, P5, P10; gap bullets |
| `synthesise_sections_v4` → **v5** | S6's home | P9 |
| `summariser_v1` → **v2** | the answer callout's source | P1–P2, P10; still citation-free, still faithfulness-judged, still no confidence language |

The shared voice rules live in **one module constant** rendered into each
surface (P1–P8 and P10; P9 is the sections-proposer only); each surface
adds only its form rules. The v6 frozen cost-baseline module is untouched.

### S8 — Result-span bolding

- The renderer bolds the span of the claim named by the card's
  `result_claim_id` (resolved from the wire's `result_ordinal` at
  projection time — S4). No `ClaimOut` change — the mark rides the card
  payload. A null `result_claim_id` renders the card unbolded.
- Body sections stay flowing prose: no bold leads, no pseudo-headings inside
  a section (the existing writer rule).

### S9 — Download/print parity

`artefactMarkdown` and the print stylesheet follow S1's order, S2's heading
levels, S3's bullet form (markdown bold leads) and S4's cards. References
format unchanged.

## Language principles

Prompt doctrine for this slice; surfaces cite them by number. The good/bad
samples in [design-inputs.md](design-inputs.md) illustrate them — encode the
principles, not the sample. Standing invariants all hold: evidence-
descriptive (no recommendations), under-claim, no pipeline vocabulary,
claims are exact substrings of prose.

- **P1 — Claim, then warrant.** Lead with the finding; number, population
  and source follow.
- **P2 — Name the world, not the reading of the files.** No corpus-touring
  (§ Terms). Write about programmes, populations, outcomes.
- **P3 — One idea per sentence; one headline per bullet.** A second fact
  gets a second sentence.
- **P4 — Contrast is the argument.** Structure by what differs (outcome vs
  behaviour, mechanism vs weight, UK vs comparator), not by cataloguing
  settings.
- **P5 — Scannable handle.** Key-findings leads are 4–8-word claims, not
  topic labels ("The levy worked on sugar", never "Fiscal measures").
- **P6 — Numbers do work.** One figure, where it decides something; counts
  and certainty bands are never the paragraph's spine.
- **P7 — Caveats attach to the claim**, they do not replace it.
- **P8 — Still descriptive.** "The mechanism is settled; the outcome is not"
  is in bounds; "so adopt X" is not.
- **P9 — Titles name the theme.** Short, parallel, contents-ready; never a
  restatement of the question.
- **P10 — Expand acronyms at first use.** Write "short-term rental
  accommodation (STRA)" the first time; the abbreviation may stand alone
  after that. Unexplained alphabet soup is not plain language (owner,
  2026-08-26, on the housing samples).

## Scope / Out of scope

**In:** the report page and its outline/presentation modules; the markdown
export; the five prompt surfaces named above (four bumps + one new);
`SectionRole` additive value;
the case-study pass and its wiring in `synthesise.py`; tests for every
behaviour rule; spec flow-back (`web-api.md` read models); deferred.md
discharge/narrowing; the ADR; `verification.md`; env-overridable
`SYNTHESIS_MODEL` (default unchanged).

**Out:** Paper-author acquire/projection (placeholders only); confidence
ratings; **ungated** "why this source matters" prose (grounded mini-note
is In); mobile/narrow-viewport work; the full briefing page; the eval
harness; a Langfuse cost/clarity autopsy; shipping a new default writer;
gather/writer model split; re-synthesising or backfilling old artefacts;
reference formatting; chat behaviour; any other capability; schema
migrations (the pass rides `synthesis_result.blocks`); new dependencies;
any new runtime egress.

## Constraints & approval gates

**Needs human approval before proceeding.** Three gates fire; all are named
here for the combined contract gate:

| Gate | What changes | Why gated |
|---|---|---|
| **Prompt surface** | `synthesise_section_v9→v10` · `synthesise_key_findings_v3` · `synthesise_sections_v5` · `summariser_v2` · **new** `synthesise_case_studies_v1` · **new** `most_relevant_note_v1` | Prompt-bearing work — lead-authored only, never delegated |
| **Public interface** | `SectionRole` gains `"case_studies"`; `SectionOut.cards` / `CaseStudyCardOut`; `ArtefactOut.most_relevant_notes`; OpenAPI regenerated | Public API surface |
| **Runtime config (additive)** | `POLICY_ATLAS_SYNTHESIS_MODEL` (default `gpt-5.6-terra`); optional `POLICY_ATLAS_MRS_NOTE_MODEL` (default `gpt-5.4-mini`) | Same pattern as planner/chat |

Further constraints:

- **Additive only.** No existing response field changes type, meaning or
  presence. Artefacts without a case-studies block are a normal state.
- **No schema migration.** If the pass cannot ride `synthesis_result.blocks`,
  halt and escalate — that is a contract change.
- **No new dependency; no generated file edited by hand** (`types.ts`
  regenerated).
- **No new runtime egress** — the pass uses the existing synthesis model
  route.
- **Prompt-hash guard** re-pinned for every bumped module; the frozen v6
  baseline module untouched.
- **Build may complete wire shapes** inside the granted gates (gap-ledger
  fields, card payload JSON, generation-cap bump). Halt if the pass needs a
  table or a non-additive public change.

## Public / private boundary

Everything this slice commits is public-safe: prompts, specs, the frozen
prototype, tests on fixtures. Live-run outputs quoted in `verification.md`
follow the standing redaction rules (no raw source text beyond cited quotes).

## Model route

Existing OpenAI route, **default `gpt-5.6-terra`** (owner amendment
2026-08-26 — cheaper live experiments). `SYNTHESIS_MODEL` is env-overridable
(`POLICY_ATLAS_SYNTHESIS_MODEL`) so a live process can pin `gpt-5.5` (or
another listed model) without a code edit. All five prompt surfaces (four
bumps + one new) are named above; no other LLM-bearing step changes. Judge
stays `gpt-5.4-mini`. Prompt-hash pins re-recorded for exactly two modules:
`synthesis_backend.py` and `summary_prompts.py`; the judge prompts are
untouched and keep their pins.

**Build pre-requisite (stop condition):** the refine-replay loop and the live
check need a working model route. Staging's OpenAI quota is recorded
exhausted (AGENTS.md); confirm quota/top-up **before conversation B opens**,
or the build halts at its baseline.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay
  as-is.
- **Flag, don't drop** — a bullet or card that fails verification degrades
  honestly, never silently disappears without its recorded reason.
- **Honest absence** — no case-studies block and no gap bullet are normal
  recorded states; metadata a card cannot source is omitted, never invented.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md)
  ("why this source matters" stays; the case-studies entry is discharged
  with a pointer here).

## Stop conditions

Halt and escalate when: an approval gate above is hit beyond its granted
shape; the case-study pass needs a table or a non-additive public change;
the live model route is unavailable at build open; scope would grow past
S1–S9; or the turn/token budget is spent.

## Acceptance checks

- `make verify` + `make frontend-verify` — green.
- Deterministic: page-order and heading-level tests on fixtures (S1, S2);
  bullet split/degrade tests incl. no-colon and boundary-crossing spans
  (S3); case-study composition/absence/role tests (S4); ranking-unchanged
  test (S5); title-bound and consumer-sweep tests (S6); markdown export
  tests (S9); prompt-pin tests for every bump.
- Prompt quality: refine-replay evidence per surface (≤3 rounds), P-numbered
  before/after examples in `verification.md`; judged behaviour beyond that
  is eval territory, not asserted here.
- Manual: one live run on a known question; eyeball the rendered report
  front matter, hierarchy, bullets, cards; one markdown download compared
  against the page.

## Verification evidence expected

Command results; the live-run artefact id and screenshots; per-surface
replay notes with before/after excerpts tagged P1–P10; the OpenAPI diff;
public-safety confirmation; known gaps; the review-stack record including
the adversarial-review decision made at this gate.

## Risk tier & review focus

**Tier 3** — four prompt bumps + one new prompt surface + an additive public
interface change. Review focus: prompt-surface correctness and injection
posture (the new pass reads chunk text), grounding integrity of the
case-study cards, honest degrade paths (split, absence, old artefacts),
scope creep past S1–S9, and the S6 consumer sweep.
