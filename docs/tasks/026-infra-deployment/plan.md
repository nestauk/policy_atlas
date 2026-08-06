# Implementation plan: 026-infra-deployment

> **Status:** **APPROVED — 2026-07-21 · owner** ("Plan approved, draft the ADR and
> close out the design phase"), as rev 2. Plan-phase adversarial review DONE
> (codex; 3 BLOCKER + 14 MAJOR + 2 MINOR, **19/19 adjudicated in** — see
> [adversarial-review-plan.md](adversarial-review-plan.md)). ADR 0026 Accepted
> same date.
> Contract: [contract.md](contract.md) (approved 2026-07-21; none of the plan
> findings contradict it — they are plan-internal reworks).
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
   owns the bare names — collision is at the CloudFormation level too); SSM prefix
   `/policy_atlas_v3/*`; VPC `policy-atlas-v3-vpc-{env}`; ALB `pa-v3-alb`; target
   group `pa-v3-api-tg` (32-char limit); Aurora cluster `policy-atlas-v3-db-cluster`
   + instance ids; ECS cluster `policy-atlas-v3-cluster`; **API service
   `policy-atlas-v3-api-service`; task families `policy-atlas-v3-api` and
   `policy-atlas-v3-migrate`** (plan-adv F8 — families are account/region-scoped;
   v2's `policy-atlas-backend` family must never receive v3 revisions); log groups
   `/policy_atlas_v3/*`; secret names `policy_atlas_v3/*`. Every copied fixed name
   resolves through this table — no ad-hoc renames. **A.3 enforces the whole table
   test-driven** (pin 13).
3. **Fourth (mini) stack:** `PaV3CertStack` in `us-east-1` holding only the
   CloudFront certificate; CDK `cross_region_references=True` wires it to
   `PaV3AppStack` (eu-west-2). Everything else: `eu-west-2` (contract decision 6).
4. **Env rename (decided):** `OIDC_AUDIENCE` → `OIDC_CLIENT_ID`; no back-compat
   alias (nothing deployed yet); C.2 sweeps every reference (envs, docs, tests,
   smoke fixtures).
5. **Health check:** target group probes `/readyz` (DB `SELECT 1` readiness;
   `/healthz` stays liveness). `/readyz` does NOT prove migration state
   (plan-adv F14) — deploy ordering (pin 7) is what makes boot-after-migrate safe;
   the probe is routing hygiene, not the invariant.
6. **First-deploy bootstrap is staged, not circular** (plan-adv F4/F6): app.py
   gains a context guard (`-c stage=network|all`, targeted edit) so
   `PaV3NetworkStack` deploys alone first — `Vpc.from_lookup` in the consumer
   stacks is a synth-time context query and MUST NOT run before the VPC exists.
   First-deploy order: preconditions gate A (dig NS · `cdk bootstrap` present in
   eu-west-2 + us-east-1 · app secret exists with enumerated keys) →
   `cdk deploy -c stage=network PaV3NetworkStack` → `cdk deploy` remaining stacks
   (API service is created at `desired_count=0` — pin 7 — so nothing serves) →
   preconditions gate B (now satisfiable: upload fonts to the bucket · create ≥1
   Cognito user) → migration task → scale service to 1 → frontend publish.
7. **Deploy-invariant encoding (CDK, not prose; plan-adv F5):** the CDK template
   pins **`desired_count=0`** permanently — every `cdk deploy` therefore *stops*
   the service as part of the CloudFormation update (stop-old is template-enforced,
   not script-hoped); the deploy script then runs migrations and scales to 1 via
   `aws ecs update-service` (deliberate, documented drift until the next deploy).
   `min_healthy_percent=0`, `max_healthy_percent=100`, no autoscaling, container
   `stop_timeout=10s`. Steady-state deploy order: `cdk deploy` (service → 0, new
   task def registered) → wait tasks stopped → migration task + **fail-loud wait
   on exit code via `describe-tasks`** → scale to 1 → build guard → fonts →
   `vite build` → `s3 sync` → invalidation. Abort at first non-zero step.
8. **Auth congruence semantics (contract decision 7, exact):** `auth.py` requires
   `token_use == "access"` and `client_id == settings.oidc_client_id`; RS256 /
   issuer / exp / sub checks unchanged. Generic `aud` validation removed —
   **explicitly**: PyJWT verifies `aud` by default even without an `audience=`
   argument (plan-adv F9), so the decode call sets `options={"verify_aud": False}`
   and the Cognito claim checks are explicit code. `dev_issuer.py` + mint CLI emit
   `client_id` + `token_use: "access"` (no `aud`). Conformance negatives:
   `aud`-only token rejected · wrong `client_id` rejected · `token_use: "id"`
   rejected · Cognito-shaped accepted.
9. **Pool/executor sizing:** new envs `DB_POOL_SIZE` (default 5, prod 15) and
   `DB_MAX_OVERFLOW` (default 10) threaded to `create_engine`; prod task env sets
   `RUN_EXECUTOR_MAX=10`. Fargate task 2 vCPU / 8 GB **initial hypothesis** —
   E.2 measures (pin 14) and verification records measured headroom, not just
   arithmetic (plan-adv F12). Values live in the committed config JSON.
10. **CloudFront:** private S3 bucket + OAC; SPA fallback 403/404 → `/index.html`
    (200); default root object; apex alias; short TTL on `index.html` only.
    **Fonts are injected into `frontend/public/fonts/` BEFORE `vite build`**
    (plan-adv F10 — Vite empties `dist/`; `public/` is copied in at build, exactly
    the contract's local-dev path).
11. **Config JSONs (contract decision 4):** committed without `aws_account_id`;
    `app.py` reads `CDK_DEFAULT_ACCOUNT`; `cdk.context.json` gitignored.
12. **Deploy-time wiring via SSM** (plan-adv F11): `PaV3AppStack` exports what
    `run-task` needs — private subnet ids, migration SG id, migration task-def ARN,
    cluster ARN — under `/policy_atlas_v3/deploy/*`; `deploy.sh` reads them (no
    hand-copied ids; `awsvpcConfiguration` fully specified).
13. **Namespacing + lookup verification** (plan-adv F18): A.3's suite is
    **table-driven over pin 2** (every name asserted in the synthesized templates)
    plus a lookup-filter test asserting the `vpc_name` filter appears in the
    generated context-provider query (template assertions can't see lookups —
    the context query can); unit synth runs with bundling skipped
    (`aws:cdk:bundling-stacks: []`) so tests need neither Docker nor AWS.
14. **Capacity measurement** (plan-adv F12): during E.2's 3-concurrent-run window,
    record CloudWatch task memory/CPU peak, `pg_stat_activity` connection
    high-water, and per-walk memory delta; the 10-run headroom claim is computed
    from these measurements.
15. **SSM tunnel mechanics** (plan-adv F2/F16): the fck-nat instance gets the SSM
    managed-instance role (targeted NetworkStack edit; fck-nat AMI ships the
    agent), its SG id is exported to SSM, and the DB stack adds the
    fck-nat→Aurora 5432 ingress rule (rubric 13 names this path as deliberate).
    The tunnel recipe (session command, port-forward args, secret lookup) is
    **designed in B.1** (lead); D.2 documents it mechanically.
16. **v2 read-only invariant:** no v3 construct imports, modifies, or attaches to
    a v2-managed resource; pins 2/13 are the enforcement surface.
17. **No new prompt surfaces; no schema changes** — Alembic runs existing
    revisions only.

## Contract-check matrix (every contract-named check → one task)

| Contract-named check | Task |
|---|---|
| Infra unit tests: synth assertions, all four stacks, no AWS creds/Docker | A.3 |
| No-Supabase-remnants + full namespacing-table + lookup-filter assertions | A.3 |
| Image hygiene: `.dockerignore` covers gitignored patterns + layer scan | A.4 |
| Auth conformance suite incl. Cognito-shaped negatives | C.2 |
| FE↔real-API smoke (real HTTP + dev issuer + SSE, stub backends) | D.3 |
| Production build guard refuses on each missing VITE_* var | D.1 (script) / D.3 (test) |
| First-deploy staged bootstrap executable (gates A and B) | D.1 |
| Live deploy + full-chain smoke incl. hosted-UI logout | E.2 |
| Parked/idle SSE stream ≥ 2 min through the ALB | E.2 |
| 3 concurrent runs + measured 10-run headroom (pin 14) | E.2 |
| Deploy-invariant check over an executing walk | E.3 |
| Fonts served; font-guard still green | E.2 / every full gate |
| Port map complete (rubric 9) | E.4 |

## Tasks

### Phase 0 — baseline (½ day)
- T0.1 `lead` inline: `make verify` green on the branch base; pin the v2 source
  commit into port-map.md. **[FULL — mandatory build-open baseline]**

### Phase A — port + namespace + delete + image (2½ days)
- A.1 `lead`: the port map + namespacing application order + per-file delete list
  (Supabase blocks, Cloud Map, autoscaling) + config JSON schema + the app.py
  stage-guard design (pin 6). *Seam design: this brief IS the copy-first
  discipline.*
- A.2 `fast-worker`: execute the port per A.1 — copy v2 files into `infra/`, apply
  the namespacing table, apply the delete list, VPC `vpc_name` filters on every
  lookup, `load_secret` URL-format edit **+ runtime bump to Python 3.12**
  (plan-adv F13), fck-nat SSM role + SG export + Aurora ingress rule per pin 15,
  health-check path + invariant values per pins 5/7, deploy SSM exports per
  pin 12. Mechanical against an exact map.
- A.3 `codex`: infra unit tests per pin 13 — table-driven namespacing assertions,
  resources present/absent (no Supabase, no Cloud Map, no autoscaling,
  `desired_count=0`), SG graph edges (Aurora ingress = API + migration + fck-nat
  SGs only), RETAIN policies, lookup-filter context test, bundling skipped. Wire
  `make -C infra test` into `make verify` (approved CI change).
- A.4 `codex` (moved from Phase D — plan-adv F7: app-stack synth needs the image
  asset to exist): backend `Dockerfile` (port v2's as base: uv + src-layout
  install, factory entrypoint, non-root user) + `.dockerignore` + hygiene tests
  per plan-adv F19: a coverage test asserting every gitignored pattern is
  dockerignored, plus a layer scan (no `.env*`/key material in any layer, not
  just the final filesystem). **[FULL — scaffold + CI wiring]**

### Phase B — new CDK surfaces (2–3 days)
- B.1 `lead`: Cognito construct design — pool (self-signup off, RETAIN,
  password/recovery posture), SPA client (code + PKCE, exact callback/sign-out URL
  list), hosted-UI domain, outputs → SSM/envs; CloudFront + cert-stack shape per
  pins 3/10; **the SSM tunnel recipe** per pin 15. *Auth-infra + network-access
  seam design.*
- B.2 `codex`: implement B.1 — Cognito constructs, `PaV3CertStack` + cross-region
  wiring, CloudFront + OAC + SPA fallback + apex alias, private font bucket;
  extend A.3's suite to cover them.
- B.3 `codex`: app-stack service wiring — **the full env/secret map, enumerated
  from `settings.py` AND the direct `os.environ` readers** (plan-adv F3:
  `api/deps.py` provider keys, `core/tracing.py` Langfuse, `search_live.py` —
  the brief lists the grep, the build enumerates and records the map in
  DEPLOYMENT.md), composed `DATABASE_URL` from the secret's connection-string
  field, `APP_ORIGIN`, `PA_BACKEND_MODE`, migration task definition, ALB
  idle-timeout explicit (≥ 4× the 15 s heartbeat).
  **[verify-fast + `make -C infra test` — plan-adv F17: verify-fast alone never
  runs the infra suite this phase extends]**

### Phase C — gated backend edits (1–2 days)
- C.1 `lead`: auth-congruence edit design per pin 8 + pool-sizing seam per pin 9.
  *The auth hard gate's design; security lane reviews the diff at step 7.*
- C.2 `codex`: implement `auth.py` (+`verify_aud: False`, explicit claim checks) +
  `dev_issuer.py` + mint CLI + settings rename + conformance suite per pin 8;
  repo-wide `OIDC_AUDIENCE` sweep.
- C.3 `fast-worker`: `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` settings + engine wiring +
  tests. **[FULL — auth-gate class]**

### Phase D — deploy script, docs, CI smoke (2 days)
- D.1 `codex`: `scripts/deploy.sh` per pins 6/7/12 (staged bootstrap, gates A/B,
  template-enforced stop, migration wait, scale-up, frontend publish incl. the
  widened build guard + `public/fonts` injection). The pins ARE the design —
  the brief is self-contained (plan-adv F15 discharged by pins 6/7/12).
- D.2 `fast-worker`: `infra/DEPLOYMENT.md` — first-deploy checklist (gates A/B),
  deploy-window + single-task caveats, the B.1-designed tunnel recipe verbatim
  (+ second-instance warning), rate-limit caveat, env/secret map from B.3.
  Mechanical: every judgment input is a named artefact (plan-adv F16).
- D.3 `codex`: FE↔real-API smoke CI job (real HTTP + dev-issuer + SSE against
  stub backends) + build-guard refusal test.
  **[FULL — CI job class lands here]**

### Phase E — live deploy + evidence (2–3 days; needs NS delegation live)
- E.1 `lead`: first staging deploy via `deploy.sh` (staged bootstrap), fix-forward
  loop. *Live evidence adjudication.*
- E.2 `lead`: contract smoke — Cognito login → project → run → SSE → artefact →
  hosted-UI logout; parked stream ≥ 2 min; fonts; 3 concurrent rapid runs **with
  pin-14 measurements captured**; headroom computed from measurements.
- E.3 `lead`: deploy-invariant check — second deploy **over an executing walk**:
  CFN stops service (template-enforced), migration between, new boot's sweep marks
  the walk `interrupted` per web-api.md, no boot failure.
- E.4 `lead`: verification.md (port map final, account-ID-scrubbed transcripts) ·
  deferred.md (close 4 items; cross-instance seam stays) · AGENTS.md phase note ·
  ADR status→Accepted. **[FULL — step-6 exit]**

## Executor routing note

Delegation-default holds; `lead` marks: T0.1/E.1–E.4 (live evidence + step-6
adjudication — 025 precedent), A.1 (the port map is the copy-first discipline's
load-bearing brief), B.1/C.1 (auth-infra, tunnel-access and auth-semantics seam
design; security lane reviews their diffs). Implementation volume: codex
(judgment-bearing: CDK constructs + tests, Dockerfile+hygiene, auth edits, deploy
script, smoke job) or fast-worker (mechanical against exact maps/artefacts: A.2,
C.3, D.2 — D.2 re-scoped mechanical per plan-adv F16 by moving recipe design into
B.1).

## Sizing

0.5 + 2.5 + 2–3 + 1–2 + 2 + 2–3 = **10–13.5 executor-days**; +20% contingency →
plan ~12–16. Live spend: 3 concurrent rapid runs + 1 sacrificial (E.3) + E.2's
run — order ~$20–50. Review stack budgets to a mid-size slice.

## Gate consolidation summary

FULL `make verify`: T0.1 (baseline) · A.4 (scaffold + CI wiring + image) ·
C.3 exit (auth-gate class) · D.3 (new CI job exercised) · E.4 (step-6 exit).
verify-fast **plus `make -C infra test`**: B.3 exit (plan-adv F17). E-phase live
checks are additive evidence, not verify substitutes.

## De-scope levers (pre-authorised order)

1. FE↔real-API smoke breadth (keep: auth + one GET + one SSE tail) · 2. Tunnel
recipe depth (keep the command + the warning) · 3. 3-concurrent → 2-concurrent
smoke (measurements still captured). **Never:** deploy invariant + its
template-enforced stop, auth congruence + negatives, namespacing/v2-read-only,
image hygiene, staged-bootstrap gates.

## Rollback (Tier 4)

Repo: single squash; revert removes `infra/` + the two named backend touches
(auth congruence, pool sizing) — both regression-tested by the suites they ship
with. Cloud: `cdk destroy PaV3AppStack PaV3DatabaseStack` (Aurora final snapshot
via RemovalPolicy; the Cognito pool is RETAIN — manual deletion only on explicit
owner sign-off); `PaV3CertStack`/`PaV3NetworkStack` destroy cleanly. Blast
radius: pins 2/16 mean no rollback step can touch a v2 resource; v2 users are
structurally unaffected. DNS: v3 records live only in the v3 zone; worst case is
the v3 domain going dark, never v2.

## Review-stack sizing (conversation C)

Tier 4: contract-verifier · `/code-review` medium (angles: CDK SG graph + secrets
handling · auth.py/dev_issuer diff · Dockerfile/.dockerignore + hygiene tests ·
deploy-script sequencing vs pins 6/7 · infra tests) · security-auditor lane
(Cognito config, token verification, public exposure, image hygiene, tunnel
IAM) · codex adversarial · human deep review. Exclude lockfiles and verbatim-
copied files from review diffs (the port map gives reviewers the verbatim/edited
split; review the deltas against v2).
