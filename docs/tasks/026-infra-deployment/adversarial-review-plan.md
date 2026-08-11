# Plan-phase adversarial review — task 026

Codex (read-only), 2026-07-21, on plan rev 1. 19 findings (3 BLOCKER · 14 MAJOR ·
2 MINOR); all lead-verified and adjudicated into plan rev 2. None contradict the
approved contract — all are plan-internal reworks. Dispositions:

| # | Sev | Finding (compressed) | Disposition (rev-2 location) |
|---|-----|----------------------|------------------------------|
| F1 | MAJOR | AGENTS.md still said "load-secret Lambda deleted", contradicting contract F3 | Fixed immediately in AGENTS.md (same commit) |
| F2 | MAJOR | fck-nat→Aurora ingress asserted but never implemented (v2 exports no fck-nat SG) | Pin 15; A.2 adds role/SG-export/ingress |
| F3 | MAJOR | B.3 env map missed `PA_BACKEND_MODE`/provider/Langfuse keys read outside `Settings` (deps.py, tracing.py, search_live.py) | B.3 brief enumerates from settings.py AND direct os.environ readers |
| F4 | BLOCKER | `Vpc.from_lookup` is a synth-time context query — cannot synth consumers before the v3 VPC exists (first deploy) | Pin 6: app.py stage guard; network stack deploys alone first |
| F5 | BLOCKER | deploy.sh booted the new API before migrations (reversed the invariant) | Pin 7: template pins `desired_count=0` — every CFN deploy stops the service; script migrates then scales to 1 |
| F6 | BLOCKER | Preconditions circular: fonts bucket + Cognito user don't exist pre-first-deploy | Pin 6: split into gate A (pre-stack) and gate B (post-stack, pre-scale-up) |
| F7 | MAJOR | A.3's synth gate precedes the Dockerfile the app-stack asset needs | Dockerfile moved D.1→A.4; tests skip bundling (pin 13) |
| F8 | MAJOR | Namespacing table missed ECS service + task-family names (families are account-scoped; v3 revisions could merge into v2's family) | Pin 2 extended (`policy-atlas-v3-api[-service]`, `policy-atlas-v3-migrate`) |
| F9 | MAJOR | PyJWT verifies `aud` by default even without `audience=` — dropping the param ≠ removing validation | Pin 8: explicit `options={"verify_aud": False}` + explicit claim checks |
| F10 | MAJOR | Font injection into `dist/` then `vite build` — Vite empties `dist/` | Pin 10: inject into `frontend/public/fonts/` before build (contract's own path) |
| F11 | MAJOR | Migration `run-task` had no awsvpc subnets/SG source | Pin 12: `/policy_atlas_v3/deploy/*` SSM exports; deploy.sh reads them |
| F12 | MAJOR | 2vCPU/8GB ten-run claim had no measurement feeding the arithmetic | Pins 9/14: sizing is a hypothesis; E.2 captures CloudWatch peaks, pg connection high-water, per-walk delta; headroom computed from measurements |
| F13 | MINOR | Retained `load_secret` ships deprecated Python 3.9 runtime | A.2: bump to 3.12 in the targeted edit |
| F14 | MINOR | `/readyz` (SELECT 1) can't detect migration state | Pin 5 caveat: ordering (pin 7) is the safety mechanism; probe is routing hygiene. No app change (respects contract's two-exceptions boundary) |
| F15 | MAJOR | D.2's brief depended on the internally-broken pin 6 | Discharged by rewritten pins 6/7/12; D.1 (deploy script) brief now self-contained |
| F16 | MAJOR | Tunnel recipe was assigned fast-worker with no v2 precedent to copy | Recipe design moved to B.1 (lead); D.2 documents mechanically from named artefacts |
| F17 | MAJOR | Phase B's verify-fast gate never runs the infra tests B extends | B.3 gate = verify-fast + `make -C infra test` explicitly |
| F18 | MAJOR | Namespacing/lookup verification too weak to catch a missed rename or wrong-VPC bind | Pin 13: table-driven assertions over the full pin-2 table + lookup-filter context test |
| F19 | MAJOR | Image-hygiene test checked final filesystem only, not build context/layers | A.4: gitignore⊆dockerignore coverage test + all-layers scan |

Reviewer verdict was "not safe to execute as drafted"; adjudication concurs — the
three blockers were real first-deploy failures. Rev 2 supersedes; the owner gate
reviews rev 2.
