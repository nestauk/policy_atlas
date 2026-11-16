---
type: Testing rule
title: Each parallel agent gets its own test database at 127.0.0.1, created with the vector extension, and never runs the shared suite
description: An agent that must run tests while the lead's gate or other agents use Postgres creates its own `policy_atlas_test_<name>` database (`createdb` then `CREATE EXTENSION IF NOT EXISTS vector`; the engine fixture migrates it), addresses it as 127.0.0.1 (localhost resolves to ::1 first and is refused), runs pytest with -p no:xdist on named files, and never `make test` or `make verify`. Timings taken under concurrent suites are not planning figures (the rev2 backfill took 49 minutes contended, 20 alone). A test token with a fixed short lifetime is a deadline too: a 60 s token failed a walk that took over a minute under load.
tags: [testing, postgres, agents, xdist, "057"]
timestamp: 2026-11-03
---

# Rule

- One database per agent, named for the agent, at `127.0.0.1`, with the `vector` extension
  created before the first test (the migrations need it); drop it when the agent is done.
- `-p no:xdist` on the named files; `make test` and `make verify` stay the lead's and run
  on an otherwise idle Postgres ([two suites on one Postgres collide](poll-deadline-tests-under-parallel-load.md)).
- The lead does not `git stash` while agents edit
  ([briefs forbid git stash](parallel-agent-briefs-forbid-git-stash.md)); at the 057 review
  the lead did it once for a ruff comparison and was lucky.
- A contended timing is an upper bound, not a planning figure; say which suites ran beside
  it.
- A test helper that mints tokens with a fixed lifetime sets a deadline on every test that
  uses them; size it to the slowest walk under a loaded gate (600 s), not to a demo.
- Tests that never ask for the `engine` fixture used to depend on an earlier test migrating
  the worker's database; adding tests reshuffled the order and exposed it (task 058).
  `conftest` now migrates each worker's database once before any test, and a one-file run
  with `-p no:xdist` gets the same.

# Why

Task 057's build ran nine agent databases beside the gate; the review ran three. The
`localhost` refusal and the missing extension each cost an agent a round. The HEAD gate's
one failure at the review was a 60 s token on a walk that took longer than that at a load
average of 170.
