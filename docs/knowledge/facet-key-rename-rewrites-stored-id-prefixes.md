---
type: Invariant
title: A grouping facet key lives inside stored group ids and is cited across tables, so a facet rename is a prefix rewrite in five places with its own downgrade
description: Group ids are `<facet>:gNN` and are cited by annotations (theme referenced_ids, pattern group_id) and synthesis blocks (group_ids) as well as by the grouping result's own keys, counts, flags and provenance and the plan's grouping_facets. Revision f1b6d3a8c2e5 (population → unit) rewrites every place set-based in SQL with exact matches, including provenance rows written before `facet_runs` existed, and its downgrade is the exact inverse; the migration test pins rows without the facet byte-identical.
tags: [migrations, grouping, data-migration, jsonb, synthesis, annotations, task-046]
timestamp: 2026-10-12
---

# Rule

Renaming a grouping facet key (046 amendment 3, R71–R73, Q26) touches:

1. `plan.payload.grouping_facets` and `steer_point_defaults[].delta.group.grouping.facets`;
2. `grouping_result.groups` (the key, every `group_id` prefix, each group's `facet`),
   `counts` and `flags` (keys), `grouping_provenance` (`facet`, `facets[]`, `facet_runs` keys —
   and a provenance with no `facet_runs`, as the facet-grain revision left older rows, is
   rewritten too);
3. `annotation.payload.theme.referenced_ids` (when `theme.source = 'grouping'`) and
   `annotation.payload.pattern.group_id`;
4. `synthesis_result.blocks[].group_ids`.

Every rewrite is a set-based `UPDATE` with bind parameters and an exact-match `WHERE`
(`item = to_jsonb(old)`, `value ? old`, `left(value, n) = old || ':'`), so a value that merely
contains the old word is untouched, a second run matches nothing, and the whole revision runs
in one transaction with the column renames. The downgrade swaps the arguments. Not rewritten,
by decision: run history with no reader (`synthesis_provenance`,
`counts.groups_unsectioned_by_facet`, `event_log`) and task-agent transcript drafts (none in
the dev database hold a facet list).

# Why

The first draft of Q26 named "the plan payload and the groups keys"; the build found the
prefix inside annotations and synthesis blocks, and the review (2026-10-12) found the
`facet_runs` gate skipping older provenance rows. Tests:
`tests/core/test_migration_046_a3.py` (up, down, and rows without the facet byte-identical).
See [historical migration tests reflect old names below a rename revision](migration-tests-reflect-old-names-below-rename-revision.md).
