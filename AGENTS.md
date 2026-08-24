# Agent protocol

- Use the commands in the `Makefile`.
- For non-trivial work, plan before editing.
- Write Google-style docstrings (`Args:`/`Returns:`/`Raises:` sections) for public modules,
  classes and functions; keep them concise. Trivial helpers and test functions need none.
- Use `docs/specs/` for product and system intent — **living intent, not golden**. If building shows
  a spec is wrong or improvable, flag it and flow the change back (`docs/specs/README`); don't
  silently obey it or silently deviate.
- Use `docs/tasks/<task-id>/` for per-task artefacts: `contract.md` (scope), `rubric.md`
  (completion criteria, when risk is medium or high), `verification.md` (evidence, or in the PR).
  `<task-id>` is `NNN-slug` (zero-padded, e.g. `001-example-slice`). Templates live in `docs/tasks/_templates/`.
- Agent-side model routing: the lead (Fable 5) plans, judges, synthesizes; delegate volume via the
  pinned agents in `.claude/agents/` — `deep-reasoner` (Opus) for reasoning offload, `fast-worker`
  (Sonnet) for mechanical sweeps and search — and Codex for the heterogeneous peer (review/rescue).
  **Prompt-bearing work (product prompts, judge rubrics, eval criteria) is lead-only — never
  delegated to a weaker model.** Details: `docs/agentic-ops/harness.md` § Agent-side model routing.
- Deterministic work (date math, parsing, counting, format conversion) runs as a script or command,
  not in latent space — if the same question twice must give the same answer, compute it.
- Do not change schema, auth, dependencies, CI, production config or public interfaces without approval.
- Never edit generated files or secrets.
- Touch only what the task requires.

# Current phase
Design — task `033-organisations` **RE-OPENED 2026-08-24 · contract rev 2.0 →
awaiting contract approval (step 1 🛑)** (branch `task/033-organisations`,
cut fresh from `dev` `b8729a5`): users belong to an organisation and see, by
default, their own work plus their org's org-visible work, read-only, with their
own chats on it. Every mutation stays the owner's. Contract:
`docs/tasks/033-organisations/contract.md`; rubric alongside. **Tier 4** —
tenancy/auth semantics + a live-DB migration + public-API additions. ADR 0032
expected.

The slice was drafted 2026-08-11 as `030-organisations` and sat in design while
031 and 032 merged (134 commits). Re-opened and de-collided 2026-08-24:
**renumbered 030 → 033** (three merged tasks hold 030) and **ADR 0030 → 0032**
(0030 = SSM jumpbox, 0031 = the portfolio layer); the alembic head it chains off
moved from 029's `d8e4a1c7f2b9` to 032's `b3c7d914e0a2`; and 032's `portfolio`
layer pulled a new owner call — **owner call (e), 2026-08-24: `portfolio` takes
the same tenancy grades as `project`**, since a colleague who can read a Task
must be able to read the Project that groups it. The contract now works in code
words throughout (screen **Task** = code `project`, screen **Project** = code
`portfolio`), and its route/test counts are re-derived at plan time instead of
being restated from rev 1. The old `task/030-organisations` branch is superseded.

**Owner call (f), 2026-08-24:** an **admin flag** ships in 033 —
`app_user.is_admin`, ops-assigned only (no HTTP write path), granting **read of
every row in every organisation, `private` included**, so an admin can support
any Task from the real UI. **Read only** — every mutation still 403s for a
non-owner holder. It is the designated home for future admin capability (an
admin dashboard hangs off it), but this slice grants exactly one thing and the
tests pin that. Because it sees private work, **disclosure is the control**:
every admin-leg read emits one `structlog` trace line, the visibility toggle
copy is corrected to say private hides a Task *from your organisation*, and
`PrivacyView.tsx` § 6 gains a sentence saying named administrators can access
content for support and that accesses are logged. That privacy edit is **live
public legal copy and needs written owner sign-off before merge**. The flag
carries a named call-out for the security lane; its broad name invites drift, so
"nothing outside the read leg reads it" is asserted structurally.

**Owner call (g), 2026-08-24:** `app_user` **stores the Cognito email**, and admins
can filter work by it. The access token carries `sub` only — the pool is
`UsernameAttributes: ["email"]`, so `cognito:username` is a generated UUID, not
the address — so the email is resolved **once at ops enrolment** (enrol *by*
email; the CLI resolves it to a `sub`) and stored. `sub` stays the key, because
addresses change and `sub` does not. Admins get `?owner_email=` on the two
listings; a non-admin passing it gets 400 whether or not the address exists.
**No new dependency and no API egress change:** the lookup shells out to the AWS
CLI already used for migrations (list args, `shell=False`, shape-validated
address), runs only in the ops CLI under the human operator's IAM, and the API
task role gains no Cognito permission. The DB now holds directly identifiable
personal data, so `PrivacyView.tsx` **§ 3** gains the email alongside § 6's
administrator sentence — **both need written owner sign-off**, and de-enrolment
clears the address as the erasure lever. No user directory (Out).

**Owner call (h), 2026-08-24:** the ops CLI owns the **whole account lifecycle** —
`user create` (Cognito `AdminCreateUser` then enrol, in one command; Cognito
first because its `sub` is the DB key; a DB failure keeps the account and prints
the `user enrol` remediation rather than deleting it) and `user delete` (removes
the Cognito account, clears `email`/`display_name`, and **never touches owned
work** — no cascade, no reassign). Delete reports the address, org and
soon-unreachable Task counts and requires the address retyped; `--force` is for
scripts only. Because ownership transfer stays Out, deleting someone with live
work **strands** it — that is now the trigger condition for a transfer slice.
Operator IAM grows to `ListUsers` + `AdminCreateUser` + `AdminDeleteUser`.

**Owner call (i), 2026-08-24:** the portfolio/project **visibility cascade** is
reopened from Out. One invariant — a `project` with a `portfolio_id` carries
that `portfolio`'s `visibility` — covering the owner's three rules (inherit on
create; promote a private project into an org portfolio; ask when an org project
meets a private portfolio) and the three cases they left open (portfolio
visibility change cascades to members behind `cascade=true`; setting a project's
visibility while it is in a portfolio is refused with both ways out named;
removing from a portfolio changes nothing). **The API never guesses** — any
side-effecting visibility change 409s `visibility_conflict` unless the caller
states the resolution, so the frontend prompt sits over the refusal rather than
replacing it. All paths are owner-only writes on both rows. Enforced in the
write paths plus a property test; the invariant spans two tables so a CHECK
cannot express it. Note "public" in product phrasing means `visibility='org'` —
nothing here is internet-public, and the contract says `org`/`private` throughout.

**Next slice after 033 — the rename** (owner, 2026-08-24): `project` → `task`
and `portfolio` → `project`, standalone, mechanical, no behaviour change,
retiring ADR 0031's vocabulary split. It touches ~249 files and breaks
`/api/v1/projects/*` URLs and bookmarks, which is why it is its own slice and
not folded into a Tier-4 tenancy diff. It must also cover the code 033 adds.

Task `032-task-lifecycle-ia` is **merged to `dev`** (PR #55, `c6bf772`) — the app
reshaped around one task and one lifecycle, with a named grouping above tasks:
screen word **Task** = the `project` row, screen word **Project** = the new
`portfolio` row. ADR 0031 (Accepted) records the vocabulary split, which stays
open until the workspace-cluster slice. Seams in `docs/deferred.md` § Task
lifecycle IA — note that `src/mock/api.ts` serves no `/api/v1/portfolios`.

Task `031-search-count-honesty` is **merged to `dev`** (PR #51, `23b3dfa`) — one
clear meaning per user-visible source count across the P1 check-in, Where I
looked and the publisher-country charts. Two items were escalated to the owner
in that PR and remain true of it: the **manual browser check was not run**, and
**no non-Claude reviewer read the slice** (the Codex CLI is not installed in
this environment, so the family flip did not happen).

Task `029-copilot-chat` is **merged to `dev`** (PR #47, `5f2e9b1`) — the unified
conversation model: a project holds many conversations, Claude-Projects-style.
Follow-up **chats** (read-only, project-scoped, answering across artefacts;
streamed NDJSON turns with claim-grained citations, deterministic floors + async
judge enrichment; tool scope `search_chunks` · `lookup` · `query_findings`, no
`search`) and **planning conversations** (one per plan lineage, closing with its
run's terminal transaction — supersedes 027's rolling thread; row-grain audit
chain conversation → plan → run → artefact). ADR 0029 (Accepted); API surface:
`docs/specs/system/web-api.md` § Conversations.

Tasks 001–028 are merged (2026-08-06 merge day: dev = #33 → #44 → #45 =
`c501022`); system **live** at `v3.policyatlas.uk`.

Search-volume work is **merged to `dev`** (PR #46, the
`37-hotfix-remove-quota` hotfix) — `029-search-volume-cap` (record caps per
backend per round; standard/deep wall clocks removed) and
`030-multi-round-search` (rapid's clock removed, the runner-orchestrated round
loop wired). It **did not go through the task cycle**: each carries a `plan.md`
and nothing else — no contract, no rubric, no verification, no ADR — so its
`docs/tasks/029-…`/`030-…` directories are leftover plan docs, not the record of
a cycled slice. They collide by name only, with the copilot-chat slice and with
three merged 030 tasks. **Nothing depends on renumbering them**; the live
behaviour is on `dev`. If the record is ever reconstructed it takes the next free
numbers, not `029`/`030`.

Known operational state: staging's OpenAI quota is **healthy** (the
2026-07-28 exhaustion was topped up; corrected here 2026-08-24 — live checks
needing a model route are unblocked). The eval slice (former 027 draft) stays
deferred — contract draft at unpushed `a5c9708`.

Tasks `001-walking-skeleton` through `025-web-app-foundation` are
complete (merged — 025 is PR #32, 2026-07-21: monorepo hoist
(`backend/` + `frontend/` + `infra/`), schema-first API
(`policy_atlas.api`, RS256/JWKS auth + dev issuer, SSE replay+tail),
runner parking + boundary continuation, React 19 + pnpm frontend on
the Nesta brand layer; spec `docs/specs/system/web-api.md`) — the EB
chain runs end-to-end live behind the
024 steering surface (one orchestrator, three moments: planning turn ·
free-text router · boundary watch; steer-point lattice P1–P4; durable
steering record on `event_log` + `capability_run` + the
`steering_history` projection; ADRs 0020–0023), with prose-first
synthesis output shape v2 (ADR 0015), select at standard depth,
fail-closed country filters/groups, IOF schema v2 (ADR 0016), the ICF
second finding schema + kind-typed `query_findings` + kind-spanning
membership bridge (ADR 0017), multi-facet grouping on the shared
two-stage clustering engine + the 022 cost/surface work (ADR 0018,
−49% synthesis cost), and the pinned prompt surfaces
(`orchestrator_v1` family, `extract_iof_v7` + vetter, `extract_icf_v2`
+ vetter, `synthesise_section_v7` (v6 frozen as the cost-harness
baseline), `synthesise_sections_v2`). 018 trailing lane: **D2
rehearsal** (owner-scheduled); the `demo-live-run` branch (C4 demo
surface) stays throwaway — never merges — and is superseded by 025
as evidence. After 026 (infra): co-pilot Q&A + transcript store, then
the eval slice (cost as a first-class axis), then Bedrock, then the
workspace cluster. All other seams remain deferred
(`docs/deferred.md`).

