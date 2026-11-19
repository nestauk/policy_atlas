---
type: Integration quirk
title: str(engine.url) hides the password; use render_as_string(hide_password=False) when the value is handed on
description: SQLAlchemy prints a URL's password as three asterisks in str(). A script that passes str(url) to another process sends a broken connection string. Render with hide_password=False, and keep that value out of logs.
tags: [sqlalchemy, database, secrets, integration-quirk, "065"]
timestamp: 2026-11-17
---

# Rule

`str(engine.url)` replaces the password with `***`. That is safe for logs and wrong for passing a URL on.

When code must hand a working URL to another process, use `url.render_as_string(hide_password=False)`. Treat the result as a secret: do not log it.

# Evidence

- `backend/src/policy_atlas/ops/db_role.py` builds the ops role's URL this way.
- `scripts/ops_e2e_local.sh` prints the local end-to-end URL the same way.

