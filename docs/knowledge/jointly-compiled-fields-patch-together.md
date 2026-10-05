---
type: Invariant
title: Fields the server compiles jointly must travel together in partial updates
description: PATCH /plan compiles geography differently per backend_scope and nulls whatever no longer fits the new scope — so a dirty-only client diff that prunes an "unchanged" geography from a scope-changing patch silently deletes the restriction. The pruned patch must re-send the displayed geography whenever it carries backend_scope (039 review stack, confirmed).
tags: [plan, patch, frontend, overlay, pitfall]
timestamp: 2026-09-08
---

# Rule

`PATCH /api/v1/tasks/{task_id}/plan` treats `geography` as a compile INPUT:
`_geography_constraints(geography, backend_scope)` maps the same token to
different constraint fields per scope (e.g. `"GB"` → `publisher_country`
under `grey_lit_only`, `author_affiliation_countries` under `academic_only`),
and `_drop_scope_incompatible_geo` nulls whatever doesn't fit the new scope.
Therefore any client that diffs before patching (the 039 dirty-only overlay)
must re-send the displayed geography whenever the patch carries
`backend_scope`, even when geography itself is "unchanged" — otherwise a
scope switch silently deletes the restriction while the UI keeps displaying
it.

Generalised: when the server derives state from fields A and B jointly, a
partial update carrying only A is not a smaller version of {A, B} — it is a
different instruction. A dirty-only diff must group jointly-compiled fields.

# Why

Found by the 039 review stack (`/code-review`, confirmed): plan
`academic_only` + `author_affiliation_countries: ["GB"]`; the user switches
Sources to grey literature and starts; the pruned patch is
`{backend_scope}`; the backend nulls the GB constraint; no error, no UI
change. Pre-039, the UI always re-sent geography, which is what masked the
coupling.

# Watch out

- The APO token makes the coupling loud instead of silent: re-sending
  `"APO"` with a non-grey scope 422s (by design) rather than dropping it.
- The re-send lives in `overlayToPlanPatch` (plan-aware branch) — a second
  client (or a scripted PATCH) has to honour the same rule itself.

# Citations

- `backend/src/policy_atlas/api/routers/planning.py` (`_geography_constraints`, `_drop_scope_incompatible_geo`)
- `frontend/src/views/workspace/planOverlay.ts` (`overlayToPlanPatch`) and
  `planOverlay.test.ts` ("re-sends the displayed geography whenever the patch changes backend_scope")
- [docs/tasks/039-apo-mod/verification.md](../tasks/039-apo-mod/verification.md) § Review findings
