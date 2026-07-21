# Policy Atlas v3.0

An evidence-led policy-analysis workspace: capabilities run bounded, inspectable
pipelines over an acquired evidence corpus and produce grounded artefacts - evidence
syntheses whose significant claims carry citations, verbatim quotes and appraisal. 
The v3.0 backend ships one capability,
the **Evidence Base**: plan → acquire → screen → classify → appraise → ingest →
(characterise · select · extract · group, plan-selected) → synthesise.

Product intent and system contracts live in [`docs/specs/`](docs/specs/index.md);
architectural decisions in [`docs/adr/`](docs/adr/); per-task plans and evidence
in [`docs/tasks/`](docs/tasks/).

## Layout

```
backend/                     Python project (import-neutral hoist, task 025 A.2)
backend/src/policy_atlas/
  runtime/                   orchestrator CLI, capability runner, LangGraph harness,
                             planner, steering, run-spec compile
  evidence_base/             the EB capability
    sourcing/                search backends + loop, acquisition, full-text ingest
    assess/                  screening, classification, appraisal
    corpus/                  characterise, select, ranking, theme grouping
    extract/                 Intervention, outcome and context findings extraction, vetters, quote verification
    group/                   multi-facet grouping over extracted findings
    synthesis/               artefact composition, section generation loop, grounding judge
  core/                      schema, db, events, logging, tracing, usage, model-client
                             plumbing, embeddings
backend/alembic/             database migrations
backend/tests/               mirrors the src tree; conftest runs migrations once per session;
                             backend/tests/data/ holds all fixtures (full-text corpus +
                             sanitized provider records)
frontend/                    web app (scaffold lands task 025 phase F)
infra/                       CDK (reserved)
docs/              specs, ADRs, task records, knowledge base, agentic-ops
```

## Setup

Requires Python ≥ 3.12, [uv](https://docs.astral.sh/uv/), and Docker (Postgres).

```sh
docker compose up -d      # Postgres (dev + test databases)
make setup                # uv sync + test DB provisioning
make verify               # okf-validate · tests · mypy · ruff · build
make verify-fast          # inner-loop variant (skips the slow ingest suite)
```

## Running

The orchestrator CLI is the product entry point:

```sh
uv run --project backend python -m policy_atlas.runtime.orchestrate
```

## Licence

AGPL-3.0-only (see [LICENSE](LICENSE)).
