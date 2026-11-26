---
type: Convention
title: How a request size limit works in an ASGI middleware here (order, disconnect, what tests can prove)
description: Facts behind api/body_limit.py. A middleware that stops a body returns http.disconnect and writes its own reply (FastAPI turns an exception raised in receive into a 400); it is added before CORS so its reply carries the CORS headers; a body no code reads costs no memory; uvicorn has no body limit and the firewall reads 8 KB; the test client joins a streamed body into one message; FastAPI reads and parses a body before the sign-in dependency runs.
tags: [api, asgi, middleware, starlette, fastapi, uvicorn, security, testing]
generated:
  by: process:okf-migrate
  at: 2026-11-26
---

# Rule

ASGI (Asynchronous Server Gateway Interface) is the interface between the web server
(uvicorn) and the app. These facts decided the shape of `api/body_limit.py`.

1. **uvicorn has no limit on the size of a request body**, and a WAF (Web Application
   Firewall) on a load balancer reads only the first 8 KB. The limit must be in the app.
2. **A middleware cannot stop a body by raising from `receive`.** FastAPI turns any
   exception raised while it reads a body into a 400 reply. The limiter returns an
   `http.disconnect` message, drops what the app then sends, and writes the 413 itself.
3. **Starlette puts a middleware added later outside one added earlier.** A middleware that
   writes its own error reply is added before CORS, so the reply gets the CORS and
   security headers and a browser can read it.
4. **A body that no code reads costs no memory.** uvicorn stops taking data from the
   network after about 64 KB until the app asks for more. A running count in `receive`
   therefore covers every body that can use memory; a route that never reads its body
   (a 404, a 405, a `GET`) replies without a 413, and that is safe.
5. **FastAPI reads and parses a JSON body before it runs the sign-in dependency.** A larger
   limit on one path (the theory of change upload) is open to requests with no sign-in up
   to that limit.
6. **After a reply has started, the only honest stop is an error.** A plain return ends a
   cut-off streamed reply as if it were complete. The limiter raises, uvicorn closes the
   connection and logs one error. Only a signed-in client that sends a large body to a
   streaming route reaches this.
7. **Starlette's test client joins a streamed request body into one message.** A test with
   a generator body proves "no `Content-Length`", not "many chunks". Count across messages
   in a test at the middleware, and check chunked requests on a real uvicorn with `curl`.

# Why

Each fact was checked on a real uvicorn during the build and the review of the size limit:
a 200 MB chunked body to an unknown path used no memory and got a 404; a raise from
`receive` came back as a 400; the 413 written inside CORS carried
`access-control-allow-origin`. Three review lanes reported fact 4 as a defect, so it is
written down with its evidence.
