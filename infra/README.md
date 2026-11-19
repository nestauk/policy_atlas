# Infrastructure

The Amazon Web Services (AWS) infrastructure for the staging and production environments. It is
written in Python with the AWS Cloud Development Kit (CDK), a tool that turns code into
CloudFormation stacks (groups of cloud resources).

## What is in it

| Path | What it holds |
| --- | --- |
| `app.py` | The CDK entry point. It builds the stacks for one environment |
| `infra/` | The stack code: network, database, application, certificate and analytics stacks. The application stack runs the API and the ops service (the separate service for operators). `components/` holds the parts the stacks share, for example the load balancer, the firewall (AWS WAF, the web application firewall, in `waf.py`) and the website's security headers (`security_headers.py`) |
| `email/` | The templates for the account emails: the invitation and the verification code. Amazon Cognito (the sign-in service) sends them through Amazon SES (Simple Email Service) when an environment turns email on |
| `*_config.json` | The committed settings for each environment (`network_config.json`, `db_config.json`, `pa_config.json`, `metabase_config.json`) |
| `metabase/` | The container image for the Metabase analytics service |
| `tests/` | The unit tests for the stacks |
| [DEPLOYMENT.md](DEPLOYMENT.md) | How a deploy works, and the operator runbook |
| [JUMPBOX.md](JUMPBOX.md) | How to reach a cloud database through the jumpbox |

## Rules

- The repository is public. Do not commit an AWS account id, a secret or an IP (Internet
  Protocol) address allowlist. `app.py` reads the account id from `CDK_DEFAULT_ACCOUNT` when it runs.
  Secrets stay in AWS Secrets Manager. The allowlists for Metabase and the ops service stay in
  AWS Parameter Store (the AWS settings store). [DEPLOYMENT.md](DEPLOYMENT.md) gives the full rule.
- `scripts/deploy.sh` is the deploy sequence. If this folder's documents and the script differ,
  the script is correct.

## Commands

Run these from the repository root.

```sh
make -C infra test                          # the stack unit tests (make verify runs them too)
make infra-setup                            # installs the CDK packages into infra/.venv
make deploy-check DEPLOY_ENV=<environment>  # checks the committed settings; changes nothing
bash scripts/waf_report.sh <staging|prod> [days]  # reads what the firewall counted or blocked; changes nothing
```

`scripts/waf_report.sh` uses your own AWS credentials. `make waf-report-test` checks the script
against sample AWS output.

`make deploy-update` and `make deploy-bootstrap` change a cloud environment. Read
[DEPLOYMENT.md](DEPLOYMENT.md) before you use them. DEPLOYMENT.md also describes the ops service,
the email sender and the firewall. Architecture decision records (ADRs)
[0046](../docs/adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md)
and [0047](../docs/adr/0047-waf-on-the-load-balancer-and-waitlist-captcha.md) give the reasons
for them.
