---
type: Invariant
title: An identifier sweep renames stored JSON keys in code but not in data — audit every JSON column on real rows
description: A vocabulary rename that rewrites identifiers also rewrites the string literals that name JSONB keys and stored values; the rows keep the old ones. Before the migration lands, scan every JSON column on a real database for retired keys and values, then either rewrite reversibly (derived rows) or read both names (append-only logs). Compatibility readers are legitimate residue of a "no retired word" invariant.
tags: [migration, vocabulary, jsonb, compatibility, review, task-038]
timestamp: 2026-09-05
---

# Rule

When a rename sweeps identifiers, treat every **stored** occurrence of the
old word as its own surface:

1. **Enumerate it from data, not from the contract.** List every JSON column
   (`information_schema.columns` where `data_type IN ('json','jsonb')`) and,
   on a real database (the migrated dev DB, staging), count rows whose text
   carries a retired key or value, per column. Task 038's contract named
   five reversible stored values; the audit found two more keys with live
   readers (`pss_id` in `selection_result.selected/excluded`,
   `project_source_snapshot_id` in `event_log` screen payloads) and several
   without.
2. **Pick the treatment by the table's nature.** Derived rows (selection
   results, provenance) get a reversible key rewrite in the migration —
   forward on upgrade, back on downgrade — and a row in the manifest's
   stored-values table. Append-only audit logs (`event_log`) are never
   rewritten: the one reader accepts both names, with a compatibility test
   that seeds the old key.
3. **A "no retired word remains" invariant exempts the readers whose data
   *is* the retired value** (`canonical_actor`, `canonical_steer_point`,
   `both_generations`, the `or payload.get(<old key>)` fallback). Read the
   invariant as "no live use", and list each exemption where it occurs.

# Why

The sweep is blind to the difference between an identifier and a string
literal naming a JSON key: `item["pss_id"]` becomes `item["tss_id"]` in every
reader while the rows still say `pss_id`, so the code compiles, the tests
(which seed new-shape rows) pass, and every pre-migration row reads back
empty. On 038 that was every existing shortlist and every source's screening
reason — invisible to the round-trip test because its fixture only seeded
what the contract enumerated.

# Watch out

- The round-trip fixture must seed the keys the audit found, not the keys
  the contract listed; assert both directions per key
  (`tests/core/test_migration_038.py`).
- Values that only telemetry writes (a prompt-version id in a decision
  payload) still show up in the audit; record them as read-by-nothing rather
  than rewriting them.
- Same family: [rename-sweep-inverts-screen-sense-words](rename-sweep-inverts-screen-sense-words.md)
  (the sweep's other blind spot), [schema-manifest-from-catalog-not-metadata](schema-manifest-from-catalog-not-metadata.md).

# Citations

- [038-vocabulary-alignment/verification.md](../tasks/038-vocabulary-alignment/verification.md) (§ Review findings R5, R6, R28; the JSON-column audit)
- [038-vocabulary-alignment/schema-manifest.md](../tasks/038-vocabulary-alignment/schema-manifest.md) (§ Stored values 6–7)
- [ADR 0036](../adr/0036-one-vocabulary-across-code-schema-api-and-screen.md) (§ Rollback)
- `backend/alembic/versions/c1a7f4e9b0d2_vocabulary_alignment.py` (`_JSONB_KEY_RENAMES`), `backend/src/policy_atlas/api/readmodels/repository.py` (`_source_reason_maps`)
