# 035 - Infrastructure diagram

Status: requested by the owner on 2026-09-08; documentation and presentation assets only.

## Outcome and scope

Create a presentation-ready infrastructure diagram for the Imagine Grant Round 2
application, using official AWS architecture icons. Deliver a landscape PDF,
high-resolution PNG and editable SVG, with a source-grounded explanation.

Represent the core architecture configured in this checkout. Do not certify live
AWS state. Clearly separate external providers from AWS-hosted services. Preserve
the single-task application and single-writer database posture. Document the
staging-only Metabase extension separately from the core diagram.

No runtime code, schema, auth, dependencies, CI, configuration or existing generated
files are changed. Existing uncommitted work is preserved. No secrets or AWS
account identifiers are read or included. Model route: not applicable.

Risk: tier 0, documentation and visual artefacts. Acceptance: source traceability,
correct service boundaries and flows, legible exports, visual inspection of the
rendered PDF, and focused repository checks. Full application verification is
unnecessary for this documentation-only task.

Owner extension, 2026-09-08: create a separate version showing a potential Bedrock
connection. Clearly label it proposed, retain the original exports, and make no
runtime or infrastructure changes.
