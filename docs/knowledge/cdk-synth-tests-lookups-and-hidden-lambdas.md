---
type: Testing rule
title: CDK synth tests — lookups are only assertable via the manifest, and framework constructs add hidden Lambdas
description: CDK falls back to dummy context values silently, so a synth that "succeeds" proves nothing about from_lookup filters — assert the cloud assembly manifest's missing-context queries instead. And triggers.Trigger synthesizes a hidden provider Lambda, so exactly-N-Lambda assertions must exempt framework providers.
tags: [cdk, testing, infra, synth]
timestamp: 2026-07-28
---

# Rule

Two traps in template-assertion suites over a CDK app (026 A.3, both encoded in
`infra/tests/unit/test_synth.py`):

1. **Lookup filters.** `Vpc.from_lookup(vpc_name=...)` never appears in a template,
   and with no cached context CDK substitutes *dummy values silently* — a green synth
   proves nothing about the lookup. The only assertable artifact is the cloud
   assembly's `manifest.json` `missing` list: assert every `vpc-provider` query
   carries the `tag:Name` filter (negative-proven: removing the filter →
   `KeyError: 'tag:Name'`).
2. **Hidden framework Lambdas.** `triggers.Trigger` synthesizes its own provider
   Lambda. "Exactly one Lambda" must count *application* Lambdas and exempt the
   provider — otherwise the assertion is wrong the day it's written, or worse,
   loosened to `>= 1`.

# Why

Both failure modes are silent-pass shaped: the suite looks like it pins the invariant
while pinning nothing (lookups) or gets "fixed" by weakening (Lambda counts).
