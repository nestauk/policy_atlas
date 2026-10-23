# Rubric: 054-toc-integration

The task is **done only if every box holds**. Otherwise it is in progress, not done.
Deliverables 1–9, decisions C1–C16, ruling T1, the terms and the acceptance checks are defined
in [contract.md](contract.md); this rubric points at them and restates nothing. Each deliverable
PR into `feat/theory-of-change` (C15) is reviewed against its own box plus the cross-cutting
boxes.

## Deliverables (one box each)

1. [ ] **1 Shell and draft**: the task kind through the registry; `TocPlan` and the Task Agent;
       the draft walk (C3); the graph validator; the read-only canvas in the Magenta Book layout
       with bands, assumption cards, markers and key; the list view; the build flag and the
       server setting (C15); E1 run and recorded.
2. [ ] **2 Evidence check**: item searches on the shared child-walk machinery (C2); the reused
       spine unchanged; the judge with verified quotes (C5); the grade as one pure function
       (C4); case studies and indicators; the detail panel; the Sources tab; the summary and
       evaluation questions; E2 and E2b run and recorded, and the E2 stop condition checked.
3. [ ] **3 Discover and consolidate**: pathways found in the evidence; the two-stage choice
       within the limits (C6); changes to user work flagged with reason and prior version (T1);
       Undo, Restore and Keep mine (C9); E6 run and recorded.
4. [ ] **4 Editing during the check**: the edit queue and follow-up pass (C10); *out of date*;
       Check again; one event per edit; change requests through the Task Agent; the plan-change
       choice (C11).
5. [ ] **5 Web search**: the Responses call and the route table (C7); Mantle in us-east-1 on
       the Bedrock route and nothing else moved there; pages stored once and only reaching
       prompts through the untrusted-text rule; the web cap on grades; "web not searched".
6. [ ] **6 Stress test and discuss**: the `stress_test` kind; four tied questions; neither chat
       edits the graph.
7. [ ] **7 Bring your own theory**: text, image and PDF import; the uploads bucket and its
       checks (C8); the audit event; "Your original".
8. [ ] **8 Export**: PNG, SVG, CSV, JSON, draw.io, PowerPoint; each opened in its target tool
       and the result recorded, including Google Slides.
9. [ ] **9 Design from an option**: the button and back-list; `source_option_id` and the widened
       link rule only for ToC targets (C13); shared documents before item searches (C14); the
       newer-run flag.

## Cross-cutting

10. [ ] `make verify` passes at each deliverable's exit; the contract's deterministic tests are
        present and green; the pinned live check (1)–(9) ran with notes and screenshots.
11. [ ] Exactly the schema in contract § Constraints, in one reversible revision whose downgrade
        refuses while ToC rows exist; the round-trip test passes.
12. [ ] OpenAPI diff additive only; generated files changed only by `make openapi-sync`; no
        secrets edited.
13. [ ] Prompt hashes: only the new entries named in the contract; every existing hash, the ES
        and OS chains, their steering and their tests unchanged.
14. [ ] Only the C16 dependencies added, each through the dependency gate.
15. [ ] Infrastructure: the bucket is private, encrypted, TLS-only and retained; only the backend
        task role is granted; the server setting is off in both environments.
16. [ ] No tests deleted, skipped or weakened without written justification.
17. [ ] Verification evidence in [verification.md](verification.md), including eval numbers with
        dataset licences and the export results by tool.
18. [ ] Known gaps and seams listed in [docs/deferred.md](../../deferred.md): full-text depth ·
        ES links and links after creation · ES findings reuse · the cross-task duplicate gap ·
        Miro API · E3, E4, E5, E7, E8 · removing the build flag.
19. [ ] The contract's five spec changes applied with rulings quoted and logged in
        `docs/specs/log.md`; frozen sources untouched.
20. [ ] ADR 0042 Accepted with sign-off date, rollback included.
21. [ ] The Tier 4 review stack ran per deliverable PR (contract verifier · `/code-review` ·
        security lane on uploads, web egress and the link rule · adversarial at contract, plan
        and code · `/simplify` · human deep review), or a step was skipped with the owner's
        written ruling; findings in [verification.md](verification.md).
