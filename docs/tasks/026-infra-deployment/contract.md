# Task contract: 026-infra-deployment

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** approved 2026-07-21 (owner); contract-stage adversarial review same day
> (15 findings adjudicated in, see
> [adversarial-review-contract.md](adversarial-review-contract.md)); the material
> F1 gate was re-decided by the owner same day (auth congruence ruling — resolved
> decision 7) ·
> Plan approved (before implementation): 2026-07-21 · owner (plan.md rev 2) ·
> ADR: 0026 (Accepted 2026-07-21).

## Goal

Policy Atlas v3 deploys to AWS. The CDK app from v2
(`../discovery_policy_atlas/infra` — three stacks: network · database · app) is ported
into this repo's `infra/` and adjusted for the v3 architecture, so the 025 web app
(API + frontend) runs at a real URL against Aurora, behind real login.

**Method pin (owner directive, 2026-07-21): copy-first, targeted edits.** v2 files are
copied over as intact as possible and then edited surgically where v3 differs — never
rewritten from scratch. Each ported file must be diffable against its v2 source, and the
diff is the review surface. Deletions (the Supabase apparatus) are whole-block removals,
not restructurings of what remains.

## Deliverable

PR landing `infra/` as a working CDK app (Python), plus deploy scripts/docs, such that
**running the deploy script** (which wraps `cdk deploy` of the three stacks plus the
imperative steps CloudFormation can't own: migration task, frontend build/sync/
invalidation, font injection — adversarial F7) produces a running system:
frontend served over HTTPS, API on Fargate, Aurora Postgres migrated via Alembic,
Cognito-backed login end-to-end. Verification includes a real deploy + smoke
(§ Acceptance checks).

## Read first

- v2 source (the port basis, read as-built): `../discovery_policy_atlas/infra/`
  (`app.py`, `infra/network_stack.py`, `infra/database_stack.py`,
  `infra/policy_atlas_stack.py`, the three `*_config.json` files, `DEPLOYMENT.md`).
- [web-api.md](../../specs/system/web-api.md) — **§ Deployment posture (v1)** is binding:
  one API instance / one worker process; the hard deploy invariant
  (stop-old-before-boot-new, hard-kill); backend-mode env semantics.
- [docs/deferred.md](../../deferred.md) § Web app (task 025 seams) — the four items this
  slice owns or touches: deploy invariant enforcement · licensed font delivery ·
  cross-instance seam (stays deferred; this slice must not accidentally scale out) ·
  the monorepo-hoist note pinning CDK at `infra/`.
- `backend/src/policy_atlas/api/settings.py` + `auth.py` — the authoritative env/secret
  surface the app stack must inject (OIDC issuer/JWKS/audience, DB URL, backend mode,
  provider keys, Langfuse).
- `frontend/src/auth/` README + `vite-env.d.ts` — the OIDC provider seam
  (`VITE_OIDC_AUTHORITY` etc.); Cognito is **config-only** on the frontend
  (`OidcAuthProvider` already ships).

## Scope / Out of scope

**In** (all under `infra/`, plus deploy scripts and minimal config touches elsewhere):

1. **CDK app skeleton** — copy `app.py`, `cdk.json`, config JSONs, `requirements*.txt`,
   `tests/` from v2; targeted edits for v3 stack names/env.
2. **NetworkStack** — copy near-verbatim (VPC, fck-nat, shared internet-facing ALB +
   wildcard ACM cert, HTTP→HTTPS redirect, Cloud Map namespace, SSM exports). Expected
   edits: naming/domain config only. **Cloud Map is cut** (adversarial F15): its only
   as-built consumers were the deleted PostgREST registration and `SUPABASE_URL` —
   keeping it contradicted the no-unused-infrastructure discipline.

   **Settled (owner, 2026-07-21): v3 deploys its own parallel network** (own VPC,
   fck-nat, ALB, cert), rather than importing v2's live shared ALB: sharing would mean
   modifying the live v2 NetworkStack (SNI cert for the v3 domain, listener-priority
   coordination) from this repo — cross-repo coupling to a stack scheduled for
   retirement, touching what's serving v2 users. Cost of the parallel month: roughly
   one extra ALB + one fck-nat instance (~$20–40/mo). Clean retirement: v2's stacks
   destroy wholesale later.
3. **DatabaseStack** — copy, then **delete the Supabase self-host apparatus wholesale**:
   Supabase Studio + postgres-meta service, PostgREST + nginx sidecar, the
   JWT-generation Lambda (including the vendored PyJWT tree, ~7.5k lines), and their
   SSM exports/SG rules. **Keep:** Aurora Postgres cluster (writer/readers, generated
   credentials secret, SG, snapshot removal policy), DB SSM exports, **and the
   `load_secret` Lambda + trigger** (adversarial F3 — originally mis-sorted into the
   delete list: it is DB plumbing, not Supabase apparatus. It composes the single
   connection-string field inside the generated RDS secret; the API and the Alembic
   task both require one composed `DATABASE_URL`, and ECS secret injection can only
   inject whole secrets or single JSON keys, never compose. Targeted edit: emit the
   SQLAlchemy/psycopg3 URL format v3 expects). **Rework (targeted):** the migration runner — v2's Lambda copies
   Supabase SQL files at synth time; v3 migrations are Alembic. **Settled (owner,
   2026-07-21): a one-shot ECS task running the backend image** (`alembic upgrade
   head`), invoked by the deploy script with a fail-loud wait on the task's exit code —
   the image already carries the code, deps and env by construction; a Lambda re-bundle
   would be a second, drift-prone packaging of the backend. v2's migration SG + Aurora
   ingress rule port as-is; only the Lambda behind them is replaced. Sequencing lives in
   the deploy script beside the deploy invariant: stop old task → migrate → boot new.
4. **App stack** (v2 `policy_atlas_stack.py`) — copy the Fargate/ALB/Route53 pattern;
   targeted edits:
   - **Backend image is authored in this slice** (adversarial F5 — v3 has no
     `backend/Dockerfile`; the contract previously implied one existed): port v2's
     Dockerfile with targeted edits (uv + src-layout install; factory entrypoint
     `uvicorn policy_atlas.api.app:create_app --factory`) **plus a `.dockerignore`
     excluding `.env`, dev-issuer key material, and everything gitignored** — v2's
     bare `COPY . .` would ship a developer's live keys into the image.
   - **Backend service:** v3 env/secret surface from `settings.py` (OIDC vars,
     `APP_ORIGIN=https://v3.policyatlas.uk` for CORS, composed `DATABASE_URL` from
     the cluster secret's connection-string field, `PA_BACKEND_MODE`, provider +
     Langfuse keys via Secrets Manager) replacing v2's Clerk/Supabase env block.
     **Health-check delta named** (adversarial F8): v2's target group probes `/`,
     which v3 does not serve — the TG health check moves to v3's real endpoints
     (`/healthz` / `/readyz`; plan picks which per their semantics).
   - **Migration task placement** (adversarial F6): the one-shot Alembic task
     definition lives in the app stack beside the ECS cluster it runs on (v2's only
     DB-stack cluster belonged to the deleted Studio); the deploy script invokes it
     between stop-old and boot-new, after image push. **Deployment posture is a hard
     pin:** `desired_count=1`, no autoscaling (delete v2's scale-on-CPU/memory block),
     ECS deployment config that stops the old task before starting the new
     (`min_healthy_percent=0`, `max_healthy_percent=100`) and a short container
     `stop_timeout` so SIGTERM never becomes a long drain-run
     (web-api.md § Deployment posture hard invariant; deferred.md adv-M3).

     **Capacity & concurrency (owner requirement, 2026-07-21): one instance ≠ one
     run.** Multi-user concurrency is in-process: the run executor
     (`RUN_EXECUTOR_MAX`, `api/settings.py`) bounds concurrent walks; project-row
     locks isolate users; SSE/steering are process-local by design. Target ceiling:
     **10 concurrent runs**. Three settings are sized together for that ceiling as
     named plan-time decisions: `RUN_EXECUTOR_MAX=10` · SQLAlchemy engine pool
     (`app.py` currently ships defaults — pool 5 + overflow 10, which 10 walk
     threads plus request traffic would exhaust; explicit `pool_size`/
     `max_overflow` required, likely a small settings addition) · Fargate task
     CPU/memory (one adequately sized task, not v2's fleet-of-small-tasks values —
     each executing walk holds ~100 docs of text mid-extraction). Named caveat, not
     a blocker: OpenAI rate limits are shared across all concurrent runs
     (deferred.md § per-run provider-rate-limit fairness) — at full concurrency
     runs degrade to slower, never to wrong. Horizontal scale-out (a second
     instance) remains forbidden until the cross-instance seam lands.
   - **Frontend:** v2's Next.js server container does not port. **Settled (owner,
     2026-07-21, superseding the earlier nginx lean): S3 + CloudFront.** Private
     bucket + Origin Access Control, distribution with the SPA fallback
     (403/404 → `/index.html`), Route53 alias at the apex (`v3.policyatlas.uk`);
     the ALB serves only the API. Frontend deploy = `vite build` (VITE_* baked at
     build time) → `aws s3 sync` → invalidation — no container, no service, no
     image build. Named wrinkle: the CloudFront ACM cert must live in us-east-1
     (small cross-region cert arrangement in CDK; the ALB's regional wildcard cert
     still covers `api.v3.policyatlas.uk`). Rationale: a static SPA needs no
     compute; v2's Next.js-server precedent never transferred, so nginx would have
     been fresh work plus a permanent running task to serve files.
   - Cognito envs → frontend build args (`VITE_OIDC_AUTHORITY`, client id, redirect) —
     config-only, no frontend code changes expected.
5. **Cognito** (new — no v2 precedent, the one genuinely fresh CDK surface): user pool +
   SPA app client (code + PKCE), hosted UI domain, **registered callback URLs and
   allowed sign-out URLs** (adversarial F10 — Cognito requires both pre-registered;
   the frontend defaults its callback to the site origin and invokes hosted-UI
   sign-out), outputs wired to the API's issuer/JWKS/audience envs and the frontend
   build args. Smallest pool that satisfies the API's RS256/JWKS verification; no
   federation, no custom attributes, no triggers.

   **Gated auth amendment (adversarial F1, reshaped by owner adjudication
   2026-07-21 — supersedes "API verification code untouched"):** Cognito *access*
   tokens carry `client_id` + `token_use: "access"`, not `aud`, so `auth.py`'s
   generic-OIDC audience validation rejects every real Cognito token (025's dev
   issuer mints `aud` tokens, which is why nothing caught it). **Owner ruling:
   Cognito is THE auth provider — the verifier becomes natively congruent with
   Cognito access-token semantics rather than patching Cognito in as a fallback.**
   Two targeted edits, one semantic:
   - `auth.py`: validate `token_use == "access"` and `client_id` == the configured
     client id (issuer / RS256 signature / exp / sub checks unchanged); the generic
     `aud` check is removed, not kept as an alternate path.
   - `dev_issuer.py` (+ mint CLI): reshaped to mint Cognito-shaped access tokens
     (`client_id`, `token_use`, same claims layout) — the local dev implementation
     stays, as a faithful Cognito imitation, so dev and prod exercise ONE
     verification path with no fallbacks.
   Config: the audience env now carries the app client id; whether it keeps the
   `OIDC_AUDIENCE` name or is renamed (e.g. `OIDC_CLIENT_ID`) is a plan-gate call.
   Auth hard gate: the security lane reviews these edits specifically. Alternatives
   rejected: `client_id`-fallback-on-missing-`aud` (two dialects, dev≠prod
   semantics — owner), ID-tokens-as-credentials (weaker semantics, frontend
   change), pre-token-generation trigger (heavier, violates "no triggers").
   Two pins (owner-scoped auth stays as 025 built it — ownership is the token `sub`,
   no user table):
   - **Self-signup disabled** — users are operator-created (console/CLI) for the
     migration window; no signup UI, no verification flows. Signup policy is the
     workspace-cluster slice's question.
   - **`RemovalPolicy.RETAIN` on the user pool** — recreating the pool would mint new
     `sub`s for every user and silently orphan their owner-scoped projects; the pool
     is as deletion-protected as the database.
   User tables, profiles, organisation management: **out** — the workspace-cluster
   slice (already sequenced); nothing in this slice's product reads them, and Cognito
   needs none of them to deliver login + per-user isolation.
6. **Licensed font delivery** (deferred.md, owner 2026-07-21): private S3 bucket;
   deploy-time injection of Averta/Zosia into the frontend build (fetched into
   `frontend/public/fonts/` before `vite build` by the deploy script). Binaries never
   enter the repo or the CDK asset tree in committable form (CI font-guard stays green).
7. **Deploy scripts + docs** — `DEPLOYMENT.md` ported and corrected; scripts own the
   deploy-invariant enforcement and migration invocation ordering. Documents the
   operational caveats of the one-instance posture: **deploys interrupt executing
   runs** (hard-kill → sweep marks them `interrupted` on next boot; deploy in quiet
   windows), and a crash means a brief outage until ECS restarts the task (the sweep
   recovers state cleanly). Includes the **production build guard** (deferred.md ←
   025 security lane; widened per adversarial F9): the frontend deploy refuses to
   build/ship a production bundle unless the full required env set is present —
   `VITE_OIDC_AUTHORITY`, `VITE_OIDC_CLIENT_ID` (the provider throws without it),
   and `VITE_API_BASE_URL` (the client defaults to same-origin, which on CloudFront
   serves no API) — not just the authority (a silent dev-token-panel bundle is a
   posture smell, not a bypass — the API still verifies RS256).

   The deploy docs also carry a **first-deploy preconditions checklist** (adversarial
   F11 — NS delegation was named as if it were the only gate; it isn't): `cdk
   bootstrap` state in the account/regions (incl. us-east-1 for the CloudFront cert),
   the application Secrets Manager secret provisioned with its exact name and JSON
   keys enumerated, fonts uploaded to the private bucket, at least one
   operator-created Cognito user, and the NS-delegation `dig` check.

   > **Superseded 2026-08-11:** task
   > [`030-rds-jumpbox`](../030-rds-jumpbox/contract.md) replaces the original
   > fck-nat tunnel below with a dedicated, fixed-target SSM jumpbox. The text
   > below records task 026's accepted scope at the time.

   Also documents the **developer DB access path**: local dev stays on docker-compose
   Postgres untouched; direct Aurora access from a laptop is an SSM port-forward tunnel
   through the fck-nat instance (no bastion, no inbound ports, IAM-gated; credentials
   from Secrets Manager) — the inspection replacement for v2's deleted Supabase Studio.
   **Warning documented alongside it:** a locally booted API pointed at Aurora is a
   second instance sharing the DB — the orphan sweep has no ownership lease, so it
   would interrupt the staging service's executing walks (and vice versa). Tunnel for
   psql/inspection: always fine. Local API against Aurora: only with the staging
   service stopped.
8. **Verify wiring** — infra unit tests (v2 `tests/` pattern: synthesized-template
   assertions) runnable locally and in `make verify` (CI change — approval requested at
   this gate as part of this contract). Plus the **FE↔real-API smoke** (deferred.md ←
   025 adv-M6, earmarked for this slice's CI work): a thin job driving the built
   frontend over real HTTP with dev-issuer auth + SSE against stub backends — the
   transport/auth/base-URL/error-mapping layer that mock mode makes invisible to the
   Playwright journey (where all five 025 live-check integration bugs lived).
9. Housekeeping carry from 025 close-out: `docs/agentic-ops/readiness.md` L24 updated to
   "001–025 merged" (done on this branch).

**Out:**

- **Bedrock** — inference stays on the OpenAI route; no Bedrock IAM/routing (own slice,
  already sequenced). The task role is the seam; nothing to pre-build.
- **Cross-instance steering/live-tail** (LISTEN/NOTIFY, instance lease) — stays a
  deferred seam. This slice *enforces* the single-instance posture; it does not build
  scale-out.
- **CI/CD deploy automation** (pipelines deploying on merge) — deploys stay operator-run
  `cdk deploy`, as in v2.
- Supabase/PostgREST/Studio in any form; Clerk in any form.
- Backend/frontend application code changes beyond config/env plumbing — with exactly
  two contracted exceptions: the gated auth congruence edits (`auth.py` +
  `dev_issuer.py`, scope item 5 / resolved decision 7) and the explicit engine pool
  sizing (§ capacity & concurrency). If the deploy reveals any other app bug, it's a
  finding to log (or a stop condition if blocking), not a silent in-slice fix beyond
  trivial config.
- Multi-region, WAF, custom dashboards/alarms beyond what copies from v2 (log groups).
- **User tables, profiles, organisation management, self-signup** — workspace-cluster
  slice (scope item 5 has the rationale; ownership stays token-`sub`-scoped as 025
  built it, no schema change).
- Co-pilot Q&A + transcript store — **re-sequenced to 027+** (owner, 2026-07-21; this
  slice took the 026 number).

## Constraints & approval gates

- **Production config** — the whole slice is one; this contract is the approval vehicle.
  Target account/env confirmed (resolved decision 1). 🛑 **no `cdk deploy` before the
  plan is approved** — the first deploy is a build-phase step, never a design-phase one.
- **Auth/tenancy** — Cognito user pool is new auth infra: gate. Pool config named in the
  plan and reviewed there; the API's verification code is untouched.
- **Dependencies** — `infra/requirements*.txt` (aws-cdk-lib, constructs, cdk-fck-nat)
  copied from v2 with versions bumped only as far as needed to synth; infra-local, never
  imported by the backend. New Python deps outside `infra/` : none.
- **CI** — adding infra tests to `make verify`: gate, requested here.
- **Schema** — none. Alembic runs *existing* migrations; no new revisions.
- **Runtime egress** — no new egress class: the deployed backend calls OpenAI/search
  providers under the already-approved controls; Cognito/JWKS is auth plumbing.
- **Secrets** — application secrets are provisioned manually in Secrets Manager (v2
  pattern) and referenced by name; never in code, config JSONs, or CDK context.
- **Naming/collision constraint** — the target account hosts live v2 during the
  migration window, so every copied fixed name collides and must be namespaced: SSM
  prefix (`/policy_atlas/*` → `/policy_atlas_v3/*`), VPC/ALB/target-group names, ECS
  cluster/service/task-family names, Aurora `cluster_identifier` + instance
  identifiers, log-group names. A **systematic targeted edit the plan sequences
  first**, not ad-hoc renames. This includes the **VPC lookups** (adversarial F2):
  v2's `Vpc.from_lookup(..., region=...)` carries no name/tag filter, and with two
  VPCs in the account it can silently bind v3's database and services to v2's VPC —
  every copied lookup gains an explicit `vpc_name` filter for the v3 VPC. v2
  resources are read-only from this repo — no v3 stack may import, modify, or attach
  to a v2-managed resource.

## Resolved decisions (owner, 2026-07-21)

1. **Account:** same AWS account as v2; **v2 stays live alongside for ~1 month** while
   users migrate, then retires. Consequences: the namespacing constraint above, and the
   parallel-network decision, settled (scope item 2).
2. **Domain: `v3.policyatlas.uk`** — frontend at the apex, API at
   `api.v3.policyatlas.uk`, wildcard cert `*.v3.policyatlas.uk` + apex SAN.
   **Precondition (devops) — partially met 2026-07-21:** the Route53 hosted zone
   exists (ID `Z01892791CHCGSTKW3NR`; the stack looks it up by name, never creates
   it), which unblocks all authoring/synth/tests. The **parent NS delegation is
   pending** (parent `policyatlas.uk` is on GoDaddy nameservers; devops adds the v3
   NS records "tomorrow" ≈ 2026-07-22). Delegation gates the **first `cdk deploy`**:
   both DNS-validated ACM certs (ALB regional wildcard + CloudFront us-east-1) wait
   for public resolution of their validation CNAMEs and hang without it. Pre-deploy
   check in the deploy docs: `dig NS v3.policyatlas.uk +short` must return the
   Route53 nameservers. After v2 retires, moving to `staging.policyatlas.uk` is a
   config-only redeploy (cert + A records + frontend rebuild for the API URL) —
   deliberately not pre-built.
3. **Cognito confirmed** as the IdP. No federation/SSO in scope.
4. **Config JSONs committed minus the account ID; account ID env-injected** (owner
   final call, 2026-07-21, third revision — supersedes both full-commit and
   gitignore-with-templates). The JSONs stay committed and reviewable (domains,
   instance sizes, capacity values), but the `aws_account_id` field is removed and
   `app.py` reads the account from the environment (targeted edit; CDK's native
   `CDK_DEFAULT_ACCOUNT` pattern). Locally: operator export / untracked `.env`.
   When a CI deploy pipeline lands in a later slice, a GitHub Actions variable feeds
   the same env var unchanged (the owner's original intent, parked until it has a
   consumer — this slice keeps deploys operator-run). **Companion pin:**
   `cdk.context.json` is gitignored — CDK caches `from_lookup` results there
   including the account ID; the cost is lookups re-running per machine. Residual
   guard unchanged: secrets stay in Secrets Manager; IP allowlists or similar never
   enter committed config.
5. **Frontend hosting: S3 + CloudFront** (owner, 2026-07-21 — revised from the earlier
   nginx-on-Fargate call; scope item 4 has the shape and rationale).
6. **Region: `eu-west-2`** (owner, 2026-07-21) — all stacks and config JSONs; the one
   exception is the CloudFront ACM certificate, which AWS requires in `us-east-1`
   (already named in scope item 4).
7. **Auth congruence** (owner, 2026-07-21, adjudicating adversarial F1): the API
   verifier speaks Cognito access-token semantics natively; the dev issuer is
   reshaped into a faithful Cognito imitation for local work — one verification
   path, no fallback dialects (scope item 5 has the exact edits).

## Public / private boundary

**The repo is public (open source).** Committable: CDK code, the `*_config.json`
files with the `aws_account_id` field removed (resolved decision 4 — account ID is
env-injected), deploy docs, synthesized-template tests. Private (never committed):
the AWS account ID (env var / untracked `.env`), `cdk.context.json` (caches the
account ID via `from_lookup`), AWS credentials, Secrets Manager values, font
binaries, IP allowlists or similar operationally sensitive values. Deploy
logs/screenshots in verification.md are scrubbed of the account ID and never show
secret values or session tokens.

## Model route

n/a — no LLM-bearing steps in this slice. (The deployed app uses the existing approved
OpenAI route; unchanged.)

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Copy-first, targeted edits** (owner pin): rewrites are a contract violation, not a
  style choice. Where v3 genuinely needs fresh code (Cognito, font bucket), it is new
  small files, not rewrites of ported ones.
- **Model only what behaves** — no speculative infra (no idle queues, no pre-built
  scale-out, no unused parameters "for later").
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md) — this slice
  closes four items: "licensed font delivery", the deploy-invariant enforcement line,
  the FE↔real-API smoke (adv-M6), and the `VITE_OIDC_AUTHORITY` build guard; it leaves
  the cross-instance seam explicitly open.

## Stop conditions

Halt and escalate when: an approval gate above is hit unapproved (especially: any
`cdk deploy` before the account/env 🛑 clears) · the deploy surfaces an application bug
with no config-level fix · scope would grow past this slice (e.g. the frontend turns out
to need code changes for Cognito after all) · turn/token budget spent.

## Acceptance checks

- `make verify` green, including the new infra test target (synthesized-template
  assertions for all three stacks; no AWS credentials required to run them).
- FE↔real-API smoke green (real HTTP + dev-issuer + SSE against stub backends), and the
  production build guard demonstrably refuses a bundle missing any of
  `VITE_OIDC_AUTHORITY` / `VITE_OIDC_CLIENT_ID` / `VITE_API_BASE_URL` (adversarial F9).
- `cdk synth` clean for all three stacks against the dev env config.
- **Live check (contract-time pin, scoped):** one real deploy to the approved dev/staging
  environment, then one cheap full-chain smoke through the deployed system — Cognito
  login in the browser → create project → start a run → SSE progress visible → artefact
  renders → **hosted-UI logout completes and re-auth is required** (adversarial F10).
  No full live e2e re-run (025's live check already evidenced the app; this slice's
  changed surface is the deployment, so the smoke evidences *deployment* correctness:
  TLS/DNS, auth wiring, DB connectivity, migrations applied, fonts served). During the
  smoke, **observe one parked/idle SSE stream ≥ 2 minutes** (adversarial F14 — business
  events can mask heartbeat/idle-timeout failure; the ALB idle timeout must be encoded
  ≥ a comfortable multiple of the 15 s heartbeat, named in the stack, not left default
  by accident). Estimated wall time: deploy ~30–45 min + smoke ~20 min.
- **Concurrency evidence, proportionate** (adversarial F12): the smoke runs **3 short
  runs concurrently** (not 1), plus documented arithmetic headroom for the 10-run
  ceiling (per-walk memory × 10 < task memory; pool size vs 10 walk threads + request
  traffic). A full 10-run live soak is deliberately not an acceptance check (cost);
  first real multi-user usage is the soak, with the sizing knobs env-tunable.
- **Deploy-invariant check, adversarial-grade** (adversarial F13): the second deploy
  happens **while a (cheap) walk is executing**, verifying the old task is hard-killed
  before the new one boots (ECS event order), the migration step runs between, and the
  boot sweep disposes of the interrupted walk exactly per web-api.md § Deployment
  posture (marked `interrupted`, no boot failure) — not an idle happy-path redeploy.
- Font check: deployed frontend serves Averta/Zosia; repo and image layers contain no
  committed binaries (font-guard green).

## Verification evidence expected

In [verification.md](verification.md): per-file port map (v2 source → v3 path ·
copied-verbatim / targeted-edit / deleted / new — the copy-first discipline made
auditable), `make verify` + synth output, deploy transcript (account ID scrubbed per
decision 4; no secret values or session tokens), smoke
narrative with screenshots, deploy-invariant ECS event evidence, known gaps.

## Risk tier & review focus

**Tier 4** — production config + auth infra + scaffold-grade addition. Review stack:
contract verifier · `/code-review` medium (review-economy pins) · security-auditor lane
(secrets handling, SG graph, Cognito config, public exposure) · codex adversarial ·
human deep review · human-approved plan · ADR + rollback plan (rollback: `cdk destroy`
of app/database stacks in non-prod; Aurora snapshot removal policy retained from v2;
DNS cutover reversible).

Focus: secrets never in code/config · SG ingress graph minimal (no v2 rules kept for
deleted services) · deploy invariant actually encoded, not just documented ·
copy-discipline (diffs traceable to v2) · no Supabase remnants · scope creep into app
code.
