# Rubric: 032-task-lifecycle-ia

The task is **done only if every box holds** — otherwise it is in progress, not
done. Terms and the G-numbers are defined in [contract.md](contract.md); this
file points there and does not restate them.

## Standard

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] The three full `make verify` runs passed — baseline, end of Phase 2, and
       the step-6 exit ([plan.md](plan.md) § Gates). Every other phase gated
       green on `make frontend-verify` (frontend) or `make verify-fast`
       (backend). The declared manual checks pass or are explicitly recorded as
       not run, with the reason.
3. [ ] No approval-gated change snuck in unapproved. The three gates in the
       contract (schema · public interface · prompt surface) were each approved
       before the work started, and nothing outside them was touched.
4. [ ] No generated files or secrets edited by hand. `api/gen/types.ts` was
       regenerated from the OpenAPI export.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed in
       [docs/deferred.md](../../deferred.md) — at minimum case studies, the
       prose "why this source matters", mobile navigation, the full briefing
       page, and what remains of the workspace-cluster IA.
8. [ ] The agreed review stack ran: fresh-context contract verifier ·
       `/code-review` · `/security-review` · `/simplify`. Findings adjudicated in
       [verification.md](verification.md).
8a. [ ] **Adversarial review is recorded as waived**, not silently missing.
       `verification.md` and the PR both state that the owner waived it on
       2026-08-17 and that the slice stays Tier 3 regardless.

## Naming

9. [ ] The screen never shows the code word. Every user-visible string calls a
       `project` row a **Task** and a `portfolio` row a **Project** (G13 terms).
       One shared labels module owns these strings; no view hard-codes them.
10. [ ] The mapping is written down where a cold reader meets it: the ADR states
        why the portfolio sits above the project rather than re-parenting the
        plan, run and artefact, and cites the
        [data-model.md](../../specs/system/data-model.md) rule it does not break.

## Entry (G1, G2)

11. [ ] The new-task page lists four capabilities. Evidence search is
        actionable. The other three are visibly marked as coming soon and are
        not focusable as links, and no route exists for them.
12. [ ] Submitting a question creates the task and posts that same question as
        the **first planning turn**, so it appears as the opening message of the
        conversation. The send control is disabled while the box is empty.
        Enter submits, Shift+Enter makes a new line, and the page says so.

## Lifecycle bar (G3)

13. [ ] Tab availability matches the contract's locking table exactly, including
        Sources open while a run is executing or paused, and the failed-run row
        where Sources stays open. Asserted by test for every row.
14. [ ] A locked tab is rendered, is visibly unavailable, and is not reachable by
        keyboard or by typing its URL — a locked route redirects to Plan rather
        than showing an empty page.
15. [ ] All six previous project paths redirect to their new homes. No previously
        bookmarkable URL 404s.

## Plan (G4)

16. [ ] The plan document opens on request and closes again, and every field the
        plan object carries is rendered. A part with no value says "Not decided
        yet" and is not hidden.
17. [ ] "Change this" on a part seeds the chat composer and focuses it. It never
        writes to the plan.
18. [ ] After Start search the workspace stays a single-column chat. Run
        progress is a green card in the planning thread (minimisable; a
        collapsed status pins above the composer only when the card is off
        screen). `JourneyPane` is not mounted. Check-ins stay in the thread.
        Finished stages that have a tab signpost a link (Sources, Landscape,
        Findings, Results).

## Report (G5, G6, G7)

19. [ ] The answer callout renders the artefact summary only when its status is
        `verified`. `pending` and `failed` each render their honest state, and
        the report still opens correctly. Asserted by test for all three states.
20. [ ] The metadata strip states last updated, sources found, sources cited and
        the publication-year range, from the existing coverage snapshot and
        funnel. It states no author, because the backend has no author for an
        artefact.
21. [ ] The contents list uses `nav_label` when present and a shortened title
        otherwise. An artefact produced before this slice still renders a usable
        contents list. A proposed `nav_label` over 28 characters is rejected at
        the proposal boundary, not truncated by the client.
22. [ ] Most relevant sources ranks by citation count, breaks ties by appraisal
        tier then title, and shows at most three. Each card states only facts —
        tier, evidence type, and which sections cite it — and asserts nothing
        about why the study matters.
23. [ ] Citations still open the source drawer, and the drawer still shows the
        quote, locator, tier, type and where else the source is used. No
        regression against the existing artefact tests.

## Sources (G8, G9)

24. [ ] Sources is one route with Themes, Landscape and All sources. Findings is
        a fourth view present only when the funnel reports findings, and absent
        otherwise.
25. [ ] Themes renders the theme name, its size and its existing prose
        description. The description is read from the existing read models; no
        new text is generated.
26. [ ] Landscape and All sources keep their current content and behaviour,
        including the existing filters and pagination. A cited row is visibly
        distinct from a reviewed row.

## History and Share (G10, G11)

27. [ ] History merges the decision log with the planning turns into one
        time-ordered list. The question and the plan drafting appear before the
        run events.
28. [ ] Every History row carries a time, a category badge, a plain sentence and
        a status accent. No event type name, component identifier or other
        pipeline vocabulary reaches the screen.
29. [ ] Share states that sharing is coming soon and does nothing else.

## Tasks and projects (G12, G13)

30. [ ] The tasks list shows every task with its status, its date, its project
        when it has one, and its source count. Status wording reuses the
        existing `runPresentation` mapping rather than a second vocabulary.
        "Stale" is derived: succeeded, and ended more than twelve months ago.
31. [ ] A task row routes by state — succeeded opens Results, every other state
        opens Plan. Asserted by test.
32. [ ] Find-a-task filters by name and opens the chosen task at its
        state-correct destination.
33. [ ] The projects list shows each project's name and its task count, and a
        project page lists that project's tasks. Nothing else is added to either
        page.
34. [ ] Portfolio routes are owner-scoped: an unknown or cross-owner portfolio is
        404, matching the existing project rule. Asserted by test.
35. [ ] A task with no project behaves normally everywhere — it appears in the
        tasks list, reads `portfolio_id: null`, and its own pages are unaffected.
36. [ ] The portfolio row carries a name, a description and an owner, and
        nothing else. No status, no lifecycle, no cached counts.

## Conversations (G14)

40. [ ] The chats overlay and the chat side-panel list show both conversation
        kinds, newest first, with planning rows badged and showing whether they
        are open or closed.
41. [ ] A planning row offers **no** rename and **no** archive control anywhere.
        The API 422s on both, so the control must not exist. Asserted by test.
42. [ ] Selecting a planning row lands on that task's Plan tab. It never opens
        inside the chat panel, and no read-only planning reader was built.
43. [ ] Chats keep their existing behaviour: they open in the panel, and they
        still rename and archive.
44. [ ] Several closed planning rows on one task render correctly — one per plan
        lineage is the expected state, not an error.

## Type scale and layout (G15)

45. [ ] The mapping in the contract's § Type scale and layout was applied. No
        sentence a person is meant to read renders below 16px; `text-caption`
        survives only on labels, chips, badges, status pills, timestamps and
        table column headers.
46. [ ] The new `text-display` token is in `index.css` **and** in the
        tailwind-merge registration in `ui/brand/cn.ts`, in the same commit. A
        test asserts the two lists are in sync, and the existing
        `Button.test.tsx` colour-plus-size guard still passes.
47. [ ] A primary button renders white text on blue in the built app, confirmed
        by eye. The 028 failure this repeats was invisible to typecheck, lint,
        185 tests and the mock e2e.
48. [ ] One page width and one report reading measure, applied consistently
        rather than per-view `max-w-*` choices.
49. [ ] The type pass is its own commit, separable from the structural steps, so
        review can read it alone.
50. [ ] `verification.md` states plainly that the mapping is verified by eye and
        at review, not by tests — no implied coverage that does not exist.

## Compatibility

37. [ ] Every changed API response is additive. No existing field changed type,
        meaning or presence. Asserted against the previous OpenAPI export.
38. [ ] The migration round-trips up and down against a scratch database.
39. [ ] No new runtime dependency was added.
