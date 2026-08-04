# Implementation plan: 028-ux-refinement

> **Status:** rev 1 (2026-08-04) — drafted after the contract-stage lane
> (23/23 adjudicated, adversarial-review-contract.md). Plan-phase
> adversarial review: _pending_ · Plan approved: _pending — owner 🛑_.
> Contract: [contract.md](contract.md) (APPROVED 2026-08-04). Annexes:
> [api-additions.md](api-additions.md) (the enumerated additive surface) ·
> binding design records `mockup/planning-stage.html` +
> `mockup/checkin-taxonomy.html` + `mockup/tab-ia-options.html` ·
> [design-inputs.md](design-inputs.md). Tier 3 → ADR 0028 due; migration
> downgrade tested; security lane scoped (part-card payload rendering ·
> authored-option exposure/validation · sort/theme param validation ·
> summary rendering).

## Implementation pins (lead-designed; briefs reference, don't re-derive)

1. **Build order is substrate-out** (027 pin 1): backend phases regenerate
   the client at their gates (`make openapi && pnpm gen`, committed,
   drift-check green). Frontend substrate only after C; views after E.
2. **Part wire** (contract strand 3 + lane finding 5): the part proposal
   persists verbatim in `planning_transcript.part` (nullable JSONB) — {id,
   step_label, title, body?, chips: [{label, kind: text|date_range|
   country_list, value}], options: [{id, label, sub, primary, reason?}]}.
   Confirmation turns are canned messages referencing part-id + option-id;
   confirmed state rehydrates from the turn sequence — no server-side
   confirmation state. Old rows (part = null) render as prose.
3. **Start safety** (lane finding 6): Start = approve-current-draft +
   dispatch in one request (the as-built approve+start seam); the ready
   plan card demotes when any part reopens (client state from the turn
   sequence + planner draft status); the start path 409s if the draft it
   would approve is older than the newest completed turn.
4. **Section budget** (lane finding 7): additive optional
   `OrchestrationPlan.section_budget` (+ `PlanDraft`/`PlanOut` mirrors),
   compiled from the thoroughness preset (Quick look → 3), threaded via a
   NEW synthesis branch in `_directive_delta`, honoured by
   `synthesise_sections_v3` and enforced as the cap (SECTION_CAP stays the
   ceiling). Budget counts ordinary sections only; key findings +
   conclusions are structural. `time_band` derivation extends: band =
   f(search_effort, analysis_depth, section_budget).
5. **Steering taxonomy lands as one coherent backend change-set** per the
   binding record: floors re-homed/slimmed + static copy rewrite +
   depth-conditional floors + Groups lattice point (after_group, deep-only,
   `grouping_flag_triggers` as its fired set) + mode table with
   **unattended default** (every existing moderate-default test updated
   deliberately, named in the diff) + P1 search-review upgrade (coverage
   record + sample titles in the bundle) + rename edit-delta (P2-only,
   batched into the single response as validated option params) +
   **promotion keeps lattice identity** (runner.py:1439–1460 rework) +
   P4 primary submits the displayed sections list.
6. **Authored-option pipeline** (lane finding 12 + owner substrate ruling):
   assign ids at authoring; validate every authored delta through the
   author-blind grammar at authoring time (drop + log + event on
   non-compile); project into `options` with `suggested: true` + `why`;
   revalidate at `_offered_option` apply time; unknown directive keys are
   loud refusals. One grammar, one validator, three producers.
7. **CheckInOut.bundle** (lane finding 11): a typed, scrubbed per-point
   projection — themes[{theme_id, name, size}], shortlist[{title,
   stratum}], proposed_sections[{title, focus}], groups[{name, size}],
   coverage counts. Only fields the cards render; nothing speculative.
8. **Summaries runtime** (strand 13, spec-bound): block summary minted as a
   trailing step of block production (summariser prompt), judged
   (faithfulness prompt, bounded regenerate-on-fail), stored in
   `block.summary` + `summary_status` (excluded from `content_hash`);
   artefact summary minted after sections complete, anchored on
   conclusions. Fallback render carries the failed/absent marker. Cost
   delta measured in the live check.
9. **Prompt surfaces are lead-authored, versioned, prompt-guard-pinned in
   the same commit**: planner_v6 (parts, no steer-walk, no default upper
   date bound, recency floor as chip) · synthesise_sections_v3 (narrative
   flow + budget) · key-findings bullets rev · summariser_v1 ·
   summary_judge_v1 · watch-authoring rev (reader framing + grammar
   vocabulary constraint).
10. **Type scale** = tokens in `index.css` (GOV.UK pattern; body ≥16px),
    swept via the copy maps; naming pass lands in vocabulary modules; the
    copy diet honours the standing exemption (honesty copy trimmed, never
    cut).

## Phases (executor marks per harness.md ladder; default = delegate)

| Phase | Content | Executor | Gate |
|---|---|---|---|
| 0 | Build-open baseline `make verify` | lead (inline — one command) | full verify |
| A | Migration (3 additive columns) + read-model/API additions per api-additions.md + client regen | **codex** (machine-verifiable spec; annex is the brief) | **full verify** (schema) |
| B | planner_v6 (lead) + part persistence/rehydration + Start safety + canned-confirm turns | prompt: **lead** (prompt-bearing) · machinery: **codex** (pins 2–3 are the brief) | verify-fast |
| C | synthesise_sections_v3 + key-findings rev + summariser + judge (lead) + budget threading + summaries runtime + time_band | prompts: **lead** · runtime: **codex** (pins 4, 8) | **full verify** (chain-adjacent) |
| D | Steering taxonomy backend (pin 5) + authored pipeline (pin 6) + bundle projection (pin 7) | **codex** (binding record + pins are the brief; lead adjudicates the diff — 024-core caution) | verify-fast |
| E | Frontend substrate: type-scale tokens + sweep, composer, naming/copy maps, 50/50 | tokens/sweep/composer: **fast-worker** (mechanical against pin 10) · scale + copy-map design: **lead** (taste-bearing) | verify-fast |
| F | Frontend views: planning flow (part cards, editable chips, inline plan card, centred chat) · artefact page (contents sidebar, disclosure, summaries, gathered section, bullets render) · sources table · check-in cards (bundle renders, grouped options, free-text row, pause salience) · signposting · settings-in-header · small wins | **lead** (product surfaces — 025/027 owner routing; Fable frontend capability) with **fast-worker** for enumerated mechanical subcomponents | verify-fast per sub-phase |
| G | Fixtures (sanitized) + vitest for judgment-bearing pieces + e2e update + fe-api-smoke names + acceptance evidence | **fast-worker** (scaffolding from contract's named test list) · adjudication: **lead** | **full verify** (step-6 exit) + live legs A/B + cost spot-checks |

Lead-mark justifications: prompts are prompt-bearing (AGENTS.md hard rule);
E-scale/F-views are taste-bearing product surfaces under the standing owner
routing; phase-0 is one command. Everything else delegates.

## Live check (step 6, pinned in the contract)

Leg A — Quick look, unattended, end-to-end: no pauses, short report (~3
ordinary sections), honest band, summaries minted+verified, collapsed
sections show them. Leg B — standard preset, "review key stages" requested:
sequential planning replay (parts, compound free-text mid-flow, chip edit,
restart-mid-planning rehydration), P1 + P4 cards (bundle renders, displayed
list submitted), pause salience on every tab, inline section edit, sources
sort/theme, artefact nav. Plus: key-findings cost/quality spot-check,
summariser+judge cost delta, before/after section-list comparison
(sections_v3). ≈25–30 min wall.

## Sizing

~22–26 executor-days (027 was 19–21 at comparable breadth; 028 adds six
prompt surfaces and the steering change-set but has no new table and a
smaller migration). Live spend: ~4–6 full runs (2 live legs + prompt
spot-checks) ≈ $30–60.

## Risks the reviewer should attack

Unattended-default test fallout breadth (mode-table flip touches many
steering tests) · part-wire rehydration edge cases (confirm-turn references
to superseded parts) · summaries cost/latency on deep runs (10 sections ×
2 calls) · sections_v3 honouring budget without degrading flow · the
promotion-identity rework's blast radius in runner.py.
