# Task contract: 038-apo-mod

One implementation slice. Boundaries: [AGENTS.md](../../../AGENTS.md).

> **Status:** drafted. Contract approved (before planning): _pending · owner_ ·
> Plan approved (before implementation): _pending · owner_ · ADR: none (test
> mod; write one only if the owner promotes it to a product feature).

## Goal

This is a **test mod** for an Australian use case. A user must be able to
restrict one run so that all sources come from Australian Policy Online (APO)
only. It is not a general product feature. Keep the change small and easy to
remove.

Two requirements:

- **R1** — the run makes no OpenAlex calls.
- **R2** — every Overton search call carries the extra query parameter
  `source=apo` (example: `https://app.overton.io/documents.php?source=apo`).

R1 needs **no new code**: the existing plan field `backend_scope =
"grey_lit_only"` already removes OpenAlex from the run, and the user can
already set it from the plan document ("Sources" dropdown). Only R2 is new.

## Deliverable

A PR on `task038/apo-mod`. After it lands, a tester can do this in the app:

1. Approve a plan as normal.
2. In the plan document, set **Sources** to grey literature only.
3. Type **APO** (or "Australian Policy Online") in the **Source geography**
   box and save.

The run then satisfies R1 and R2, and the plan document shows the APO
restriction (**R3** — the restriction must be visible, not silent).

## Terms

| Term | Meaning |
|---|---|
| **APO** | Australian Policy Online — a named collection inside Overton. Overton filters to it with the query parameter `source=apo`. |
| **Overton / OpenAlex** | The two live search backends (`backend/src/policy_atlas/evidence_base/sourcing/search_live.py`). |
| **backend_scope** | Existing plan field. `grey_lit_only` = Overton only. Defined in `runtime/orchestration_plan.py`. |
| **Source geography** | The free-text box on the plan document edit form. The backend compiles it into scope constraints (`api/routers/planning.py`, `_geography_constraints`). |
| **scope constraints** | The plan's filter block (`ScopeConstraints`). It splits into per-backend filter dictionaries, which pass through fail-closed allowlists before they become query parameters. |

## Read first

- `docs/specs/system/web-api.md` § Plan (the PATCH `/plan` surface).
- The as-built filter chain: `orchestration_plan.py` (`ScopeConstraints`,
  `to_filters`) → `sourcing/search_loop.py` (allowlists, `overton_wire_params`)
  → `sourcing/search_live.py` (`_OVERTON_ALLOWED_WIRE_KEYS`, `_search`).

## Design (the minimal route)

Reuse the two edit surfaces the user already has. Do not touch the planner
prompt or the orchestrator.

- A new optional constraint `publisher_source` on `ScopeConstraints`
  (value: `"apo"`). It flows down the existing fail-closed chain and becomes
  `source=apo` on the Overton call.
- The Source geography box accepts the token "APO" / "Australian Policy
  Online" (case-insensitive) and compiles it to that constraint. This works
  only when Sources is grey literature only; any other Sources value is a 422
  with a message that says to pick grey literature first.
- The plan document shows "APO" back in the geography position (R3).

Known limit, accepted: asking for APO in the planning **chat** does nothing —
the planner prompt (`planner_v10`) is not taught the field. The tester edits
the approved plan instead. If this mod graduates to a product feature, the
upgrade path is a proper plan field plus a planner prompt bump — a new slice.

**Removal note:** all additions are optional fields and one token branch.
Removal deletes them; stored plans that carry `publisher_source` must then be
tolerated or re-saved — note this in `docs/deferred.md` at close-out.

## Scope / Out of scope

- **In (backend):** `runtime/orchestration_plan.py` (field + `to_filters` +
  the scope-compatibility validator), `runtime/planner_prompt.py`
  (`PlanDraftWire` gains the optional field only — **no prompt text change**),
  `sourcing/search_loop.py` (filter-key allowlist, block validation, wire
  mapping), `sourcing/search_live.py` (wire-param allowlist),
  `api/routers/planning.py` (`_geography_constraints` token branch,
  `_drop_scope_incompatible_geo`).
- **In (frontend):** the scope-chip/geography display mapping
  (`views/workspace/planOverlay.ts` / `planVocabulary.ts`) so "APO" round-trips
  into the geography box; regenerated `openapi.json` + `api/gen/types.ts` via
  `make openapi-sync` (never by hand).
- **Out:** planner prompt text (stays `planner_v10`) · orchestrator/runner ·
  backend selection code (`scoped_search_backends` already covers R1) · any
  new UI control · schema/database · OpenAlex client.

## Constraints & approval gates

- **Runtime egress:** the Overton call gains one constant query parameter.
  No new destination, no new data leaves the system. Still a gated surface —
  this contract is the approval request.
- **Public interface:** `ScopeConstraints` in the API gains one optional
  field (additive; shows up in `PlanOut`). No breaking change.
- No new dependencies, no CI change, no schema change, no prompt change.

## Public / private boundary

Nothing new. The parameter value `apo` is a constant, not project data.

## Model route

n/a — no LLM-bearing step changes. `planner_v10` is untouched.

## Stop conditions

Standard (AGENTS.md). Also: if Overton rejects `source=apo` on a live call,
stop and report — do not guess at alternative parameter spellings.

## Acceptance checks

- `make verify` green (includes `drift-check` for the regenerated types).
- Unit tests: geography token "APO" → `publisher_source="apo"` →
  Overton wire params contain `source=apo` (R2); token rejected with 422
  unless Sources is grey literature only; unknown tokens still fail as before.
- **Live manual check (pinned scope):** one plan edited through the UI as in
  § Deliverable, one acquire round. Evidence: the logged/traced Overton
  request URL contains `source=apo`; zero OpenAlex requests; returned
  documents are APO records. No full end-to-end run — the changed surface is
  plan-edit + acquire, a few minutes of wall time.

## Verification evidence expected

`verification.md`: command results, the live-check request URL and sample
result, diff summary, note that `planner_v10` and the orchestrator are
untouched.

## Risk tier & review focus

**Tier 3** — it touches runtime egress (one constant parameter on an existing
call) and adds one optional public-API field. The touch is narrow and
additive; ❓ **owner call:** whether the Tier-3 adversarial-review lanes run in
full or are waived for this test mod (record the ruling here).

Review focus: the fail-closed chain stays fail-closed (no allowlist widened
beyond the one key); the 422 path; no planner/orchestrator drift.
