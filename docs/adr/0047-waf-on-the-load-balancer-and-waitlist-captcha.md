# ADR 0047 — A web application firewall on the shared load balancer, counted before it blocks, and a CAPTCHA on the waitlist form

- **Status:** Accepted — 2026-11-17 (Karlis Kanders, owner, task 064b plan gate). Built
  2026-11-17 as decided; the general rate limit was pinned at 6,000 the same day from the
  Phase 0 measurement (recorded in the task's `verification.md`).
- **Date:** 2026-11-17
- **Task:** [064b-waf-captcha](../tasks/064b-waf-captcha/contract.md), second slice of the
  [064 security hardening programme](../tasks/064-security-hardening/programme.md).
- **Builds on:** the 2026-10-19 project review (findings H-03 and M-30; the review file sits
  in the programme folder) · the 036 review decision of 2026-09-03 ("WAF rate rule is the
  upgrade path; no CAPTCHA"), which this record supersedes · the programme rules (every
  environment-specific value is a config key; staging leads by one release for anything
  that can lock people out).

## Context

Nothing inspects a request before the load balancer passes it to the API. One machine can
send as many requests as it likes, and the public waitlist form, which needs no sign-in, is
protected by a hidden form field only. The review asked for a firewall with rate limits and
AWS's managed rule sets (H-03) and for a CAPTCHA on the waitlist (M-30).

Four facts shape the design. AWS WAF has no high-level CDK construct, so the rules are
written as raw CloudFormation properties. A web ACL on a load balancer inspects only the
first 8 KB of a request body, and this API's chat, plan and theory-of-change requests are
often larger. WAF keeps request samples for three hours only, so learning what a rule would
block over a week needs a log. The load balancer is shared with Metabase.

The AWS documentation pages these decisions rest on (gathered 2026-11-17):

- Token domains: https://docs.aws.amazon.com/waf/latest/developerguide/waf-tokens-domains.html
- The CAPTCHA reply (405, `x-amzn-waf-action`, CORS headers):
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-captcha-and-challenge-actions.html
- The CAPTCHA script and API key:
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-js-captcha-api.html and
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-js-captcha-api-key.html
- Rate-based rules:
  https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-high-level-settings.html
- The managed groups and the 8 KB body rule:
  https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-baseline.html
- Logging and the logging filter:
  https://docs.aws.amazon.com/waf/latest/developerguide/logging-cw-logs.html and
  https://docs.aws.amazon.com/waf/latest/developerguide/logging-management.html

## Decisions

1. **The web ACL is created by the app stack, not the network stack.** The programme map
   sketched it in the network stack beside the load balancer. The app stack already imports
   the load balancer's ARN through SSM, the association takes an ARN, and the three keys
   that govern the firewall live in `infra/pa_config.json` with the other app-behaviour
   keys. One component file, `infra/infra/components/waf.py`, holds everything WAF-shaped.
2. **Three per-environment keys, no more.** `waf.enabled` (the off switch and the
   rollback), `waf.mode` (`count` or `block`, for the general rate rule and the managed
   groups), `waf.captcha` (the CAPTCHA rule and, through the deploy script, the frontend's
   puzzle). `captcha` without `enabled` is refused. The rule limits (50 and 3,000 per
   5 minutes), the immunity time (1,800 s), the host scoping and the body-size exclusion
   have one right value everywhere and are hard-coded. Production ships with the CAPTCHA
   off and turns it on by a later config change, so staging leads by one release.
3. **Every rule is scoped to the API, and the managed groups skip the health paths.** The
   general rate rule and the managed groups match the API host only; the managed groups
   also skip `/healthz` and `/readyz`, so the load balancer's health check and the deploy
   script's readiness call can never be refused by them (owner: do not block by default).
   The waitlist rules match the waitlist path only, decoded and lower-cased before
   comparison so an encoded path cannot skip them. Metabase shares the load balancer and
   matches nothing; it keeps its own IP allowlist.
4. **Count first, block later, per environment.** Every rule that could refuse a real
   person starts in count mode. After a week and a deliberate pass, the owner reads the
   report and switches `waf.mode` to block by a config change, then repeats the pass at
   once. The waitlist rate rule blocks from the start at 50 per 5 minutes per address: the
   CAPTCHA already stops scripts, so the number only bounds a script with a stolen token,
   and fifty leaves room for an office or an event behind one address. The general rate
   limit is not guessed: the build measures the busiest address's 5-minute peak in the
   staging API log and sets the limit at ten times that, never below 3,000. Measured
   2026-11-17: staging did not yet log the client address (that arrives with 064a), so
   the build took the site-wide peak, 520 requests in one 5-minute window over 14 days,
   as the bound no single address can exceed, and pinned 6,000.
5. **The common group's body-size rule is always counted.** `SizeRestrictions_BODY` matches
   bodies over 8 KB, which this API sees in normal use. It is overridden to count in both
   modes. This also settles review finding H-02 (a request size limit at the edge): it
   cannot be done at a load balancer web ACL, which sees 8 KB and no more, so an API-side
   body limit is a later slice.
6. **A CAPTCHA puzzle, shown up front, loaded on first interaction, with the token in a
   header.** The rule matches `POST` on the waitlist path only, so the browser's preflight
   passes. The form loads the CAPTCHA script when a person first focuses a field, so a
   visitor who never signs up loads no third-party script; it renders the puzzle before
   submit and sends the token in `x-aws-waf-token`, because the token cookie does not
   cross from the page's host to the API's. The web ACL's token domain list holds the
   environment's domain, which covers the page and the API as subdomains. The puzzle is
   rendered before the first submission rather than after a refusal, so no person pays a
   failed round trip. The form recognises a WAF refusal by the `x-amzn-waf-action` header,
   never by the status code alone, and a slow script delays a person but never locks them
   out. The immunity time is 30 minutes so a long answer does not earn a second puzzle.
7. **The CAPTCHA script URL and API key are account values resolved before the deploy
   touches AWS state.** They belong to the AWS account and region, not to the web ACL, and
   ship in the browser bundle by AWS's design, so they are not secrets. The API key is
   created by hand once per account as a first-deploy precondition; the deploy script only
   lists keys (`wafv2:ListAPIKeys`), picks the one bound to the environment's domain, and
   does so before `cdk deploy`, so a missing key or permission fails with nothing changed.
   It refuses a production build that lacks the values while the CAPTCHA rule is on.
8. **A filtered WAF log replaces reading samples.** WAF logs only the requests a rule
   counted, blocked, challenged or counted-by-override into a CloudWatch log group kept for
   one month. A read-only report script sums the metrics and queries the log by the rule
   inside a group, so the count-week decision is made from evidence, by a person, in
   minutes.
9. **An emergency off switch.** `aws wafv2 disassociate-web-acl` detaches the firewall in
   seconds without a release. For a false positive in production that cannot wait for
   the release cycle. **As built (review correction):** a deploy does *not* re-attach it,
   because CloudFormation updates only changed template resources and does not detect a
   detached association; `aws wafv2 associate-web-acl` puts it back by hand
   (`infra/DEPLOYMENT.md` § 4 "The firewall"). The contract's W8 row says "undone by the
   next deploy"; this record corrects it.

## As built (064b review stack, 2026-11-17)

- **The log redacts three headers.** A counted request is logged with every request
  header, so without redaction a signed-in person's bearer token would sit in the log
  group for a month. `authorization`, `cookie` and `x-aws-waf-token` are redacted.
- **The host scope-down matches by prefix.** The load balancer routes on the host name and
  ignores a `:443` suffix or a trailing dot; an exact match would let such a request skip
  the general rate rule and the managed groups. The waitlist rules stay path-only on
  purpose: a host condition there would be a CAPTCHA bypass by the same trick.
- **The health-path exclusion is exact** (`/healthz`, `/readyz`), as the decision says.
- **The logging filter is written as a plain CloudFormation dict.** CDK 2.261 types the
  property `Any`, and a typed value serialises with camelCase keys CloudFormation rejects.
- **The web ACL's metric name is its name**, so the report's `WebACL` dimension is one
  constant.
- **The report groups in Python over raw log records**, reading every place a rule name
  appears (inside groups and at the ACL level), because a Logs Insights `stats` over array
  fields sees only the first element.

## Consequences

- About $11 a month per environment, plus request and puzzle fees in cents.
- The frontend loads its first third-party script, from an AWS URL, on the first interaction
  with the form. The Content Security Policy slice (064c) follows this one so it can list
  that source. A person whose browser blocks `awswaf.com` cannot sign up.
- Two hand steps per account before the first deploy: the deploy-role permission and the
  API key.
- During a deploy that turns the CAPTCHA on, the old frontend bundle is live for a few
  minutes with the rule already in place; a waitlist submission in that window is refused.
  The same deploy takes the API down for its migration, so this adds nothing new.
- Local development, CI and the mock journey see no puzzle, because the script URL is set
  only by the deploy script when the CAPTCHA is on.
- Turning the firewall off is one key and one deploy, or one command in an emergency;
  nothing has to be restored.

## Alternatives considered

- **The silent challenge instead of a puzzle.** Cheaper and invisible, but a script driving
  a real browser passes it. The owner ruled CAPTCHA and confirmed it at the plan gate
  (contract owner item 1, settled).
- **A WAF on CloudFront as well.** The frontend is static files; CloudFront's own protections
  cover it, and a second web ACL doubles the cost for no API coverage.
- **An in-app rate limiter.** Would run inside the API process, after the request has been
  read, and would need shared state across containers (M-28). The edge is the right place.
- **Rendering the puzzle only after a 405.** AWS's documented pattern. With a CAPTCHA rule the
  first submission always fails, so every person would see one failed submit.
- **Letting the deploy script create the API key.** One more permission and one more code
  path for a step that runs once per account.
- **Per-rule count overrides inside the managed groups instead of one group override.**
  AWS prefers it for testing, because a group override still stops at the first blocking
  rule inside the group. It needs every rule name listed; the repeated deliberate pass
  after the block switch covers the gap at no cost.
