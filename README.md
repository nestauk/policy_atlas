# Policy Atlas v3.0

An evidence-led policy-analysis workspace: capabilities run bounded, inspectable
pipelines over an acquired evidence corpus and produce grounded artefacts - evidence
syntheses whose significant claims carry citations, verbatim quotes and appraisal. 
The v3.0 backend ships one capability,
the **Evidence Base**: plan → acquire → screen → classify → appraise → ingest →
(characterise · select · extract · group, plan-selected) → synthesise.

Product intent and system contracts live in [`docs/specs/`](docs/specs/index.md);
architectural decisions in [`docs/adr/`](docs/adr/); per-task contracts and evidence
in [`docs/tasks/`](docs/tasks/).

## Layout

```
src/policy_atlas/
  runtime/         orchestrator CLI, capability runner, LangGraph harness,
                   planner, steering, run-spec compile
  evidence_base/   the EB capability — future capabilities land as siblings
    sourcing/      search backends + loop, acquisition, full-text ingest, grounding
    screen/        screening, classification, appraisal
    corpus/        characterise, select, ranking, theme grouping
    extract/       IOF + ICF findings extraction, vetters, quote verification
    group/         multi-facet grouping over extracted findings
    synthesis/     terminal artefact composition, section loop, grounding judge
  core/            schema, db, events, logging, tracing, usage, model-client
                   plumbing, embeddings
alembic/           database migrations
tests/             mirrors the src tree; conftest runs migrations once per session;
                   tests/data/ holds all fixtures (full-text corpus + sanitized
                   provider records)
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
uv run python -m policy_atlas.runtime.orchestrate
```

## Licence

AGPL-3.0-only (see [LICENSE](LICENSE)).
