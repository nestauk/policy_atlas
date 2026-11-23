---
paths:
  - "scripts/record_*_fixtures.py"
  - "scripts/_fixture_sanitizer.py"
  - "backend/tests/data/provider_records/**"
---

# Recorded provider fixtures: facts the code does not show

Each line is a fact about this repository that is easy to miss when you read one file.
Use your own judgement for everything else. Remove a line when a test enforces it.

- The recorders clean known keys, and `test_fixture_leak_guard` checks only URLs, DOIs and
  award ids. A provider field outside the key list (a nested list item, a field only some
  records carry) puts real names into this public repository with every test green.
