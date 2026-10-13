# Verification - 8 September 2026

## Delivered

- `output/pdf/policy-atlas-infrastructure.pdf`: one landscape page, 1920 x 1080
  points, with searchable text.
- `output/pdf/policy-atlas-infrastructure.png`: 3840 x 2160 pixels.
- `output/pdf/policy-atlas-infrastructure.svg`: editable vector text, shapes and
  official AWS SVG icons, with title and descriptive metadata.
- Task README: caption, source mapping, scope, icon provenance and rebuild command.

## Evidence

1. Read CDK network, database, application and Cognito resources; environment
   configuration; deployment wrapper and workflows; ADR 0026; API deployment
   posture; live search and document retrieval code; staging Metabase contract.
   The README maps diagram claims to these sources.
2. Rendered using the task's `make render` target with the bundled Python runtime
   and Poppler. Initial renderer environment issues were resolved by providing
   a temporary Fontconfig file and writable font cache. No dependency changes.
3. Inspected the complete final PDF-to-PNG rendering. Fixed the initial overlap
   between the Aurora data description and backup caption. The final image has
   no clipped labels, overlapping text or connectors through service captions.
4. Independently rendered the SVG through Sharp and inspected its complete
   1920 x 1080 preview. Icons, boundaries, text and connectors render correctly.
5. Programmatically verified: one-page PDF, expected key service labels in
   extracted text, exact 3840 x 2160 PNG dimensions, and well-formed SVG XML.
6. `git diff --check`: passed.
7. `make audit-paths`: the first attempt could not access the default uv cache;
   retry with a writable cache hit an installed uv/macOS system-configuration
   panic. Running the exact underlying `scripts/audit_paths.py` with the bundled
   Python succeeded: 106 files checked, zero violations. The Makefile wrapper
   remains environment-blocked; the underlying check passed.

## Boundaries

No runtime or infrastructure changes, deployment, live AWS audit, or secrets
access. Full `make verify` was not required or run for this tier-0 artefact task.
All pre-existing modified and untracked Metabase files were left untouched.

The figure deliberately makes no horizontal-scaling, replica, UK-only processing
or current Bedrock claim. Staging analytics and simplified supporting resources
are documented in the README. The stale Next.js stack-header comment was flagged
in the README; implementation and ADR 0026 agree on React / Vite, so no change to
system intent or product specification was necessary.

## Bedrock proposal extension

- Produced separately named `policy-atlas-infrastructure-bedrock-proposed`
  PDF, PNG and SVG exports at the owner's request.
- Used the official Bedrock icon from the same AWS package. Dashed teal route
  shows existing NAT egress reaching the proposed Bedrock service; task-role
  authentication and non-deployed status are explicit.
- Checked AWS documentation for IAM invocation and streaming permissions,
  regional endpoints and the optional PrivateLink alternative. Linked sources
  and implementation assumptions in the README. No model selection is asserted.
- Inspected the complete final PDF raster and independently rendered SVG;
  no clipped labels, overlapping text or misplaced service boundaries.
- Programmatic checks passed: one-page PDF; Bedrock, proposed-status, task-role
  and current-OpenAI labels; 3840 x 2160 PNG; valid SVG XML.
- SHA-256 verification confirmed all three original exports are byte-for-byte
  unchanged. `git diff --check` passed. No runtime or infrastructure changes.
