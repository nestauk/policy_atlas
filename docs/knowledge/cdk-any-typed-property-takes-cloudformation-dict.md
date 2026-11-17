---
type: Integration quirk
title: A CDK L1 property typed `Any` takes a plain dict with CloudFormation's key names, not a typed Property
description: In aws-cdk-lib 2.261 `CfnLoggingConfiguration.logging_filter` is typed `Any`; a typed `LoggingFilterProperty` passed to it serialises with camelCase keys that CloudFormation rejects, and synth does not notice. Write such values as dicts with the PascalCase names from the CloudFormation reference, and assert the rendered keys in the synth test.
tags: [cdk, cloudformation, wafv2, l1-constructs, synth, integration-quirk]
timestamp: 2026-11-17
---

# Rule

The plan's assumption on 064b was "every nested value is built from the typed
`CfnWebACL.*Property` classes, so a wrong property name fails at synth". That holds only
for properties CDK types. When an L1 property is typed `Any` (the installed 2.261
`CfnLoggingConfiguration.logging_filter` is one), a typed Property object passed to it is
serialised with the library's own camelCase names (`defaultBehavior`, `filters`,
`actionCondition`), synth succeeds, the synth test can pin the wrong keys, and the first
deploy fails in CloudFormation, or worse, CloudFormation ignores the unknown keys and the
resource deploys without the setting.

So: for a property typed `Any`, pass a plain dict whose keys are the PascalCase names in
the CloudFormation resource reference (`DefaultBehavior`, `Filters`, `Behavior`,
`Requirement`, `Conditions`, `ActionCondition`, `Action`), and make the synth test assert
those names and that no rendered key starts lower-case. Check the type of every L1
property you set against the installed package, not the docs page, before trusting synth
to catch a misspelling.

The contract verifier found this on 064b by fetching the CloudFormation reference and
comparing it with the rendered template; the build's own test had locked in the defect.

# Citations

- [task 064b verification](../tasks/064b-waf-captcha/verification.md) § Review findings
  (contract verifier F1).
- `infra/infra/components/waf.py` (`logging_filter=`) and
  `infra/tests/unit/test_waf.py::test_w8_…`.
- CloudFormation: `AWS::WAFv2::LoggingConfiguration LoggingFilter`.
