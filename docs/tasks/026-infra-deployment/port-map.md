# Port map — task 026 (A.1 brief; running build artefact)

**v2 source:** `../discovery_policy_atlas` @ commit
`db3027a792dd91fb6d8179d25a2f7af410ff805a` (pinned at build open, 2026-07-21).
Method pin: **copy-first, targeted edits** — every ported file is diffable against its
v2 source; deletions are whole-block removals. This file is maintained as the build's
running artefact (plan pin 1) and finalised at E.4.

## Namespacing table (plan pin 2 — every fixed name resolves through here)

| Surface | v2 name | v3 name |
|---|---|---|
| CFN stack ids | `NetworkStack` / `DatabaseStack` / `PolicyAtlasStack` | `PaV3NetworkStack` / `PaV3DatabaseStack` / `PaV3AppStack` (+ new `PaV3CertStack`, us-east-1) |
| SSM prefix | `/policy_atlas/*` | `/policy_atlas_v3/*` |
| VPC name | `policy-atlas-vpc-{env}` | `policy-atlas-v3-vpc-{env}` |
| ALB | `policy-atlas-shared-alb` | `pa-v3-alb` |
| Target group | `policy-atlas-backend-tg` | `pa-v3-api-tg` |
| Aurora cluster id | `policy-atlas-db-cluster` | `policy-atlas-v3-db-cluster` |
| Aurora instance ids | `policy-atlas-db-writer` / `policy-atlas-db-reader-{n}` | `policy-atlas-v3-db-writer` / `policy-atlas-v3-db-reader-{n}` |
| ECS cluster | `policy-atlas-cluster` (+`policy-atlas-studio-cluster`, deleted) | `policy-atlas-v3-cluster` |
| ECS service | `policy-atlas-backend-service` | `policy-atlas-v3-api-service` |
| Task families | `policy-atlas-backend` | `policy-atlas-v3-api` + `policy-atlas-v3-migrate` (new) |
| Log groups | `/policy_atlas/application` | `/policy_atlas_v3/application` |
| App secret name | `policy_atlas/backend` | `policy_atlas_v3/app` |
| Domain | `staging.policyatlas.uk` | `v3.policyatlas.uk` (apex = frontend, `api.` = API) |

v2 resources are **read-only** from this repo: no v3 construct imports, modifies, or
attaches to a v2-managed resource (plan pin 16). Every `Vpc.from_lookup` gains
`vpc_name="policy-atlas-v3-vpc-{env}"` (contract adversarial F2).

## Per-file port map

Disposition: **verbatim** · **targeted-edit** (diffable against v2) · **deleted** ·
**new** · **replaced** (v2 file exists but carries nothing portable — named per file).

| v2 path (infra/…) | v3 path | Disposition |
|---|---|---|
| `app.py` | `infra/app.py` | targeted-edit: account from `CDK_DEFAULT_ACCOUNT` env (decision 4); stage guard `-c stage=network\|all` (pin 6); stack ids per table; + `PaV3CertStack` with `cross_region_references=True` (B.2 wires) |
| `cdk.json` | `infra/cdk.json` | targeted-edit: drop `@policy-atlas/ecr:repositoryName` context; rest verbatim |
| `network_config.json` | `infra/network_config.json` | targeted-edit: drop `aws_account_id`; domain `v3.policyatlas.uk` |
| `db_config.json` | `infra/db_config.json` | targeted-edit: drop `aws_account_id`, all Supabase keys (`studio-meta`, `studio_*`, `postgres_meta_tag`, `postgrest-proxy`, `postgrest_tag`, `studio_whitelist_ips` — allowlist never committed), `base_domain_name`; drop empty `production` block |
| `pa_config.json` | `infra/pa_config.json` | targeted-edit: drop `aws_account_id`, whole `frontend` compute block (S3/CloudFront needs no sizing), autoscaling keys; backend block re-sized per pin 9 (cpu 2048 / mem 8192, `secret_name: policy_atlas_v3/app`); `desired_count` key removed (template pins 0) |
| `requirements.txt`, `requirements-dev.txt` | `infra/requirements*.txt` | verbatim (bump only if synth demands) |
| `infra/__init__.py` | `infra/infra/__init__.py` | verbatim |
| `infra/network_stack.py` | `infra/infra/network_stack.py` | targeted-edit: names/SSM per table; **delete Cloud Map block** (lines 133–151, F15); + fck-nat SSM role + fck-nat SG id SSM export (pin 15) |
| `infra/database_stack.py` | `infra/infra/database_stack.py` | targeted-edit: **delete wholesale** — shared-ALB + Cloud Map imports (l.43–86), JWT secret + `generate_supabase_jwt` Lambda + trigger (l.130–150, 207–211, 422–426), Studio cluster/task/service/TG/DNS (l.164–205, 257–349), PostgREST + nginx (l.351–426), their SSM exports (l.440–448), migration **Lambda** + copytree (l.226–254 minus SG). **Keep:** Aurora cluster + generated secret + DB SG + `load_secret` Lambda/trigger + migration SG + its 5432 ingress + DB SSM exports. **Add:** fck-nat→Aurora 5432 ingress (SG id from SSM, pin 15) |
| `infra/policy_atlas_stack.py` | `infra/infra/policy_atlas_stack.py` | targeted-edit: **delete** frontend task/service/autoscale/TG/DNS block (l.164–261), backend autoscaling (l.329–336), Clerk/Supabase/PostgREST env+secret+SG blocks (l.100–107, 153–162, 271–273, 286–306 replaced); TG health check → `/readyz` (pin 5); `desired_count=0`, `min_healthy_percent=0`, `max_healthy_percent=100`, `stop_timeout=Duration.seconds(10)` (pin 7); deploy SSM exports `/policy_atlas_v3/deploy/*` (pin 12); minimal env block (B.3 completes the full map) |
| `infra/deploy_functions/load_secret/load_secret.py` | same | targeted-edit: URL scheme → `postgresql+psycopg://` (SQLAlchemy/psycopg3); runtime bump in stack to `PYTHON_3_12` (plan-adv F13) |
| `infra/deploy_functions/generate_supabase_jwt/` (+ vendored PyJWT) | — | deleted |
| `infra/deploy_functions/run_migrations/` | — | deleted (replaced by one-shot ECS Alembic task, B.3) |
| `assets/postgrest-proxy/` | — | deleted |
| `tests/` | `infra/tests/` | replaced — v2 file is a commented-out scaffold stub; v3 suite is fresh, table-driven over this file's namespacing table (pin 13, A.3) |
| `DEPLOYMENT.md` | `infra/DEPLOYMENT.md` | replaced — v2's 8 lines describe a GitHub-Actions pipeline v3 doesn't have; v3 doc authored at D.2 from named artefacts |
| v2 `backend/Dockerfile` | `backend/Dockerfile` | targeted-edit (A.4): uv two-stage stays; src-layout install; factory entrypoint `uvicorn policy_atlas.api.app:create_app --factory`; non-root user; **new** `backend/.dockerignore` (every gitignored pattern + `.env*` + dev-issuer keys) |
| — | `infra/infra/cert_stack.py` | new (B.2): `PaV3CertStack`, us-east-1, CloudFront cert only |
| — | Cognito + CloudFront + font bucket constructs | new (B.1 designs placement; B.2 implements) |
| — | `scripts/deploy.sh` | new (D.1) |
| — | FE↔real-API smoke CI job | new (D.3) |

## Config JSON schema (v3, committed — decision 4)

No `aws_account_id` anywhere; `app.py` reads `CDK_DEFAULT_ACCOUNT` and aborts with a
clear message if unset. `cdk.context.json` gitignored (A.2 adds the entry). Env key:
`staging` (the only populated env; `production` blocks are not pre-built).

```jsonc
// network_config.json
{"staging": {"aws_region": "eu-west-2", "fck_nat": {"instance_type": "t4g.nano"},
             "public_domain_name": "v3.policyatlas.uk", "azs": 3}}
// db_config.json
{"staging": {"aws_region": "eu-west-2", "writer_instance_size": "t3.medium",
             "reader_instance_size": "t3.medium", "readers": 0}}
// pa_config.json
{"staging": {"aws_region": "eu-west-2", "policy_atlas_config": {
    "domain_name": "v3.policyatlas.uk", "backend_subdomain": "api",
    "backend": {"cpu": 2048, "memory_limit_mib": 8192, "internal_port": 8000,
                 "secret_name": "policy_atlas_v3/app"}}}}
```

## Stage-guard design (pin 6, targeted app.py edit)

`stage = app.node.try_get_context("stage") or "all"`; valid: `network` | `all`.
`stage=network` instantiates **only** `PaV3NetworkStack` — the other three stacks (and
therefore every `Vpc.from_lookup` context query) are never constructed, so first deploy
can't dead-lock on a VPC that doesn't exist yet. `stage=all` builds all four.
Unknown value: abort loudly like the missing-`env_name` guard.

## A.2 execution order (fast-worker brief — mechanical, in this order)

1. Copy the verbatim/targeted files from the pinned v2 commit into `infra/` (layout
   above). Do not reformat, do not restyle — the v2 diff is the review surface.
2. Apply the namespacing table everywhere (grep for every v2 name; zero stragglers).
3. Apply the delete list (whole blocks, including now-unused imports).
4. Apply the targeted edits named per file above (stage guard, account-from-env,
   config schema, `/readyz`, invariant values, deploy SSM exports, load_secret URL +
   runtime, fck-nat SSM role + SG export + Aurora ingress, VPC lookup `vpc_name`
   filters).
5. `.gitignore`: add `cdk.context.json`, `infra/cdk.out/`.
6. fck-nat SSM role: consult the installed `cdk-fck-nat` API (source-driven) — attach
   `AmazonSSMManagedInstanceCore` via the provider's exposed role/props; do not
   hand-roll an instance profile if the construct exposes one.
7. Prove: `cd infra && pip install -r requirements.txt -r requirements-dev.txt` (venv)
   and `cdk synth -c env_name=staging --context stage=all` synthesizes all stacks
   without AWS calls *where possible* — lookups need context; it is acceptable at A.2
   to prove synth via the A.3 test harness pattern (bundling skipped, mocked context)
   instead of a live-account synth.

Deviations found mid-execution: stop and report, don't improvise (the port map is the
contract's copy-first discipline).
