# Implementation plan: 024-steering-surface

> Status: drafted (2026-07-16) — plan-stage adversarial review pending ·
> plan 🛑 pending. Binds to contract rev 4 (as amended: adversarial
> adjudication + owner cost adjudication) and the design annex
> [steerability-refinement.md](steerability-refinement.md). Executor
> reality: **Codex quota exhausted (verified live 2026-07-16)** — every
> `codex` default routes **codex→deep-reasoner**; revert to codex if
> credits land (substitutions logged in verification.md).

## Implementation pins (lead-designed; briefs reference, don't re-derive)

- **`capability_run` DDL** (decision 2): `capability_run_id UUID pk` ·
  `project_id UUID FK project` · `evidence_scope_id UUID` · `capability
  TEXT NOT NULL` (check: `'evidence_base'`) · `plan_id UUID` +
  `plan_version INT` · `status TEXT` (check: running/succeeded/degraded/
  failed/aborted) · `session_id UUID NULL` · `started_at/ended_at
  timestamptz`; composite FK `(evidence_scope_id, project_id)` →
  evidence_scope (the selection_result precedent) + `UNIQUE
  (capability_run_id, project_id)` so `runs` gains a **composite** FK
  `(capability_run_id, project_id)` — the schema's cross-project-guard
  convention (review m2). One alembic revision, explicit ids,
  roundtrip-tested.
- **Event vocabulary**: `steering.pause` · `steering.decision` ·
  `steering.rejected` · `steering.refused` · `component.skipped` ·
  `agent_judgement_routed`. Every payload carries `capability_run_id`,
  `plan_id`, `plan_version`, `boundary`; decision payloads add
  `decided_by` (`user|orchestrator|standing_default`), `authored_by`,
  `user_text` (verbatim, when prose given), `interpreted_action`,
  `confirmed`, execution profile, `rerun_mode`
  (`additive|replacement|null`); **mode changes ride `steering.decision`
  (`response: mode_change`)** — every decision surfaces (review N3).
  Attachment: the run the event is about (`after_component`); else
  most-recent attempted run id — and (review M2, `event_log.run_id` is
  NOT NULL) the invariant: **no steering event is emitted before the
  first component run exists**; the watch's earliest emission is
  acquire's *output* boundary, and Task 2 asserts a resolved run_id on
  every emission. Transactional pairing: decision/skip/re-run with
  their state change; pause/refused/rejected standalone.
- **Criteria-changed re-screen — IN via generation supersession (owner
  expanded the schema gate at the plan gate, 2026-07-16, reversing the
  B1 exclusion).** Review B1 stands as the feasibility fact: the
  no-schema recency-first pin was infeasible (`uq_ssr_scope_source_stage`
  partial UNIQUE blocks the fresh stage-1 INSERT, schema.py:268;
  `_load_stage1_docs` skips screened docs, screen.py:357; the column is
  `screened_at`). Schema-backed design (lead): **(i)**
  `source_screening_result.screen_generation INT NOT NULL DEFAULT 0`;
  **(ii)** the partial unique index widened to `(evidence_scope_id,
  project_source_snapshot_id, screen_stage, screen_generation) WHERE
  status != 'failed'`. Re-screen (a replacement re-run) writes fresh
  rows at `generation = max+1`; old rows immutable;
  `effective_screen_rows` orders **generation DESC, stage DESC**
  (stage-1→stage-2 flow and demote-only intact within a generation —
  what they always meant); `_load_stage1_docs`'s skip is bypassed only
  under the explicit re-screen re-run. Consumers move in lockstep
  (characterise ×2, select eligibility, screen skip logic) — interface
  unchanged, they consume the function. Stage-2 rows: a re-screen
  re-runs stage 2 at the new generation only where the P2 option asks
  for it; otherwise the new generation is stage-1-only and effective
  rows for its docs are stage-1 (by design — the criteria changed).
  Rides the same Phase-1 alembic revision as `capability_run`.
- **Watch caps (internal constants, dev-side only)**:
  `WATCH_FALLBACK_TOOL_CALLS = 2` · invocation classes = decision-point
  | trigger-fired | anomalous check-in (failed/retried/skipped/degraded)
  · clean boundaries emit deterministic
  `agent_judgement_routed{verdict: "clean_boundary"}` with no LLM call.
- **Bundles (option-completeness, per point)**: P2 = characterise
  coverage object + `search_coverage_record` rows + screen counts +
  executed/zero-result queries; P3 = selection preview (top-N selected:
  title/stratum/type/tier/reason) + selected-vs-pool composition +
  full-text availability + budget picture (`budget_exhausted` vs
  `ranked_below_cut` per stratum) + ranking-trust signals + dropped-
  strata representative digests (top 3–5 titles, never full lists); P4 =
  `propose_synthesis_plan` payload + grouping flags + B2′ priority
  counts. All deterministic renders, versioned, test-pinned.
- **Grammar keys**: exact shapes per annex Families B/D; every parser
  fail-closed, `DIRECTIVE_STRING_MAX` bounds, control-char scrub;
  guidance fenced-block framing texts are lead-supplied in the briefs
  (the screen-criteria "data, not instructions" pattern). D1 rubric
  version derivation: `v2-hierarchy-v1+<sha256(canonical-json)[:8]>`.
- **B2′ persistence**: `extraction_result` summary JSONB gains
  `relevance_annotations: {finding_id: "priority"|"normal"}` +
  provenance `relevance_emphasis` echo; annotator runs post-vetting,
  only when emphasis present; coverage-validated (vetter pattern);
  fail-open → `relevance_unannotated` flag.
- **Prompts (all lead)**: `orchestrator_v1` family (planning moment
  succeeds `planner_v5`; router moment; watch moment — triage /
  decision / authoring framings) · `finding_relevance_v1` ·
  `synthesise_section_v8` = v7 + additive optional priority-findings
  block (cost-baseline note per contract d10). Models:
  `POLICY_ATLAS_ORCHESTRATOR_MODEL` (judgment-class default) ·
  triage + B2′ on mini-class.
- **Zero-egress suite posture**: stub orchestrator backend (all three
  moments), stub tools, scripted CLI IO; `make verify` unchanged in
  character.

## Tasks

**Phase 0 — build-open baseline (full `make verify`)** — lead.

**Phase 1 — walk identity + event chassis + projection (full verify —
schema class, mandatory)**
1. One alembic revision: `capability_run` table + composite `runs` FK
   **+ `screen_generation` column + the widened partial unique index**
   (both DDL pins above) + roundtrip tests. — **fast-worker**
   *(mechanical)*
2. Runner: walk-row lifecycle (open/thread/close) + the **emission
   chassis** (vocabulary, payload rules, run-id assertion,
   transactional-pairing helper) + emission at the **Phase-1-reachable
   paths only** (pause, user decision, skip) with their per-path tests.
   Rescoped per review M1: the orchestrator-decider, router
   (refused/rejected), and clean-boundary paths get their emission
   wiring + tests **inside the tasks that build those paths** (11, 12,
   14, 15) — rubric item 10's completeness is a **Phase-5 exit
   criterion**, not Phase 1's. — **codex→deep-reasoner** *(runner
   surgery; machine-verifiable per reachable path)*
3. `steering_history` projection + two-walk rebuild test +
   payload-partition assertions (signature lead-pinned:
   `steering_history(conn, project_id, capability_run_id=None) →
   ordered walk stories`). — **fast-worker** *(read model from a precise
   vocabulary)*

**Phase 2 — grammar widening (`make verify-fast` — additive fail-closed
keys, byte-identical defaults guard-tested; breadth argued at the gate
table)**
4. D3 refresh · D5 target · D6 strata_scope · D7 exclude_ids · D8
   granularity: parser extensions on existing grammars + provenance +
   `standard`/absent ≡ as-built guards. — **fast-worker** *(pattern-
   following; exact key specs in annex)*
5. D1 appraise rubric override: appraise's first parser + derived
   rubric_version + select/synthesis coherence tests. — **fast-worker**
   *(derivation pinned above; behaviour is a table override)*
6. D9+B5 characterise parser (themes + guidance) · B1 search guidance ·
   B3 group guidance: keys + fenced-block composition plumbing
   (block texts lead-supplied in brief) + isolation tests (guidance
   reaches only its component's prompt payload; scope intent untouched —
   the 017 criteria-isolation precedent). — **fast-worker**

**Phase 3 — re-run machinery (full verify — reader semantics change:
effective rows)**
7. Replacement re-run: component-parameterised generalisation of
   `apply_reselect`/`_run_select_rerun` (reselect · re-characterise ·
   re-group), reference re-threading, plan-version rows, mode stamping.
   — **codex→deep-reasoner**
8. Segment re-entry (NEW construct, M3): bounded forward re-walk
   (acquire→assess) + single boundary re-entry, one cycle per boundary;
   fault-injected tests (failed re-entry degrades honestly, nothing
   already-processed re-runs, no double-spend downstream). —
   **codex→deep-reasoner** *(separate brief from 7 — one concern each)*
9. Generation supersession (restored — owner schema-gate expansion; the
   pin above is the design): `effective_screen_rows` generation-first
   ordering + the re-screen generation write path + skip-logic bypass
   under re-screen + consumer lockstep tests (characterise ×2, select
   eligibility, screen skip) + the stage-2→fresh-generation-stage-1
   supersession test (now buildable). — **codex→deep-reasoner**
   *(reader-semantics change; the review's mandatory-class argument for
   this phase's full gate)*

**Phase 4 — lattice + triggers + modes (`make verify-fast` —
runner/steering-internal, schema untouched)**
10. Trigger floor readers (all decision-8 classes, persisted state only)
    + seeded-row tests. — **fast-worker** *(per-class specs from the
    study's file:line inventory)*
11. P1–P4 wiring: pause-set recompile (mode table), bundle builders
    (pins above; P2 options include criteria+re-screen via Task 9's
    generation path; P2's
    executed/zero-result queries and screen quality-collapse triggers
    parse `search.executed`/`source.screened` event JSONB — exact
    payload keys pinned in the brief from the study, review N1),
    canonical floors incl. the generic non-lattice floor, P3
    preview/options, P4 `propose_synthesis_plan` wiring; **the
    authority-order test lives here** (review m1): a live user answer
    at an attended pause beats a standing declared rule
    (user > declared rules; Task 12 pins rules > orchestrator). —
    **codex→deep-reasoner** *(runner+steering coherence)*
12. Unattended (c): per-point standing-instructions vocabulary on
    `steer_point_defaults`, discretion path, hard-stop honouring,
    loudest-flag collation ordering; scripted tests. —
    **codex→deep-reasoner** *(same subsystem, separate brief)*

**Phase 5 — orchestrator seam + prompts + B2′ + CLI (full verify —
public interface + LLM integration). Split-risk phase (review N5): if it
needs splitting mid-build, the pre-marked seam is 5a = seam + prompts
(13, 14) | 5b = router + CLI (15, 17) | 5c = B2′ + fixtures (16, 18),
each sub-phase exiting on verify-fast with the full verify at 5's true
exit. Deep-reasoner concentration acknowledged (review m4): nine heavy
briefs route to one lane while Codex is out — phases serialize anyway;
if lead adjudication saturates, the lightest briefs (7, 17) pull inline
to the lead rather than queueing.**
13. Prompt family: `orchestrator_v1` (three moments) ·
    `finding_relevance_v1` · `synthesise_section_v8` additive block ·
    guidance fenced-block texts. — **lead** *(prompt-bearing; the
    non-delegable core)*
14. Orchestrator backend: protocol + structured-output impl
    (planner-pattern mirror) + stub + wire models (fan-out plan, watch
    verdict, authored options) + gated invocation + single-shot bundles
    + fallback loop (cap pinned) + deliberation eventing. —
    **codex→deep-reasoner**
15. Router compile path: fan-out → per-component deltas through the
    existing apply paths; partial-compile per-fragment refusals;
    confirm-before-apply; degrade-to-menu. — **codex→deep-reasoner**
16. B2′ (split per review M3 — it is a fencing surface, not volume):
    **16a** annotator pass + fencing + finding-grain read post-vetting
    (the roll-up is doc/profile-grain — the annotator reads finding
    rows directly) + synthesis-consumer foregrounding wiring —
    **codex→deep-reasoner** *(integrity-class; pairs with Task 13's
    lead-owned v8 block)*; **16b** run-scoped persistence + coverage
    validation + fail-open flag — **fast-worker** *(vetter-pattern
    mirror, precise brief)*.
17. CLI: free text at every pause, confirmation renders (fan-out +
    re-run mode declaration), mode labels, standing-instructions
    authoring flow; scripted-IO tests incl. stub e2e. —
    **codex→deep-reasoner**
18. Injection fixtures: poisoned `query_findings` result in
    deliberation · hostile finding into the annotator · author-blind
    scrub-equality. — **fast-worker** *(fixture specs in contract)*

**Phase 6 — flow-back + records (`make verify-fast` — docs/ledger)**
19. execution-orchestration rewrite (§ Steering modes + § routing rule:
    decider dial, mode table/labels, classifier-⏸ discharge, Unattended
    mechanism revision, Minimal behaviour change) + `log.md`. —
    **lead** *(spec prose is design-bearing)*
20. deferred.md sweep (annex Still-OUT list in; 017 deviations
    discharged; 025 notes) + knowledge entries. — **fast-worker**
    *(exact list from the annex)*

**Phase 7 — step-6 exit (full verify, mandatory) + live check +
`verification.md`** — **lead**.

**ADR** (step 4): lead authors `docs/adr/0020-steering-surface.md` at
plan confirmation, committed before the build opens (017 precedent) —
records: steering-event vocabulary + walk entity · the decider dial ·
sequencing-invariant revision · classifier-⏸ discharge · Unattended (c)
mechanism · recency-first screen supersession · the LLM→LLM residual
acceptance.

## Live-check script (contract pin, cost-adjudicated)

One Moderate run, smoke corpus: free-text steers at P2 (additive
re-search on a subtopic) · P3 (combined levers; preview render) · P4
(sections pruned via prose) · one inexpressible intent (refusal + event)
· one Minimal segment with a watch self-decision (flagged) ·
`steering_history()` from a fresh connection. P1 by fault-injected tests
only. ≤20 orchestrator turns · ~$5–12 · ~30–45 min.

## Review-stack sizing (conversation C)

Medium `/code-review`, per-angle diff scoping (events/projection ·
re-run machinery · watch/router · grammar parsers · B2′ · CLI); **one**
security lane headlined: watch/router injection surfaces + B2′ fencing +
Unattended discretion + author-blind equality + the recency-first
supersession; contract-verifier (Opus); adversarial family-flip via
codex if credits are back, else deep-reasoner. Budget ≤250K reasoning /
≤500K fast-worker; fixtures + scripted-IO data excluded from review
diffs.

## Gate consolidation summary

| Boundary | Gate | Why |
|---|---|---|
| Phase 0 open | full verify | mandatory baseline |
| Phase 1 exit | full verify | schema migration (mandatory class) |
| Phase 2 exit | verify-fast | additive fail-closed keys; `standard` ≡ as-built guard-tested; no reader semantics touched |
| Phase 3 exit | full verify | reader semantics change (effective rows) — mandatory-adjacent |
| Phase 4 exit | verify-fast | runner/steering-internal over Phase-1/3 seams |
| Phase 5 exit | full verify | public interface + LLM integration |
| Phase 6 exit | verify-fast | docs/ledger only |
| Phase 7 exit | full verify | step-6 exit (mandatory class) |

Five full gates / six code phases; the three fast gates argued above.

## De-scope levers (contract stop-conditions, pre-authorised order)

Lever #2 (criteria-changed re-screen) was exercised on feasibility
(review B1), then **restored by the owner's schema-gate expansion** —
it returns to being an in-build lever, now cut-able as a clean
sub-feature toggle (skip Task 9 + the P2 criteria option; the
generation column ships regardless, inert at generation 0). Lever #1
stays the first cut: the fallback deliberation loop (ship single-shot
only; escalation demand-meter). Any pull is flagged in verification.md.

## Gate-framing note (review N4)

`verify-fast` here = full test suite minus the slow ingest integration
test, plus typecheck + lint — the three fast gates skip only
`build`/`okf-validate`/one ingest test; seeded-row trigger tests and
grammar suites run at their own phase gates. No mandatory-class signal
is deferred by a fast gate.
