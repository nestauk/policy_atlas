---
type: Runbook
title: macOS swap exhaustion presents as a Docker daemon wedge
description: Docker Desktop's VM wedges (API 500s, vCPU spin) long before anything names memory; check sysctl vm.swapusage first when Docker "breaks" mid-suite.
tags: [macos, docker, ops, diagnostics]
timestamp: 2026-07-10
---

# Rule

When Docker Desktop "breaks" mid-suite on macOS — its API returning 500s, the
VM's vCPUs spinning, containers unreachable — check memory pressure **first**:

```
sysctl vm.swapusage
```

Swap near its ceiling is the likely root cause; a Docker Desktop restart
recovers the wedge but only freeing memory prevents the next one.

# Why

During 017's Phase 1–2 gates the host reached ~15.8 GB of a 17 GB swap
ceiling; load average peaked ~240. The visible symptom was purely
Docker-shaped (two VM wedges, API 500s) — nothing in Docker's own errors
mentioned memory, and two restarts were burned before the swap reading
explained both.

# Watch out

The same pressure also produces the false test timeouts described in
[deadline clocks need spawn headroom](process-start-deadlines-need-spawn-headroom.md)
— one root cause, two unrelated-looking symptom families.

Second wedge family (026 E): the VM's *network* path can wedge independently —
API responsive, every pull hangs indefinitely, gvisor tx errors in the VM log,
memory fine. App-level quit doesn't recycle the VM; a full process kill +
relaunch does (~1.5h burned before that order was tried).

Third family (055 build, 2026-10-27): after six days up, the engine simply stopped answering
— every `docker` call (and so `make verify`) hung with no error and no load. `docker desktop
restart` from the shell recovered it without the GUI; a scripted quit-and-reopen of the app
was refused by the permission mode. Probe with a timeout first (`perl -e 'alarm 10; exec
@ARGV' docker info`; macOS has no `timeout`).
