---
type: Process rule
title: Binary verification evidence (screenshots, recordings) is never committed — attach it to the task PR
description: The repo is public and squash-merged blobs live in every clone forever; 026 and 027 committed 32 evidence PNGs before the pattern was caught at the 027 merge. Evidence dirs are gitignored; verification.md references the PR attachment.
tags: [process, task-cycle, git, public-repo, evidence]
timestamp: 2026-08-06
---

# Rule

Verification evidence that is binary — screenshots, screen recordings, exported
traces — never enters the git tree. Keep it in `docs/tasks/NNN-slug/evidence/`
locally (that path is gitignored), attach the files (or a zip) to the task PR,
and have `verification.md` reference the PR attachment. GitHub hosts PR
attachments permanently, keeps them next to the review they support, and they
cost clones nothing.

# Why

The repo is public and squash-merges: once a blob reaches `dev`, every clone
downloads it forever — git cannot diff, dedupe, or later remove it without a
history rewrite. Evidence accretes per task (026 added 8 PNGs, 027 had 24, 028
had 23 staged) and is point-in-time by nature: nobody re-reads a screenshot of
a dead layout, but everyone pays for it on clone. Screenshots of a staging app
are also a mild leak surface (URLs, account names, UI content) in a public
tree. Caught at the 027 merge (2026-08-06); 027/028 branches were stripped
before landing, 026's 8 remain on dev as accepted sunk cost.

# Scope

Text evidence (logs, command transcripts, diffs) stays committable inside
`verification.md` itself — the rule is about binaries. Spec *source* material
(e.g. `docs/specs/sources/**/screenshots/`) is content, not evidence, and is
exempt.
