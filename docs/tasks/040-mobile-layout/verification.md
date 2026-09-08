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

| Defect | 390px observation | ≥768px unchanged |
|---|---|---|
| D1 | Header is two rows: logo+BETA, then New Task/Tasks/Projects + account icon spread across the row (`result-390-top.png`) | 768/1280: single row as on `dev` |
| D2 | Bottom bar shows all five tabs with active underline; navigation to all five verified by URL (smoke log); horizontally scrollable | 768/1280: tabs in the task bar, no bottom bar |
| D3 | No outline above the report | 1280: outline sidebar present, scroll-spy intact |
| D4a | Title renders at 30px, 2–3 words per line (`result-390-top.png`) | 768/1280: 36px |
| D4b | Download button in the eyebrow row above the title — **intended at all widths** (`result-1280-top.png`) | same change, by contract |
| D5 | Section headings 20px, body 16px (`d8-expanded-390.png`) | 1280: 24/19px unchanged |
| D6 | Claim tap opens a bottom sheet, <45svh, scrollable, overlay intact (`claim-sheet-390.png`) | 1280: right slide-over unchanged (cascade-level parity verified against compiled Tailwind output) |
| D7 | Paper full-bleed, no gray frame, `px-4` (`result-390-top.png`) | 1280: gray frame + ring/shadow unchanged |
| D8 | "Expand +" renders under the collapsed summary, not beside the heading; tap expands; "Collapse −" at section end (`d8-collapsed-390.png`, `d8-expanded-390.png`) | 1280: label beside the heading as before |
| D9 | Rail replaced by one-tap strip; tap navigated to `/tasks/<id>` (Agent tab) — asserted by URL | 1280: resizable panel unchanged |

Full-chain smoke (pinned): open task → all five tabs via the bottom bar (URLs
logged) → claim citation opened → Download menu opened (PDF/Markdown,
`download-menu-390.png`). ~2 min wall time.

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
  (D9). Note: a `?chat=` deep link opened on a phone shows no panel — the
  conversation is reachable via the Agent tab (accepted, within D9's contract).

## Review findings

_Added at step 7._

## Rubric status

_Added at step 7._

## Intent & assumptions

- "Mobile" = viewport < 768px (`max-md:`); iPad portrait (768px) renders desktop.
- Desktop-unchanged invariant held by construction (additive `max-md:`/`md:hidden`
  classes only), checked visually at 768/1280px and by the unchanged e2e suite.

## Known unverified items

- Real device (iOS Safari) pass — checked only in Chromium device emulation;
  `env(safe-area-inset-bottom)` padding on the bottom bar is untested on hardware.
- `LiveArtefactBody` (streaming report) mobile rendering — class changes applied,
  not visually driven (no live run was streamed during the check).

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
