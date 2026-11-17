# Task 064b: a firewall in front of the API, and a CAPTCHA on the waitlist form

## What / why

Today nothing stands between the internet and the API except the load balancer, and the
public waitlist form is protected by a hidden form field only. The October 2026 security
review asked for a firewall with rate limits and AWS's managed attack rules (finding H-03)
and a CAPTCHA on the waitlist (M-30). This PR is the second slice of the security
programme (`docs/tasks/064-security-hardening/programme.md`), after the quick wins of PR #120.

Task folder: `docs/tasks/064b-waf-captcha/`. Decision record:
`docs/adr/0047-waf-on-the-load-balancer-and-waitlist-captcha.md`.

### What it does, in plain words

1. **A firewall (AWS WAF) on the shared load balancer**, built by one new infra component
   and switched by three keys per environment in `infra/pa_config.json`: `waf.enabled`
   (off means nothing is built), `waf.mode` (`count` or `block`), `waf.captcha`.
2. **Six rules.** A CAPTCHA on `POST /api/v1/waitlist` (staging on, production off until
   staging has proved it); more than 50 waitlist posts in 5 minutes from one address are
   blocked; more than 3,000 requests in 5 minutes from one address to the API are counted
   now and blocked later; AWS's three managed rule groups (common attacks, known bad inputs,
   bad-reputation addresses) on the API host, skipping the two health paths. Everything that
   could refuse a real person starts in **count mode**: the rules record what they would
   block and let it through. After a week the owner reads the report and switches to block.
3. **The body-size rule is always counted**, because chat messages, plan edits and
   theory-of-change imports are often over the 8 KB the firewall inspects. A request size
   limit therefore cannot be done at the load balancer; it is left for an API-side slice.
4. **The waitlist form shows the puzzle** on the first click into a field (never on page
   load, so a visitor who never signs up loads no third-party script), keeps Submit grey
   until the puzzle is solved, and sends the token in a request header the API's CORS now
   allows. Locally and in CI the form is exactly as before.
5. **The deploy script** looks up the account's CAPTCHA script URL and key *before* it
   touches AWS, so a missing key or permission fails with nothing changed, and refuses a
   production frontend build without them while the CAPTCHA rule is on.
6. **A firewall log of matched requests only** (one month, bearer tokens and cookies
   redacted) and a read-only report script, `scripts/waf_report.sh`, that prints per-rule
   totals and the rule *inside* a group that matched, for the count-week decision.
7. **The deployment guide** gains the firewall section: the keys, the count week, the switch
   to block, excluding a rule, turning it off, the emergency `disassociate-web-acl` switch
   (and the fact that a deploy does *not* re-attach it), where the CAPTCHA values come from.

### Before merge: two hand steps per account (the owner)

- Add `wafv2:ListAPIKeys` to the deploy role.
- `aws wafv2 create-api-key --scope REGIONAL --region eu-west-2 --token-domains v3.policyatlas.uk`
  (staging; `policyatlas.uk` for production, needed only when its CAPTCHA is turned on).

Without the first, the staging deploy fails before any stack change. Without the second,
the same, with the command printed.

## Proof it works

Evidence: `docs/tasks/064b-waf-captcha/verification.md`.

- **`make verify`:** pass (backend 4,831 tests, infra 125, frontend 1,998, build).
  `make deploy-build-guard-test` pass (three parts). `make audit` pass.
- **One test per problem:** rendered-template tests for every rule in both modes and both
  domains, disabled and invalid configs, the log's filter and redaction; six vitest cases
  for the form's CAPTCHA branches; a CORS preflight test; guard and key-lookup cases
  against a stubbed `aws`; the report against two recorded log records.
- **Not yet done, by design:** the staging live check (needs the two hand steps and this
  merge), the Phase 0 measurement that pins the general rate limit (needs a staging SSO
  session; the code ships the contract's 3,000 floor), the count week. Each is listed in
  verification.md with the exact commands.

## Risk tier

Tier 4 — production config in both accounts, the first third-party script in the browser,
rules that can refuse real users. Owner-approved contract and plan, ADR 0047, rollback by
config (`waf.enabled: false`, `waf.mode: count`, `waf.captcha: false`) or the emergency
switch.

## AI role

Claude (Fable) designed the slice with the owner (contract revision 2, plan draft 2, ADR),
wrote the delegation briefs, reviewed every delegated diff, adjudicated the review stack
and wrote the docs. Codex built the infra component and the two scripts; an Opus
frontend-designer agent built the form and hook; a Sonnet worker made the CORS change. The
owner ruled on the six design items, approved contract, plan and ADR, and waived the
fresh-conversation rule for the review (recorded in verification.md).

## Review focus

- A real browser must never be refused by the waitlist rules in normal use (preflight,
  token domain, the 30-minute immunity, a slow script).
- The deploy resolves the CAPTCHA values before any AWS state change and never builds a
  production bundle without them while the rule is live.
- `waf.enabled: false` builds nothing and resolves nothing.
- The log redacts `authorization`; the body-size rule is counted in both modes; Metabase
  traffic matches no rule; the report names the rule inside a group and only reads.

## Reviews run

Findings recorded in `verification.md` § Review findings.

- [x] Contract verifier (Opus): 8 findings; the one that mattered most, a CloudFormation
  key-name defect in the logging filter that synth and the synth test both accepted.
- [x] `/code-review medium`: 7 findings, 3 adopted.
- [x] Security lane (scoped to this diff): 1 finding, adopted (bearer tokens in the log).
- [x] Adversarial review (Codex, read-only): 3 findings, all adopted.
- [x] `/simplify`: applied the cheap cleanups, declined the rest with reasons.

## Known gaps & deferred seams

`docs/deferred.md` § Firewall and CAPTCHA (task 064b seams): the count-to-block switch and
production's CAPTCHA as follow-on config changes; no alerts on firewall metrics until an
alarm topic exists; the exclusion list hard-coded; the GitHub-runner readiness risk in block
mode; a person whose browser blocks `awswaf.com` cannot sign up; no deploy-time check that
the firewall is attached; the report's 10,000-record ceiling; the general rate limit at the
floor until measured. One contract sentence (W8, "undone by the next deploy") is corrected
in the ADR and the deployment guide and left for the owner to amend in the contract.

## Public safety

- [x] No secrets, credentials, or real/acquired source text in the diff or evidence. The
  CAPTCHA script URL and API key are public by AWS design and are not committed anyway.
- [x] Logs / traces / screenshots are public-safe (the placement screenshots are stubs and
  gitignored; the staging evidence will have addresses removed).
- [x] No approval-gated change snuck in unapproved: the three keys, the web ACL and its
  log, one deploy-role permission and one API key per account (by hand), one CORS header,
  two `VITE_*` values, one pre-deploy step, two scripts, one spec sentence, as contracted.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
