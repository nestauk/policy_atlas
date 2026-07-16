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
  evidence_scope (the selection_result precedent). `runs` gains
  `capability_run_id UUID NULL` FK. One alembic revision, explicit ids,
  roundtrip-tested.
- **Event vocabulary**: `steering.pause` · `steering.decision` ·
  `steering.rejected` · `steering.refused` · `component.skipped` ·
  `agent_judgement_routed`. Every payload carries `capability_run_id`,
  `plan_id`, `plan_version`, `boundary`; decision payloads add
  `decided_by` (`user|orchestrator|standing_default`), `authored_by`,
  `user_text` (verbatim, when prose given), `interpreted_action`,
  `confirmed`, execution profile, `rerun_mode`
  (`additive|replacement|null`). Attachment: the run the event is about
  (`after_component`); else most-recent attempted run id. Transactional
  pairing: decision/skip/re-run with their state change; pause/refused/
  rejected standalone.
- **Effective-screen-row supersession rule (M4, lead design):
  recency-first** — `effective_screen_rows` orders `created_at DESC,
  screen_stage DESC` (stage only as same-timestamp tiebreak). A fresh
  stage-1 row from a criteria-changed re-screen supersedes a stale
  stage-2 confirmation (intended replacement semantics); the normal
  stage-1→stage-2 flow is unaffected (stage-2 rows are newer). **No
  schema change.** Consumers moving in lockstep: `characterise.py`
  (both call sites), select's eligibility read, screen's own skip
  logic. Demote-only stays an invariant *within* a screening pass;
  across re-screens, recency wins by design (the ADR records this).
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
1. `capability_run` table + `runs.capability_run_id` + migration +
   roundtrip tests (DDL pinned above). — **fast-worker** *(mechanical)*
2. Runner: walk-row lifecycle (open/thread/close) + steering-event
   emission at every path (pause/decision/rejected/refused/skipped +
   clean-boundary `agent_judgement_routed`) + payload rules +
   transactional pairing; emission tests per path × decider. —
   **codex→deep-reasoner** *(runner surgery, multi-path coherence;
   machine-verifiable via the contract's event-path test list)*
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
9. Effective-screen-row recency-first rule + consumer lockstep
   (characterise ×2, select eligibility, screen skip logic) +
   supersession tests incl. the stage-2→fresh-stage-1 case. —
   **codex→deep-reasoner** *(design pinned above; impl + lockstep)*

**Phase 4 — lattice + triggers + modes (`make verify-fast` —
runner/steering-internal, schema untouched)**
10. Trigger floor readers (all decision-8 classes, persisted state only)
    + seeded-row tests. — **fast-worker** *(per-class specs from the
    study's file:line inventory)*
11. P1–P4 wiring: pause-set recompile (mode table), bundle builders
    (pins above), canonical floors incl. the generic non-lattice floor,
    P3 preview/options, P4 `propose_synthesis_plan` wiring. —
    **codex→deep-reasoner** *(runner+steering coherence)*
12. Unattended (c): per-point standing-instructions vocabulary on
    `steer_point_defaults`, discretion path, hard-stop honouring,
    loudest-flag collation ordering; scripted tests. —
    **codex→deep-reasoner** *(same subsystem, separate brief)*

**Phase 5 — orchestrator seam + prompts + B2′ + CLI (full verify —
public interface + LLM integration)**
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
16. B2′ annotator pass + run-scoped persistence + synthesis consumer
    (marks into substrate payloads + P4 counts). — **fast-worker**
    *(vetter-pattern mirror; prompt from 13)*
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

1. Fallback deliberation loop (ship single-shot only; escalation
   demand-meter). 2. Criteria-changed re-screen at P2 (supersession
   redesign moves to its own slice). Both flagged in verification.md.
