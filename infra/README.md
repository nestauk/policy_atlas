# Infrastructure

The Amazon Web Services (AWS) infrastructure for the staging and production environments. It is
written in Python with the AWS Cloud Development Kit (CDK), a tool that turns code into
CloudFormation stacks (groups of cloud resources).

## What is in it

| Path | What it holds |
| --- | --- |
| `app.py` | The CDK entry point. It builds the stacks for one environment |
| `infra/` | The stack code: network, database, application, certificate and analytics stacks |
| `*_config.json` | The committed settings for each environment (`network_config.json`, `db_config.json`, `pa_config.json`, `metabase_config.json`) |
| `metabase/` | The container image for the Metabase analytics service |
| `tests/` | The unit tests for the stacks |
| [DEPLOYMENT.md](DEPLOYMENT.md) | How a deploy works, and the operator runbook |
| [JUMPBOX.md](JUMPBOX.md) | How to reach a cloud database through the jumpbox |

## Rules

- The repository is public. Do not commit an AWS account id, a secret or an IP allowlist.
  `app.py` reads the account id from `CDK_DEFAULT_ACCOUNT` when it runs. Secrets stay in AWS
  Secrets Manager. [DEPLOYMENT.md](DEPLOYMENT.md) gives the full rule.
- `scripts/deploy.sh` is the deploy sequence. If this folder's documents and the script differ,
  the script is correct.

## Commands

Run these from the repository root.

```sh
make -C infra test                          # the stack unit tests (make verify runs them too)
make infra-setup                            # installs the CDK packages into infra/.venv
make deploy-check DEPLOY_ENV=<environment>  # checks the committed settings; changes nothing
```

`make deploy-update` and `make deploy-bootstrap` change a cloud environment. Read
[DEPLOYMENT.md](DEPLOYMENT.md) before you use them.
