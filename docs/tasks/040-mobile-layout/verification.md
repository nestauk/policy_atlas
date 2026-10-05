# Verification: 040-mobile-layout

Evidence for the mobile-layout slice (defects D1–D9 in [contract.md](contract.md)).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline) | fail → explained | § Baseline note; frontend-relevant parts green. |
| `make frontend-verify` (baseline) | pass | typecheck · lint · 562 tests · build |
| `make frontend-verify` (phase 1) | pass | 562 tests |
| `make frontend-verify` + `pnpm e2e` (phase 2) | pass | 564 tests; e2e 11/11 |
| `make frontend-verify` + `pnpm e2e` (phases 3–5 combined tree) | pass | 568 tests; e2e 11/11 |
| `make verify` (step-6 exit) | **pass (exit 0)** | Fully green incl. backend — the baseline `test_admin_leg` red did not reproduce (flaky; see below). |
| `make verify` (step-7 open, review gate) | pass (exit 0) | Fresh conversation, before any review lane ran. |
| `make frontend-verify` + `make verify` (step-7 fixes) | pass (exit 0) | 569 tests (568 + a listbox keyboard test) after the adjudicated fixes. |

### Baseline note (build-open, 2026-09-08)

The first full `make verify` on the branch showed 13 backend test failures. An
isolated rerun (`make test` alone, nothing else touching the shared Postgres)
cleared 12 of them — test-DB pollution consistent with the known
stranded-rows/parallel-lane failure mode (AGENTS.md § Landmines). One genuine
pre-existing red remains, unrelated to this frontend-only slice:
`tests/api/test_admin_leg.py::test_administrator_reads_a_null_organisation_row_and_an_ownerless_one`.
**Owner accepted proceeding with this red on 2026-09-08.** The slice's own gates
are `make frontend-verify` + `pnpm e2e`, green at baseline and at every phase.
At the step-6 exit the full `make verify` passed clean (exit 0) — the
`test_admin_leg` failure did not reproduce, so it reads as flaky, not broken;
worth a backlog note rather than a fix in this slice.

Environment note: this branch builds in a git worktree; `docker compose` derives
its project name from the directory, so root-Makefile DB checks need
`COMPOSE_PROJECT_NAME=policy_atlas` to find the shared dev Postgres.

## Checks beyond the build

**Live manual check (contract-pinned scope):** real backend (`make -C backend dev`,
port 8000) + real frontend (vite, port 5173), dev-issuer token minted for
`dev-user`, Playwright-driven at 390×844 / 768×1024 / 1280×800 on seeded task
`dafe0dd3` ("How to increase teacher effectiveness in Australia", succeeded run).
Screenshots in [screenshots/](screenshots/).

This table is the **phase-6 snapshot, before owner amendments A1–A6** — where an
amendment supersedes a row (D9 → A6 removed the strip; D1's row-2 arrangement →
A4), the amendments table below is authoritative for the shipped state.

| Defect | 390px observation | ≥768px unchanged |
|---|---|---|
| D1 | Header is two rows: logo+BETA, then New Task/Tasks/Projects + account icon spread across the row (`result-390-top.png`; superseded by A4 — see below) | 768/1280: single row as on `dev` |
| D2 | Bottom bar shows all five tabs with active underline; navigation to all five verified by URL (smoke log); horizontally scrollable | 768/1280: tabs in the task bar, no bottom bar |
| D3 | No outline above the report | 1280: outline sidebar present, scroll-spy intact |
| D4a | Title renders at 30px, 2–3 words per line (`result-390-top.png`) | 768/1280: 36px |
| D4b | Download button in the eyebrow row above the title — **intended at all widths** (`result-1280-top.png`) | same change, by contract |
| D5 | Section headings 20px, body 16px (`d8-expanded-390.png`) | 1280: 24/19px unchanged |
| D6 | Claim tap opens a bottom sheet, <45svh, scrollable, overlay intact (`claim-sheet-390.png`) | 1280: right slide-over unchanged (cascade-level parity verified against compiled Tailwind output) |
| D7 | Paper full-bleed, no gray frame, `px-4` (`result-390-top.png`) | 1280: gray frame + ring/shadow unchanged |
| D8 | "Expand +" renders under the collapsed summary, not beside the heading; tap expands; "Collapse −" at section end (`d8-collapsed-390.png`, `d8-expanded-390.png`) | 1280: label beside the heading as before |
| D9 | Rail replaced by one-tap strip; tap navigated to `/tasks/<id>` (Agent tab) — asserted by URL. **Superseded by A6: the strip was removed; as shipped the rail/panel are `max-md:hidden` with no stand-in** | 1280: resizable panel unchanged |

Full-chain smoke (pinned): open task → all five tabs via the bottom bar (URLs
logged) → claim citation opened → Download menu opened (PDF/Markdown,
`download-menu-390.png`). ~2 min wall time.

**Owner amendments A1–A6** (contract § Owner amendments), verified the same way:

| Amendment | 390px observation | ≥768px unchanged |
|---|---|---|
| A1 | New Task full-width, smaller type, no "Coming soon" overlap (`a1-newtask-390.png`) | 1280 layout as before |
| A2/A3 | Task and project rows wrap: title on its own line, metadata below (`a2-tasks-390.png`) | 1280 grid columns aligned as before (`a4-tasks-1280.png`) |
| A4 | Nav links left-justified row 2; account icon on the logo row, top-right (`a1-newtask-390.png`) | 1280 header identical (`a4-tasks-1280.png`) |
| A5 | Sources sub-tabs smaller; theme filter is an app-styled popover listbox, options wrap at 14px (`theme-open-390.png`) | Popover at 1280 too — **intended all-widths change**, owner call (`theme-open-1280.png`) |
| A5 rev 2 | All sources table + filter chips denser below md: one type-size step down, tighter padding, four chips on one line (`allsources-dense-390.png`) | 1280 table unchanged |
| A6 | Chat strip removed; report full-width; Agent reachable via bottom bar (`a6-result-390.png`) | 1280 rail/panel unchanged |

## End-to-end command

```
cd backend && uv run python -m policy_atlas.api.dev_issuer mint --dir .dev-issuer \
  --sub dev-user --client-id policy-atlas-dev --ttl 3600 > $SCRATCH/devtoken.txt
# dev servers already running: make -C backend dev (8000), pnpm dev (5173)
node live.mjs && node live2.mjs && node smoke.mjs   # Playwright drives, scripts in the session scratchpad
```

## Diff summary

- **Phase 1** (`55053b8`, fast-worker): report page. Outline hidden below md (D3);
  title 36→30px below md (D4a); download button moved above the title into the
  eyebrow row — all widths, owner-approved (D4b); part/section/body type steps
  down below md via the shared presentation constants and their hardcoded twins
  (D5); full-bleed paper below md (D7).
- **Phase 2** (`c7a7ffa`, lead): global NavBar wraps to two rows below md (D1);
  new `LifecycleBottomBar` reusing `LifecycleBar` and the same computed item
  list, bottom-pinned, `overflow-x-auto`, print-hidden, safe-area padded (D2).
  **Flagged deviation (minor):** `PublicTaskShell.tsx` was not in the contract's
  likely-touched list but renders the same task bar + `LifecycleBar` — the same
  D2 defect — so it received the same treatment; public share links on phones
  are a primary mobile case. No behaviour beyond D2's fix.
- **Phase 3** (`dd1f7ae`, deep-reasoner): `SheetContent` class-only change —
  bottom sheet below md, `max-h-[45svh]`; both consumers inherit (D6). Variant
  cascade order verified against the compiled tailwindcss@4.3.3 output.
- **Phase 4** (`651f8bd`, fast-worker): expand/collapse label hidden beside the
  heading below md; mobile-only secondary buttons after the summary and at the
  section end; heading row stays the sole `aria-expanded` toggle (D8).
- **Phase 5** (`1ca6a65`, deep-reasoner): chat rail and expanded panel hidden
  below md; one-tap `MobileAgentStrip` links to the Agent tab; no viewport JS
  (D9). **The strip was removed by A6 — no `MobileAgentStrip` ships**; below md
  the rail/panel carry `max-md:hidden` with no stand-in. Note: a `?chat=` deep
  link opened on a phone shows no panel — the conversation is reachable via the
  Agent tab (accepted, within D9's contract).
- **Amendments A1–A6** (lead, owner-directed 2026-09-08): New Task mobile type +
  full width (A1); task/project rows wrap to title + metadata lines (A2/A3);
  nav links left-justified with the account icon on the logo row (A4); smaller
  Sources sub-tabs and the Key-theme filter as a Popover listbox at all widths,
  plus (rev 2) a denser All-sources table/chips below md (A5); the D9 mobile strip
  removed — the bottom bar's Agent tab supersedes it (A6). `make frontend-verify`
  green (568 tests) after the amendments.

## Review findings

Step 7 ran 2026-09-08 in a fresh conversation. Gate: full `make verify` green
(exit 0) before any lane; the baseline `test_admin_leg` red did not reproduce
(reads as flaky — backlog note, not a slice fix). Lanes (all-Claude build, so
Codex is the family flip): contract verifier (pinned Opus, read-only) ·
`/code-review medium` · security finder (`/security-review` flow) · Codex
adversarial. Review diff excluded `docs/tasks/040-mobile-layout/**`.
This slice has no model inference, so no traces exist; the live-trace lane's
analog was a lead content-read of the screenshots against the claims table
(pre/post-amendment states confirmed).

**Convergent (3 lanes + lead diff-read) — adopted, fixed:**

- Theme-filter popover listbox had no keyboard interaction model (Codex MAJOR ·
  code-review · contract-verifier F6): no arrow keys, focus stayed on the
  trigger, `aria-label` masked the selected value, and the visible label was an
  inert span (the removed `<label>`+`<select>` opened on label click). Fixed in
  `SourcesView.tsx`: arrows/Home/End move focus, open focuses the selected
  option, real `<label htmlFor>`, `aria-labelledby` announces label + selection;
  keyboard test added. Residual (deferred): no type-ahead.

**Single-lane — adopted, fixed:**

- Mobile Expand/Collapse buttons lacked `aria-expanded` and were copy-pasted
  4× (Codex MINOR + code-review): extracted `MobileDisclosureToggle` (carries
  `aria-expanded`), used at all call sites.
- `ReferencesSection` missed the D8/D5 sweep (code-review): every collapsible
  section but References had the mobile toggle and body step-down. Same
  treatment applied — adjudicated as the same defect on a twin surface (the
  PublicTaskShell precedent), not scope growth.
- F3 (contract verifier): `gap-x-5` in `Nav.tsx` was the one unconditional
  class — at ≥md it truncated the task-bar title 20px earlier than `dev`.
  Scoped to `max-md:gap-x-5`; the global bar's links↔account gap restored via
  `md:mr-5` on the links div, conditional on the account menu rendering, so the
  signed-out desktop DOM is untouched. Desktop-unchanged invariant now holds
  with no unlisted exceptions.
- `AnnotatedProse` inlined the exact `REPORT_BODY_CLASS` string 2× while the
  same diff updated the constant (code-review): now uses the constant.
- F1/F4/F5 (contract verifier, doc-vs-built): the D9 row and phase-5 summary
  described a `MobileAgentStrip` that A6 removed (zero hits in `frontend/src`);
  the D-table cited pre-amendment screenshots unlabelled; the diff summary
  called the popover a "capped select". All corrected above; the D-table is now
  labelled a phase-6 snapshot.
- F2 (contract verifier): A5 rev 2 (denser All-sources below md, commit
  `76c5502`) was owner-directed but never written into the contract — recorded
  in the contract's A5 row.

**Adopted as gaps (recorded, not fixed here):** F7 (Agent-tab mobile rendering
unevidenced) → Known unverified; shared-listbox seam, type-ahead residual, F10
(History tab reads clipped on first paint; scrollable per D2, cosmetic) →
Deferred work.

**Declined, with reasons:**

- F8 (`aria-label="Task stages"` outside `vocabulary.ts`): vocabulary.ts
  governs renameable product labels; this is aria-only copy, no rename
  occurred, rubric 6 holds. Convention question for the owner, not a defect.
- PublicTaskShell computes `publicLifecycleTabs(base)` twice (contract-verifier
  nit; code-review independently dropped the same finding): public tabs carry
  no marker logic, so the fork-hazard the "compute once" rule guards against
  does not exist there.
- Codex NITs on class-token/DOM-duplication test assertions: JSDOM cannot
  apply responsive CSS, so token assertions are the honest ceiling for unit
  tests; the compensating controls are the compiled-cascade check and the
  pinned live manual check. Coverage gap accepted, not a defect.

**Fake-done check on the step-7 fixes:** no test deleted/weakened — the
rewritten queries pin *more* (accessible names, `aria-expanded` values) and a
keyboard test was added; no error swallowed; no stub. `make verify` re-run
green after fixes (see Commands run).

**Flagged deviations — both confirmed as-is:** PublicTaskShell (same D2 defect,
same component, no behaviour beyond D2; contract-verifier concurs "within the
contract's vocabulary") and `?chat=` on mobile (contract § Constraints permits
a CSS-hidden alternative rendering; panel stays mounted, no layout gap).

**Lane economics:** reasoning-class ≈190K tokens (contract verifier 114K ·
security finder 56K · Codex 18K), no fast-worker fan-out; within the ≤250K/
≤500K split. `/simplify` skipped, justified: `/code-review medium` ran the
reuse/simplification angles and its three cleanup findings (shared toggle,
constant reuse, listbox seam) were applied or deferred above — a second
same-family pass would re-read the same diff for nothing.

## Rubric status

| # | Status |
|---|---|
| 1 | ✅ Holds — every defect anchored to shipping code by the contract verifier; D-table now labelled as the phase-6 snapshot. |
| 2 | ✅ Holds after F3 fix — compiled-cascade proof that every `max-md:` rule postdates its base utility; the one unconditional class (`gap-x-5`) removed; D4b + A5 remain the only all-widths changes, both owner-approved. |
| 3 | ✅ `make verify` green at step-6 exit and re-run green after step-7 fixes; live check recorded with screenshots at 390/768/1280. 768px evidence is one screenshot (header/task bar) — sheet/panel parity at 768 rests on the cascade proof. |
| 4 | ✅ Zero JS viewport logic (grep-verified by the contract verifier). |
| 5 | ✅ 21 files, all `frontend/src/**` + task docs; no deps/schema/auth/CI. |
| 6 | ✅ Generated files and `vocabulary.ts` untouched; no label renamed. |
| 7 | ✅ No test deleted/skipped; counts rose in every touched suite; D2/D9 covered; step-7 fixes added a keyboard test and aria assertions. |
| 8 | ✅ Bottom bar is a `<nav class="print-hide">` — hidden twice over by `@media print`; `font-guard` green inside `make verify`. |
| 9 | ✅ Evidence recorded; gap list extended with review findings (F7, F10, listbox seam); flow to `docs/deferred.md` is step 8. |
| 10 | ✅ This section — four lanes ran, findings adjudicated, fixes applied and re-verified. |

## Intent & assumptions

- "Mobile" = viewport < 768px (`max-md:`); iPad portrait (768px) renders desktop.
- Desktop-unchanged invariant held by construction (additive `max-md:`/`md:hidden`
  classes only), checked visually at 768/1280px and by the unchanged e2e suite.

## Known unverified items

- Real device (iOS Safari) pass — checked only in Chromium device emulation;
  `env(safe-area-inset-bottom)` padding on the bottom bar is untested on hardware.
- `LiveArtefactBody` (streaming report) mobile rendering — class changes applied,
  not visually driven (no live run was streamed during the check).
- The Agent tab's own mobile rendering (the workspace route) — A6 makes it the
  only way into the conversation on a phone, but the live check asserted the
  bottom-bar navigation by URL only; no 390px screenshot of the workspace
  itself (review finding F7).

## Public safety

Screenshots show seeded demo data only ("teacher effectiveness in Australia").
No secrets, tokens redacted (scratchpad only), no source text beyond what the
product renders.

## Review handoff (step-7/8 inputs)

- Executor provenance (family-flip context): phase 1 fast-worker · phase 2 lead ·
  phase 3 deep-reasoner · phase 4 fast-worker · phase 5 deep-reasoner · phase 6
  lead. All Claude-family — Codex review at step 7 is the family flip.
- Adjudication items: the PublicTaskShell scope extension (phase 2) and the
  `?chat=`-on-mobile behaviour (phase 5), both flagged above.
- Diff-scoping: `docs/tasks/040-mobile-layout/**` is evidence, not product code.
- **Knowledge candidates** (014 retro):
  - Worktree + docker compose: the compose project name derives from the
    directory, so a second worktree silently loses the shared db
    (`COMPOSE_PROJECT_NAME` fixes it); the same root cause made the first
    `make verify` unrepresentative — diagnose baseline reds with an isolated
    rerun before believing them.
  - Tailwind v4 `max-md:` variants make a strict desktop-unchanged invariant
    cheap: additive classes only; `max-md:starting:*` stacks correctly and can
    be proven from the compiled cascade rather than eyeballed.
  - The lifecycle tab list must be computed once and rendered twice (NavBar +
    bottom bar) or the pending-check-in marker logic forks.
  - Radix Dialog side-sheets convert to bottom sheets with classes alone —
    no `side="bottom"` variant needed; both consumers inherited.

## Deferred work

To flow to `docs/deferred.md` at step 8:

- List pages (Tasks/Projects), splash, and the Sources sub-tab strip ("All
  sources" clips slightly at 390px): no dedicated mobile pass (contract § Out
  of scope).
- 768px exactly (iPad portrait): the task bar title + five tabs were already
  tight before this slice (pre-existing, out of scope) — visible in
  `screenshots/result-768-top.png`.
- Expanded chat panel on mobile is hidden, not redesigned; a real mobile chat
  layout is a future slice.
- Popover-as-listbox is now hand-rolled in three places (`FilterSelect` in
  SourcesView, `ProjectPicker` in NewTaskView, the pickers in
  workspace/PlanDocument) with drifting details — a shared `ui/` listbox
  component is the seam (step-7 code-review finding; keyboard nav was fixed in
  `FilterSelect` only).
- `FilterSelect` keyboard support covers arrows/Home/End/Enter but not the
  native `<select>`'s type-ahead; add if AT users ask.
- The bottom bar's last tab ("History") sits flush against the 390px viewport
  edge on first paint — scrollable as D2 requires, but reads clipped; cosmetic
  (review finding F10).
