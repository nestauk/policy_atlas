# Plan

1. Read the CDK application, configuration, deployment wrapper, ADR 0026 and the
   web API deployment posture; distinguish current configuration from future intent.
2. Obtain official AWS architecture icons directly from AWS. Draw a 16:9 landscape
   composition with cloud, VPC and subnet boundaries, browser access, private
   compute and data, external providers, and supporting operations.
3. Produce PDF, PNG and editable SVG from a shared deterministic drawing source.
   Keep build instructions and provenance with the task.
4. Inspect the rendered export for clipping, overlap and readability; check every
   service and connection against source; record evidence and limitations.

## Bedrock variant

Add an optional renderer mode and official Bedrock icon. Show an explicitly
proposed HTTPS route through existing EC2 NAT to Bedrock, with invocation
permissions on the ECS task role. Retain the current external OpenAI route.
Verify current AWS endpoint/IAM documentation, export separate PDF/PNG/SVG files,
inspect the result, and confirm original exports remain byte-for-byte unchanged.
