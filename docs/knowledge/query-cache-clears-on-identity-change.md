---
type: Invariant
title: The React Query cache clears on every settled auth-identity change — at render time, before the swapped router mounts
description: Query keys carry only resource ids, not the caller, so the cache outlives a sign-in/sign-out router swap and can serve one identity's data to the next. App.tsx clears the whole cache on a settled status change, inline in render (a passive useEffect fires after the new router has already rendered a frame of stale data).
tags: [frontend, react-query, auth, task-037]
timestamp: 2026-09-04
---

# Rule

Query keys in this app identify **resources** (`task(id)`), not the
caller. Any router swap on auth-status change therefore re-reads whatever
the previous identity cached — a just-signed-out owner's `access: "full"`
task renders in the public shell until a tokenless refetch lands.

The fix is one clear of the whole cache on every settled identity change
(`App.tsx`), with two properties that both matter:

- **Whole-cache, not per-key**: selective invalidation re-creates the bug
  the first time a new query key ships without joining the list. Clearing
  everything is the security-conservative default; the refetch cost is one
  navigation's worth.
- **At render time, not in `useEffect`**: a passive effect runs after the
  swapped router has committed (and possibly painted) a frame of the stale
  data. The clear happens inline in render, ref-guarded on the settled
  status transition, before the router is chosen (037 review stack ruling;
  the effect version shipped first and was caught at step 7).

Origin: 037 contract adversarial review (finding 2), timing hardened by
the 037 review stack.
