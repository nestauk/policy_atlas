---
type: Integration quirk
title: The HTTP library decodes whatever Content-Encoding a reply names, not what the request offered
description: An Accept-Encoding request header does not limit what httpx expands. httpx picks its decoder from the reply's Content-Encoding (zstd when the zstandard package is installed, also stacked layers such as "gzip, gzip") and expands inside iter_bytes, before any size cap in our code. A size cap on a fetch from an arbitrary host needs a check of the reply header before the body is read.
tags: [evidence-search, fetch, httpx, security, compression]
generated:
  by: process:okf-migrate
  at: 2026-11-26
---

# Rule

- `Accept-Encoding` is a request to the host. A hostile host ignores it. httpx (the HTTP
  client library) reads the reply's own `Content-Encoding` header and expands the body
  with every decoder it has: gzip and deflate always, zstd when the `zstandard` package is
  installed (it is here, pulled in by another dependency), brotli when a brotli package is.
- A header that lists several formats (`gzip, gzip`) makes httpx expand the layers one
  after another.
- The expansion happens inside `response.iter_bytes()`. A size cap that counts the chunks
  from `iter_bytes()` sees the data only after it is expanded.
- So a fetch from an arbitrary host must check the reply's `Content-Encoding` before it
  reads the body. `fetch_live.py::_encoding_refused` refuses anything other than one plain
  layer of gzip or deflate, for the document fetcher and for the Europe PMC client.
- One gzip layer still expands each network chunk about 1,000 times before the cap (64 KB
  to about 66 MB). The full fix reads `iter_raw()` and expands with an output limit; it is
  in `docs/deferred.md`.

# Why

The first fix for a decompression-bomb finding only sent `Accept-Encoding: gzip, deflate`,
on the belief that "a server must honour the request header". Two review lanes showed the
gap with httpx 0.28.1 and zstandard 0.25.0: with that request header sent, a zstd reply of
6 KB and a `gzip, gzip` reply of 483 bytes each became 200 MB in one `iter_bytes()` step.
The test of the first fix checked only the request header, so it passed.
