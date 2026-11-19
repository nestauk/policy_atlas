---
paths:
  - "backend/src/policy_atlas/evidence_search/**"
  - "backend/src/policy_atlas/runtime/**"
  - "backend/src/policy_atlas/api/**"
---

# Evidence search data: facts the code does not show

Each line is a fact about this repository that is easy to miss when you read one file.
Use your own judgement for everything else. Remove a line when a test enforces it.

- A document can have several `source_screening_result` rows (one per stage and screening
  generation, plus failed attempts). Read them through `effective_screen_rows()` in
  `evidence_search/assess/screen.py`: a plain `status = 'relevant'` join lets demoted
  documents back in and counts confirmed ones twice, with no error.
