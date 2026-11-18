# Verification: 064c-csp

Evidence for task 064c (Content Security Policy and security headers on CloudFront).
Contract: [contract.md](contract.md) (revision 2). Plan: [plan.md](plan.md) (draft 2).
ADR: [0048](../../adr/0048-content-security-policy-and-security-headers-on-cloudfront.md).

## Commands run

| Gate | Command | Result | Notes |
|---|---|---:|---|
| Phase 0 (build-open) | `make verify` | pass | Backend 4,831 passed, 1 skipped; frontend 1,998 passed; lint, typecheck, build, drift-check green. |
| Phase 0 (build-open) | `make -C infra test` | pass | 125 passed. |

## Plan-time AWS reads (read again 2026-11-18 at build-open, read-only)

**The managed `SECURITY_HEADERS` policy** (staging account):

```
$ AWS_PROFILE=pa_staging aws cloudfront get-response-headers-policy \
    --id 67f7725c-6f97-4210-82d7-5512b31e9d03 \
    --query 'ResponseHeadersPolicy.ResponseHeadersPolicyConfig.SecurityHeadersConfig'
{
    "XSSProtection": {"Override": false, "Protection": true, "ModeBlock": true},
    "FrameOptions": {"Override": false, "FrameOption": "SAMEORIGIN"},
    "ReferrerPolicy": {"Override": false, "ReferrerPolicy": "strict-origin-when-cross-origin"},
    "ContentSecurityPolicy": {},
    "ContentTypeOptions": {"Override": true},
    "StrictTransportSecurity": {"Override": false, "AccessControlMaxAgeSec": 31536000}
}
```

This matches plan P2: the five kept headers, their values and their override flags. HSTS has
no `IncludeSubdomains` and no `Preload`. There is no CSP.

**Custom response headers policies** (both accounts; limit 20):

```
$ AWS_PROFILE=pa_staging aws cloudfront list-response-headers-policies --type custom \
    --query 'ResponseHeadersPolicyList.Quantity'
0
$ AWS_PROFILE=pa-prod aws cloudfront list-response-headers-policies --type custom \
    --query 'ResponseHeadersPolicyList.Quantity'
0
```

So the name `policy-atlas-v3-security-headers` is free in both accounts.
