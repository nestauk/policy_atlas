---
type: Security rule
title: A tenancy predicate lives or dies in its compiled SQL — pin the compilation, not the intent
description: SQLAlchemy renders a correlated EXISTS as a cross join without explicit .correlate(); a selected boolean leg is SQL NULL (not False) on NULL columns; a bare with_for_update on a joined statement locks every joined row; a per-user invariant needs a per-user lock. Each surfaced in 033's org-tenancy slice.
tags: [sqlalchemy, tenancy, security, locks, postgres, "033"]
timestamp: 2026-08-25
---

# Rule

When a SQL predicate **is** the security boundary, verify what it compiles
to and pin that structurally — the ORM's default behaviour differs from the
intent in four recurring ways:

1. **Correlated `EXISTS` needs explicit `.correlate(table)`** (plus
   `select_from` for the inner table). Without it SQLAlchemy renders a
   cross join, and a cross-joined org leg is true for any row in any org.
   Pin the compiled SQL (`test_org_read_leg_is_a_correlated_sql_predicate`).
2. **A selected boolean leg must be `coalesce(..., false())`**. Selecting
   `owner_user_id == :me OR <org leg>` beside a row yields SQL `NULL` on an
   ownerless row; `scalar_one_or_none()` then reads "no row" and a caller
   the widening leg admitted is treated as denied — 033's admin SSE closed
   on every connect for ownerless rows while the plain GET worked.
3. **A joined lock statement needs `with_for_update(of=table)`**. The bare
   form locks every joined row — found twice in 033 (the turn reservation
   and the graded conversation resolver both silently locked the owner's
   task row through the join).
4. **The lock's subject must match the invariant's subject.** A
   conversation-row lock cannot serialize a *per-user* count across
   conversations; 033's pending cap needed a transaction-scoped
   `pg_advisory_xact_lock(hashtext(:user_id))` — and taken before the
   cross-conversation sweep, or two same-user transactions deadlock on
   rows swept in opposite orders.

# Why

All four passed type-checking, review reading, and ordinary tests — the
intent was visible in the Python and wrong only in the compiled SQL or the
lock semantics. Three were caught by structural pins or two-connection
tests, one by an adversarial reviewer reproducing it empirically.

# Watch out

- **Widening a listing's grade and adding its row filter must land in one
  change** — 033's own-chats filter had to ship with the grade widening or
  colleagues would see the owner's conversations for the window between.
  Same family as re-keying a cap and its sweeper together: a limit and its
  enforcement move as one.
- The lock a path takes is part of its tenancy design: 033's pre-existing
  task lock on chat paths protected nothing the conversation row could
  not, and removing it was safe only because that was proven, not assumed.
- `hashtext` collisions between two subjects cost a needless wait and
  nothing else — acceptable for a cap, not for a correctness-critical
  mutual exclusion.

# Citations

- [backend/src/policy_atlas/api/routers/_access.py](../../backend/src/policy_atlas/api/routers/_access.py)
- [backend/src/policy_atlas/api/chat_turns.py](../../backend/src/policy_atlas/api/chat_turns.py)
- 033 verification.md § Review findings (the coalesce and advisory-lock adoptions)
