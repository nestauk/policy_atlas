---
type: Integration quirk
title: docker save layout depends on the daemon's image store — OCI blobs vs legacy layer.tar
description: Under Docker Desktop's containerd store, docker save emits OCI layout (blobs/sha256/*); the legacy store emits */layer.tar. Layer-scanning tooling must handle both or it silently scans nothing.
tags: [docker, tooling, image-hygiene, security]
timestamp: 2026-07-28
---

# Rule

`docker save` output shape is a function of the *daemon's image store*, not the image:
containerd store → OCI layout (`blobs/sha256/*`, media types in `index.json`); legacy
graph-driver store → `<layer>/layer.tar`. `scripts/image_layer_scan.sh` handles both
(026 A.4, re-confirmed load-bearing in Phase E).

# Why

A scanner that globs only `*/layer.tar` finds zero layers under containerd and can
report a **clean pass over nothing** — the fail-open shape of a hygiene gate.

# Watch out

OS public CA trust stores (`/etc/ssl/certs/*.pem`, certifi bundles) legitimately match
naive `*.pem` "key material" patterns — exempt certificates, not keys (the 026 scan
exempts them explicitly; 151 such files in the backend image).
