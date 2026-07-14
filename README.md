# 🌐 Policy Atlas

We're harnessing AI to improve policy design, helping users search, synthesise, and
simulate policy interventions.

Find more information [on the website](https://www.nesta.org.uk/project/policy-atlas-harnessing-ai-to-improve-policy-design/).

⚠️ This is heavy work-in-progress ⚠️

## Overview

This repo holds the **Policy Atlas v3.0 backend** — an evidence-led policy-analysis
workspace where capabilities run bounded, inspectable pipelines over an acquired
evidence corpus and produce grounded artefacts: every significant claim carries its
citations, verbatim quotes and appraisal.

The first capability, the **Evidence Base**, runs end-to-end:

> plan → acquire → screen → classify → appraise → ingest →
> (characterise · select · extract · group) → synthesise

Further capabilities (options assessment, value for money, …) will land beside it.

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
tests/             mirrors the src tree; tests/data/ holds all fixtures
docs/              specs, ADRs, task records, knowledge base, agentic-ops
```

## Getting started

Requires Python ≥ 3.12, [uv](https://docs.astral.sh/uv/), and Docker (Postgres).

```sh
docker compose up -d      # Postgres (dev + test databases)
make setup                # uv sync + test DB provisioning
make verify               # okf-validate · tests · mypy · ruff · build (the gate)
```

Run the orchestrator CLI:

```sh
uv run python -m policy_atlas.runtime.orchestrate
```

With no `OPENAI_API_KEY` set it runs in **stub mode** — deterministic, zero egress.
With keys configured (`.env`), the same command runs the live chain.

## Documentation

Product intent and system contracts live in [`docs/specs/`](docs/specs/index.md),
architectural decisions in [`docs/adr/`](docs/adr/), and per-task contracts and
evidence in [`docs/tasks/`](docs/tasks/).

## License

This project is licensed under the GNU Affero General Public License v3.0 — see the
[LICENSE](LICENSE) file for details.
