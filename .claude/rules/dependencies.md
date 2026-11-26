---
paths:
  - "backend/pyproject.toml"
  - "backend/uv.lock"
---

# Backend dependencies: facts the code does not show

Each line is a fact about this repository that is easy to miss when you read one file.
Use your own judgement for everything else. Remove a line when a test enforces it.

- Chunk hashes are the same across processes only because
  `evidence_search/sourcing/ingest_full_text.py` patches pymupdf4llm's `column_boxes` at
  import by matching its exact source. After an upgrade that moves that source the patch
  does nothing, and the same PDF can hash two ways; the backstop test catches it only by chance.
