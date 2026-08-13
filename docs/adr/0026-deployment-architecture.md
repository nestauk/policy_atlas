# ADR 0026 — Deployment architecture (v3 on AWS: v2 CDK port, parallel and namespaced)

**Status:** Accepted — 2026-07-21 (owner; 026 plan gate, "Plan approved, draft the
ADR and close out the design phase"). Contract:
`docs/tasks/026-infra-deployment/contract.md` (all 15 contract-stage + 19
plan-stage adversarial findings adjudicated — see the two
`adversarial-review-*.md` records). Plan: `docs/tasks/026-infra-deployment/plan.md`
(rev 2).

## Context

Tasks 001–025 produced a deployable product (API + SPA + Aurora-ready schema) with
no deployment substrate. v2 (`../discovery_policy_atlas`) has a proven three-stack
CDK app, but v3's architecture diverges: no Supabase layer (direct
SQLAlchemy/psycopg), OIDC/JWKS auth instead of Clerk, a static Vite SPA instead of
a Next.js server, Alembic instead of raw-SQL migrations, and a deliberately
process-local steering/SSE design (web-api.md § Deployment posture) that forbids
horizontal scale-out until the cross-instance seam lands. v2 must stay live during
a ~1-month user migration, in the same AWS account.

## Decision

1. **Copy-first port, targeted edits** (owner method pin): v2's CDK files are
   copied and surgically edited, never rewritten; a per-file port map
   (verbatim / targeted-edit / deleted / new) is the review surface. The Supabase
   apparatus is deleted wholesale; `load_secret` (DB-URL composer) is kept.
2. **Parallel, namespaced coexistence**: v3 deploys its own network (VPC, fck-nat,
   ALB, wildcard cert for `v3.policyatlas.uk`) alongside live v2 in the same
   account (~$20–40/mo for the overlap). Every fixed name — CloudFormation stack
   ids (`PaV3*`), SSM prefix (`/policy_atlas_v3/*`), ECS families/services, Aurora
   identifiers, log groups, secrets — resolves through a namespacing table,
   test-enforced; v2 resources are read-only from this repo. Retirement of v2 is
   a wholesale destroy with no v3 dependency.
3. **One instance, template-enforced deploy invariant**: `desired_count=0` is
   pinned in the CDK template, so every CloudFormation deploy stops the service;
   the deploy script then runs migrations (one-shot ECS task on the backend image,
   fail-loud wait) and scales to 1. This encodes web-api.md's hard invariant
   (stop-old-before-boot-new; the leaseless orphan sweep) structurally rather than
   procedurally. Concurrency is in-process: `RUN_EXECUTOR_MAX=10`, explicit engine
   pool sizing, one adequately sized Fargate task (measured, not assumed —
   capacity evidence captured at the live check).
4. **Cognito is THE auth provider; the API speaks its access-token semantics
   natively** (owner ruling on adversarial F1): `auth.py` validates
   `token_use == "access"` + `client_id` (PyJWT `verify_aud` explicitly off);
   the dev issuer remains for local work as a faithful Cognito imitation — one
   verification path, no fallback dialects. Pool: self-signup disabled,
   `RemovalPolicy.RETAIN` (recreation would re-mint `sub`s and orphan
   owner-scoped projects). User tables / org management stay out
   (workspace-cluster slice).
5. **Static frontend on S3 + CloudFront** (OAC, SPA fallback, us-east-1 cert via a
   dedicated mini-stack): no compute for static files; licensed fonts are injected
   into `public/fonts/` from a private bucket at deploy time, never committed.
6. **Deploys stay operator-run** (`scripts/deploy.sh <env>`, staged first-deploy
   bootstrap with two precondition gates); CI/CD automation is a later slice. The
   AWS account id is env-injected (`CDK_DEFAULT_ACCOUNT`), never committed —
   the repo is public.

### 2026-08-11 automation amendment (task 030)

Decision 6's later slice has landed. The deployment *decision* remains attended:
an engineer explicitly dispatches `dev` to the one staging environment, and a
stable published Release is the production promotion event. GitHub Actions now
executes the unchanged authoritative stop→migrate→scale→publish wrapper using
short-lived, Environment-scoped AWS OIDC credentials. First deployments and
failure recovery remain attended Makefile operations. Per-environment concurrency
queues without cancellation; GitHub Environment protection plus in-workflow ref
validation forms the promotion boundary. The fixed v3 resource names/SSM prefix
mean staging and production use separate AWS accounts unless a future namespacing
decision changes the CDK.

## Consequences

- v2 users are structurally isolated from every v3 operation, including rollback
  (`cdk destroy PaV3*`; Aurora snapshots + Cognito pool RETAIN survive).
- Deploys interrupt executing runs by design (documented; deploy in quiet
  windows); a single-task crash is a brief outage with clean sweep recovery.
  Scale-out remains a recorded deferred seam (lease + LISTEN/NOTIFY), not an
  infra toggle.
- The auth congruence edit and pool sizing are the only two backend code touches;
  both ship with conformance/regression suites and get dedicated security-lane
  review.
- Moving to `staging.policyatlas.uk` after v2 retires is a config-only redeploy.
- Four deferred items close with this slice (fonts, deploy invariant, FE↔real-API
  smoke, OIDC build guard); the cross-instance seam stays open.
