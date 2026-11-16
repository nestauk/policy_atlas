# Design annex: <task-id>

The lead's script for a frontend-heavy slice: every state, transition and line of copy the
build must produce. The contract cites this file by version; looks live here, not in the
contract. Owner feedback rounds (mock and polish) edit this file first, then the mock or the
app. Keep the voice: a short label, then one plain sentence; no mannered prose.

> **Version:** 1 · Mock: _private artifact link_ · Frozen: _date_ · Polish rounds: _log below_

## Rules for this slice

Standing rules the surfaces must honour (examples: no countdown or percent bar; nothing
animates unless real data is arriving; no text changes without a visible transition;
reduced motion honoured; counts only where the total is known before the loop).

## Fixed example data

The one example run, task or record every scene and every test uses (names, counts, titles).

## Surfaces and states

One subsection per surface. For each: what it shows at rest, each state and what moves it
to the next, the exact copy, and what it must never do.

### <surface>

- **At rest:** …
- **State A → B:** trigger · what changes · copy.
- **Never:** …

## Scenes (mock)

Numbered scenes the mock plays, each with its copy and a one-line caption. The mock journey
test asserts these states.

## Owner rulings

Dated list. Each ruling names what it replaces.

## Polish log

| Round | Phase | Date | Notes applied | Sign-off |
|---|---|---|---|---|
| 1 | build, agent pass | | | lead |
| 2 | build, owner pass | | | owner |
| 3 | review, agent pass | | | lead |
| 4 | review, owner pass | | | owner |

## Deferred polish

Notes the owner gave that this slice does not take, with where they go (`docs/deferred.md`).
