---
type: Convention
title: Content-keyed identity via uuid5 — deterministic ids beat run-keyed uuid4 where fixtures pin byte-equality
description: 028's theme_id = uuid5(namespace, f"{task_id}:{theme_name}") keeps stub runs byte-identical across re-runs and gives bookmarks/filters a durable key with no new table — but the identity is only as stable as the content it hashes; a re-characterise that reproduces a theme name byte-identically keeps its id, any wording drift mints a new one. Renames preserve the id by design (the payload name changes, the id does not).
tags: [identity, uuid5, determinism, themes, fixtures, task-028]
timestamp: 2026-08-05
---

# Rule

Where an entity needs a durable public id but no dedicated table —
028's characterisation themes — derive it from content:
`uuid5(NAMESPACE, f"{task_id}:{name}")`. Properties that matter:

- **Stub determinism:** identical inputs mint identical ids, so byte-equality
  fixtures survive re-runs (run-keyed `uuid4` breaks them every run).
- **Rename-stability by construction choice:** 028's P2 `rename_theme`
  updates the payload's display name and *keeps* the minted id, so
  bookmarks/filters keyed on `theme_id` survive renames.
- **Honest scope of "survives re-characterise":** a fresh characterise run
  re-mints from its own theme names — the id survives ONLY when the LLM
  reproduces the name byte-identically. Do not claim durable identity
  across regeneration for content-keyed ids (028 review F30 corrected
  exactly this over-claim).

# Watch out

- The id's stability contract must be written where the id is minted —
  consumers will otherwise assume table-grade durability.
- Filters must key on the id, never the name
  (`source_tag.theme_id`), because tag rows keep historical names.

# Citations

- `backend/src/policy_atlas/evidence_search/corpus/characterise.py`
  (theme_id minting)
- `backend/src/policy_atlas/api/continuation.py` (`_apply_theme_renames`
  keeps ids)
