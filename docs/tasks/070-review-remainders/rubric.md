# Rubric: 070-review-remainders

The task is **done only if every box holds**. Item ids (A1 to A3) are the contract's.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes.
3. [ ] No approval-gated change beyond the two the contract names (A1 public interface,
       A2 request header). No schema, auth, dependency, CI, config or scaffold change.
4. [ ] No generated file edited by hand: `frontend/openapi.json` and the frontend types
       come from `make openapi-sync`, and `make drift-check` passes.
5. [ ] No test deleted, skipped or weakened.
6. [ ] Verification evidence recorded in [verification.md](verification.md).
7. [ ] Known gaps listed in [docs/deferred.md](../../deferred.md): the `api/app.py`
       body-size entry is removed, and the two gaps in the plan are added.
8. [ ] Review stack for Tier 3 ran (contract verifier, code review, security review,
       adversarial review), with findings in [verification.md](verification.md).

Slice-specific:

9. [ ] **A1:** a request with a `Content-Length` above the limit gets HTTP 413 with no
       sign-in, the app behind the limiter is not called, and the reply carries the CORS
       header for the app's origin.
10. [ ] **A1:** a request with no `Content-Length` that streams more than the limit gets
        413. A normal small request passes.
11. [ ] **A1:** a theory of change upload of the largest allowed file (10 MB before
        encoding) still returns 201. A path that only looks like the upload path gets the
        default limit.
12. [ ] **A1:** the ops app refuses a body above the default limit.
13. [ ] **A1:** each text field in the plan's table refuses a value above its limit with
        HTTP 422, and accepts a value at the limit.
14. [ ] **A2:** a document request and a Europe PMC request each carry
        `Accept-Encoding: gzip, deflate`.
15. [ ] **A3:** when a batch and both of its halves fail with an outage error, the
        provider is called 3 times for that batch, and every text is reported as failed.
        This holds for OpenAI error types, for Bedrock error types and for a malformed
        reply.
16. [ ] **A3:** when a batch fails with an outage error and one half then works, that
        half's vectors are kept.
17. [ ] **A3:** a Bedrock `ValidationException` and a missing-credentials error are not
        treated as outages.
18. [ ] **A3:** the existing isolation test (one bad text, the others are embedded) and
        the existing throttling test stay green, unchanged.
