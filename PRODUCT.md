# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are senior policy makers and policy analysts/researchers in
government and the civil service. They work a live policy question (a strategy,
a white paper, a briefing) and need an evidence-led answer they can defend,
inspect and reuse outside the tool. Strategies and white papers are indicative
examples of the job, never assumptions about the reader's actual task.

Nesta staff operate and evaluate the product. They are not the audience.

## Product Purpose

Policy Atlas is an evidence-led policy-analysis workspace. It is not a document
generator and not a chatbot. A **Task** is one use of a **Capability** (for
example an Evidence search) that produces **Artefacts**: a grounded report, a
screened source list, extracted findings. A **Project** groups related Tasks.

The terminal product is an inspectable decision-support body: artefacts, the
evidence corpus behind them, claim provenance, comments, versions, links between
Tasks and a decision log. Humans use that body to brief, advise, write, clear
and publish outside the tool. The tool supports policy judgement; it does not
replace it.

Success: a policy team reaches a defensible, evidence-grounded position faster
than by hand, and every significant claim can be traced to its source without
leaving the workspace.

## Positioning

The combination a neighbouring tool cannot truthfully copy (owner, 2026-09-09):

1. **Policy-method capabilities**, not general research. Evidence search, options
   scoping, theory of change, stakeholder mapping and later methods run as
   bounded, inspectable plans.
2. **Policy-focused, user-testing-driven** development and design, built with and
   for government users.
3. **Academic-grade rigour** of the kind found in research AI tools such as
   Elicit or Consensus: citations, verbatim quotes, grounding tier and appraisal
   are co-emitted with each claim, never stapled on afterwards.

Neighbours: general chat deep-research tools (no bounded policy method, weak
provenance) and academic research tools (rigour without the policy method or
the policy audience).

## Operating Context

- **Task lifecycle tabs**, fixed order: Agent · Result · Sources · Share · History.
  The Agent tab holds the pinned Task Agent chat (planning, check-ins, questions)
  and every other chat in the Task. The conversation steers; the artefact and its
  evidence are the work product.
- **Run shape** (Evidence search): task landing → empty workspace → planning
  conversation → plan ready → build with check-ins → report summary → progressive
  detail → evidence table → comments → rerun as new version → re-entry with
  catch-me-up. Runs are long (minutes to tens of minutes) and cost real money.
- **Steering**: agents own method, humans own substance (options,
  recommendations, assumptions, value judgements). Steering modes change how often
  the human is involved, never that boundary.
- **Sharing**: Tasks are visible inside an organisation and can be shared
  read-only via a public view. A banner tells users not to enter sensitive or
  confidential information.
- **Environments**: local dev (Vite on :5173, FastAPI backend, mock mode with a
  scripted fixture run for Playwright), staging, and the live system at
  v3.policyatlas.uk behind OIDC (Cognito) sign-in. A public splash page with a
  waitlist form fronts the app.

## Capabilities and Constraints

- **Capabilities**: Evidence search is live. Options scoping is in build
  (feature branch). Theory of change and stakeholder mapping are in progress.
  Value for money, meta-analysis and critical review are planned.
- **Vocabulary is canonical** in `docs/specs/vocabulary.md`. Screen copy for
  entity names comes from one place, `frontend/src/lib/vocabulary.ts`; no view
  hard-codes "Task" or "Project". "Evidence base" names the collected sources,
  "Evidence search" the capability, "report" the synthesised output. Say
  "feasibility check", never "spike".
- **Stack**: React 19, TypeScript strict, Vite, Tailwind CSS 4, Radix primitives,
  TanStack Query, react-router 7, Recharts, pnpm 10+. Backend is Python 3.12,
  FastAPI, LangGraph, Postgres via Alembic. API types are generated from
  `frontend/openapi.json`; hand edits fail the drift check.
- **Reuse over mirroring** (owner ruling 2026-09-07): new capabilities use or
  modify Evidence search components. Each component is marked as-is, modified or
  new, and "new" needs a justification.
- **Copy principle** (owner): "just enough text". Labels over explainers. No
  clutter copy in product surfaces or design artefacts.
- **Model only what behaves**: no label, flag or object exists unless it changes
  system behaviour. Build light, leave seams.
- **Out of scope for v3.0**: auto-writing the final white paper, full clearance
  workflow, full RBAC, private deployments, a general-purpose agent platform.
- **Repo is public, AGPL-3.0.** Secrets, account IDs, IP allowlists and licensed
  font binaries are never committed.

## Brand Commitments

The Nesta visual identity is binding (owner, 2026-09-09). Policy Atlas is a
Nesta tool and looks like one. Source of truth:
`docs/specs/sources/evidence-base-ux/nesta-brand-tokens.md` (frozen source) and
the built components in `frontend/src/ui/brand/`.

- Electric Blue `#0000FF` is the hero colour; one hero colour per layout. Navy
  `#0F294A`, Dark Grey `#646363`, and the Nesta primary and secondary palettes.
- Buttons: 0 px radius with 45° cutouts. One primary per view. Sentence-case,
  action-oriented labels.
- Navigation: "growing underline" active state, brand group left, links right.
- Type: Zosia Display for short headlines, Averta for everything else. Both are
  licensed and never committed; every surface must render correctly on the
  fallback stack (`make font-guard` enforces this).
- Never recreate the Nesta logo; use master artwork.
- Voice: plain, direct, sentence case. Design artefacts and product copy follow
  the "just enough text" principle.

## Evidence on Hand

- Product intent and system contracts: `docs/specs/` (product.md, vocabulary.md,
  capabilities/, system/). Architecture decisions: `docs/adr/`.
- UX sources (frozen): `docs/specs/sources/` including the Evidence search UX
  handoff, hi-fi CSS, task-lifecycle and synthesis-report prototypes, splash page,
  and the Nesta brand tokens.
- Options scoping concept boards and rulings: `docs/specs/sources/options-scoping/`.
- Real fixture corpus and sanitised provider records: `backend/tests/data/`.
  Mock-mode scripted run: `frontend/src/mock/`.
- Live system at v3.policyatlas.uk for screenshots of incumbent surfaces.
- **Absent, do not fabricate**: testimonials, customer names, usage numbers,
  benchmarks, pricing, procurement claims. User-testing sessions inform design but
  no quotable findings are recorded in the repo.

## Product Principles

Owner and team, 2026-09-09. Each principle names a goal and what it means for
the product.

1. **Change behaviour, not just knowledge.** A feature that only informs is a
   research tool. A feature that shifts what gets drafted, checked or escalated
   is a policy tool. For every feature, name the behaviour it changes, not just
   the information it adds.
2. **Give control if wanted.** Let expert users steer and override the tool
   directly: filter, pin, edit or discard rather than accept outputs as final.
   Direct and guide automated searches and analyses. Identify thoughtful moments
   where users might want more control. Offer customisable search parameters
   (jurisdiction, timeline, methodology) and intuitive pin, edit and discard
   controls on generated content.
3. **Earn trust every time.** Keep absolute credibility: no hidden
   hallucinations, outputs that stand up to intense scrutiny. Every claim,
   statistic or policy example carries a mandatory, verifiable citation that
   traces back to the primary document or data. Be transparent about why the AI
   has or has not done something.
4. **Provide detail when needed.** Balance high-level summaries with the deep,
   granular evidence needed to withstand rigorous cross-examination and
   ministerial challenge. Make information quick to find and grasp. Use
   progressive disclosure from a concise executive takeaway down to raw
   transcripts, methodology notes and full unedited source excerpts. Summarise
   by default for users short on time and attention.
5. **Assist human judgement.** Co-pilot, not autopilot. Present trade-offs, risks,
   open questions and missing perspectives rather than a single answer, so the
   human makes the call. Prompt critical thinking, not passive acceptance.
6. **Share a team brain.** Break down internal silos so individual discoveries,
   annotations and curated evidence collections benefit the whole team. Provide
   shared workspaces where policy professionals collaborate and build on verified
   evidence threads, without duplicated or isolated effort.

Architectural commitments that serve these principles live in
`docs/specs/product.md`: artefacts over chat, evidence-led and inspectable,
agency versus accountability, progressive disclosure, model only what behaves,
build light and leave seams.

## Accessibility & Inclusion

Target: WCAG 2.2 AA (owner, 2026-09-09), the UK public-sector web standard.
Nesta grey on white already meets AAA; check contrast for every colour pairing
over images and coloured fills. Keyboard operation, visible focus, and text
labels beside status colour are required on every surface.
