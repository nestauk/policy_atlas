# Verification: 026-infra-deployment

> **Status: COMPLETE — phases 0/A–E all verified (E landed 2026-07-28 after the three
> operator preconditions cleared).** The system is live at `v3.policyatlas.uk`.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline @ f5deb02) | pass | full gate, before any change |
| `make verify` (step-6 tree @ c5e552f) | pass | includes the new `make -C infra test` (28 tests) |
| `make verify-fast` (A.2, C-phase gates) | pass | 1924 backend tests + mypy + ruff |
| `make -C infra test` | pass | 28 passed — synth assertions, no AWS/Docker needed |
| `make fe-api-smoke` | pass | 3/3 Playwright specs against the real local API |
| `make deploy-build-guard-test` | pass | refusal proven per missing VITE_* var |
| `bash scripts/image_layer_scan.sh` | pass | image builds; 9 layers scanned clean |
| `bash -n scripts/deploy.sh` | pass | shellcheck not installed locally (noted) |
| `bash scripts/deploy.sh bootstrap` (2026-07-28) | pass | gates A+B green; all four stacks live |
| `bash scripts/deploy.sh update` ×3 | pass | stop→migrate→scale→publish, 4/4 PASS each |
| `make verify` (step-6 exit @ E.4 tree) | pass | full gate, all suites |
| `make verify` (step-7 pre-review re-run) | pass | fresh conversation, self-verify gate |
| `make verify` (post-review-fix tree) | pass | full gate; infra suite now 29 tests (new hardening pins) |
| `make okf-validate` (post-step-8 knowledge) | pass | 99 concepts, 0 violations |

## Checks beyond the build

- **Infra unit suite** (`infra/tests/unit/`, 28 tests): table-driven namespacing over the
  port-map pin-2 table; v2-prefix absence; Supabase/Cloud Map/autoscaling absence; exactly
  one deploy Lambda (`load_secret`; CDK's Trigger-provider Lambda exempted); deploy
  invariants (`DesiredCount=0`, min/max healthy 0/100, `StopTimeout=10`, TG `/readyz`);
  Aurora SG ingress = exactly {API SG, migration SG, fck-nat SG} on 5432; fck-nat role has
  `AmazonSSMManagedInstanceCore`; Aurora `DeletionPolicy: Snapshot`; Cognito pool RETAIN +
  self-signup off + secretless PKCE client + exact callback/logout URLs; CloudFront OAC +
  SPA fallback + apex alias; buckets fully private; **lookup-filter test** reads the cloud
  assembly `manifest.json` missing-context queries and fails if any `vpc-provider` query
  loses the `tag:Name: policy-atlas-v3-vpc-staging` filter (negative-proven by removing
  the filter → `KeyError: 'tag:Name'`).
- **Auth conformance** (`backend/tests/api/test_auth_conformance.py`): Cognito-shaped
  accepted · `aud`-only rejected · wrong `client_id` rejected · `token_use: "id"`
  rejected · bogus `aud` alongside correct Cognito claims accepted (proves
  `verify_aud: False` doesn't resurrect the generic path).
- **Pool sizing** (`backend/tests/api/test_settings.py`): defaults/overrides/rejections;
  lifespan passes `pool_size`/`max_overflow` to `create_engine` (spied).
- **Image hygiene** (`infra/tests/unit/test_image_hygiene.py`): every gitignore pattern
  reachable in the backend build context is dockerignored; Dockerfile has non-root USER +
  factory CMD. Layer scan proves no `.env*`/`.dev-issuer/`/private-key material in ANY
  layer (public CA trust stores exempted). Image sanity: `import policy_atlas.api.app;
  import alembic` OK in-container; `alembic --help` OK.
- **FE↔real-API smoke** (browser, real HTTP): authenticated project-list GET renders ·
  project-create POST navigates to the project · stub run started and **"Searching
  sources" rendered from the real authenticated SSE tail** (fetch-streaming transport,
  not EventSource — the client attaches the bearer header).

## End-to-end command

```bash
make fe-api-smoke   # builds SPA w/ dev-issuer token, boots real API (stub mode,
                    # isolated policy_atlas_smoke DB), drives Chromium over real HTTP
```

Live-deploy end-to-end (Phase E, ran 2026-07-28):

```bash
export AWS_PROFILE=pa-dev AWS_REGION=eu-west-2 CDK_DEFAULT_ACCOUNT=<account>
bash scripts/deploy.sh bootstrap    # first deploy: gates A/B, 4 stacks, migrate, scale, publish
bash scripts/deploy.sh update       # steady-state redeploys (ran 3×)
```

**E.2 full-chain smoke** (Playwright/Chromium against the live system; key screenshots
and an account-scrubbed deploy transcript in [evidence/](evidence/) — landed at step 7,
which recovered them from the build session's scratchpad):
cold visit → auto-redirect to Cognito hosted UI → login (operator-created smoke user) →
project created → planner (live LLM) → run started → stage timeline streamed over
authenticated SSE → **parked/idle stream observed 130 s with zero reconnects and no
error UI** (ALB idle timeout 120 s never tripped the 15 s-heartbeat stream) →
hosted-UI sign-out lands on the Cognito domain → **fresh visit redirects to login
(re-auth required)**. Fonts: `/fonts/Averta-Regular.otf` 200 `font/otf`,
`/fonts/Zosia-Display.woff2` 200 `font/woff2` via CloudFront; SPA deep-link fallback 200.
**Artefact**: completed run renders a full synthesised evidence base (9 sections:
Key findings … Conclusions, References).

**E.2 concurrency** (3 runs planned+started in parallel browser pages, window
10:30–10:48 UTC): runs #1 and #2 completed end-to-end with artefacts; run #3 parked at
a real synthesis check-in, was answered live ("Synthesise as proposed"), then failed
honestly at the synthesis stage with OpenAI **429 quota-exhausted** (account billing
cap — the two failed-stage cards surface the provider error verbatim; every prior
stage completed). Measurements (pin 14, 2 vCPU/8192 MB task):
memory peak 10.2 % (≈ 840 MB) vs idle 4.4 % (≈ 360 MB) → **≈ 160 MB/walk → 10
concurrent ≈ 1.9 GB, > 4× headroom**; CPU one 1-min burst to 99 % (triple
acquire/screen overlap), otherwise ≤ 53 % — degrade-to-slower, never wrong; Aurora
connections high-water **8 of the 25** ceiling (pool 15 + overflow 10) → ~2/walk →
10 walks ≈ 22 ≤ 25, env-tunable. `pg_stat_activity` cross-checked live over the SSM
tunnel (9 connections incl. the observer).

**E.3 deploy-invariant over an executing walk** (the sign-out-fix redeploy landed while
the leg-1 walk was executing): ECS service events show task `ff7a3948…` **stopped
11:19:44 BST**, drained, steady state at 0; migration PASS between; new task `4cec833a…`
**started 11:25:59 BST**, steady 11:26:36 BST — stop-before-boot at the event level. The
new boot's sweep logged `continuation.sweep_orphan_without_attachment` (10:26:26 UTC =
11:26:26 BST, seconds after the new task steadied) for
the interrupted project; the UI shows the run `Interrupted`; no boot failure
(`/healthz`+`/readyz` 200). Bonus negative proof: a **no-change** CFN deploy does NOT
re-assert `DesiredCount=0` — caught when a frontend-only redeploy timed out at the
stop-wait; fixed with an explicit `scale_down_service` in the script tail (commit).

**SSM tunnel recipe validated verbatim** (pin 15): fck-nat instance located by stack
tag → `AWS-StartPortForwardingSessionToRemoteHost` → `psql` over TLS →
`pg_stat_activity` + `alembic_version` queried. (session-manager-plugin installed
user-local, no sudo.)

## Diff summary

v2's CDK app ported copy-first into `infra/` ([port-map.md](port-map.md) has the
per-file disposition table and the pinned v2 commit `db3027a`): three stacks namespaced
`PaV3*` with every fixed name resolved through the pin-2 table, Supabase apparatus
(Studio, postgres-meta, PostgREST+nginx, JWT Lambda + vendored PyJWT) deleted wholesale,
Cloud Map cut, autoscaling deleted. Deploy posture is template-encoded: `desired_count=0`
pinned so every `cdk deploy` stops the service; script (`scripts/deploy.sh`) owns
migrate→scale→publish ordering with fail-loud waits. New surfaces: Cognito
(`cognito_auth.py`), `PaV3CertStack` (us-east-1) + CloudFront OAC/SPA-fallback, private
font + SPA buckets, one-shot Alembic ECS task, SSM deploy/auth exports. Backend: the two
contracted edits only — auth congruence (`auth.py`, `dev_issuer.py`, settings rename
`OIDC_AUDIENCE`→`OIDC_CLIENT_ID`) and engine pool sizing. Backend Dockerfile + strict
`.dockerignore` authored (A.4). CI: `make -C infra test` joined `make verify`;
new `fe-api-smoke` job.

**Phase-E owner-approved frontend fixes (contract stop-condition instances, both
approved in-session 2026-07-28):**
1. **Cold-visit auth gating** (`OidcAuthProvider.tsx` + tests): first unauthenticated
   entry rendered the shell whose queries 401'd forever — nothing triggered
   `signinRedirect` (dev-token mode gates in the provider; every prior harness started
   pre-authenticated). The provider now gates: cold visits auto-redirect to the hosted
   UI with the route stashed; the shell never mounts tokenless.
2. **Sign-out control** (`AppShell.tsx`): `AuthApi.signOut` had no UI consumer — Cognito
   sessions had no exit. Header button added; hosted-UI logout + re-auth-required both
   asserted live.

**Phase-E operational findings (documented in DEPLOYMENT.md preconditions):**
- CDK bootstrap needs an IAM-capable principal; PowerUserAccess cannot run it (a failed
  attempt under PowerUser left a DELETE_FAILED toolkit stack in us-east-1 — cleaned by
  DevOps with admin creds).
- `ecs run-task` needs scoped `iam:PassRole` (`PaV3AppStack-*` roles,
  `iam:PassedToService: ecs-tasks.amazonaws.com`) — added to the operator permission set.
- The provisioned app secret carried v2's `LANGFUSE_HOST` key; code adapts (tracing
  accepts it natively) rather than patching a live secret.
- Staging's OpenAI quota exhausted during E.2 (run #3's 429) — live runs fail honestly
  until billing tops up.

**Flagged deviations / build findings (minor, resolved in-slice):**
1. **Smoke DB isolation** — the FE↔API smoke initially reused `policy_atlas_test`; its
   persisted rows broke 4 migration round-trip tests in full verify (they downgrade with
   existing data). Fix: smoke owns disposable `policy_atlas_smoke`, recreated per run,
   dropped at teardown; `policy_atlas_test` reset. Root-caused, not guessed.
2. **Layer-scan layout** — `docker save` under Docker Desktop's containerd store emits
   OCI layout (`blobs/sha256/*`), not legacy `*/layer.tar`; the scan script now handles
   both and exempts OS public CA trust stores (certificates, not key material).
3. **Smoke SSE assertion** — original spec asserted "Mapping the landscape"
   (= `characterise`, an orchestrator-discretionary stage — known project pitfall);
   corrected to the always-present acquire stage "Searching sources", which persists in
   the timeline (no race against stub-speed execution).
4. **A.3 "exactly one Lambda"** — CDK's `triggers.Trigger` synthesizes a framework
   provider Lambda; the assertion counts application Lambdas and exempts the provider.
5. Local-only environment incident (not a repo change): Docker Desktop's VM network was
   wedged (pulls hung indefinitely, gvisor tx errors); full process kill + relaunch
   fixed it. Cost ~1.5h wall clock.

## Review findings

Step 7 ran 2026-07-28 in a fresh conversation (adjudicator ≠ author). Lanes: contract
verifier (pinned Opus, read-only) · security auditor · Codex adversarial (read-only
rescue brief, family flip per the executor-provenance map) · Claude finder fan-out
(3 fast-worker lenses: correctness line-by-line on codex-written surfaces, cross-file
consistency, v2-delta/removed-behaviour vs `db3027a`) · live-trace content review
(lead, Langfuse) · `make okf-validate` via `make verify` (green before and after fixes).

**Process substitution (recorded):** `/code-review` is user-typed-only in the review
session (`disable-model-invocation`), so the Claude half of the heterogeneous pair ran
as the scoped 3-lens finder fan-out above — same angles, lens-matched pathspecs.
**Economy:** fast-worker ≈ 330K (≤ 500K ✓); reasoning-class ≈ 260K vs the 250K
guideline (contract-verifier ran long re-running suites + v2 diffs) — noted for the
review-economy retro thread. Codex tokens external.

**Live-trace lane (013 lesson):** E-window traces read for content, not just counts —
the timeline matches the E.2 narrative (leg-1 walk 10:13 UTC; three concurrent runs
from 10:28; synthesis check-in proposal 10:34; every chain terminates in synthesise).
Run #3's failure verified **in-trace**: two `synthesise:proposal` GENERATIONs at
10:53 UTC, level ERROR, `RateLimitError: Error code: 429 … exceeded your current
quota` verbatim — billing exhaustion, not a code path. A completed synthesise trace
(run `65a3948d…`) content-checked: proposal → agentic section turns with real
`lookup`/`search_chunks` tool calls → judge (gpt-5.4-mini) tiered-grounding verdicts →
repairs re-judged to tier_1 — validator/judge behaviour healthy on real outputs. No
un-flagged ERROR observations in the window.

**Adopted (fixed in-slice, this branch):**
1. *Fail-fast preflight* (Claude correctness, MAJOR): the production-build guard ran
   last, inside `publish_frontend` — a publish-config problem surfaced only after
   stop→migrate. `resolve_frontend_publish_config` now runs before `scale_down_service`
   (`scripts/deploy.sh`).
2. *SPA publish race* (Codex M9): `s3 sync --delete` deleted old hashed chunks before
   the (un-waited) invalidation propagated. Now: sync without `--delete` → invalidate →
   `wait invalidation-completed` → pruning sync.
3. *Aurora at-rest encryption* (security, MEDIUM — the only MEDIUM+): `storage_encrypted=True`
   + `deletion_protection=True` + 7-day backups; template-pinned by a new synth test.
   ⚠️ **StorageEncrypted forces cluster REPLACEMENT on the next deploy** — adopted now
   deliberately, while the DB holds smoke data only (flagged in the PR).
4. *Cognito client hardening* (security L3/L8): access 60 min explicit, refresh 24 h
   (was default 30 d in sessionStorage), `prevent_user_existence_errors` — synth-pinned.
5. *CloudFront security headers* (security L2): managed `SECURITY_HEADERS` response
   policy on both behaviors — synth-pinned.
6. *Supply-chain pinning* (security L5 + Codex M11, **convergent across families**):
   `aws-cdk-lib==2.261.0`, `cdk-fck-nat==1.6.22`, `npx cdk@2.1133.0`, uv image `:0.9`.
7. *Task-role secret grants dropped* (security INFO 1): ECS injects secrets via the
   execution role; the app never calls Secrets Manager (grep-verified) — task-role
   grants only widened a compromised process's reach.
8. *`OIDC_JWKS_URL` https-only* (security L6): plain `http://` on the verifier's trust
   root was a config foot-gun; local dev uses `OIDC_JWKS_PATH`.
9. *Dead `MigrationTaskSG` construct deleted* (v2-delta MINOR + contract-verifier N8,
   convergent): imported-and-discarded SG whose comment claimed deploy.sh used it.
10. *Test tightening* (Claude correctness M2/N3): the tautological ECS-secret assertion
    now requires a Secrets Manager reference shape; the fck-nat role test pins
    single-role + policy. Unused ported imports removed (port-map A.2 step 3 as stated).
11. *Runbook realignment* (Codex N12 + contract-verifier M1/M2, convergent):
    DEPLOYMENT.md — Cloud Map row cut, "script doesn't exist" note replaced, § 4
    rewritten to the as-built order (explicit scale-down, preflight, no-op-deploy
    exception), failure-recovery + stale-context + SSM-replacement caveats added,
    RETAIN-semantics corrected (retained pool ≠ identity continuity; `cdk import` to
    re-adopt), destroy preconditions (deletion protection off, fonts bucket emptied),
    fresh-account two-pass bootstrap documented. Port-map rows completed (ALB
    idle_timeout, migration-SG export). verification.md Langfuse bullet + E.3 timezone
    labels fixed (contract-verifier M3/N7).

**Deferred (docs/deferred.md):**
- *Deploy lock* (Codex M1): single-operator posture documented; lock seam recorded.
- *Reauth loop on persistent OIDC callback error* (Codex M8): second facet appended to
  the existing return-to seam entry.
- *Return-to router restoration* (Codex M5): **already deferred at E.4** — convergent
  with the build's own seam entry; no new action.

**Declined (recorded reasons):**
- *Post-CFN-failure outage* (Codex M2): inherent to the owner-approved template-pinned
  `desired_count=0` posture; fail-loud + rerun is the design. Recovery steps now in the
  runbook instead.
- *SSM coupling / stale-context* (Codex M3/M4): real CDK lifecycle caveats, not defects
  in scope for a single-env staging deploy — documented in the runbook caveats.
- *Bootstrap not one-shot* (Codex M7): deliberate fail-loud gate; two-pass flow now
  documented. Not a defect.
- *fck-nat SG narrowing* (security L7): a NAT must accept all VPC egress; the
  SSM-bastion path is the contracted tunnel deliverable (rubric 13). Accepted risk.
- *JWT clock-skew leeway* (security INFO 5): conformance suite pins exact-expiry
  semantics; Fargate clock drift is negligible; churn on a live-verified auth path
  declined. Revisit only if real-world boundary 401s appear.
- *Coarse authorization* (security INFO 3): **factually wrong** — the API is strictly
  owner-scoped (`api/routers/_common.py:40`, `projects.py:47`; 025's authz suite).
- *Sign-out token revocation* (security INFO 4): mitigated by the 24 h refresh validity.
- *`sslmode=verify-full`* (security INFO 6), *MFA* (INFO 2), *Cognito URL derivation
  from config* (contract-verifier N10): noted; single-env staging trade-offs, owner may
  opt in later.
- *Container-name / class-name renames* (cross-file N): container name is task-def-scoped
  (no v2 collision possible — the namespacing table's purpose); class renames would add
  v2-diff noise against copy-first discipline (rubric 9).
- */simplify + ponytail-review as separate passes*: the finder lanes already surfaced the
  dead code and unused imports (fixed above); wholesale simplification of live-verified,
  v2-diffable infra would trade review-provenance for churn. Skipped with this record.

**Build-flagged deviations — each re-examined, none carried silently:**
1. *Smoke DB isolation* — **confirmed as-is**: disposable `policy_atlas_smoke` is the
   right shape (the shared-test-DB trap is a knowledge candidate); migration
   round-trip tests green in this phase's `make verify`.
2. *Layer-scan OCI layout* — **confirmed empirically**: the correctness lane rebuilt
   the real image and re-ran the scan (9 layers clean; the 151 `/etc/ssl` exemptions
   are trust stores, not key material).
3. *Smoke SSE assertion → "Searching sources"* — **confirmed**: asserting the
   always-present acquire stage matches the project's characterise-is-discretionary
   rule; the trace lane re-verified characterise is non-terminal in the live window.
4. *A.3 exactly-one-Lambda provider exemption* — **confirmed**: CDK's
   `triggers.Trigger` framework Lambda is real; the exemption is correctly scoped to
   the provider (re-run green).
5. *Docker Desktop VM wedge* — **confirmed environmental**: no repo change; knowledge
   candidate only.

**Knowledge candidates (step 8):** all 16 build candidates adjudicated — 7 new concepts
authored, 9 folded into new concepts' watch-outs or existing concepts
(`testing-database`, `synthesise-is-run-terminus`, `macos-swap-presents-as-docker-wedge`),
zero declined; authored from build candidates **and** stack findings per the 014 retro
rule (`docs/knowledge/log.md` 2026-07-28 entry).

**Fake-done check on the fixes applied this phase:** no test relaxed or deleted; every
new invariant is positively asserted (`test_aurora_cluster_is_encrypted_guarded_and_backed_up`,
client-validity/headers pins); the two tightened assertions are strictly stronger; the
refresh-validity pin was corrected to CDK's rendered minutes (1440), not loosened.
`make verify` green at the post-fix tree.

## Rubric status

All 14 boxes hold at the post-review tree; three needed explicit adjudication:

- **1–7, 9, 10, 13, 14 — hold** (contract-verifier scoreboard, findings above folded).
- **8 — holds now**: Tier-4 stack ran as recorded above (contract verifier · Claude
  finder fan-out standing in for `/code-review` · security-auditor lane · Codex
  adversarial); human deep review = step 9 (PR).
- **11 — holds, wording adjudicated**: rubric says `desired_count=1`; the as-built,
  plan-approved (pin 7) encoding is **stronger** — template pins 0, the script owns the
  scale-to-1 — and the second-deploy invariant was evidenced over an executing walk
  (E.3). Adopted as satisfying the item's intent.
- **12 — holds, deviation adjudicated**: "config-only changes" was overtaken by two
  owner-approved contract stop-condition instances (cold-visit gating, sign-out) —
  recorded at E.2 with approvals in-session; the stack confirms both fixes as necessary
  (a cold visit had no authenticated path at all) and correctly scoped.
- **Evidence locality — discharged in-stack**: the contract asked for smoke screenshots
  + scrubbed transcript in the task folder; the review session recovered them from the
  build scratchpad, checked each screenshot for public safety, scrubbed the transcript
  (zero 12-digit identifiers remain), and landed them in [evidence/](evidence/)
  (hosted-UI login · SSE timeline · synthesis check-in card · full artefact · run #3's
  two verbatim 429 cards · post-sign-out re-auth). The stack additionally re-verified
  the live claims against Langfuse traces. Hosted-zone ID in contract.md is
  owner-authored, contract-time, and not on the private list — accepted explicitly.

## Intent & assumptions

- Gate consolidation as landed: phases A–D completed together in one build session; one
  FULL `make verify` at the final tree (c5e552f) covers the A.4/C.3/D.3 full gates, with
  verify-fast + infra-suite runs green at each intermediate checkpoint. The plan's gate
  map anticipated consolidation across consecutive gates.
- `LOG_LEVEL=INFO` is wired in the task env though no backend reader consumes it yet
  (v2 carry; harmless).
- `LANGFUSE_HOST` is the injected key (the provisioned secret carries v2's key name;
  tracing.py accepts both aliases — E.1 deviation above). ~~`LANGFUSE_BASE_URL` chosen~~
  — stale pre-E.1 bullet corrected by the review stack.

## Known unverified items

- Run #3's synthesis completion — blocked on the exhausted OpenAI quota (billing); the
  failure surface itself is evidence (honest 429 cards after all prior stages passed).
  Two other runs completed end-to-end with artefacts.
- A full 10-run live soak — deliberately not an acceptance check (contract): first real
  multi-user usage is the soak; sizing knobs are env-tunable and the measured headroom
  is recorded above.
- shellcheck never ran on deploy.sh (not installed); `bash -n` + three full live
  executions stand in.

## Public safety

No secrets, tokens, account ids, or IP allowlists in any committed file or in this
document (the misconfigured-account discovery above names no usable identifiers; config
JSONs carry no `aws_account_id` — decision 4). Deploy transcripts in Phase E must be
account-ID-scrubbed before landing here.

## Review handoff (step-7/8 inputs)

- **Executor provenance (family flip):** codex implemented A.3/A.4/B.2/B.3/C.2/D.1/D.3;
  fast-worker A.2/C.3/D.2; lead authored A.1/B.1/C.1 designs + review-time fixes
  (layer-scan OCI fix, smoke DB isolation, SSE assertion fix). Claude anchors review.
- **Diff-scoping:** exclude from review diffs: `docs/tasks/*` artefacts, the
  verbatim-copied portions of `infra/` (port-map.md gives the verbatim/edited split —
  review the deltas against v2 @ `db3027a`).
- **Adjudication items:** the 5 flagged deviations above; the auth diff
  (`9f40d32`) is the security lane's primary surface (contract hard gate).
- **Knowledge candidates** (014 retro — raw list for step 8):
  - PowerUserAccess and CDK: bootstrap (IAM role creation) and `ecs run-task`
    (`iam:PassRole`) both exceed it; day-to-day `cdk deploy` is fine because
    CloudFormation executes through the bootstrap roles. Scope PassRole to the stack's
    role prefix + `iam:PassedToService`.
  - CloudFormation only re-asserts a template value on a *changed* deploy: a pinned
    `DesiredCount=0` does not stop a scaled-up service on a no-op deploy — template
    pins need script-side alignment for config-only redeploys.
  - Provider-level auth gating must cover the COLD path, not just expiry: every
    pre-live harness (mock, dev-token, CI smoke) starts authenticated, so only a real
    cold visit against the real IdP exercises first-entry 401 handling.
  - An auth seam without a sign-out consumer passes every test and strands real users —
    assert the affordance, not just the API.
  - `history.replaceState` is invisible to react-router: return-to restoration needs a
    router navigate, not a history patch (deferred seam).
  - Cognito classic hosted UI duplicates its form for responsive layouts — UI automation
    needs `:visible` selectors.
  - oidc sessionStorage sessions don't survive hard reloads, but Cognito's own cookie
    makes the re-auth round-trip silent (no login form) — looks like a flash of
    "signing in", not a logout.
  - `docker save` layout depends on the daemon's image store (containerd OCI
    `blobs/sha256/*` vs legacy `layer.tar`) — already listed from A.4; confirmed
    load-bearing again in E.
  - Shared test DBs are a trap for migration round-trip tests: any harness that persists
    real rows (smoke, manual poking) breaks downgrade-with-data tests later and looks
    like a schema bug. Disposable per-harness DBs, always.
  - `docker save` layout depends on the daemon's image store: containerd store → OCI
    `blobs/sha256/*`; legacy store → `*/layer.tar`. Layer-scanning tools must handle both.
  - Docker Desktop VM network can wedge (API alive, all pulls hang, gvisor tx errors);
    app-level quit doesn't recycle the VM — full process kill + relaunch does.
  - Never assert orchestrator-discretionary stages (`characterise`) in UI tests — assert
    the acquire stage; recurring project pitfall, now bitten in a spec once.
  - CDK `triggers.Trigger` adds a hidden framework Lambda to the template — "exactly N
    Lambdas" assertions must exempt the provider.
  - The CDK lookup-filter can only be asserted via the cloud assembly's missing-context
    queries (`manifest.json`), never via template assertions — and CDK falls back to
    dummy context values silently, so a test that synthesizes "successfully" proves
    nothing about lookups.
  - PyJWT verifies `aud` by default when the claim is present even with no `audience=`
    argument — removing an audience check requires explicit `verify_aud: False` plus
    hand-rolled claim checks (plan-adv F9 held in practice).
  - uv src-layout images: `uv sync --no-dev --no-install-project --frozen` (deps layer)
    then post-COPY `uv sync --no-dev --frozen` (project) gives cacheable layers and a
    working `import policy_atlas` with no PYTHONPATH hacks.

## Deferred work

Closed by this slice (pending review-stack confirmation at step 8): licensed font
delivery (bucket + deploy-time injection) · deploy-invariant enforcement
(template-pinned `desired_count=0` + script ordering) · FE↔real-API smoke (adv-M6) ·
the widened `VITE_*` production build guard. **Stays open:** cross-instance
steering/live-tail seam (this slice enforces single-instance posture; scale-out remains
forbidden). `docs/deferred.md` edits land at E.4/step 8 against the final merged state.
