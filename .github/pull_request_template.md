<!-- One task contract = one PR. Keep it reviewable. Don't make the reviewer reconstruct intent from the diff. -->

## What / why

<!-- What changed, in user or system terms, and why. Link the task: docs/tasks/<task-id>/contract.md -->

Task: `docs/tasks/<task-id>/`

## Proof it works

Evidence lives in `docs/tasks/<task-id>/verification.md` — summarise here, don't duplicate the table.

- **`make verify`:** pass / fail / stub
- **Manual / end-to-end:** what was exercised + the exact command (or link to verification.md)

## Risk tier

<!-- Sets review depth (see the contract's risk table). -->

Tier _N_ — _why_.

| Tier | Review |
|---|---|
| 0–1 | tests + AI review or human skim |
| 2 | contract verifier + tests + human review |
| 3 | + security + adversarial review + human deep review |
| 4 | + human-approved plan + ADR + rollback plan |

## AI role

<!-- What the agent did vs what the human directed/approved. -->

## Review focus

Correctness · missed requirements · security · provenance integrity · scope creep · over-abstraction.
<!-- Narrow to what this slice actually risks. -->

## Reviews run

Findings recorded in `verification.md`.

- [ ] Contract verifier
- [ ] `/code-review`
- [ ] `/security-review`
- [ ] Adversarial review (Tier 2+)
- [ ] `/simplify`

## Known gaps & deferred seams

<!-- What's intentionally unfinished. New seams → docs/deferred.md. -->

## Public safety

- [ ] No secrets, credentials, or real/acquired source text in the diff or evidence.
- [ ] Logs / traces / screenshots are public-safe.
- [ ] No approval-gated change (schema · auth · **runtime egress** · deps · CI · prod config · public interface · scaffold) snuck in unapproved. (*Runtime egress* = the running product reaching search/model providers with project data; agent/dev-time lookups, MCP and installs are fine.)
