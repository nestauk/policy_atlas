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
