# Task contract: 026-infra-deployment

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status:** drafted. Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: expected (Tier 4 — deployment
> architecture + rollback plan).

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
`cdk deploy` of the three stacks into the target environment produces a running system:
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
   edits: naming/domain config only. (Cloud Map served PostgREST in v2; it stays because
   it's cheap and the copy is smaller than the removal — cut it only if the plan shows
   nothing consumes it.)
3. **DatabaseStack** — copy, then **delete the Supabase self-host apparatus wholesale**:
   Supabase Studio + postgres-meta service, PostgREST + nginx sidecar, the
   JWT-generation Lambda (including the vendored PyJWT tree, ~7.5k lines), the
   `load_secret` Lambda, and their SSM exports/SG rules. **Keep:** Aurora Postgres
   cluster (writer/readers, generated credentials secret, SG, snapshot removal policy),
   DB SSM exports. **Rework (targeted):** the migration runner — v2's Lambda copies
   Supabase SQL files at synth time; v3 migrations are Alembic. 🟡 leaning: replace with
   a one-shot ECS task running the backend image (`alembic upgrade head`) invoked by the
   deploy script — the image already carries the code, deps and env; a Lambda re-bundle
   of the backend is the larger delta. Plan decides the exact shape.
4. **App stack** (v2 `policy_atlas_stack.py`) — copy the Fargate/ALB/Route53 pattern;
   targeted edits:
   - **Backend service:** v3 env/secret surface from `settings.py` (OIDC vars, DB URL
     from the cluster secret, `PA_BACKEND_MODE`, provider + Langfuse keys via Secrets
     Manager) replacing v2's Clerk/Supabase env block. **Deployment posture is a hard
     pin:** `desired_count=1`, no autoscaling (delete v2's scale-on-CPU/memory block),
     ECS deployment config that stops the old task before starting the new
     (`min_healthy_percent=0`, `max_healthy_percent=100`) and a short container
     `stop_timeout` so SIGTERM never becomes a long drain-run
     (web-api.md § Deployment posture hard invariant; deferred.md adv-M3).
   - **Frontend:** v2's Next.js server container does not port. 🟡 leaning: nginx
     container serving the Vite `dist/` behind the same shared ALB (maximum reuse of the
     copied listener-rule/Fargate/Route53 pattern; one hosting idiom for both services).
     Alternative: S3 + CloudFront (more moving parts to write fresh, breaks the
     copy-first grain). Owner may override at the contract gate.
   - Cognito envs → frontend build args (`VITE_OIDC_AUTHORITY`, client id, redirect) —
     config-only, no frontend code changes expected.
5. **Cognito** (new — no v2 precedent, the one genuinely fresh CDK surface): user pool +
   SPA app client (code + PKCE), hosted UI domain, outputs wired to the API's
   issuer/JWKS/audience envs and the frontend build args. Smallest pool that satisfies
   the API's RS256/JWKS verification; no federation, no custom attributes, no triggers.
6. **Licensed font delivery** (deferred.md, owner 2026-07-21): private S3 bucket;
   deploy-time injection of Averta/Zosia into the frontend build (fetched into
   `frontend/public/fonts/` before `vite build` by the deploy script). Binaries never
   enter the repo or the CDK asset tree in committable form (CI font-guard stays green).
7. **Deploy scripts + docs** — `DEPLOYMENT.md` ported and corrected; scripts own the
   deploy-invariant enforcement and migration invocation ordering.
8. **Verify wiring** — infra unit tests (v2 `tests/` pattern: synthesized-template
   assertions) runnable locally and in `make verify` (CI change — approval requested at
   this gate as part of this contract).
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
- Backend/frontend application code changes beyond config/env plumbing. If the deploy
  reveals an app bug, it's a finding to log (or a stop condition if blocking), not a
  silent in-slice fix beyond trivial config.
- Multi-region, WAF, custom dashboards/alarms beyond what copies from v2 (log groups).
- Co-pilot Q&A + transcript store — **re-sequenced to 027+** (owner, 2026-07-21; this
  slice took the 026 number).

## Constraints & approval gates

- **Production config** — the whole slice is one; this contract is the approval vehicle.
  🛑 **before any `cdk deploy`**: target AWS account/env confirmed by the owner.
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
- **Naming/collision constraint** — depends on ❓1 below: if the target account also
  hosts a live v2, every copied fixed name (SSM `/policy_atlas/*`, cluster/service/ALB
  names, log groups) collides and must be namespaced — a systematic targeted edit the
  plan must sequence first, not ad-hoc renames.

## Open questions (owner, at this gate)

1. ❓ **Target account/VPC:** fresh account, or the v2 account? Does v2 stay live
   alongside? (Decides the namespacing edit above, and whether NetworkStack deploys at
   all or v3 imports v2's existing SSM-exported network.)
2. ❓ **Domain:** v3's public domain / subdomains (v2 pattern:
   `*.staging.policyatlas.uk` wildcard + per-service subdomains).
3. ❓ **Cognito confirmed** as the IdP (the API is Cognito-shaped by 025 design; any
   org SSO/federation requirement changes the pool scope).
4. ❓ **Config JSONs committable?** v2 commits account IDs + domains in
   `*_config.json`. Repo is AGPL and may go public — commit as v2 does, or gitignore
   with committed `*.example` templates?
5. 🟡 **Frontend hosting** — leaning nginx-on-Fargate (above); confirm or override.

## Public / private boundary

Committable: CDK code, config templates, deploy docs, synthesized-template tests.
Private (never committed): AWS credentials, Secrets Manager values, font binaries,
`cdk.context.json` if it embeds account specifics (❓4 governs config JSONs). Deploy
logs/screenshots in verification.md scrubbed of account IDs if ❓4 resolves private.

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
  closes "licensed font delivery" and the deploy-invariant enforcement line, and leaves
  the cross-instance seam explicitly open.

## Stop conditions

Halt and escalate when: an approval gate above is hit unapproved (especially: any
`cdk deploy` before the account/env 🛑 clears) · the deploy surfaces an application bug
with no config-level fix · scope would grow past this slice (e.g. the frontend turns out
to need code changes for Cognito after all) · turn/token budget spent.

## Acceptance checks

- `make verify` green, including the new infra test target (synthesized-template
  assertions for all three stacks; no AWS credentials required to run them).
- `cdk synth` clean for all three stacks against the dev env config.
- **Live check (contract-time pin, scoped):** one real deploy to the approved dev/staging
  environment, then one cheap full-chain smoke through the deployed system — Cognito
  login in the browser → create project → start a run → SSE progress visible → artefact
  renders. No full live e2e re-run (025's live check already evidenced the app; this
  slice's changed surface is the deployment, so the smoke evidences *deployment*
  correctness: TLS/DNS, auth wiring, DB connectivity, migrations applied, fonts served).
  Estimated wall time: deploy ~30–45 min + smoke ~15 min.
- **Deploy-invariant check:** a second deploy over the running instance, verifying the
  old task is fully stopped before the new one boots (ECS event order in the console/CLI)
  and no run interruption beyond the documented sweep semantics.
- Font check: deployed frontend serves Averta/Zosia; repo and image layers contain no
  committed binaries (font-guard green).

## Verification evidence expected

In [verification.md](verification.md): per-file port map (v2 source → v3 path ·
copied-verbatim / targeted-edit / deleted / new — the copy-first discipline made
auditable), `make verify` + synth output, deploy transcript (scrubbed per ❓4), smoke
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
