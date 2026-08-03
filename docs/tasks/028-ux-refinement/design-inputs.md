# Design inputs: 028-ux-refinement

## 1. User interviews (2026-08, four internal Nesta policy team members)

Four internal policy team members used the current iteration (027 build, local).
Team review produced the change list below (owner-supplied verbatim, lightly
grouped). These are the slice's requirements source.

**Type scale and text size**
- Increase default text sizes for readability.
- Adopt a consistent type scale (pattern reference: GOV.UK
  https://design-system.service.gov.uk/styles/type-scale/) across headings and
  body — text-size consistency per content type.

**Chat**
- Chat input: fixed in position while content scrolls; expandable multi-line
  input (not a single-line machine); cap prose line length ~70 characters.
- Users aren't sure where to look when the plan sits beside the planning chat.
  Proposal: build the plan up sequentially — more planning turns where the
  planner suggests each part and the user clicks buttons to confirm / edit /
  add their own. When the plan is complete or close, it shows inline in the
  chat (expandable). Chat centred at the planning stage.
- Enter submits (consistent with common chat patterns).

**Output artefacts**
- Hierarchy: global header for project settings; tabs for search/analysis
  content — avoid clutter.
- Consolidate artefact/stage names (e.g. "Search plan" vs "Search results") so
  users can distinguish stages.
- Sticky navigation through reports — Substack-style sidebar / GOV.UK contents
  sidebar; keep your place, jump between sections.
- Default run split 50/50.
- Progressive disclosure: collapsible report sections (Wikipedia-style
  headers), high-level summaries visible by default, click to expand.
- Key findings as bullet points, not dense paragraphs; better formatting in
  the evidence-base artefact generally.

**Sources**
- Sortable table columns; clean up the table; rename Strength → "Evidence
  strength".

**Navigation & workflow**
- Better signposting from initial chat → plan → start analysis.
- Themes link to a filtered source list; label "Key themes" clearly; label the
  per-theme counts as "Documents".

**General**
- Information overload — manage what the user faces through planning and
  outputs.
- "Just enough text" — cut redundant copy.
- Sweep for other small wins.

## 2. Claude Design mock-up (owner-authored, 2026-08)

`mockup/policy-atlas-ux-v2.dc.html` — copied from the claude.ai/design project
"Policy Atlas UX improvements"
(https://claude.ai/design/p/1ec48731-40e5-4c42-be0d-d0283dc6af8c, file
`Policy Atlas UX v2.dc.html`). It is a **UX spec, not code to port** — same
standing rule as the demo branch in 027: markup, copy and interaction design
are the spec; its data/state layer (`support.js` dc-runtime, kept out of the
repo) never crosses. Notable encoded decisions:

- Centred single-column planning chat (max-width ~680px), empty-state prompt,
  plan parts arriving as cards ("Plan · 1 of 4" … "4 of 4": question · scope ·
  search effort · check-ins) with primary/secondary option buttons, "Refine
  it" prefilling the composer, and a confirmed state (✓ label + Change).
- The completed plan as an inline expandable chat card (settings grid + steps
  list + "Start the analysis" + "~10 min · pause or steer at any check-in").
- Global header: breadcrumb (product / project), tabs Workspace · Evidence
  base · Findings · Sources, orange badge dot on Workspace when a check-in is
  pending. (No Landscape or Decision log tabs — an IA question, see contract.)
- Run stage: chat | journey at 50/50; journey = stage bar, timeline with
  notes, sources→evidence funnel, completion card.
- Check-in card in the chat thread with option buttons; answered echo line;
  composer disabled while running with honest steering note.
- Composer: auto-growing textarea (3 rows base), Enter to send / Shift+Enter
  newline hint, Send button.
- Evidence base: sticky contents sidebar with scroll-spy (top-bar variant also
  mocked), A4 article, coverage snapshot cells that navigate into
  sources/findings, collapsible sections with one-line summaries always
  visible ("Expand +"/"Hide −"), key findings as bullets with citation-ref
  chips and gap tags, Key themes rows with "N documents →" buttons that open
  the theme-filtered sources view, "How the evidence was gathered" section
  carrying funnel + evidence-type bars + publication-year chart, references.
- Sources: filter chips (All/Included/Screened out/Cited) + theme select;
  sortable columns Source · Year · Origin · Evidence type · Evidence strength
  · Status; venue rendered under title; count footer.
- Findings: gated empty card when the run wasn't deep search; kind filter
  chips.
- Prose line-length caps throughout (66–78ch).

Where the mock-up and as-built 019–027 behaviour conflict, as-built behaviour
wins (standing rule); the mock-up's *fictional* data details (stage names,
counts, copy) are placeholders, not requirements.

## 3. Real artefact shape (owner fidelity correction, 2026-08-03)

The owner flagged that both mock-ups' section lists ("Key findings" · "How
interventions compare" · "Key themes" · "Gaps in the evidence" …) are **not
what a live synthesis produces**. Verified against the dev DB (live 027-check
artefacts, `synthesis_result.blocks`):

- Real shape: `key_findings` ("Key findings") + **~7–8 `standard` sections
  with long, question-specific analytical titles** + `conclusions`
  ("Conclusions"). Example (pupil-attendance artefact, 2026-07-29): "Direct
  attendance support: mentoring, follow-up, and school-home collaboration" ·
  "Strength and applicability of the evidence base for UK attendance
  policy" · etc. `SectionRole = key_findings | standard | conclusions`.
- **No themes / gaps / how-gathered sections exist in artefacts.** Themes are
  a separate durable read-model surface; gaps are gap-typed claim annotations
  inside sections.
- `SectionOut.focus` is the **writing brief** ("Synthesize across UK and
  comparator evidence on…"), not a reader summary — it must never render.
  The prose's first sentence is the takeaway by prompt design and serves as
  the collapsed summary.

Consequences folded into the contract: strand 5 (summary = first sentence,
never focus; sidebar designed for long real titles), strand 8 (themes as a
data-driven component, no fake artefact section), and the fork-C mock-up
rebuilt on the real attendance artefact (`mockup/tab-ia-options.html` rev 2).
Any 028 mock-up or fixture work uses real or sanitized-real section lists,
not invented ones.

## 4. Owner feedback on mock-up rev 2 (2026-08-03) → rev 3 + contract

- **Summaries always visible:** the one-line summary shows in the collapsed
  state; expanding reveals the full cited prose (contract strand 5).
- **Key findings never collapses** — always rendered in full (strand 5).
- **Section-flow root cause named:** interviewees' confusion came from not
  knowing whether the overview "What the evidence shows…" section connects
  to the per-theme sections that follow — the overview→theme transition
  jars. Owner: likely a prompt fix at section planning, or a section
  organisation rethink → contract strand 12 (scoped
  `synthesise_sections` rev, third gated prompt surface).
- **Fork C direction (🟡 hybrid):** the report's "How the evidence was
  gathered" section shows **cited-only** plots (relevant to the page it's
  on); the **Landscape tab stays** for the overall evidence base. Six tabs.
  Mock-up rev 3 shows the ruled design.

## 5. Owner approval of rev 3 + scope additions (2026-08-03)

Owner: "this looks good now" — fork C hybrid confirmed. Two additions:

- **Summaries navigation layer folds in** (contract strand 13): the ⏸
  deferred "Block summaries / artefact summary / faithfulness judging"
  bundle, spec'd and binding at `provenance-grounding.md` § Summaries. The
  collapsed-section summaries (rev 3's always-visible one-liners) become the
  verified block summaries; first sentence stays as the honest fallback for
  legacy/failed.
- **Check-in refinement** (contract strand 14), two live-testing findings:
  (a) real check-ins overwhelm — the latest live `steering.pause` bundle
  carries 9 boostable evidence types, 5 appraisal tiers, screen-confidence
  bounds and the full proposed-section list in one card, and users can't
  tell what each option means; (b) users didn't notice a pending check-in —
  they thought the analysis was still running (badge + title marker proved
  insufficient). Fix shape: presentation-first (recommended action leads,
  rest disclosed, plain-language "what this does" lines) + an unmissable
  cross-tab paused state; option-set thinning at source only via a gated
  orchestrator composition rev if plan-time payload analysis demands it.

## 6. Check-in survey (owner-directed, 2026-08-03: "read a few of them")

All 48 live `steering.pause` events in the dev DB surveyed before fixing the
strand-14a direction:

| Type | Component | Count | Standard options |
|---|---|---|---|
| boundary `check_in` (watch mode) | appraise/characterise/classify/ingest/screen× | 7 | 3 — continue · change mode · stop |
| `evidence_base_coverage` | select | 35 | 4 — continue · search more · re-screen · re-characterise |
| `search_exception` | acquire | 2 | 5 — deepen · rescope filters · guide queries · accept thin · stop |
| `synthesis_shape` | synthesise | 2 | 5 — as proposed · edit sections · emphasis boosts · regroup ×2 |
| `deepening_selection` | select | 2 | 9 — as proposed · deepen clusters · strongest · most relevant · budget · +ICF profile · refresh extraction · scope strata · exclude docs |

Findings that set the direction:
- **Standard option copy is static code** (`runtime/steering.py`), and leaks
  internal jargon to policy users: `weight_emphasis quality x2.0 — a
  multiplier on the default weight`, `(D3 memo refresh)`, `(D6)`, `(D7)`,
  `(D8)`, `(B3)`, "characterisation", "document grain". → plain-language
  rewrite is a **code copy change, no prompt rev**.
- **Up to 4 orchestrator-authored options stack on top** of the standard
  set (observed on synthesis_shape and a full-text-recovery boundary), so
  worst-case ~13 choices. The authored options carry `why` rationales that
  are the clearest prose in the payload — render them, distinctly.
- Options classify cleanly: proceed · change-emphasis (replaces) ·
  additive · scope/exclude (requires input) · meta (mode/stop) — a static
  per-id class map supports grouped presentation without touching
  behaviour.
- Boundary check-ins' deterministic render is raw machine text
  (`appraise: succeeded | wall_clock=0.332s | counts: …`) — 027 already
  presents these friendly with raw behind a disclosure; no new work.
