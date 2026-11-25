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
7. [ ] Known gaps listed; the `api/app.py` body-size entry in
       [docs/deferred.md](../../deferred.md) is removed, because A1 closes it.
8. [ ] Review stack for Tier 3 ran (contract verifier, code review, security review,
       adversarial review), with findings in [verification.md](verification.md).

Slice-specific:

9. [ ] **A1:** a request with a `Content-Length` above the limit gets HTTP 413 before the
       body is read and before sign-in. A request with no `Content-Length` that streams
       more than the limit also gets 413.
10. [ ] **A1:** a theory of change upload of the largest allowed file (10 MB before
        encoding) still returns 201.
11. [ ] **A1:** each text field in the plan's table refuses a value above its limit with
        HTTP 422, and accepts a value at the limit.
12. [ ] **A2:** every document request the fetcher sends carries
        `Accept-Encoding: gzip, deflate`, and no request offers zstd.
13. [ ] **A3:** when a batch and both of its halves fail with an outage error, the
        provider is called 3 times for that batch, and every text is reported as failed.
        This holds for the OpenAI backend and for the Bedrock backend.
14. [ ] **A3:** when one bad text fails a batch with an input error, the other texts are
        still embedded (the existing isolation test stays green, unchanged).
15. [ ] **A3:** throttling is still never split (the existing test stays green, unchanged).
