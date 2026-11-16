---
type: Integration quirk
title: Lambda runs a container image as its own user, so the image's home directory and imports must survive a foreign uid
description: AWS Lambda ignores the image's USER and runs it as its own user; a home directory made by useradd --create-home is mode 700 and the function never starts (the Runtime Interface Emulator as uid 1000 reproduces it on a laptop). The handler must not import the operator CLI (its type-stub dependency is absent from the image and the import fails only in Lambda); `uv sync --no-group ops` must be on both sync lines; a test pins the Dockerfile lines that make the image start.
tags: [lambda, docker, infra, "057"]
timestamp: 2026-11-03
---

# Rule

- `chmod 755 /app` (or an equivalent world-readable application directory) after the
  `useradd --create-home` line; the Runtime Interface Emulator run as uid 1000 is the laptop
  proof (`docker run --user 1000 ... python -m awslambdaric <handler>`).
- The handler module imports nothing that pulls in the operator CLI or other dev-only
  dependencies; a subprocess test that hides the dev package catches it before the first
  cold start.
- `uv sync --no-group ops` on every sync line of the Dockerfile: the second line re-resolves
  and would reinstate the group.
- Pin the Dockerfile lines with a test (`tests/ops/test_dockerfile_lines.py`) so a later
  tidy cannot drop them; the acceptance evidence is the emulator run, not a reading of the
  file.

# Why

Task 057's function could not start under the emulator (the home directory was 700) and
its first import failed on `mypy_boto3_cognito_idp` through the CLI. Both found at the build
on the laptop; the contract verifier at review found that nothing pinned the two lines.
