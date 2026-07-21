# Implementation plan: 026-infra-deployment

> **Status:** DRAFTED — plan-phase adversarial review pending, then owner 🛑.
> Contract: [contract.md](contract.md) (approved 2026-07-21, all 15 adversarial
> findings adjudicated — see [adversarial-review-contract.md](adversarial-review-contract.md)).
> Tier 4 → owner-approved plan + ADR + rollback required. ADR drafted at plan
> approval (deployment architecture; next free number).
> Build opens in a fresh conversation with `task-cycle-build` — re-ground from:
> contract.md · this plan · the v2 source at the pinned commit; run `make verify`
> first (Phase 0).

## Implementation pins (lead-designed; briefs reference, don't re-derive)

1. **Port discipline mechanics:** the v2 source commit is pinned in the port map at
   build open (`git -C ../discovery_policy_atlas rev-parse HEAD`); every ported file
   gets a port-map row (v2 path → v3 path · verbatim / targeted-edit / deleted / new)
   maintained as the build's running artefact — [port-map.md](port-map.md).
2. **Namespacing table (the A.1 brief's core):** CloudFormation stack ids
   `PaV3NetworkStack` / `PaV3CertStack` / `PaV3DatabaseStack` / `PaV3AppStack` (v2
   owns `NetworkStack`/`DatabaseStack`/`PolicyAtlasStack` — ids collide at the
   CloudFormation level, not just resources); SSM prefix `/policy_atlas_v3/*`;
   VPC `policy-atlas-v3-vpc-{env}`; ALB `pa-v3-alb`; target group `pa-v3-api-tg`
   (32-char limit); Aurora cluster `policy-atlas-v3-db-cluster` + instance ids;
   ECS cluster `policy-atlas-v3-cluster`; log groups `/policy_atlas_v3/*`; secret
   names `policy_atlas_v3/*`. Every copied fixed name resolves through this table —
   no ad-hoc renames.
3. **Fourth (mini) stack:** `PaV3CertStack` in `us-east-1` holding only the
   CloudFront certificate; CDK `cross_region_references=True` wires it to
   `PaV3AppStack` (eu-west-2). Everything else: `eu-west-2` (contract decision 6).
4. **Env rename (contract's plan-gate call, decided):** `OIDC_AUDIENCE` →
   `OIDC_CLIENT_ID` — under Cognito access-token semantics the value *is* the app
   client id; keeping the old name would misdescribe every deployment henceforth.
   No back-compat alias (nothing is deployed yet); dev `.env` files update once.
5. **Health check:** target group probes `/readyz` (readiness — don't route before
   the app can serve; `/healthz` stays the liveness probe for humans/scripts).
6. **Deploy entrypoint:** one script, `scripts/deploy.sh <env>` — steps in order:
   preconditions gate (dig NS · cdk bootstrap present incl. us-east-1 · app secret
   exists with enumerated keys · fonts present in bucket · ≥1 Cognito user) →
   `cdk deploy` all four stacks (backend image builds/pushes as a CDK asset) →
   scale service to 0 + wait stopped → run migration task (`aws ecs run-task`,
   command `alembic upgrade head`) + **fail-loud wait on exit code via
   `describe-tasks`** → scale service to 1 → frontend: build guard (full VITE_* set)
   → font injection into `dist/` → `vite build` → `s3 sync` → CloudFront
   invalidation. Abort at the first non-zero step.
7. **Deploy-invariant encoding (CDK, not prose):** `desired_count=1`,
   `min_healthy_percent=0`, `max_healthy_percent=100`, no autoscaling block,
   container `stop_timeout=10s` (bounded SIGTERM window — the walk executor must
   never drain-run through a deploy).
8. **Auth congruence semantics (contract decision 7, exact):** `auth.py` requires
   `token_use == "access"` and `client_id == settings.oidc_client_id`; RS256 /
   issuer / exp / sub checks unchanged; generic `aud` validation removed (PyJWT
   `audience=` param dropped; explicit claim checks). `dev_issuer.py` + mint CLI
   emit `client_id` + `token_use: "access"` (no `aud`). Conformance suite gains
   negative cases: `aud`-only token rejected · wrong `client_id` rejected ·
   `token_use: "id"` rejected · Cognito-shaped accepted.
9. **Pool/executor sizing (contract § capacity):** new envs `DB_POOL_SIZE`
   (default 5, prod 15) and `DB_MAX_OVERFLOW` (default 10) threaded to
   `create_engine`; prod task env sets `RUN_EXECUTOR_MAX=10`. Fargate task:
   2 vCPU / 8 GB initial (headroom arithmetic recorded in verification; values
   live in the committed config JSON — devops-tunable without code).
10. **CloudFront:** private S3 bucket + OAC; SPA fallback = 403/404 → `/index.html`
    (HTTP 200); default root object `index.html`; apex alias A-record; no caching
    of `index.html` beyond short TTL (assets are content-hashed by Vite).
11. **Config JSONs (contract decision 4):** committed without `aws_account_id`;
    `app.py` targeted edit reads the account from `CDK_DEFAULT_ACCOUNT`;
    `cdk.context.json` gitignored.
12. **v2 read-only invariant:** no v3 construct imports, modifies, or attaches to a
    v2-managed resource; the namespacing table is the enforcement surface, and the
    infra tests assert the v3 SSM prefix + stack names.
13. **No new prompt surfaces; no schema changes** — Alembic runs existing revisions
    only.

## Contract-check matrix (every contract-named check → one task)

| Contract-named check | Task |
|---|---|
| Infra unit tests: synth assertions, all four stacks, no AWS creds | A.3 |
| No-Supabase-remnants assertion (grep-level + template-level) | A.3 |
| Auth conformance suite incl. Cognito-shaped negatives | C.2 |
| FE↔real-API smoke (real HTTP + dev issuer + SSE, stub backends) | D.4 |
| Production build guard refuses on each missing VITE_* var | D.2 (script) / D.4 (test) |
| First-deploy preconditions checklist executable | D.2 |
| Live deploy + full-chain smoke incl. hosted-UI logout | E.2 |
| Parked/idle SSE stream ≥ 2 min through the ALB | E.2 |
| 3 concurrent runs + 10-run headroom arithmetic | E.2 |
| Deploy-invariant check over an executing walk | E.3 |
| Fonts served; font-guard still green | E.2 / every full gate |
| Port map complete (rubric 9) | E.4 |

## Tasks

### Phase 0 — baseline (½ day)
- T0.1 `lead` inline: `make verify` green on the branch base; pin the v2 source
  commit into port-map.md. **[FULL — mandatory build-open baseline]**

### Phase A — port + namespace + delete (2 days)
- A.1 `lead`: the port map + namespacing application order + the per-file delete
  list (Supabase blocks, Cloud Map, autoscaling) + config JSON schema (minus
  account id, eu-west-2, capacity values). *Seam design: this brief IS the
  copy-first discipline; everything downstream executes it.*
- A.2 `fast-worker`: execute the port per A.1 — copy v2 files into `infra/`, apply
  the namespacing table, apply the delete list, VPC name filters on every lookup,
  `load_secret` URL-format targeted edit, health-check path + deploy-invariant
  values per pins 5/7. Mechanical against an exact map.
- A.3 `codex`: infra unit tests — synthesized-template assertions for all four
  stacks with stubbed context (no AWS creds): resources present/absent
  (no Supabase, no Cloud Map, no autoscaling), SSM prefix, stack names, SG graph
  edges (Aurora ingress = API SG + migration SG + fck-nat SG only), deploy-invariant
  values, RETAIN policies (Cognito pool once B lands, Aurora snapshot). Wire
  `make -C infra test` into `make verify` (approved CI change).
  **[FULL — scaffold + CI wiring]**

### Phase B — new CDK surfaces (2–3 days)
- B.1 `lead`: Cognito construct design — pool (self-signup off, RETAIN, password/
  recovery posture), SPA client (code + PKCE, exact callback/sign-out URL list),
  hosted-UI domain, outputs → SSM/envs; CloudFront + cert-stack shape per pins
  3/10. *Auth infra design is a security seam.*
- B.2 `codex`: implement B.1 — Cognito constructs, `PaV3CertStack` +
  cross-region wiring, CloudFront + OAC + SPA fallback + apex alias, private font
  bucket; extend A.3's test suite to cover them.
- B.3 `codex`: app-stack service wiring — env/secret map from `settings.py`
  (post-rename), composed `DATABASE_URL` from the secret's connection-string field,
  `APP_ORIGIN`, migration task definition (same image, command override, migration
  SG), ALB idle-timeout explicit (≥ 4× the 15 s SSE heartbeat). Template tests
  extended. **[verify-fast — infra-only new files]**

### Phase C — gated backend edits (1–2 days)
- C.1 `lead`: auth-congruence edit design per pin 8 + pool-sizing seam per pin 9
  (exact claim checks, error taxonomy, settings surface). *The auth hard gate's
  design; security lane reviews the diff at step 7.*
- C.2 `codex`: implement `auth.py` + `dev_issuer.py` + mint CLI + settings rename
  (`OIDC_CLIENT_ID`) + conformance suite per pin 8; sweep the repo for
  `OIDC_AUDIENCE` references (envs, docs, tests, FE smoke fixtures).
- C.3 `fast-worker`: `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` settings + engine wiring +
  tests (defaults preserved; explicit values honoured).
  **[FULL — auth-gate class]**

### Phase D — image, deploy script, CI smoke (2–3 days)
- D.1 `codex`: backend `Dockerfile` (port v2's as base: uv + src-layout install,
  factory entrypoint, non-root user) + `.dockerignore` (everything gitignored,
  `.env*`, dev-issuer key material) + a build-context leak test (image filesystem
  contains no `.env`/key files).
- D.2 `codex`: `scripts/deploy.sh` per pin 6 + the preconditions checklist as
  executable checks + the widened production build guard + font injection step.
- D.3 `fast-worker`: `infra/DEPLOYMENT.md` — ported from v2 then corrected:
  first-deploy checklist, deploy-window + single-task caveats, SSM tunnel recipe
  (+ the local-API-against-Aurora second-instance warning), rate-limit caveat.
- D.4 `codex`: FE↔real-API smoke — CI job driving the built frontend over real
  HTTP with dev-issuer auth + SSE against stub backends (transport/auth/base-URL/
  error-mapping layer); build-guard refusal test.
  **[FULL — CI job class lands here; exercises the new gates end-to-end]**

### Phase E — live deploy + evidence (2–3 days; needs NS delegation live)
- E.1 `lead`: first staging deploy via `deploy.sh` — preconditions gate, fix-forward
  loop. *Live evidence adjudication (025 I.2 precedent).*
- E.2 `lead`: contract smoke — Cognito login → project → run → SSE → artefact →
  hosted-UI logout; parked stream ≥ 2 min; fonts; **3 concurrent rapid-effort runs**
  + 10-run headroom arithmetic recorded.
- E.3 `lead`: deploy-invariant check — second deploy **over an executing walk**:
  ECS event order (stop before start), migration between, sweep marks the walk
  `interrupted` per web-api.md, no boot failure.
- E.4 `lead`: verification.md (port map final, transcripts account-ID-scrubbed) ·
  deferred.md (close 4 items, cross-instance seam stays) · AGENTS.md phase note ·
  ADR status→Accepted. **[FULL — step-6 exit]**

## Executor routing note

Delegation-default holds; `lead` marks and their justifications: T0.1/E.1–E.4
(live evidence + step-6 adjudication — 025 precedent), A.1 (the port map is the
copy-first discipline's load-bearing brief), B.1/C.1 (auth-infra and auth-semantics
seam design; the security lane reviews their diffs). All implementation volume is
codex (judgment-bearing: CDK constructs, auth edits, Dockerfile, deploy sequencing,
smoke job) or fast-worker (mechanical against exact maps: A.2, C.3, D.3).

## Sizing

0.5 + 2 + 2–3 + 1–2 + 2–3 + 2–3 = **9.5–13.5 executor-days**; +20% contingency →
plan ~11–16. Live-check spend: 3 concurrent rapid runs + 1 sacrificial run for E.3
+ E.2's run — order ~$20–50 at the $15-standard-run anatomy (rapid runs are
cheaper); named here per the review-economy retro. Review stack budgets to a
mid-size slice (this is smaller than 025 — hold the pins).

## Gate consolidation summary

FULL `make verify`: T0.1 (baseline) · A.3 (scaffold + CI wiring) · C (auth-gate
class) · D.4 (new CI job exercised) · E.4 (step-6 exit). verify-fast: B.3 exit
(infra-only new files, no schema/app contact). E-phase live checks are additive
evidence, not verify substitutes.

## De-scope levers (pre-authorised order)

1. FE↔real-API smoke breadth (keep: auth + one GET + one SSE tail) · 2. Tunnel
recipe depth (keep the command + the warning) · 3. 3-concurrent → 2-concurrent
smoke. **Never:** deploy invariant, auth congruence + its negatives,
namespacing/v2-read-only, `.dockerignore` secret hygiene, preconditions gate.

## Rollback (Tier 4)

Repo: single squash; revert removes `infra/` + the two named backend touches
(auth congruence, pool sizing) — both regression-tested by the conformance suite
they ship with. Cloud: `cdk destroy PaV3AppStack PaV3DatabaseStack` (Aurora leaves
a final snapshot by RemovalPolicy; the Cognito pool is RETAIN — orphaned pools are
deleted manually only after explicit owner sign-off, never by rollback);
`PaV3NetworkStack`/`PaV3CertStack` destroy cleanly. Blast radius: the namespacing
table + v2-read-only invariant mean no rollback step can touch a v2 resource; v2
users are structurally unaffected throughout. DNS: v3 records live only in the v3
zone; worst case is the v3 domain going dark, never v2.

## Review-stack sizing (conversation C)

Tier 4: contract-verifier · `/code-review` medium (angles: CDK SG graph + secrets
handling · auth.py/dev_issuer diff · Dockerfile/.dockerignore · deploy-script
sequencing · infra tests) · security-auditor lane (Cognito config, token
verification, public exposure surface, image hygiene) · codex adversarial ·
human deep review. Exclude lockfiles and the port-map's verbatim-copied files from
review diffs (review the *deltas* against v2, per-angle scoping — the port map
gives reviewers the verbatim/edited split).
