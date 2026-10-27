"""Run the post-screening chain on a briefing's own references and grade the report.

Usage (from the repo root; needs DATABASE_URL, OPENAI_API_KEY and, unless
``--no-langfuse``, the Langfuse keys in backend/.env):

    uv run --project backend --env-file backend/.env \\
        python scripts/evals/post_screening_and_synthesis/run_synthesis.py \\
        --docs 16 --depth landscape --no-langfuse

Per briefing: a task with an approved plan is seeded, every resolved reference is
ingested as an upload with a stage-1 ``relevant`` screen row (so the walk's own
stage-1 screening has nothing to do), the plan walk runs with no search backends, and
the Result artefact is rendered as markdown. Outputs land in
``results/runs/<date>-<depth>-<label>/``. Task rows are kept so the report can be
opened in the app.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import _bootstrap  # noqa: F401
from utils import (
    EXPERIMENT,
    MODEL,
    RESULTS_DIR,
    load_kept,
    load_test_set,
    openai_client,
    prompt,
    write_csv,
)
from evals_search_utils import git_commit
from ground_truth import LABEL_SEP, ref_cache_path
from langfuse import Evaluation, propagate_attributes
from metrics import cost_usd
from openai import OpenAI
from policy_atlas.core import tracing
from policy_atlas.core.db import get_engine
from policy_atlas.core.logging import configure_logging
from policy_atlas.core.openai_client import traced_parse
from policy_atlas.core.tracing import submit_with_context
from policy_atlas.core.prompt_fields import metadata_dict
from policy_atlas.core.schema import (
    runs,
    source_screening_result,
    source_snapshot,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.screen import _insert_screen_row, _screen_basis
from policy_atlas.evidence_search.sourcing.ingest_upload import ingest_upload
from policy_atlas.runtime.agent import _write_plan_row, live_task_agent_and_backends
from policy_atlas.runtime.inherit import _report_markdown
from policy_atlas.runtime.runner import NullIO, RunnerBackends, RunPlanOutcome, run_plan
from policy_atlas.runtime.task_plan import AnalysisDepth, TaskPlan, _enabled_components
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from upload import DATASET

CORPUS_FIELDS = ["label", "text_basis", "n_chunks", "stage2_status"]
FACT_FIELDS = [
    "fact_id",
    "statement",
    "ref_labels",
    "ingested",
    "verdict",
    "quote",
    "rationale",
]
VERDICTS = (
    "fully_represented",
    "partially_represented",
    "not_represented",
    "misrepresented",
    "uncertain",
)
JUDGE_WORKERS = 8
JUDGE_MAX_OUTPUT_TOKENS = 2_000  # a verdict ran about 250 completion tokens


class Verdict(BaseModel):
    verdict: Literal[
        "fully_represented",
        "partially_represented",
        "not_represented",
        "misrepresented",
        "uncertain",
    ]
    quote: str
    rationale: str


@dataclasses.dataclass
class Seeded:
    task_id: uuid.UUID
    scope_id: uuid.UUID
    plan_id: uuid.UUID
    plan: TaskPlan
    seed_run_id: uuid.UUID
    ingested: list[dict[str, Any]]  # resolved refs that went into the corpus


def load_resolved(doc_id: str) -> list[dict[str, Any]]:
    """Cached resolutions for the kept references, in references.csv order.

    Raises:
        FileNotFoundError: If a kept reference has not been resolved yet.
    """
    out = []
    for ref in load_kept(doc_id, "references"):
        path = ref_cache_path(doc_id, ref["label"])
        if not path.exists():
            raise FileNotFoundError(
                f"run `ground_truth.py resolve --docs {doc_id}` first: {path}"
            )
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


def seed_task(
    engine: Engine, doc: dict[str, str], depth: AnalysisDepth, backends: RunnerBackends
) -> Seeded:
    """Create task + approved plan, ingest the corpus and pre-screen it as relevant.

    Args:
        engine: SQLAlchemy engine.
        doc: A row of the test set CSV.
        depth: Analysis depth for the plan; components follow from it.
        backends: Live backends; the embedder is used for upload ingest.
    """
    plan = TaskPlan(
        title=f"Eval {doc['Doc ID']}: {doc['Title']}",
        question=doc["Research question"],
        backend_scope="both",
        search_effort="rapid",  # unused: the walk runs with no search backends
        analysis_depth=depth,
        components=sorted(_enabled_components(depth)),
        steering_mode="unattended",
    )
    task_id, scope_id, plan_id = _write_plan_row(engine, plan=plan)
    resolved = [r for r in load_resolved(doc["Doc ID"]) if r["status"] != "dropped"]
    seed_run_id = uuid.uuid4()
    now = datetime.now(UTC)
    with engine.begin() as conn:
        conn.execute(
            runs.insert().values(
                run_id=seed_run_id,
                task_id=task_id,
                status="succeeded",
                started_at=now,
                ended_at=now,
            )
        )
        for ref in resolved:
            snapshot_id = ingest_upload(
                conn,
                task_id=task_id,
                chunks=ref["chunks"],
                source_locator=ref["source_locator"],
                metadata=ref["metadata"],
                text_basis=ref["status"],
                embedder=backends.embedding,
            )
            tss_id = conn.execute(
                select(task_source_snapshot.c.task_source_snapshot_id).where(
                    task_source_snapshot.c.source_snapshot_id == snapshot_id
                )
            ).scalar_one()
            _insert_screen_row(
                conn,
                task_id=task_id,
                run_id=seed_run_id,
                scope_id=scope_id,
                tss_id=tss_id,
                status="relevant",
                basis=_screen_basis(ref["metadata"]),
                confidence=1.0,
                stage=1,
            )
    return Seeded(task_id, scope_id, plan_id, plan, seed_run_id, resolved)


def run_pipeline(
    engine: Engine, seeded: Seeded, backends: RunnerBackends, session_id: uuid.UUID
) -> RunPlanOutcome:
    """Run the plan walk with no search backends and check the seed held.

    Raises:
        RuntimeError: If the walk did not complete, acquire added sources, or the
            walk's own stage-1 screening screened anything.
    """
    outcome = run_plan(
        engine,
        task_id=seeded.task_id,
        evidence_scope_id=seeded.scope_id,
        plan=seeded.plan,
        plan_id=seeded.plan_id,
        plan_version=1,
        plan_row_id=seeded.plan_id,
        backends=dataclasses.replace(backends, search_backends=[]),
        io=NullIO(),
        session_id=session_id,
    )
    if outcome.status not in ("succeeded", "degraded"):
        raise RuntimeError(f"walk ended {outcome.status}: {outcome.collation_render}")
    with engine.connect() as conn:
        acquired = conn.execute(
            select(func.count())
            .select_from(task_source_snapshot)
            .where(
                task_source_snapshot.c.task_id == seeded.task_id,
                task_source_snapshot.c.origin == "acquired",
            )
        ).scalar_one()
        screened = conn.execute(
            select(func.count())
            .select_from(source_screening_result)
            .where(
                source_screening_result.c.evidence_scope_id == seeded.scope_id,
                source_screening_result.c.screen_stage == 1,
                source_screening_result.c.screened_by_run_id != seeded.seed_run_id,
            )
        ).scalar_one()
    if acquired or screened:
        raise RuntimeError(
            f"seed did not hold: acquired={acquired} stage1_screened={screened}"
        )
    return outcome


def stage2_status(engine: Engine, scope_id: uuid.UUID) -> dict[str, str]:
    """``eval_ref_label`` -> latest stage-2 screen status for the scope."""
    with engine.connect() as conn:
        rows = conn.execute(
            select(source_snapshot.c.metadata, source_screening_result.c.status)
            .select_from(source_screening_result)
            .join(
                task_source_snapshot,
                task_source_snapshot.c.task_source_snapshot_id
                == source_screening_result.c.task_source_snapshot_id,
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id
                == task_source_snapshot.c.source_snapshot_id,
            )
            .where(
                source_screening_result.c.evidence_scope_id == scope_id,
                source_screening_result.c.screen_stage == 2,
            )
            .order_by(source_screening_result.c.screened_at)
        ).fetchall()
    return {metadata_dict(row.metadata)["eval_ref_label"]: row.status for row in rows}


def report_markdown(engine: Engine, seeded: Seeded, outcome: RunPlanOutcome) -> str:
    with engine.connect() as conn:
        return _report_markdown(
            conn, source_task_id=seeded.task_id, run_id=outcome.capability_run_id
        )


def judge_facts(
    client: OpenAI,
    langfuse_client: Any,
    report: str,
    facts: list[dict[str, str]],
    *,
    session_id: uuid.UUID,
    doc_id: str,
) -> tuple[dict[str, Verdict], dict[str, Any]]:
    """Grade every fact against the report, one model call per fact.

    Per fact rather than batched: each call is small and the verdicts cannot
    influence each other. Each call is one Langfuse generation in the run's session.

    Returns:
        ``fact_id -> Verdict`` and a usage record (model, prompt sha, token totals,
        ``judge_llm_cost_usd_computed``).
    """
    system, sha = prompt("judge_v1")

    def one(fact: dict[str, str]) -> tuple[str, Verdict, Any]:
        parsed, usage = traced_parse(
            client,
            langfuse_client,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Key fact:\n{fact['statement']}\n\nReport:\n{report}",
                },
            ],
            response_format=Verdict,
            model=MODEL,
            max_output_tokens=JUDGE_MAX_OUTPUT_TOKENS,
            usage_event="eval.synthesis.judge",
            label="judge",
            name="eval.synthesis.judge",
            prompt_version=f"judge_v1@{sha}",
            session_id=session_id,
            metadata={
                "experiment": EXPERIMENT,
                "doc_id": doc_id,
                "fact_id": fact["fact_id"],
            },
        )
        return fact["fact_id"], parsed, usage

    # submit_with_context carries the caller's propagated Langfuse attributes
    # (the experiment metadata) into the worker threads.
    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as pool:
        results = [
            f.result() for f in [submit_with_context(pool, one, fact) for fact in facts]
        ]
    tokens = {
        key: sum(getattr(u, key) or 0 for _, _, u in results)
        for key in ("prompt", "cached", "completion")
    }
    return {fid: v for fid, v, _ in results}, {
        "model": MODEL,
        "prompt_sha": sha,
        "tokens": tokens,
        "judge_llm_cost_usd_computed": cost_usd(
            MODEL,
            prompt_tokens=tokens["prompt"],
            cached_tokens=tokens["cached"],
            completion_tokens=tokens["completion"],
        ),
    }


def score(
    facts: list[dict[str, str]], verdicts: dict[str, str], ingested_labels: set[str]
) -> dict[str, Any]:
    """Coverage over all facts and over facts with at least one ingested source.

    Args:
        facts: Kept rows of ``key_facts.csv``.
        verdicts: ``fact_id -> verdict`` string.
        ingested_labels: Reference labels that made it into the corpus.
    """
    counts = {v: 0 for v in VERDICTS}
    for fact in facts:
        counts[verdicts[fact["fact_id"]]] += 1
    ingested = [
        f for f in facts if set(f["ref_labels"].split(LABEL_SEP)) & ingested_labels
    ]
    fully_ingested = sum(
        1 for f in ingested if verdicts[f["fact_id"]] == "fully_represented"
    )
    return {
        "n_facts": len(facts),
        "n_ingested": len(ingested),
        "coverage_all": counts["fully_represented"] / len(facts) if facts else 0.0,
        "coverage_ingested": fully_ingested / len(ingested) if ingested else 0.0,
        **{f"n_{v}": c for v, c in counts.items()},
    }


def run_dir(depth: str, label: str) -> Path:
    return RESULTS_DIR / f"{datetime.now(UTC):%Y-%m-%d}-{depth}-{label}"


def run_doc(
    engine: Engine,
    client: OpenAI,
    langfuse_client: Any,
    backends: RunnerBackends,
    doc: dict[str, str],
    depth: AnalysisDepth,
    out_root: Path,
) -> dict[str, Any]:
    """Seed, run, report, judge and score one briefing; write its run folder.

    Returns:
        The ``eval_results.json`` record (ids, walk status, judge usage, scores).
    """
    doc_id = doc["Doc ID"]
    session_id = uuid.uuid4()
    started = datetime.now(UTC)
    seeded = seed_task(engine, doc, depth, backends)
    print(
        f"doc {doc_id}: seeded task {seeded.task_id} with {len(seeded.ingested)} sources"
    )
    outcome = run_pipeline(engine, seeded, backends, session_id)
    report = report_markdown(engine, seeded, outcome)
    if not report.strip():
        raise RuntimeError(
            f"doc {doc_id}: walk {outcome.status} but the report is empty"
        )
    demoted = stage2_status(engine, seeded.scope_id)

    facts = load_kept(doc_id, "key_facts")
    verdicts, judge_usage = judge_facts(
        client, langfuse_client, report, facts, session_id=session_id, doc_id=doc_id
    )
    ingested_labels = {r["label"] for r in seeded.ingested}
    scores = score(facts, {k: v.verdict for k, v in verdicts.items()}, ingested_labels)
    resolution = [r["status"] for r in load_resolved(doc_id)]

    out = out_root / doc_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(report, encoding="utf-8")
    write_csv(
        out / "facts.csv",
        [
            {
                "fact_id": f["fact_id"],
                "statement": f["statement"],
                "ref_labels": f["ref_labels"],
                "ingested": "y"
                if set(f["ref_labels"].split(LABEL_SEP)) & ingested_labels
                else "n",
                "verdict": verdicts[f["fact_id"]].verdict,
                "quote": verdicts[f["fact_id"]].quote,
                "rationale": verdicts[f["fact_id"]].rationale,
            }
            for f in facts
        ],
        FACT_FIELDS,
    )
    write_csv(
        out / "corpus.csv",
        [
            {
                "label": r["label"],
                "text_basis": r["status"],
                "n_chunks": len(r["chunks"]),
                "stage2_status": demoted.get(r["label"], ""),
            }
            for r in seeded.ingested
        ],
        CORPUS_FIELDS,
    )
    record = {
        "doc_id": doc_id,
        "depth": depth,
        "git_commit": git_commit(),
        "task_id": str(seeded.task_id),
        "evidence_scope_id": str(seeded.scope_id),
        "capability_run_id": str(outcome.capability_run_id),
        "langfuse_session_id": str(session_id),
        "walk_status": outcome.status,
        "steps": [
            {"component": s.component, "status": s.status, "reason": s.reason}
            for s in outcome.steps
        ],
        "n_refs_full_text": resolution.count("full_text"),
        "n_refs_abstract_only": resolution.count("abstract_only"),
        "n_refs_dropped": resolution.count("dropped"),
        "n_stage2_demoted": sum(1 for v in demoted.values() if v != "relevant"),
        "report_chars": len(report),
        "wall_clock_s": (datetime.now(UTC) - started).total_seconds(),
        "judge": judge_usage,
        "scores": scores,
    }
    (out / "eval_results.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8"
    )
    print(
        f"doc {doc_id}: walk {outcome.status}, report {len(report)} chars, "
        f"stage-2 demoted {record['n_stage2_demoted']}, "
        f"coverage all={scores['coverage_all']:.2f} "
        f"ingested={scores['coverage_ingested']:.2f} -> {out}"
    )
    return record


def item_scores(*, output: dict[str, Any], **_: Any) -> list[Evaluation]:
    """Per-briefing Langfuse scores from a ``run_doc`` record."""
    scores = output["scores"]
    return [
        Evaluation(name="coverage_all", value=scores["coverage_all"]),
        Evaluation(name="coverage_ingested", value=scores["coverage_ingested"]),
        Evaluation(name="n_facts", value=scores["n_facts"]),
        Evaluation(name="n_fully", value=scores["n_fully_represented"]),
        Evaluation(name="n_misrepresented", value=scores["n_misrepresented"]),
        *(
            Evaluation(name=key, value=output[key])
            for key in (
                "n_refs_full_text",
                "n_refs_abstract_only",
                "n_refs_dropped",
                "n_stage2_demoted",
            )
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--docs", nargs="+", required=True, help="Doc IDs")
    parser.add_argument(
        "--depth", choices=("landscape", "standard", "deep"), default="deep"
    )
    parser.add_argument("--run-label", default="run")
    parser.add_argument("--no-langfuse", action="store_true")
    args = parser.parse_args()

    configure_logging()
    engine = get_engine()
    client = openai_client()
    langfuse_client = None if args.no_langfuse else tracing.get_langfuse()
    _, backends = live_task_agent_and_backends(langfuse_client)
    out_root = run_dir(args.depth, args.run_label)
    docs = load_test_set(args.docs)

    if langfuse_client is None:
        for doc in docs:
            run_doc(engine, client, None, backends, doc, args.depth, out_root)
        return

    # Same shape as scripts/evals/search/checks/production_recall.py: our own item
    # list so --docs can narrow the run while it still attaches to the dataset.
    dataset = langfuse_client.get_dataset(DATASET)
    by_id = {doc["Doc ID"]: doc for doc in docs}
    items = [i for i in dataset.items if i.input["doc_id"] in by_id]
    missing = set(by_id) - {i.input["doc_id"] for i in items}
    if missing:
        raise SystemExit(
            f"docs {sorted(missing)} are not in dataset {DATASET!r}; run upload.py"
        )
    _, judge_sha = prompt("judge_v1")
    meta = {
        "experiment": EXPERIMENT,
        "depth": args.depth,
        "judge_model": MODEL,
        "judge_prompt_sha": judge_sha,
        "git_commit": git_commit(),
    }

    def task(*, item: Any, **_: Any) -> dict[str, Any]:
        with propagate_attributes(metadata=meta):
            return run_doc(
                engine,
                client,
                langfuse_client,
                backends,
                by_id[item.input["doc_id"]],
                args.depth,
                out_root,
            )

    langfuse_client.run_experiment(
        name=EXPERIMENT,
        run_name=f"{args.run_label}/{args.depth}",
        data=items,
        task=task,
        evaluators=[item_scores],
        max_concurrency=1,
        metadata=meta,
        _dataset_version=dataset.version,
    )


if __name__ == "__main__":
    main()
