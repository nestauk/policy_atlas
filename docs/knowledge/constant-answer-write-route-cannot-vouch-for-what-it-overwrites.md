---
type: Security rule
title: A constant-answer public write cannot check the value it stores, so anyone can overwrite it
description: "A public route that must answer the same for every input cannot look the input up. Two results follow: the write must build its answer from its own values (an upsert with no RETURNING), and any stored value the route may replace can be replaced by a stranger with a well-formed fake."
tags: [security, public-route, waitlist, invite-links, oracle]
generated:
  by: agent:task-cycle-review
  at: 2026-11-26
---

# Rule

`POST /api/v1/waitlist` answers the same status, fields and headers for every accepted body, so it cannot be used to test an address or an invite code. To keep that:

- The route never reads the link table. It stores a code that has the right form and drops any other.
- The write is one `INSERT … ON CONFLICT DO UPDATE` with **no `RETURNING`**. The answer is built from the values the route made itself (a new id, the time), so a new row and a repeat look the same.

The cost: the route cannot tell a real code from a made-up one. A waiting request takes a newer code (so a person whose link expired can use a new one), which means anyone who knows the address can replace a valid code with a fake one. A request in a listed domain still gets its account; one in an unlisted domain then waits until an operator approves it, and the Waitlist page shows "code not recognised". The owner accepted this limit; the contract's first wording ("cannot stop or delay an account") was wrong and two review lanes found it independently.

When a constant-answer route is allowed to replace a stored value, write down who can replace it and what that costs. "Only a holder of a valid value" is never true for such a route.

# Evidence

- `backend/src/policy_atlas/api/routers/waitlist.py`: the upsert and its `where`.
- `backend/tests/api/test_waitlist.py::test_waitlist_answer_is_the_same_for_every_invite_code`, `::test_the_public_route_never_reads_invite_links`.
- `docs/adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md`, the invite-link amendment (the abuse ceiling and the known limit).
