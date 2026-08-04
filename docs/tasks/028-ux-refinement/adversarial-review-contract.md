# 028 contract-stage adversarial review — findings & adjudication

> Lane: codex-rescue (read-only), job `task-msdvvss3-jm7jch`, 2026-08-04.
> 23 findings: 17 MAJOR, 6 minor. **All 23 adjudicated IN** (lead-verified
> the load-bearing code claims: runner promotion drop at runner.py:1439–1460,
> CheckInOut bundle absence, GET /plan approved-first). No owner ruling
> overturned — the fixes implement the rulings; gate not reopened. The plan
> 🛑 sees the folded result.

| # | Sev | Finding (compressed) | Adjudication → fix |
|---|---|---|---|
| 1 | MAJ | Rubric certifies "five-tab IA" (pre-hybrid stale) | rubric item 1 → six-tab hybrid |
| 2 | MAJ | Rubric/disciplines keep a forbidden `focus` summary path | both → verified block summary, first-sentence fallback; focus never |
| 3 | MAJ | Out-of-scope clause still says "render/copy only" steering + "two prompt revs" | Scope/Out rewritten: strand-14 behaviour inventory in-scope; six prompt surfaces |
| 4 | MAJ | dc.html still the unqualified UX spec vs 3-part binding record | Goal: binding records supersede dc.html on conflict |
| 5 | MAJ | Part wire too thin for the binding cards | part wire extended: option {id, label, sub, primary, reason?}; typed chips {label, kind: text\|date_range\|country_list, value} for inline editors; confirm turns reference part-id + option-id; confirmed state rehydrates from turn sequence |
| 6 | MAJ | Reopened part leaves stale approved plan startable | pin: Start = approve-current-draft + dispatch atomically; a reopened part demotes ready (start disabled, honest copy); run-start never consumes a draft older than the newest completed turn |
| 7 | MAJ | section_budget unspecified end-to-end; ~4 ambiguity | pin: additive `section_budget` on OrchestrationPlan + PlanDraft/PlanOut mirrors; `_directive_delta` gains a synthesis branch; budget counts ORDINARY sections (key findings/conclusions structural, excluded); SECTION_CAP becomes the ceiling |
| 8 | MAJ | P4 as_proposed re-proposes sections at run time | pin: the P4 primary submits the DISPLAYED list as the sections directive — what you saw is what gets written |
| 9 | MAJ | Inline section editing unconstrained | pin: structural roles (key findings, conclusions) not editable/removable |
| 10 | MAJ | Theme rename transport undefined (one response per check-in) | pin: renames are card-local edits batched into the single response as validated params on the proceed/other option; one response, atomic |
| 11 | MAJ | CheckInOut has no bundle — cards can't show theme map/shortlist/sections/groups | additive `CheckInOut.bundle` (typed per-point projection, scrubbed) → api-additions.md |
| 12 | MAJ | Authored options not HTTP-selectable as-built (no id; projection drops them) | strand-14 text corrected; additive: authored options exposed in options with ids + `suggested` marker + why; validation at authoring + apply as pinned |
| 13 | MAJ | Summaries read-model fields absent from the gate list | contract gate now references api-additions.md as THE enumerated list (fields were already there) |
| 14 | MAJ | landscape `scope=cited` param absent from gate list | same as 13 (already in annex) |
| 15 | MAJ | Watch promotion erases steer_point identity → promoted Groups shows generic floor | named behaviour change: promotion at a lattice boundary keeps the point's identity/bundle/options |
| 16 | MAJ | Live check's pause assertions unreachable under unattended default | acceptance: one leg explicitly requests check-ins ("review key stages"); plus a short unattended leg proving no-pause default |
| 17 | min | Wall-time estimate not reproducible | acceptance names presets per leg (Quick look + one standard); estimate ≈25–30 min |
| 18 | MAJ | Verification says "both prompt revs" (six exist) | all six prompt-surface diffs in verification.md |
| 19 | min | Fork-C record details uncontracted (compact funnel line; References collapse) | strand 10 lines added |
| 20 | min | Origin column silently dropped | strand 7: Origin retained, non-sortable |
| 21 | min | Project-settings-in-header demoted to optional candidate | strand 11: committed item, not candidate |
| 22 | min | `theme` param identity (name vs id) + rename/bookmark interaction | additive `ThemeOut.theme_id`; filter by id; renames keep id (bookmarks survive) |
| 23 | min | Failed summary status can hide behind fallback | pin: fallback renders WITH the failed marker surfaced (spec: "surfaced as such"); acceptance asserts |
