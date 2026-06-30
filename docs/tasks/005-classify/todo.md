# Todo: 005-classify

## Phase 1 — Schema foundation

- [ ] **Task 1** — `schema.py` + migration: add `source_classification_result` table with
      all constraints named; migration roundtrips clean
- [ ] **Task 2** — `test_schema.py`: bump table-count assertion 13 → 14

### Checkpoint 1
- [ ] `make verify` green; `len(metadata.tables) == 14`

## Phase 2 — Module and wiring

- [ ] **Task 3** — `classify.py`: `ClassifyContext`, `ClassifyResult`, `_stub_classify`
      (8 sentinels + default), `classify_sources`
- [ ] **Task 4** — `plan.py` + `harness.py`: registry entry + `_run_classify` node + edge
- [ ] **Task 5** — `test_compile.py` + `tests/helpers.py`: valid-component test + FK-safe
      `delete_project_data`

### Checkpoint 2
- [ ] `make verify` green; `Plan(component="classify", ...)` compiles

## Phase 3 — Test suite and demo

- [ ] **Task 6** — `test_classify.py`: 17 test cases (stub paths, round-trips, constraints,
      harness, delete_project_data)
- [ ] **Task 7** — `skeleton.py`: classify run after screen; classification results logged

### Checkpoint 3 (final)
- [ ] `make verify` fully green
- [ ] `python -m policy_atlas.skeleton` exits 0 with classify results
- [ ] Migration roundtrip clean
- [ ] All rubric boxes checkable
