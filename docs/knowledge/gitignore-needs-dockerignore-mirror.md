---
type: Integration quirk
title: A .gitignore line without its backend/.dockerignore mirror turns make verify red one commit later
description: The infra image-hygiene test (`test_dockerignore_covers_gitignored_backend_content`) requires every gitignored path that could land in the backend image to be ignored by Docker too. Adding `PRODUCT.md` / `DESIGN.md` to `.gitignore` (2026-09-09) passed its own commit and failed the next slice's build-open baseline.
tags: [infra, docker, gitignore, make-verify, task-044]
timestamp: 2026-09-17
---

# Rule

Every line added to `.gitignore` that names a repo-root or `backend/` path gets the same line in
`backend/.dockerignore` in the same commit. The failure surfaces one commit later than its cause,
in whoever runs `make verify` next.

# Why

Task 044's build opened on a red base (`b4b1e93b` had ignored the local impeccable design files
without the mirror); the hotfix `5854676a` is two lines. Cheap to do, expensive to diagnose from
the infra suite's message alone.

# Citations

- `infra/tests` — `test_dockerignore_covers_gitignored_backend_content`
- [044 verification.md](../tasks/044-scoping-shell-baseline/verification.md) § Phase 0
