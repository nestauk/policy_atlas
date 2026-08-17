# Task contract: <task-id>

One implementation slice. Copy this `_templates/` set into `docs/tasks/<task-id>/` and fill —
`<task-id>` is `NNN-slug` (zero-padded, e.g. `001-example-slice`).
Keep it reviewable. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted / approved. Contract approved (before planning): _date · who_ ·
> Plan approved (before implementation): _date · who_ · ADR: _ref / none_.

## Goal

What changes, in user or system terms. One slice — not a roadmap.

## Deliverable

The concrete thing produced (PR + the artefact/behaviour it lands). What "shipped" looks like.

## Terms

One row for each term a cold reader cannot expand: internal labels (`P1`), abbreviations
(`PSS`), and any word this slice uses in a special sense. The rubric and the plan point
here; they do not restate it. Delete this section only if the slice introduces no such term.

| Term | Meaning |
|---|---|
| **<term>** | <one or two short sentences. Name the table, file or spec that owns it.> |

## Read first

Specs this slice depends on (route via [specs/index.md](../../specs/index.md)). Read the source
section in depth, not the heading. *Example* — EB slices commonly touch
[EB capability](../../specs/capabilities/evidence-base/capability.md),
[data-model](../../specs/system/data-model.md) and
[provenance-grounding](../../specs/system/provenance-grounding.md); for a non-EB slice, replace this
with the relevant capability/system specs.

## Scope / Out of scope

- **In:** files, components, behaviours likely touched.
- **Out:** what must not change (other capabilities are ⏸ deferred — stay out).

## Constraints & approval gates

Interfaces, schema, deps, generated files, perf, compatibility.
**Needs human approval before proceeding** (from AGENTS.md + the architecture):
schema / data model · auth / tenancy · external egress (`search`, inference route) ·
dependencies · CI · production config · public interfaces · frontend scaffold + package manager.

*Egress* here = the **running product** reaching search/model providers with project data; agent/dev-time
doc lookups, MCP and package installs are not gated.

## Public / private boundary

What is public-safe (committable durable artefacts) vs what stays private (raw evidence,
uploaded/acquired source text, traces, credentials, exploit notes). Default: private unless cleared.

## Model route

Inference route + model for any LLM-bearing step (v3.0: OpenAI under approved controls → Bedrock,
behind the routing seam). Prompt-bearing changes are high-leverage — name them. `n/a` if no inference.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no label/type/flag that doesn't change v3.0 behaviour.
- **Flag, don't drop** — below-bar / weakly-grounded material is flagged, never hidden.
- **Honest absence** — any gap/coverage claim carries its base (the searched→extracted ladder).
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md), not silent omissions.

## Stop conditions

Halt and escalate when: an approval gate above is hit, a blocker has no in-scope fix, scope would
grow past this slice, or the turn/token budget is spent. Report the blocker; don't push through.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green.
- Deterministic vs AI eval: name which apply (schema/event-log/quote-presence are tests; judge
  behaviour is an eval). If a check is red, say whether it's expected for this slice, a known repo
  failure, or a blocker — don't call the slice done with an unexplained red check.
- Manual / browser / API checks required.

## Verification evidence expected

What must exist in [verification.md](verification.md) (or the PR) to call this done:
command results, manual-check notes, diff summary, public-safety confirmation, known gaps.

## Risk tier & review focus

Pick one; it sets the review depth:

| Tier | Slice looks like | Review |
|---|---|---|
| 0 | typo, comment, small docs | focused check |
| 1 | small isolated code change | tests + AI review or human skim |
| 2 | feature slice, integration, refactor | contract verifier + tests + human review |
| 3 | auth, schema, data integrity, secrets, untrusted input, egress | + security + adversarial review + human deep review |
| 4 | migration, production config, deletion, public-API change | + human-approved plan + ADR + rollback plan |

Focus: correctness, missed requirements, security, provenance integrity, scope creep, over-abstraction.
