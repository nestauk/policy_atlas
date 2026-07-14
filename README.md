# Policy Atlas v3.0

An evidence-led policy-analysis workspace: capabilities run bounded, inspectable
pipelines over an acquired evidence corpus and mint grounded artefacts — evidence
syntheses whose significant claims carry citations, verbatim quotes and appraisal,
co-emitted rather than stapled on afterwards. The v3.0 backend ships one capability,
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
  data/            package fixture data (sanitized provider records) backing the
                   zero-egress stub backends
alembic/           database migrations
tests/             mirrors the src tree; conftest runs migrations once per session
docs/              specs, ADRs, task records, knowledge base, agentic-ops
```

## Setup

Requires Python ≥ 3.12, [uv](https://docs.astral.sh/uv/), and Docker (Postgres).

```sh
docker compose up -d      # Postgres (dev + test databases)
make setup                # uv sync + test DB provisioning
make verify               # okf-validate · tests · mypy · ruff · build (the gate)
make verify-fast          # inner-loop variant (skips the slow ingest suite)
```

## Running

The orchestrator CLI is the product entry point:

```sh
uv run python -m policy_atlas.runtime.orchestrate
```

With no `OPENAI_API_KEY` in the environment it runs in **stub mode** — deterministic
backends over the packaged fixture corpus, zero egress — which is also the repo's
standardised smoke check. With keys configured (`.env`), the same command runs the
live chain (OpenAI + optional Langfuse tracing).

## Licence

AGPL-3.0-only (see [LICENSE](LICENSE)).
