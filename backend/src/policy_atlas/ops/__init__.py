"""Operator command line for organisation tenancy (task 033, contract § 9).

The single procedure for creating an organisation, provisioning and enrolling a
person, moving rows between organisations, and granting or revoking the support
role. It replaces the deleted ``staging-user`` / ``prod-user`` / ``cognito-user``
make targets, which created a Cognito account **without** enrolling it,
suppressed the invitation, and took a password on the command line.

Invocation — the operator's own laptop, over the SSM jumpbox tunnel
(``infra/DEPLOYMENT.md`` § 6), never the ECS migration task: Cognito permission
belongs to the human operator, not to a task role.

.. code-block:: shell

   export PA_OPS_ACCOUNT_STAGING=<account id>       # never committed: the repo is public
   export PA_OPS_USER_POOL_STAGING=eu-west-2_xxxxxxxxx
   export DATABASE_URL='postgresql+psycopg://dbadmin:...@localhost:15432/policy_atlas_db?sslmode=require'

   uv run python -m policy_atlas.ops --env staging org create --name "Nesta"
   uv run python -m policy_atlas.ops --env staging user create \\
       --email person@example.org --display-name "A Person" --org "Nesta"

**No password ever passes through this CLI** (contract § 9). ``user create``
calls ``AdminCreateUser`` with ``DesiredDeliveryMediums=["EMAIL"]`` — AWS
defaults that to SMS — and lets Cognito send its own invitation. There is no
``--temporary-password`` flag and no code path calls ``AdminDeleteUser``:
deleting a user is Out (owner call (h)), because it is coupled to ownership
transfer.

Two safety properties are the reason this is a program and not a shell script:

- **Environment safety** (:mod:`policy_atlas.ops.environment`). Cognito and
  Postgres are addressed separately, so an operator holding a production tunnel
  open on ``localhost:15432`` with staging credentials would write staging
  identities into production. Every command resolves and cross-checks the pair
  before it acts.
- **Compare-and-refuse under a row lock** (:mod:`policy_atlas.ops.commands`).
  Every command that writes ``app_user`` reads the row ``FOR UPDATE`` and
  refuses when the current state is not the state the operator was acting on,
  so two operators cannot interleave a de-enrolment and an admin grant into a
  resurrected administrator.
"""

from policy_atlas.ops.cli import main

__all__ = ["main"]
