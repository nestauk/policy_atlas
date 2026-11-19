---
type: Invariant (verified)
title: A BEFORE UPDATE trigger does not guard INSERT, so a rule like can clear but never grant needs INSERT OR UPDATE
description: A database trigger set to BEFORE UPDATE leaves INSERT open. A role that may clear a privilege but never grant it could still insert a row with the privilege set. Declare the trigger BEFORE INSERT OR UPDATE, and test both.
tags: [postgres, triggers, privileges, security, "065"]
timestamp: 2026-11-17
---

# Rule

A trigger fires only on the events it names. `BEFORE UPDATE` does not fire on `INSERT`.

The ops database role may clear `is_admin` or `is_ops` on a person but never set them. With an update-only trigger, that role could insert a new `app_user` row with the flag already on. Three review lanes found it independently.

The fix is `BEFORE INSERT OR UPDATE`, plus a test for each event.

# Evidence

- `backend/alembic/versions/c6d4e2f1a9b8_065_ops_role_quotas_domains.py`: `CREATE TRIGGER trg_app_user_refuse_privilege_grant BEFORE INSERT OR UPDATE ON app_user`.
- `backend/tests/ops/test_pa_ops_login.py::test_pa_ops_cannot_grant_admin_or_ops` tries both the UPDATE and the INSERT as the role and expects SQLSTATE 42501 each time.
- Task record: `docs/tasks/065-accounts/verification.md` § Review findings (security L1, adversarial 2, verifier 1).

