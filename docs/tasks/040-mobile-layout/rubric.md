# Rubric: 040-mobile-layout

The task is **done only if every box holds** — otherwise it is in progress, not done.
Defect numbers refer to the table in [contract.md](contract.md) § Defects.

1. [ ] Implementation satisfies [contract.md](contract.md): all nine defects D1–D9 fixed
       at 390px, each evidenced in the manual-check table.
2. [ ] **Desktop-unchanged invariant:** at 768px and 1280px the header, task bar, report
       view, provenance sheet and chat panel render as on `dev`, with D4b (download button
       above the title) as the only intended difference.
3. [ ] `make verify` passes; the pinned live manual check (contract § Acceptance checks)
       ran and is recorded with screenshots at 390/768/1280px.
4. [ ] All mobile styling is breakpoint-gated (`max-md:` or equivalent); no JS viewport
       logic beyond what D9 required.
5. [ ] No approval-gated change snuck in — no new dependencies, schema, auth, egress, CI,
       public-interface or scaffold changes.
6. [ ] No generated files or secrets edited by hand; no vocabulary label renamed.
7. [ ] No tests deleted, skipped or weakened without written justification; D2 and D9
       behaviour changes carry test updates.
8. [ ] Print stylesheet and `make font-guard` unaffected; the D2 bottom bar is hidden in
       print like the other nav chrome.
9. [ ] Verification evidence recorded in [verification.md](verification.md); known gaps
       (e.g. list pages, splash, expanded chat panel on mobile) listed and flowed to
       [docs/deferred.md](../../deferred.md).
10. [ ] Required Tier-2 review stack ran (contract verifier · code review · simplification),
        findings adjudicated in verification.md.
