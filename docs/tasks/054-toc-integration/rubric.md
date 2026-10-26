# Rubric: 054-toc-integration

The task is **done only if every box holds**. Otherwise it is in progress, not done.
Increments 1–7, decisions C1–C21, rulings T1 and W1–W18, the terms and the acceptance checks are
defined in [contract.md](contract.md); this rubric points at them and restates nothing. Each
increment's PR into `feat/theory-of-change` (C15) is reviewed against its own box plus the
cross-cutting boxes that apply to it.

## Increments (one box each)

1. [ ] **1 Core**: the task kind through the registry; `TocPlan` and the Task Agent (at most two
       questions); the draft walk and the check walk in the order discover, merge, judge, choose
       (C3); item searches on the capability-neutral child search, with the OS option-search tests
       unedited (C2); the judge with both questions, verified quotes, conditions, case studies and
       the robust-model flag (C5); the grade as one pure function, two grades per link (C4); the
       sentences with every citation checked (C20); the read-only Result page to the wireframes
       (C21); the build flag and server setting (C15); the iteration phase run, with E1, E2 and E6
       recorded and the E2 stop condition checked; **the owner's word that the core is good
       enough to build on**.
2. [ ] **2 Editing and changes**: row revisions and compare-and-apply for every writer, race tests
       green (C10); edits flag and the user decides, with Keep the evidence, the minimal Check
       again and Search for more, shown in all four places (C19); change requests through the
       Task Agent (S9); the change list with Undo per change and Undo all, Keep mine, Restore
       (C9); the plan-change choice (C11).
3. [ ] **3 Web search**: the Responses call and the typed route table with its address allow-list
       and no fallback (C7); only web calls go to Mantle on the Bedrock route; pages through
       `LiveDocumentFetcher` and the new page writer, stored once and reaching prompts only
       through the untrusted-text rule; the web cap on grades; "web not searched".
4. [ ] **4 Stress test and discuss**: the `stress_test` kind; four questions tied to a box or link,
       starting with the critical connection; the Task Agent's suggestion; neither chat edits the
       graph.
5. [ ] **5 Bring your own theory**: text, image and PDF import; the uploads bucket, its checks,
       lifecycle and access rules (C8, C17); the audit event; the original inside the plan panel.
6. [ ] **6 Export**: the PDF report, PNG, SVG, CSV, JSON, draw.io, PowerPoint; each opened in its
       target tool and the result recorded; Google Slides claimed only if its import keeps the
       arrows attached.
7. [ ] **7 Design from an option**: the button and back-list; `from_option`, `source_option_id` and
       the widened link rule only for ToC targets, with ES and OS create unchanged (C13); shared
       documents before item searches (C14); the newer-run flag. Or the owner's recorded ruling to
       release without it first (W12).

## Cross-cutting

8.  [ ] The gates of C18 held: full `make verify` at build open, at each migration and at each
        increment's end; the contract's deterministic tests present and green; each try-it session
        recorded with notes and screenshots.
9.  [ ] Exactly the schema in contract § Schema, in three reversible revisions, each downgrade
        refusing only while its own data exists; each round-trip test passes.
10. [ ] OpenAPI diff additive only; generated files changed only by `make openapi-sync`; no
        secrets edited.
11. [ ] Prompt hashes: only the entries in contract § Prompts and model routes; every existing
        hash, the ES and OS chains, their steering and their tests unchanged.
12. [ ] Only the C16 dependencies added, each through the dependency gate.
13. [ ] Every new route's access matches C17 for anonymous, same-organisation, owner and
        cross-organisation callers.
14. [ ] Infrastructure: the bucket is private, encrypted, TLS-only and retained; only the backend
        task role is granted; the server setting is off in both environments.
15. [ ] No tests deleted, skipped or weakened without written justification.
16. [ ] Verification evidence in [verification.md](verification.md): eval numbers with dataset
        licences, the iteration log, export results by tool.
17. [ ] Known gaps and seams listed in [docs/deferred.md](../../deferred.md): full-text depth · ES
        links and links after creation · ES findings reuse · the cross-task duplicate gap · Miro
        API · E3, E4, E5, E7, E8 · removing the build flag · an upload retention rule · J9.
18. [ ] The contract's five spec changes applied with rulings quoted and logged in
        `docs/specs/log.md`; frozen sources untouched.
19. [ ] ADR 0042 Accepted with sign-off date, rollback included.
20. [ ] The C18 review stack ran: `/code-review` and the security lane on each increment's PR,
        focused as C18 states; the contract verifier, a Codex adversarial pass on the code and
        `/simplify` once before the merge to `dev`; findings in [verification.md](verification.md).
