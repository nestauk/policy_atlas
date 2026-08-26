# Task contract: 034-synthesis-report

One implementation slice. Keep it reviewable. Boundaries are in
[AGENTS.md](../../../AGENTS.md). Specs are in [docs/specs/](../../specs/index.md).

> **Status:** drafted 2026-08-26 · pending owner approval.
> Contract approved (before planning): _date · who_ ·
> Plan approved (before implementation): _date · who_ ·
> ADR: expected (case-studies pass — a new grounded content form produced
> late, shown early; and the S6 reversal of 028's overview lead section).
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
> **Review-stack decision required at this gate:** Tier 3 standard includes
> contract- and plan-stage adversarial review via `codex-rescue`; the Codex
> CLI is not installed in this environment (the same gap recorded on 031,
> 032 and 033, each with an explicit owner waiver). Confirm the same waiver
> — or name another mechanism — before planning. The tier stays 3 either way.

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
| **Front matter** | The report's executive block, in page order: answer callout · metadata strip · Key findings · Case studies · Most relevant sources. Shown before any body section. |
| **Body** | The ordinary (`standard`) synthesis sections plus Conclusions, each collapsed on its one-line summary. |
| **Back matter** | References and Method (today's "How the evidence was gathered", relabelled). |
| **Answer callout** | The existing verified artefact summary (`ArtefactOut.summary`), rendered as the labelled callout. Citation-free navigation per [capability.md](../../specs/capabilities/evidence-base/capability.md) § Output structure — the label must not crown it the evidential headline (owner ruling: not "The answer"). |
| **Lead-colon form** | A key-findings bullet shaped `Lead phrase: warrant.` The lead is a 4–8-word claim (not a topic label); the renderer bolds everything before the first `: `. |
| **Gap bullet** | A key-findings bullet carrying a gap-typed claim with its coverage base, rendered with a distinct marker. New in this slice (the pass today re-states only finding/chunk/pattern claims). |
| **Case study** | One named programme a policy reader can point at (place — instrument), carried as a card: title, short mechanism prose, one bolded result claim, citations, honest strength/design metadata. Grain = programmes, never papers (papers are S5's job) and never raw finding rows. |
| **Most relevant sources** | Today's deterministic top-3-by-citation-count block (`mostRelevantSources`). Ranking and facts-only rule unchanged in this slice. |
| **Corpus-touring** | Prose about the act of reading the corpus ("a high-level reading of the documents", "in the material read here", "this body of work", "Inference:") instead of about programmes, populations and outcomes. Banned by P2. |
| **P1–P9** | The language principles (§ Language principles). Prompt surfaces cite them by number. |
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
  range, relabelled from "Years covered") · Last updated. Study types leave
  the strip (they remain under Method). No Authors.
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
- **Gap bullets in** (owner ruling): the pass may emit at most **2**
  gap-typed claims, each carrying its coverage base exactly as section gap
  claims do; `KEY_FINDINGS_CLAIM_TYPES` gains `"gap"`. Never forced — a
  report with no headline gap emits none.
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
  key-findings pass: runs after key findings, reads the report's surviving
  verified claims and cited chunk text, and emits 0 or 2–4 cards. Judged and
  verified like any grounded block; absence is a recorded state
  (`counts["case_studies"]`), never an error — mint nothing when the claims
  do not support two distinct programmes.
- Card anatomy: title (place — instrument, e.g. "United Kingdom — Soft
  Drinks Industry Levy"), short mechanism prose, exactly one **result
  claim** (the card's headline number/outcome — the wire marks its claim id;
  the renderer bolds its span, S8), citations as usual. Strength/design/year
  metadata comes from the cited sources' appraisal and classification where
  present and is omitted honestly where not — never invented.
- Storage: a new block with `role: "case_studies"` riding
  `synthesis_result.blocks` — **no new table**. Public shape: `SectionRole`
  gains `"case_studies"` (additive); the card structure is additive payload
  on that section. Produced last, shown in front matter (the key-findings
  production ≠ presentation pattern; the ADR records it).
- Chat context and any other `blocks` readers must tolerate the new role
  (they already filter by role).

### S5 — Most relevant sources

- Moves above the body (after Case studies) and restyles as cards: title,
  appraisal chip, evidence type · venue/year, cited-in facts.
- Ranking (citation count, appraisal tie-break) and the facts-only rule are
  **unchanged** — no "why this study matters" sentence (that seam stays in
  `docs/deferred.md`).

### S6 — Short section titles

Body titles today restate the question ("What the evidence shows about
effectiveness for preventing or reducing childhood obesity…").

- Prompt (`synthesise_sections_v4` → **v5**): `title` is the short,
  parallel, contents-ready theme name (P9), bounded tighter (proposal
  validator: ≤ 60 chars); `focus` keeps the full writing brief; `nav_label`
  may equal the title. `FORBIDDEN_SECTION_TITLES` still applies — one-word
  titles must dodge the banned generics ("Findings", "Summary" …).
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
| `synthesise_section_v8` → **v9** | body + conclusions writer | P1–P4, P6–P8; the banned-vocabulary list gains corpus-touring phrases; the no-bullets/no-headers-inside-a-section rule stays |
| `synthesise_key_findings_v2` → **v3** | S3's home | P3, P5; gap bullets |
| `synthesise_sections_v4` → **v5** | S6's home | P9 |
| `summariser_v1` → **v2** | the answer callout's source | P1–P2; still citation-free, still faithfulness-judged, still no confidence language |

The shared voice rules live in **one module constant** rendered into each
surface (one instruction, one place); each surface adds only its form rules.
The v6 frozen cost-baseline module is untouched.

### S8 — Result-span bolding

- The case-study wire marks the result claim; the renderer bolds that
  claim's span. No `ClaimOut` change — the mark rides the card payload.
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

## Scope / Out of scope

**In:** the report page and its outline/presentation modules; the markdown
export; the six prompt surfaces named above; `SectionRole` additive value;
the case-study pass and its wiring in `synthesise.py`; tests for every
behaviour rule; spec flow-back (`web-api.md` read models); deferred.md
discharge/narrowing; the ADR; `verification.md`.

**Out:** Authors; confidence ratings; "why this source matters" prose;
mobile/narrow-viewport work; the full briefing page; the eval harness;
re-synthesising or backfilling old artefacts; reference formatting; chat
behaviour; any other capability; schema migrations (the pass rides
`synthesis_result.blocks`); new dependencies; any new runtime egress.

## Constraints & approval gates

**Needs human approval before proceeding.** Two gates fire; both are named
here for the combined contract gate:

| Gate | What changes | Why gated |
|---|---|---|
| **Prompt surface** | `synthesise_section_v8→v9` · `synthesise_key_findings_v2→v3` (+ `"gap"` claim type) · `synthesise_sections_v4→v5` · `summariser_v1→v2` · **new** `synthesise_case_studies_v1` | Prompt-bearing work — lead-authored only, never delegated |
| **Public interface** | `SectionRole` gains `"case_studies"` (additive); the case-study card payload on that section; OpenAPI regenerated | Public API surface |

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

## Public / private boundary

Everything this slice commits is public-safe: prompts, specs, the frozen
prototype, tests on fixtures. Live-run outputs quoted in `verification.md`
follow the standing redaction rules (no raw source text beyond cited quotes).

## Model route

Existing OpenAI route, `gpt-5.5` synthesis model — unchanged. All six prompt
surfaces are named above; no other LLM-bearing step changes.

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
replay notes with before/after excerpts tagged P1–P9; the OpenAPI diff;
public-safety confirmation; known gaps; the review-stack record including
the adversarial-review decision made at this gate.

## Risk tier & review focus

**Tier 3** — five prompt bumps + one new prompt surface + an additive public
interface change. Review focus: prompt-surface correctness and injection
posture (the new pass reads chunk text), grounding integrity of the
case-study cards, honest degrade paths (split, absence, old artefacts),
scope creep past S1–S9, and the S6 consumer sweep.
