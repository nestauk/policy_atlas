# Plan: 033-organisations

> **Status:** drafted 2026-08-24, against [contract.md](contract.md) rev 3.0
> (**approved 2026-08-24**) and the 42-item [rubric.md](rubric.md).
> **Plan approval (step 3 🛑): _pending_.** ADR 0032 is written in Phase 11 and must record
> that it **amends ADR 0031 decision 4**.
>
> **Executor marks** follow the repo default: implementation goes to subagents
> (`fast-worker` for mechanical volume from a precise spec, `deep-reasoner` for design-
> bearing work, `codex` for the heterogeneous peer). A **lead** mark needs a justification,
> given inline. Taste- and prompt-bearing surfaces stay with the lead.

## Shape of the build

Thirteen phases. **The three approval-gated phases run first** — schema, auth semantics and
the public API — so a refused gate surfaces before anything is built on top of it. The
frontend is last because it consumes the whole API surface, and the ops CLI sits between
them because it depends on the schema but nothing depends on it.

The one ordering constraint that is not obvious: **Phase 3 (route consolidation) must
enumerate the call sites from the tree before it starts**, not from the contract. Rev 2.0's
enumeration missed an entire router, and the contract deliberately refuses to restate
counts for exactly this reason.

**`make verify` runs four times** — baseline, end of Phase 2, end of Phase 7, and the exit
gate. Backend phases in between gate on `make verify-fast`; frontend phases gate on
`make frontend-verify`, since `verify-fast` is backend-only and would prove nothing there.

## Phases

### Phase 0 — Baseline · *executor: fast-worker*
Record `make verify` green on the branch before any change, and capture the current
alembic head (`b3c7d914e0a2`) and route inventory. Evidence for `verification.md`.

### Phase 1 — Schema and migration 🛑 **GATE: schema** · *executor: deep-reasoner*
`organisation`, `app_user` (with `display_name` NOT NULL, `email`, `is_admin`), `org_id` +
`visibility` on `project` and `portfolio`, `conversation.created_by` with its backfill, the
two org-leg indexes, a lock timeout on the migration.
**Tests:** up/down roundtrip on the scratch-DB pattern (029's `test_migrations_029.py` as
template); backfill correctness; **and the rollback-exposure test** — proving that pre-033
code would list a colleague's conversation to the project owner, so rubric 32's risk is
evidenced rather than asserted.
*Design-bearing (a live-DB migration with a data step), so not fast-worker.*

### Phase 2 — The access helper 🛑 **GATE: auth/tenancy semantics** · *executor: deep-reasoner*
One helper: three read legs (owner, same-org, admin), one write grade. **The org leg is a
SQL predicate** — the NULL rule is the highest-blast-radius mistake in the slice, so this
phase owns it and pins it with the two-NULL-callers test. 404/403 discipline. The four
named readers of `is_admin` and the structural assertion against that closed list.
**Full `make verify` at the end of this phase.**

### Phase 3 — Route consolidation · *executor: fast-worker, spec from lead*
Enumerate every project-, portfolio- and conversation-scoped route **from the tree**, then
route each through the helper. Includes the seven routes on `conversations.py`'s
conversation-id router, graded per contract § 4: own-conversation for chats, project-owner
for planning, admin read-only, colleague 404.
*Mechanical once the enumeration and grades are fixed; the lead writes the spec and the
grade table, the worker applies it.*

### Phase 4 — Chats, cap and sweeper · *executor: deep-reasoner*
`created_by` writes; the own-chats filter exactly as specified
(`created_by = :me OR (created_by IS NULL AND owner_user_id = :me)`); the three colleague
mutations and nothing more; **the pending cap and `_expire_stale_pending_turns` re-keyed
together**; lock scope reviewed so a colleague's turn cannot block the owner's rename,
archive or run-start.
*The sweeper re-key is a correctness trap — a colleague permanently capped with no operator
lever — so it does not go to a mechanical worker.*

### Phase 5 — SSE re-authorisation · *executor: deep-reasoner*
`_tail` re-authorises per batch and closes the stream when access is gone. Tests for all
three revocation events: de-enrolment, visibility flip, admin revoke.
*Touches the streaming loop and the tick hub; a wrong lifetime here is a hang or a leak.*

### Phase 6 — The visibility and org invariant · *executor: deep-reasoner*
i.1–i.6 over **both** `visibility` and `org_id`; the property test across all six paths;
`update_portfolio` barred from writing `visibility` outside the cascade (the blind
`.values(**changes)` splat is the specific defect); the both-fields PATCH 422; i.5's 409
and the corrected way-out semantics, including a test that the i.5-then-i.2 loop cannot
silently re-expose a row.
*Two-table invariant with a property test — design-bearing.*

### Phase 7 — API surface 🛑 **GATE: public API** · *executor: fast-worker, spec from lead*
`GET /api/v1/me`; `scope`, `portfolio_id` and `owner_email` on the listings; `ProjectOut`
and `PortfolioOut` gaining `visibility`, `is_owner`, `owner_display` (**never the email**);
`POST /portfolios {from_project_id}` under the write grade; error envelope gaining 403
`forbidden` and 409 `visibility_conflict`, with 422 reused for the two parameter cases
rather than a third semantic; `make openapi-sync`.
**Full `make verify` at the end of this phase.**

### Phase 8 — The admin leg and its trace · *executor: deep-reasoner*
The admin read leg wired through the helper and the listing scope resolver; **trace grain**
— per row on direct reads, per request on cross-org listings **including a zero-result
search**, per SSE subscribe and re-authorisation, nothing for an entitled read; admin
refused every mutation including chat creation and turn POST.
*The audit is the only control this feature has (§ 12), so it is not mechanical work.*

### Phase 9 — Ops CLI 🛑 **GATE: `boto3` + `boto3-stubs`, the `Dockerfile` change, Cognito account creation** · *executor: deep-reasoner*
The `ops` dependency group installed in dev and CI with `--no-group ops` in
`backend/Dockerfile`; `org create`; `user create` with `DesiredDeliveryMediums=["EMAIL"]`;
**`user enrol` carrying the person's rows across as `private` in one transaction** (owner
call (j)); `resync`; single-row assign; de-enrol clearing `org_id` on their rows; admin
grant/revoke with its own trace; the **environment-mismatch guard** and the **`FOR UPDATE`
concurrency guard**; **deletion of the `staging-user`, `prod-user` and `cognito-user` make
targets**.
*Three approval gates and the highest-consequence operational failure in the design.*

### Phase 10 — Frontend · *executor: fast-worker for the matrix, lead for copy*
The switcher (**hidden when `/me` returns no organisation**, so rubric 14 holds on day
one); `owner_display` on rows and cards; **the owner/non-owner affordance matrix component
by component** — `PlanningPane` and its `ChatSidePanel` duplicate, `PlanCard`, `RunPane`,
suggestion chips, plan-start card, check-in responses, retry controls; the **owner-scoped
check-in banner**; `HistoryView` readable with the project; the account menu; **React Query
invalidation across families** with `scope` in every affected key; `PortfolioDetailView`
using the `portfolio_id` filter; the mock API additions.
*Copy is taste-bearing and stays with the lead — the visibility-outcome lines and the
admin's "this spans organisations" label are one sentence each, per the just-enough-text
principle. The affordance matrix is mechanical from a component list.*
Gates on `make frontend-verify`.

### Phase 11 — Records · *executor: lead*
ADR 0032 (**recording that it amends ADR 0031 decision 4**); spec flow-back to `web-api.md`
§§ Auth boundary, Portfolios, Conversations, plus `data-model.md`, `JUMPBOX.md` and
`DEPLOYMENT.md` (CLI invocation and the **roll-forward** rollback posture); the deferred
seams; and **the three privacy-notice discrepancies written up verbatim as an open
escalation** to the notice's owner.
*Judgment- and prose-bearing throughout; the escalation in particular must be exact.*

### Phase 12 — Exit gate · *executor: lead, with fast-worker for evidence capture*
Full `make verify` and `make drift-check`; the staging live check per contract
§ Acceptance (including **enrolling a user who already owns Tasks** and confirming they
arrive private); the built-image check that `boto3` is absent; **the DPIA screening and
processing-record update recorded as done**; `verification.md` assembled.

## Decisions this plan takes

1. **Gated phases first, frontend last.** A refused gate must surface before code is built
   against it (032's precedent).
2. **Four full `make verify` runs**, not one per phase — baseline, Phase 2, Phase 7, exit.
   Backend phases between them use `verify-fast`; frontend phases use `frontend-verify`.
3. **Phase 3 enumerates from the tree, never from the contract.** The contract deliberately
   omits route counts because rev 2.0's were wrong.
4. **Design-bearing work does not go to `fast-worker`.** The sweeper re-key, the SSE
   lifetime, the invariant and the trace grain are all places where a plausible-looking
   implementation is wrong in a way tests written from the same misunderstanding would not
   catch.
5. **The security lane runs as three scoped passes** (tenancy boundary · privileged read
   and audit · operator CLI), per the contract's § Risk tier. That is the review cost of
   the one-slice ruling and it is scheduled, not discovered at step 7.
6. **Codex is on PATH again**, so the heterogeneous peer lane is available for the
   plan- and code-stage adversarial reviews. 031's gap was environmental and no longer
   applies.

## Risks this plan carries

- **The live check needs a real deliverable mailbox.** The pool has no `EmailConfiguration`,
  so invitations use the 50-per-day `COGNITO_DEFAULT` sender from an address that is
  routinely spam-filtered. If no mailbox is available, Phase 12 stalls with everything else
  green. **Resolve before Phase 9, not at Phase 12.**
- **The migration takes `ACCESS EXCLUSIVE`** while the API is scaled to zero; an idle
  jumpbox session blocks it. Phase 1 sets a lock timeout and Phase 12's runbook adds a
  blocker preflight, but the rehearsal against production-scale data is the real mitigation.
- **Phase 10 is the largest single phase** and the one with no natural test boundary. If it
  slips, it slips alone — nothing after it depends on it except the live check.
