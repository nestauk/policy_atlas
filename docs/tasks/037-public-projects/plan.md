# Plan: 037-public-projects

Requirement ids (R1–R5), design decisions (D1–D6), the public read surface
and all terms are defined in [contract.md](contract.md). This plan cites
them and adds nothing to scope.

Executor marks per AGENTS.md § Agent-side model routing. Verify gates:
full `make verify` at the build-open baseline, at the end of Phase 2 (the
auth phase — mandatory class), and at the step-6 exit; `make verify-fast`
closes Phases 1, 3 and 4 (argued below; the plan gate reviews this).

## Phase 0 — Build-open baseline — `lead` (inline)

Run `make verify` on the branch before any edit. Never build on a red base.

## Phase 1 — Schema and write path (R1 backend) — `fast-worker`

Mechanical transcription of an exact spec; every item below is named.

1. Alembic revision on head `a8c3e1f5b9d2`: add
   `project.is_public BOOLEAN NOT NULL DEFAULT FALSE`. Copy the house
   `SET LOCAL lock_timeout = '5s'` pattern from
   `a4f1c8e3b6d2_organisation_tenancy.py`. Downgrade drops the column.
2. `core/schema.py` (~line 101): the column on the `project` table. No
   index — public reads are primary-key lookups.
3. `contract/projects.py`: `is_public: bool` and
   `access: Literal["full", "public"]` on `ProjectOut` (graded reads
   always say `"full"`; the public leg sets `"public"` — D5);
   `is_public: bool | None = None` on `ProjectUpdate`, **added to the
   explicit-null validator** beside `name` and `visibility` so
   `{"is_public": null}` is 422, never a database 500 (adversarial
   finding 5).
4. `routers/projects.py` `update_project`: accept `is_public` under the
   existing write grade (owner-only); on each actual flip write one audit
   event (`project.shared_publicly` / `project.unshared`) in the same
   transaction, following the `project.renamed` precedent.
5. Tests: schema round-trip (`tests/core/test_schema.py` column set);
   PATCH owner 200 / colleague 403 / anonymous 401 / explicit null 422;
   audit event on flip and not on a no-op PATCH; `is_public` and `access`
   present in `ProjectOut`.

Gate: `make verify-fast` (additive column + field plumbing; the full-verify
signal comes one phase later, before anything reads the column).
Commit.

## Phase 2 — The public read leg (R2, R4, R5 backend) — `codex`

Judgment-bearing, machine-verifiable done (the test list below). The seam
design is fixed here, by the lead; Codex implements against it.

Seam design (fixed):

1. `api/auth.py` — `get_optional_user` keyed on the **raw
   `Authorization` header**, not on `HTTPBearer`'s parse: header absent →
   `None`; header present in any form → delegate to the strict path, which
   401s bad tokens, wrong schemes (`Basic …`) and malformed values alike
   (D2; adversarial finding 4 — `HTTPBearer(auto_error=False)` returns
   `None` for wrong-scheme headers, so it cannot carry this rule alone).
   Test matrix: no header · expired token · garbage token · `Basic x` ·
   bare `Bearer`. Re-export through `deps.py`.
2. `routers/_access.py` — one narrow helper beside `accessible_project`
   (name suggestion: `readable_or_public_project`). Order: if `user` is
   not `None`, try the graded read first (unchanged semantics, admin trace
   included); fall back to the public check
   `is_public AND status = 'active'`; anonymous callers get only the
   public check. Refusal is the standard indistinguishable 404
   (`NOT_FOUND_DETAIL`). It must **not** touch `_read_legs`,
   `own_estate`, `listing_scope` or any cascade code (D3; contract § Out).
   The helper returns whether the read was served by the public leg, so
   the caller can redact (D5).
3. `routers/read_models.py` — drop the router-level
   `dependencies=[Depends(get_current_user)]`; each of the eleven handlers
   takes `user: AuthenticatedUser | None = Depends(get_optional_user)`;
   `_owned` becomes the public-or-graded gate. **Exception:** `decisions`
   keeps `get_current_user` (it is outside the public surface).
4. `routers/projects.py` — `GET /projects/{id}` moves to optional auth on
   its own router instance in the same file (the router-level dependency
   covers all other project routes unchanged). Public-leg reads return the
   redacted shape with `access = "public"`; graded reads `access = "full"`
   (D5).
5. Conformance tests (`tests/api/test_api_conformance.py`): a third class,
   *conditionally public* — the eleven routes answer without a token: 404
   (byte-identical body) for private/archived/unknown, 200 for a public
   active Task. Every other `/api/v1` route still 401s without a token.
   The existing 404 sweep keeps passing.
6. Test battery (the done-definition): the contract § Acceptance checks
   R2/R4/R5 list, verbatim — anonymous 200 / identical 404s / bad token
   401 / decisions-SSE-chat-planning still 401 / listings unchanged /
   signed-in outsider reads public (D4) / redaction (D5) / flip-off
   revokes (R5).

Gate: **full `make verify`** (auth phase — mandatory class). Commit.

## Phase 3 — Share tab (R1 frontend) — `fast-worker`

1. `pnpm gen` to pick up `is_public` in `api/gen/types.ts` (generated —
   never hand-edited).
2. `views/ShareView.tsx`: a "Public link" section replacing the
   `shareComingSoon` placeholder slot — owner-only (mirror the
   `VisibilityControl` `isOwner` guard): an on/off control wired to
   `useUpdateProject` with `{is_public}`, a Copy-link button
   (`navigator.clipboard`, the current origin + `/projects/{id}/results`),
   and the exposure copy the contract's § Public / private boundary
   requires (words in `lib/vocabulary.ts`, with the rest of the copy).
3. Component tests: control visible to owner only; toggle calls the
   mutation; copy button writes the URL; exposure copy present.

Gate: `make verify-fast` (frontend-only, no schema/reader contact). Commit.

## Phase 4 — Public task routes (R2, R3 frontend) — `lead`

`lead` justification: this phase rewires the seam between the 036 router
swap, the auth provider and the query-client identity — cross-cutting
design where a fire-and-forget brief would need mid-course steering.

1. Client seam — decide at the first task, two named options:
   (a) `authMiddleware` attaches no header and skips the 401-retry when
   the auth status is `unauthenticated`, so `useApiClient` works signed
   out; or (b) the public shell provides the already-exported tokenless
   `createApiClient` (`api/client.ts:31`) through the existing client
   context. Prefer (a) if it stays under ~20 lines; it leaves every view
   and hook untouched.
2. `routes.tsx` — the public router gains `/projects/:projectId` routes:
   `results`, `sources` (+ its four children), and an index redirect to
   `results` (R3). Same paths as the authenticated router; the route
   elements are the existing view components, reused.
3. A `PublicTaskGate` route element: fetch the project tokenless; while
   loading show the existing loading state; on 404 (not public, archived,
   unknown) fall through to the current `StashAndSplashRedirect`
   behaviour — a signed-out visitor on a private Task sees exactly what
   they see today (R4).
4. A slim public shell around the two tabs: brand header + **Sign in**
   button (reuse the splash sign-in wiring), `LifecycleBar` with the
   two-tab set from `lifecycle.ts` (Results · Sources), no chat panel, no
   settings menu, no Share/Plan/History (R2). Tab paths for `share`,
   `history`, plan land on the gate's redirect to `results`.
5. **Public view mode inside the reused views (adversarial finding 1).**
   `ArtefactView` unconditionally calls `useConversations` and
   `useRunStream`, renders the "Ask about this analysis" affordance, and
   `useRunStream` throws without a `RunStreamProvider` — whose mounting
   opens the non-public SSE route. The public shell therefore provides a
   public-view context: `useConversations` runs with `enabled: false`, an
   inert `RunStreamProvider` variant never opens SSE, and the chat
   affordance is not rendered. Same treatment for anything in the Sources
   children that touches a non-public route (audit each of the four).
6. **Identity-change cache flush (adversarial finding 2).** The single
   `QueryClient` outlives the router swap and its keys carry only
   `projectId`, so a just-signed-out owner could see cached private data
   on a public or revoked URL. Clear the query cache on every auth-status
   transition (sign-in and sign-out), at the same place `App.tsx` remounts
   the router.
7. **Signed-in outsiders (adversarial finding 3, D4).** The authenticated
   router must not hand a public-leg Task to the full `AppShell` (chat
   panel, SSE, five tabs). Where `AppShell` loads the project, branch on
   `access === "public"` and render the same slim two-tab view instead.
8. Tests: anonymous route renders Results for a public Task (mock fetch);
   private Task redirects to splash with the URL stashed; tab set is
   exactly two; the public view's request log contains only
   public-surface GETs (no conversations, SSE, decisions); cache cleared
   on sign-out (owner → sign-out → same URL never paints cached content);
   a signed-in outsider gets the slim view; signed-in entitled behaviour
   unchanged (`App.tsx` still swaps routers on `auth.status`).

Gate: `make verify-fast`. Commit.

## Phase 5 — Specs, seams, verification (step 6) — `lead` (inline)

Spec edits are precision writing on the tenancy section — not delegated.

1. `docs/specs/system/web-api.md`: § Auth gains the conditionally-public
   class beside the waitlist exception; § Projects documents `is_public`,
   the redacted shape, D3 (link-only, listings unaffected) and the
   public read surface list.
2. `docs/deferred.md` § Export & sharing: mark the read-only/public-links
   part discharged by 037; add the named gaps (mock-API public mode; a
   public-mode e2e).
3. Manual browser check (the contract's live-check pin, ~5 min) and
   `verification.md`: commands, results, the boundary confirmation, gaps.

Gate: **full `make verify`** (step-6 exit). Commit.

## Out-of-plan reminders

- No portfolio-level public sharing, no share tokens, no public index —
  stop conditions if tempted (contract § Out).
- The step-4 ADR (0035: public read leg via `is_public`, D1/D2) is written —
  `docs/adr/0035-public-task-read-access.md` (0034 was taken by the
  case-studies decision from task 034).
- Review phase (steps 7–10) runs in a fresh conversation:
  `task-cycle-review`, with the security lane on the Phase-2 diff.
