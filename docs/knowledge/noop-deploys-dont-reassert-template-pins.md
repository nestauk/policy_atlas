---
type: Integration quirk
title: CloudFormation re-asserts a template value only on a changed deploy — pins need script-side alignment
description: A template-pinned value (DesiredCount=0) does not reset live drift on a no-op deploy — CloudFormation skips unchanged stacks entirely. Any invariant a script deliberately drifts from (scale-to-1) must also be re-asserted by the script, not just the template.
tags: [deployment, aws, cloudformation, cdk, invariant]
timestamp: 2026-07-28
---

# Rule

`PaV3AppStack` pins `DesiredCount=0` so every *changed* deploy stops the API service.
But CloudFormation only applies a template value when the stack actually changes: a
config-only redeploy (frontend-only, secret-only) is a **no-op** for the app stack and
leaves the scaled-up service running. `scripts/deploy.sh` therefore scales to 0
explicitly before its stop-wait (E.2 fix — the wait timed out on a frontend-only
redeploy before it).

# Why

A template pin is a *desired-state declaration evaluated at diff time*, not a
continuously-enforced invariant. Any value the deploy script deliberately drifts from
(here: `update-service --desired-count 1`) will survive every unchanged deploy.

# Watch out

Same mechanism, replacement direction: the app stack consumes network/DB identifiers
via SSM parameter names, resolved at deploy time. If an SSM-exported resource is
replaced (new physical ID, same name), the app template is byte-identical and its
deploy is skipped — stale IDs persist. Force-redeploy the consumer after any such
replacement; also reset `cdk.context.json` if the VPC itself was replaced
(`infra/DEPLOYMENT.md` § 4 caveats, 026 review Codex lane).
