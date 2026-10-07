# Completion rubric

Risk: Tier 3. The slice adds an internet-routed staging service, database, secrets and a network rule to the existing database security group. It does not change production, authentication, schema or database permissions.

- [x] Only staging enables the analytics stack.
- [x] Metabase runs without a public IP in private subnets and accepts traffic only from the shared ALB.
- [x] Metabase state uses a separate encrypted PostgreSQL instance with backups, deletion protection and snapshot removal policy.
- [x] Database credentials and the connection-details encryption key are injected from Secrets Manager and never appear as plaintext task environment values.
- [x] The ALB route uses a non-conflicting priority, hostname matching and `/api/health` checks.
- [x] DNS resolves the staging hostname to the shared ALB.
- [x] Logs have a defined retention period.
- [x] One-task deployments do not overlap old and new Metabase tasks during database migrations.
- [x] Policy Atlas database access is network-only; no broad credentials or grants are added.
- [x] Deployment preflight validates analytics configuration when enabled.
- [x] CDK unit tests and deployment checks pass through Makefile targets.
- [x] Operator documentation describes first-admin setup and the source-data follow-up.
- [x] Only the Metabase hostname route has a source-IP condition.
- [x] The listener rule resolves one to three CIDRs from SSM without committing
  their values in configuration or the synthesized template.
- [x] AWS deployment fails before CDK when the parameter is missing, malformed or
  exceeds the ALB per-condition limit.
