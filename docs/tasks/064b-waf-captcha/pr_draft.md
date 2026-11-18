# Task 064b: a firewall in front of the API, and a CAPTCHA on the waitlist form

> **Base branch.** This PR is built on top of PR #120 (064a), so its base is that branch for
> now and the diff shows only 064b. When #120 is merged, the base changes to `dev`.

## What / why

The October 2026 security review found that nothing stands between the internet and the API
except the load balancer, and that the public waitlist form is protected by one hidden form
field only. It asked for a firewall with rate limits and AWS's ready-made attack rules (finding
H-03), and a CAPTCHA on the waitlist (M-30). This PR adds both. It is the second part of the
security programme (`docs/tasks/064-security-hardening/programme.md`), after the quick wins in
PR #120.

Task folder: `docs/tasks/064b-waf-captcha/`. Decision record:
`docs/adr/0047-waf-on-the-load-balancer-and-waitlist-captcha.md`.

### What changes

**The firewall**

1. A firewall (AWS WAF, "Web Application Firewall") sits on the load balancer and looks at
   every request before the API sees it. One new infrastructure file builds it
   (`infra/infra/components/waf.py`).
2. Every rule applies only to the API's web address or to the waitlist path. Metabase shares
   the load balancer, and its traffic matches no rule.
3. Three settings per environment in `infra/pa_config.json` control it: `enabled` (off builds
   nothing), `mode` (`count` or `block`), and `captcha`. A wrong value stops the build and
   the deploy before anything in AWS changes.

**The six rules**

4. **The waitlist CAPTCHA.** A sign-up without a solved puzzle is refused. Staging has it on.
   Production has it off until staging has proved it.
5. **The waitlist limit.** More than 50 sign-ups in 5 minutes from one address are blocked.
6. **The general limit.** More than 6,000 requests in 5 minutes from one address to the API.
   This number is measured, not guessed: the busiest 5-minute window in two weeks of the
   staging log held 520 requests from everybody together, and production's held 264. The
   limit is ten times the higher one, rounded up.
7. **AWS's three ready-made rule groups:** common web attacks, known bad inputs, and addresses
   with a bad reputation. They skip the two health-check paths, so the load balancer's own
   checks are never refused.

**Count first, block later**

8. Every rule that could refuse a real person starts in **count mode**: it records what it
   would have blocked and lets the request through. After a week the owner reads the report
   and switches to block, one environment at a time, staging first.
9. One rule in the common group, the body-size rule, is always counted and never blocks. Chat
   messages, plan edits and theory-of-change imports are often over the 8 KB the firewall
   can inspect. So a request size limit cannot be done in the firewall. It is left for a
   later change in the API.

**The waitlist form**

10. The puzzle appears when a visitor first clicks into a field, never on page load. So a
    visitor who never signs up never loads a script from AWS.
11. Submit stays grey until the puzzle is solved. The form sends the puzzle's token in a
    request header, and the API now allows that header from the browser.
12. On a laptop and in CI the form is exactly as before, because the puzzle settings are
    only given to the staging and production builds.

**The deploy**

13. Before it changes anything in AWS, the deploy script looks up the account's puzzle
    settings. If they are missing it stops with the one command that fixes it. It refuses to
    build the production website without them while the CAPTCHA is on.

**Seeing what the firewall does**

14. A firewall log that keeps only the requests a rule matched, for one month. Login tokens,
    cookies and puzzle tokens are blanked out before the log is written.
15. A read-only report script, `scripts/waf_report.sh`, prints per rule how many requests it
    counted, blocked or challenged, and which rule inside a group matched. This is what the
    owner reads at the end of the count week.

**The deployment guide** (`infra/DEPLOYMENT.md`, "The firewall") explains the three settings,
the count week, the switch to block, excluding one rule, turning it all off, and an emergency
switch that detaches the firewall in seconds. A deploy does **not** put the firewall back
after the emergency switch. The guide gives the command that does.

## Size of the diff

9 commits; 35 files, +2,971 / −30 lines against the 064a branch. More than half of the new
lines are docs: the task records and the deployment guide. The tests are about the same size
as the code.

| what | files | added | removed |
|---|---:|---:|---:|
| infrastructure and deploy (`infra/` code and config, `scripts/`, `Makefile`) | 6 | 611 | 5 |
| frontend code (`frontend/src`) | 3 | 136 | 4 |
| backend code (one CORS line) | 1 | 3 | 1 |
| tests (infra, scripts, frontend, backend) | 6 | 590 | 2 |
| docs (task records, decision record, knowledge, guides) | 19 | 1,631 | 18 |

## Proof it works

Evidence: `docs/tasks/064b-waf-captcha/verification.md`.

- The full test suite (`make verify`) passes, and so do the deploy-script tests
  (`make deploy-build-guard-test`) and the dependency check (`make audit`).
- Each rule has a test that reads the generated AWS template, in both modes and for both
  environments. The form has six tests for the puzzle cases, the API has a test for the new
  header, and the deploy script and the report script are tested against recorded AWS
  replies.
- **A dry run against the real staging account**, without changing anything:
  - AWS's own firewall check (`aws wafv2 check-capacity`) accepts all six rules. It also
    caught one wrong field name that every test and every reviewer had missed, which would
    have failed the first deploy. It is fixed, and a test now catches that whole kind of
    mistake.
  - `cdk diff` against staging shows exactly four new things (the firewall, its attachment,
    its log, the log's settings) and no change to permissions or the network. Everything
    else in the diff is 064a's.
- The checks on the live staging site cannot run until this is deployed. The list, with the
  exact commands, is in `verification.md` § Staging live check.

## Risk tier

Tier 4 (the highest). It changes production configuration in both accounts, adds the first
script from a third party to the website, and adds rules that can refuse real users. Every
such rule starts in count mode, and each setting can be undone by changing one line of
configuration.

## AI role

The agent (Claude) wrote the contract, rubric, plan and decision record, each approved by the
owner. Codex built the firewall file and the two scripts. A Claude design agent built the form
changes, and a smaller Claude agent made the one-line API change. The lead agent reviewed each
piece before it was committed, ran the review stack, fixed what it found, and wrote the docs.
The owner decided: keep the puzzle, measure the general limit instead of guessing it,
production runs its own count week, the ready-made rule groups skip the health checks, and the
owner does the AWS steps by hand. The owner also allowed the review to run in the same
conversation as the build (recorded in `verification.md`).

## Review focus

- **A real person must never be refused by the waitlist rules in normal use.** Check the
  browser's preflight request, the puzzle's domain, the 30 minutes a solved puzzle stays
  valid, and what happens when the puzzle script is slow.
- **The deploy looks up the puzzle settings before it changes anything in AWS**, and never
  builds a production website without them while the CAPTCHA is on.
- **`enabled: false` builds nothing and looks up nothing.**
- **The log blanks out login tokens.** The body-size rule is counted in both modes. Metabase
  traffic matches no rule. The report only reads.

## Reviews run

Findings and decisions in `verification.md` § Review findings.

- [x] Contract verifier (a fresh Claude Opus agent, read-only)
- [x] `/code-review` (medium)
- [x] Security review (scoped to this PR's changes only)
- [x] Adversarial review by Codex (a different model family, read-only)
- [x] `/simplify`
- [x] Dry run against the staging account (`check-capacity` and `cdk diff`)

What the reviews found and this PR fixes:

- The log's filter settings were written with the wrong letter case. The tests passed, but
  AWS would have refused the first deploy. The dry run later found the same mistake in a
  second place, in four rules. Both are fixed, and a test now checks every field name.
- The firewall log stored every request header, so the login token of a signed-in person
  would have been kept in the log for a month. Those headers are now blanked out.
- The report asked AWS for the firewall's numbers under the wrong name, so every total would
  have read 0. It also counted only the first matching rule in each record. Both are fixed.
- A request to the API's address with `:443` added could skip the general limit and the
  ready-made rules. The address match now covers that.
- If the puzzle script failed in one particular way, Submit stayed grey for ever. The form
  now shows the "did not load" message instead.
- The deploy only found the puzzle key if it named exactly one domain. It now finds it among
  several.
- On a deploy with the CAPTCHA off, old puzzle settings in the shell could reach the website
  build. The deploy now clears them.
- The draft said a deploy puts the firewall back after the emergency switch. It does not. The
  guide and decision record are corrected. The contract still has the old sentence, for the
  owner to change.

## Known gaps & deferred seams

`docs/deferred.md` § Firewall and CAPTCHA lists what was left for later: switching to block
and turning on production's CAPTCHA (both config changes after the count week), alerts on the
firewall's numbers, the exclusion list being in code, a person whose browser blocks AWS's
puzzle script cannot sign up, no deploy-time check that the firewall is attached, and the
report reading at most 10,000 log records. The general limit was measured from all traffic
together, because staging only logs each visitor's own address once 064a is deployed. A
measurement per address afterwards can only lower the number.

Before deploy, the owner's two AWS steps: the puzzle key for staging is **created**, and the
deploy role in both accounts can **already** read it, because both roles have full
administrator rights. That is wider than the deployment guide asks for. Narrowing it is a
separate task.

## Public safety

- [x] No secrets, credentials, or real source text in the diff or evidence. The puzzle key is
  public by design (it ships in the website's code) and is not committed anyway.
- [x] Logs and screenshots are public-safe. The measurement records only per-window totals, no
  addresses. The exported log files were deleted after reading.
- [x] No change that needs approval was added without it: the three settings, the firewall and
  its log, one AWS permission, one puzzle key per account (by hand), one API header, two
  website build values, one deploy step, two scripts and one spec sentence are all in the
  approved contract.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
