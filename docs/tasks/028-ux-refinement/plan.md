# Implementation plan: 028-ux-refinement

> **Status:** rev 2 (2026-08-04) — plan-phase adversarial review DONE
> (codex job `task-msdwl2bh-boncq5`: 39 findings, 35 MAJOR, **39/39
> adjudicated in** — [adversarial-review-plan.md](adversarial-review-plan.md);
> rev 2 is the full rewrite it demanded). Plan approved: _pending — owner 🛑_.
> Contract: [contract.md](contract.md) (APPROVED 2026-08-04; two mechanism
> corrections from this lane folded — approval-at-ready seam, live-check
> estimate). ADR 0028 drafted (flips Accepted at this gate).
>
> **Fresh build conversation re-grounds from:** contract.md · this plan ·
> [api-additions.md](api-additions.md) · the three binding mock-ups ·
> [design-inputs.md](design-inputs.md) · both adversarial records ·
> `docs/specs/system/web-api.md` · `docs/specs/system/provenance-grounding.md`
> § Summaries · `docs/tasks/027-frontend-uplift/contract.md` +
> `verification.md` (substrate invariants) · `docs/agentic-ops/harness.md`
> (routing) · [rubric.md](rubric.md). Run `make verify` first (T0).
>
> **Plan-gate items needing explicit owner sign-off:** (i) GET /plan serves
> a newer-than-approved draft with honest status (read-behaviour change —
> the stale-start fence's other half); (ii) live check re-estimated at
> ~45–60 min across two legs; (iii) sizing ~24–29 executor-days.

## Implementation pins (lead-designed; briefs reference, don't re-derive)

1. **Substrate-out build order** (027 pin 1): every backend phase that
   changes the API ends with `make openapi && pnpm gen`, committed,
   drift-check green (phases A, C, D). Frontend substrate after D; views
   after E.
2. **Part wire** (finding 5, contract): part persists verbatim in
   `planning_transcript.part` — {id, step_label, title, body?, chips:
   [{label, kind: text|date_range|country_list, value}], options: [{id,
   label, sub, primary, reason?}]}. Confirmations are canned turns
   referencing part-id + option-id. **Rehydration rules** (F34): the
   latest proposal per part-id wins; a confirm referencing a superseded
   proposal renders as plain prose (honest degrade, never mis-binds);
   reopening a part re-proposes it in a new turn; confirmations of other
   parts stay valid unless re-proposed. Old rows (part=null) render as
   prose. Named tests: replay-with-superseded-confirm ·
   reopen-then-re-confirm · null-part rendering.
3. **Ready/approve/start seam — as-built-correct** (F13–F15, F33):
   approval happens when a turn reaches ready (planning.py persists the
   approved row) — unchanged. New: the approved row records
   `source_turn_index` in its payload; **any newer completed turn
   supersedes readiness** — `GET /plan` serves the newer draft with
   `status: draft` (named read-behaviour change, sign-off item i);
   `POST /runs` 409s `plan_stale` when the approved plan's
   `source_turn_index` < the newest completed turn. The plan card demotes
   from ready on those statuses. Start stays dispatch-only (no atomicity
   claim; the fence is the turn linkage).
4. **Section budget** (F32): additive optional
   `OrchestrationPlan.section_budget` + `PlanDraft`/`PlanOut` mirrors.
   Compile: Quick look → 3; Standard/Deep → null (today's behaviour,
   SECTION_CAP-bounded); free text compiles 2–8. Threads via a new
   synthesis branch in `_directive_delta` AND via the P4
   `propose_sections` call (F10 — the preview must honour the same
   budget). Budget counts ordinary sections; key findings + conclusions
   structural. `time_band` table gains one row class: small-budget
   (≤4) → "~5–10 min" at rapid/landscape and standard; other cells
   unchanged — the table stays deterministic and enumerated in code.
5. **Steering taxonomy change-set** per the binding record: floors
   re-homed/slimmed + plain-language static copy + depth-conditional
   floors + Groups lattice point (after_group, deep-only,
   `grouping_flag_triggers`) + mode table with unattended default (every
   moderate-default test updated deliberately, named in the diff) + P1
   search-review upgrade (bundle carries per-backend counts, queries,
   sample titles — F2) + rename edit-delta (P2-only, batched into the
   single response as validated option params; **display-name update on
   the id-keyed record** — see pin 7) + **promotion keeps lattice
   identity on BOTH paths** (F16: runner.py after-boundary ~1439 and
   before-boundary ~1654) + P4 primary submits the **displayed ordinary
   list** as the sections directive (F17: grammar unchanged {title,
   focus}; structural rows display-only; the bundle carries ordinary
   proposals only).
6. **One validator, three producers — the seam signature** (F18–F19):
   extract the author-blind validation into one function taking (delta,
   component, ctx) where ctx = {backend_scope, current_components,
   completed_components, rerun_surface}. Call sites: router compile
   (as-built ctx), watch authoring (boundary ctx), option apply
   (`_offered_option` grows a ctx reconstructed from pause payload +
   project state). Authored options: ids assigned at authoring; validated
   pre-persist (drop + log + event); projected into `options` with
   `suggested: true` + `why`; revalidated at apply; unknown directive
   keys always a loud refusal.
7. **Theme identity** (F8, F37): characterise assigns `theme_id` (uuid)
   at persist; theme tags carry `theme_id` alongside name (additive
   column); `ThemeOut.theme_id` exposed; the sources `theme` filter binds
   to id via id-keyed membership; rename updates the display name on the
   characterisation record only (id-keyed reads unaffected; bookmarks
   survive). Lands in A (identity + exposure); D adds the rename delta.
8. **Summaries runtime — the 027 emitter precedent** (F20–F21, F35–F36):
   summariser + judge run AFTER the synthesise component transaction
   commits, in short standalone transactions per block (+ one artefact
   summary anchored on conclusions); provider failures degrade-and-disable
   (`summary_status: failed`, structlog, never a component failure).
   Backend seam: two new protocol methods (`write_block_summary`,
   `judge_summary`) with stub + live implementations and usage accounting.
   Projection: `SectionOut.summary` = the section's single block's summary
   (as-built one block per section; a multi-block section omits honestly —
   recorded seam). Named tests: post-commit visibility · rollback isolation
   · degrade-on-provider-failure · failed-marker rendering.
9. **Prompt surfaces lead-authored, versioned, prompt-guard same-commit**:
   planner_v6 · synthesise_sections_v3 (flow + budget) · key-findings rev ·
   summariser_v1 · summary_judge_v1 · watch-authoring rev (reader framing +
   grammar vocabulary).
10. **Sort spec** (F38): nulls last · case-insensitive title · status by
    rank map · default asc (year desc) · stable tie-breaker = existing
    ingestion id order · unknown sort/order → 422.
11. **Type scale** = `index.css` tokens (GOV.UK pattern, body ≥16px);
    naming/copy land in vocabulary modules; honesty copy trimmed never cut.

## Phases (executor per harness ladder; est. days; gates)

| # | Content | Executor | Est | Gate |
|---|---|---|---|---|
| 0 | Build-open baseline | lead (one command) | 0.2 | **full verify** |
| A | Migration (5 columns: transcript.part · block.summary+status · artefact.summary+status; + theme-tags theme_id) · theme identity (pin 7) · read-model/API additions it can fully serve (sort/order/theme+spec pin 10 · scope=cited · summaries fields · ThemeOut.theme_id · PlanDraft/PlanOut budget mirrors) · client regen | **codex** (annex + pins are the brief) | 3 | **full verify** (schema) |
| B | planner_v6 (lead) · part persistence/rehydration per pin 2 · ready/approve seam per pin 3 | prompt: **lead** (prompt-bearing) · machinery: **codex** | 3.5 | verify-fast |
| C | synthesise_sections_v3 + key-findings rev + summariser + judge prompts (lead) · budget threading incl. P4 preview (pin 4) · summaries runtime (pin 8) · time_band row | prompts: **lead** · runtime: **codex** | 4 | **full verify** (chain-adjacent) + client regen |
| D | Steering change-set (pin 5) · validator seam (pin 6, signature lead-designed) · CheckInOut.bundle + authored exposure · client regen | **codex**, lead adjudicates the diff (024-core caution) | 4.5 | **full verify** (runner-adjacent — F12) |
| E | Frontend substrate: type tokens + sweep · composer · naming/copy maps · 50/50 | scale+copy-map design: **lead** (taste) · sweep/composer: **fast-worker** (mechanical vs pin 11) | 2 | verify-fast |
| F.1 | Planning flow views: part cards · editable chips · inline plan card + demotion states · centred chat (+ fixtures & vitest in-phase) | **lead** (product surface, standing owner routing) · fast-worker: fixture scaffolds, chip editor plumbing | 3 | verify-fast |
| F.2 | Artefact page: contents sidebar/scroll-spy · disclosure + summaries (+failed marker) · bullets render · gathered section (cited plots + compact funnel line + References collapse — lane fixes 19) · six-tab invariant | **lead** · fast-worker: chart/plumbing subtasks | 3 | verify-fast |
| F.3 | Sources + themes: sortable table (Origin retained non-sortable — fix 20) · theme filter by id · "Key themes"/"Documents" labels | **fast-worker** (spec'd by pin 10 + record) · lead review | 1.5 | verify-fast |
| F.4 | Check-in cards: bundle renders per point · grouped options + free-text row + compile-confirm mini-thread · suggested block · pause salience set · rename UI · inline section editing | **lead** (product surface) · fast-worker: enumerated card subcomponents | 3 | verify-fast |
| F.5 | Signposting · settings-in-header (committed item) · small wins (listed at this gate) | **fast-worker** vs the list · lead adjudicates | 1 | verify-fast |
| G.1 | Backend test matrix (F23/F31): mode-table permutations · floors per point · promotion both paths · rename atomicity · authored validation drop/log/event · budget threading + band table · sort determinism · theme-id filter · summary states · stale-plan fence | **fast-worker** scaffolds from this named matrix · **codex** for the runner-adjacent cases | 2.5 | verify-fast |
| G.2 | e2e update + fe-api-smoke names · live legs A/B · cost spot-checks (key-findings A/B · summariser+judge delta · sections before/after) · verification.md (incl. all six prompt diffs — fix 18) · deferred.md updates (summaries seam discharged; new seams) · ADR flip | evidence + adjudication: **lead** (judgment; the step-6 exit is the lead's gate) · fast-worker: e2e mechanics | 2.5 | **full verify** (step-6 exit) |

Total ≈ **24–29 executor-days**. Lead marks justified inline: prompts
(hard rule) · taste-bearing product surfaces (standing owner routing) ·
diff adjudication + step-6 evidence (judgment) · phase 0 (one command).

## Live check (step 6; ~45–60 min wall — sign-off item ii)

**Leg A — Quick look, unattended** (~15 min): full planning slow-path
(three parts, chip edit incl. date range, ready card details-open, Start),
zero pauses, short report (3 ordinary + structural), honest band, summaries
minted+verified and shown collapsed; composer Enter/Shift+Enter/growth;
50/50 at run; key-findings bullets with working claim popovers.
**Leg B — Quick look, FREQUENT (requested in words)** (~25–35 min):
compound opening fast-path · restart-mid-planning rehydration · P1 search
review (bundle: counts/queries/titles) · P2 themes + one rename + one
free-text steer through compile→confirm · P3 reading list · P4 displayed-
list submit + one inline section edit · pause salience on every tab ·
answered echoes in thread · a legacy artefact renders the fallback with
marker. Groups/deep surfaces: mock e2e + G.1 matrix (bounded live scope —
stated honestly). Plus the three cost/quality spot-checks (ride the legs
where possible). Budget allowance ~$40–80 (incl. regenerate-on-fail and
artefact summaries).

## Review-stack handoff (step 7 — scope pinned now)

Security lane: part-card payload rendering (scrub over part/chips/options)
· authored-option exposure + validation (injection via why/label; delta
grammar abuse) · sort/theme param validation · summary rendering (judged
text is still model-authored — scrub + display invariant). Diff-scoping:
exclude generated client + lockfiles + mock-up HTML; review the six prompt
diffs explicitly.

## Risks (attack surface for the build)

Unattended-default test fallout breadth · rehydration edge cases (pin 2
tests are the net) · summaries cost/latency on deep runs (with retries and
artefact grain) · sections_v3 honouring budget without degrading flow ·
promotion rework blast radius (both paths) · GET /plan behaviour change
ripples into 025/027 tests that assume approved-first.
