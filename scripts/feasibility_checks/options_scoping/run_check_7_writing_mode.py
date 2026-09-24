"""Runner for feasibility check 7 — writing mode (options scoping, task 044 phase 4.4).

Owner ruling 2026-09-09 (044 contract § Baseline, C6): "let's go with sequential, but we
should also do some sort of test comparing it to a parallel version before finalising". This
script produces the two baselines side by side; the lead reads them.

    uv run --project backend --env-file backend/.env python \
        scripts/feasibility_checks/options_scoping/run_check_7_writing_mode.py \
        sequential neet --data <dir>

Commands:
    sequential <corpus>   the baseline template through the product's own ``synthesise_scope``
    parallel <corpus>     the same eight required sections as a naive fan-out, one section
                          per thread, each with an empty ledger, joined in the ruled order
    compare <corpus>      side-by-side table + the deterministic repetition list

Not product code. Substrate discipline
(``docs/knowledge/run-component-driver-for-scoped-live-checks.md``): the dev database only,
``DATABASE_URL`` forced after the env file loads, an existing screened selection reused and
never re-searched. Every run happens inside a transaction that is **rolled back**: no baseline
artefact, block, citation or roll-up survives the check. The ``--data`` folder holds the
outputs, outside the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas"
)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy import select as sa_select

from policy_atlas.core.embeddings import OpenAIEmbeddingBackend  # noqa: E402
from policy_atlas.core.schema import block, runs, synthesis_result  # noqa: E402
from policy_atlas.evidence_search.synthesis import synthesise as S  # noqa: E402
from policy_atlas.evidence_search.synthesis.baseline_prompt import (  # noqa: E402
    BASELINE_PROPOSED_SECTIONS_MAX,
    BASELINE_SECTIONS,
    BASELINE_TEMPLATE_KEY,
    SOURCES_SECTION_TITLE,
    compile_intent,
)
from policy_atlas.evidence_search.synthesis.grounding_judge import (  # noqa: E402
    OpenAIGroundingJudgeBackend,
)
from policy_atlas.evidence_search.synthesis.synthesis_backend import (  # noqa: E402
    OpenAISynthesisBackend,
)
from policy_atlas.evidence_search.synthesis.synthesise import (  # noqa: E402
    SynthesiseContext,
    synthesise_scope,
)
from policy_atlas.runtime.scoping_plan import _baseline_section_directives  # noqa: E402

# --------------------------------------------------------------------------- corpora

# Dev-database scopes with a real screened selection. ``synthesise_scope`` reads its evidence
# from the product schema (chunks, screening, appraisal, coverage), so a check that runs the
# product's own path runs against a scope, not against an exported JSON corpus: the 035 exports
# in the data folder carry document records, not the screened substrate synthesise needs.
CORPORA: dict[str, dict[str, Any]] = {
    "neet": {
        "task_id": uuid.UUID("1e03e719-1670-4ca9-aa2c-2f810c852d8b"),
        "scope_id": uuid.UUID("843661e4-2120-48ab-b099-0880ff078ee2"),
        "note": "the 035 NEET corpus (design reference), 59 screened-in documents",
        "intent": {
            "target_unit": "young people aged 16 to 24 who are not in education, "
            "employment or training",
            "where": "England",
            "intended_change": "reduce the number of young people who are NEET",
            "outcomes": [
                "NEET rate",
                "entry into education, employment or training",
            ],
        },
    },
    "thin": {
        "task_id": uuid.UUID("bea5e7bc-b6ac-407d-887d-4256e0b5c07e"),
        "scope_id": uuid.UUID("1b57fbc4-b18f-491f-a9bf-3b516aebe4ac"),
        "note": "the thinnest dev-database corpus, 36 screened-in documents on social "
        "media / AI and young people's mental health (NOT an 035 corpus — no 035 corpus "
        "thinner than NEET exists on this machine as a screened scope)",
        "intent": {
            "target_unit": "young people",
            "where": "the United Kingdom",
            "intended_change": "reduce harm to young people's mental health and cognitive "
            "abilities from social media and AI use",
            "outcomes": ["mental health", "cognitive ability"],
        },
    },
}

SECTION_TITLES: tuple[str, ...] = tuple(s.title for s in BASELINE_SECTIONS)


# --------------------------------------------------------------------------- harness helpers


def engine():
    """Return an engine on the forced dev database."""
    return create_engine(os.environ["DATABASE_URL"], future=True)


def backends() -> dict[str, Any]:
    """Return the real provider backends the agent CLI wires for synthesise."""
    return {
        "synthesis_backend": OpenAISynthesisBackend(),
        "grounding_judge_backend": OpenAIGroundingJudgeBackend(),
        "embedding_backend": OpenAIEmbeddingBackend(),
    }


def suppress_extras() -> None:
    """Hold both modes to the eight required sections.

    Baseline mode always runs the extras proposer, so a seven-run fan-out would pay seven
    proposal calls and could write different section sets per run. The comparison the owner
    asked for is over the eight required sections, so the proposer is stubbed to "no extras"
    in BOTH modes. Driver-side only — nothing here ships.
    """
    S._baseline_extra_sections = lambda **_: (
        [],
        ["check7: extras proposer suppressed"],
    )


class Timer:
    """A progress emitter that records per-section wall clock instead of writing events."""

    def __init__(self) -> None:
        self.skeleton: list[dict[str, str]] = []
        self.sections: list[dict[str, Any]] = []
        self._started: dict[int, float] = {}

    def emit_skeleton(self, sections, *, key_findings: bool = True) -> None:
        self.skeleton = [dict(s) for s in sections]

    def section_started(self, synthesis_index: int) -> None:
        self._started[synthesis_index] = time.perf_counter()

    def section_completed(self, synthesis_index: int, *, prose: str) -> None:
        started = self._started.get(synthesis_index, time.perf_counter())
        title = (
            self.skeleton[synthesis_index]["title"]
            if synthesis_index < len(self.skeleton)
            else f"section {synthesis_index}"
        )
        self.sections.append(
            {
                "index": synthesis_index,
                "title": title,
                "wall_s": round(time.perf_counter() - started, 1),
                "prose": prose,
            }
        )


# The depth the directive is compiled for (task 044 phase 8: rapid carries no
# proposed-section budget; the seven sections are the same); set from the CLI.
DEPTH = "standard"


def baseline_context(section_titles: list[str] | None = None) -> dict[str, Any]:
    """Return the scope context carrying the compiled baseline synthesis directive.

    Args:
        section_titles: When given, only these model-written sections are supplied (the
            fan-out's one-section directives). ``None`` supplies all eight.
    """
    sections = _baseline_section_directives()
    if section_titles is not None:
        keep = set(section_titles)
        sections = [
            s
            for s in sections
            if s["title"] in keep or s["title"] == SOURCES_SECTION_TITLE
        ]
    synthesis: dict[str, Any] = {"template": BASELINE_TEMPLATE_KEY, "sections": sections}
    if DEPTH == "standard":
        # Proposed sections are a standard-depth allowance (phase 8): the product's
        # rapid directive carries no budget and synthesise makes no proposal call.
        synthesis["section_budget"] = BASELINE_PROPOSED_SECTIONS_MAX
    return {"synthesis": synthesis}


def run_one(
    corpus: dict[str, Any],
    *,
    section_titles: list[str] | None,
    shared_backends: dict[str, Any],
) -> dict[str, Any]:
    """Run ``synthesise_scope`` once in baseline mode and roll the transaction back.

    Args:
        corpus: A ``CORPORA`` entry.
        section_titles: Model-written sections to supply, or ``None`` for all eight.
        shared_backends: Provider backends (thread-safe HTTP clients).

    Returns:
        ``{summary, provenance, blocks, sections, wall_s}`` — everything read back before the
        rollback.
    """
    intent = compile_intent(**corpus["intent"])
    context = baseline_context(section_titles)
    run_id = uuid.uuid4()
    timer = Timer()
    eng = engine()
    with eng.connect() as conn:
        trans = conn.begin()
        try:
            # synthesis_result carries an FK to (run_id, task_id): the harness owns the
            # runs row on the product path, so the driver mints one here. Rolled back.
            conn.execute(
                runs.insert().values(
                    run_id=run_id,
                    task_id=corpus["task_id"],
                    status="running",
                    started_at=datetime.now(UTC),
                )
            )
            # The scope row is NOT updated. ``synthesise_scope`` parses its directive from
            # the ``SynthesiseContext`` it is handed, not from the row (the harness reads
            # the row only to build that context), and a driver that wrote the directive to
            # the shared row took a Postgres row lock that silently serialised the fan-out.
            ctx = SynthesiseContext(
                scope_id=corpus["scope_id"],
                intent=intent,
                context=context,
                # A scoping chain has no characterise, extract or group step: the
                # baseline's evidence is the documents' own text.
                characterisation_run_id=None,
                selection_run_id=None,
                extraction_run_id=None,
                grouping_run_id=None,
            )
            t0 = time.perf_counter()
            started_epoch = time.time()
            summary = synthesise_scope(
                conn,
                task_id=corpus["task_id"],
                run_id=run_id,
                context=ctx,
                progress_emitter=timer,
                **shared_backends,
            )
            wall = round(time.perf_counter() - t0, 1)
            row = conn.execute(
                sa_select(
                    synthesis_result.c.synthesis_provenance,
                    synthesis_result.c.blocks,
                    synthesis_result.c.counts,
                ).where(synthesis_result.c.run_id == run_id)
            ).one()
            blocks = {str(b["block_id"]): b["title"] for b in row.blocks}
            prose_by_block = {
                str(r.block_id): r.content
                for r in conn.execute(
                    sa_select(block.c.block_id, block.c.content).where(
                        block.c.block_id.in_([uuid.UUID(k) for k in blocks])
                    )
                )
            }
        finally:
            trans.rollback()
    eng.dispose()
    return {
        "run_id": str(run_id),
        "wall_s": wall,
        "started_epoch": started_epoch,
        "ended_epoch": started_epoch + wall,
        "summary": summary,
        "call_counts": row.synthesis_provenance["call_counts"],
        "counts": row.counts,
        "blocks": [
            {
                "title": b["title"],
                "role": b["role"],
                "claim_counts_by_type": b["claim_counts_by_type"],
                "tool_call_count": b["tool_call_count"],
                "prose": prose_by_block.get(str(b["block_id"]), ""),
            }
            for b in row.blocks
        ],
        "section_wall_s": {s["title"]: s["wall_s"] for s in timer.sections},
    }


# --------------------------------------------------------------------------- output


def out_dir(data: Path, corpus_name: str) -> Path:
    d = data / "check7" / corpus_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_markdown(path: Path, *, title: str, record: dict[str, Any]) -> None:
    """Write the artefact blocks plus the run's numbers as markdown."""
    lines = [f"# {title}", ""]
    lines.append(f"Wall clock: {record['wall_s']}s. ")
    lines.append(f"Generation calls: {json.dumps(record['call_counts'])}. ")
    lines.append(f"Tokens: {json.dumps(record['summary']['usage_totals'])}.")
    lines.append("")
    lines.append("| section | wall s | claims by type | tool calls |")
    lines.append("|---|---|---|---|")
    for b in record["blocks"]:
        lines.append(
            f"| {b['title']} | {record['section_wall_s'].get(b['title'], '—')} | "
            f"{json.dumps(b['claim_counts_by_type'])} | {b['tool_call_count']} |"
        )
    lines.append("")
    for b in record["blocks"]:
        lines.append(f"## {b['title']}")
        lines.append("")
        lines.append(b["prose"])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", path)


def save_json(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps(record, indent=1, default=str), encoding="utf-8")
    print("wrote", path)


# --------------------------------------------------------------------------- commands


def cmd_sequential(data: Path, corpus_name: str) -> None:
    corpus = CORPORA[corpus_name]
    suppress_extras()
    record = run_one(corpus, section_titles=None, shared_backends=backends())
    d = out_dir(data, corpus_name)
    save_json(d / "sequential.json", record)
    write_markdown(
        d / "sequential.md",
        title=f"Baseline — sequential ({corpus_name}: {corpus['note']})",
        record=record,
    )
    print(
        f"sequential {corpus_name}: {record['wall_s']}s total, "
        f"tokens {record['summary']['usage_totals']}"
    )


def cmd_parallel(data: Path, corpus_name: str) -> None:
    corpus = CORPORA[corpus_name]
    suppress_extras()
    shared = backends()
    t_zero = time.time()
    t0 = time.perf_counter()
    with ThreadPoolExecutor(len(SECTION_TITLES)) as ex:
        futures = {
            title: ex.submit(
                run_one, corpus, section_titles=[title], shared_backends=shared
            )
            for title in SECTION_TITLES
        }
        results = {}
        for title, fut in futures.items():
            results[title] = fut.result()
    wall = round(time.perf_counter() - t0, 1)

    # Naive join, in the ruled order: each section's own block, then one Sources foot (the
    # foot is code-rendered from the run's coverage record, so every arm renders the same
    # text — the join takes it once).
    blocks: list[dict[str, Any]] = []
    for title in SECTION_TITLES:
        for b in results[title]["blocks"]:
            if b["title"] == title:
                blocks.append(b)
    sources = next(
        (
            b
            for b in results[SECTION_TITLES[0]]["blocks"]
            if b["title"] == SOURCES_SECTION_TITLE
        ),
        None,
    )
    if sources is not None:
        blocks.append(sources)

    call_counts: Counter[str] = Counter()
    usage: Counter[str] = Counter()
    for r in results.values():
        call_counts.update(r["call_counts"])
        for k, v in r["summary"]["usage_totals"].items():
            if isinstance(v, int):
                usage[k] += v
    record = {
        "wall_s": wall,
        "wall_s_slowest_section": max(r["wall_s"] for r in results.values()),
        "wall_s_sum_of_sections": round(sum(r["wall_s"] for r in results.values()), 1),
        "call_counts": dict(call_counts),
        "summary": {"usage_totals": dict(usage)},
        "blocks": blocks,
        # The section's own writing time (tool loop + judge), as the sequential arm measures
        # it. Each fan-out arm also pays the run's setup (retrieval scope + substrate load,
        # no model calls); ``run_wall_s`` below carries that, so the two are comparable.
        "section_wall_s": {
            t: results[t]["section_wall_s"].get(t) for t in SECTION_TITLES
        },
        "run_wall_s": {t: results[t]["wall_s"] for t in SECTION_TITLES},
        # Overlap evidence: how much of the fan-out actually ran at the same time.
        "arm_windows": {
            t: [
                round(results[t]["started_epoch"] - t_zero, 1),
                round(results[t]["ended_epoch"] - t_zero, 1),
            ]
            for t in SECTION_TITLES
        },
        "per_section_runs": {
            t: {
                "run_id": results[t]["run_id"],
                "call_counts": results[t]["call_counts"],
                "usage_totals": results[t]["summary"]["usage_totals"],
            }
            for t in SECTION_TITLES
        },
    }
    d = out_dir(data, corpus_name)
    save_json(d / "parallel.json", record)
    write_markdown(
        d / "parallel.md",
        title=f"Baseline — parallel fan-out ({corpus_name}: {corpus['note']})",
        record=record,
    )
    print(f"parallel {corpus_name}: {wall}s total, tokens {dict(usage)}")


# --------------------------------------------------------------------------- compare

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# A "figure" worth tracking carries a unit, a decimal or thousands separator, or four or
# more digits (a year, a count). Bare small integers — "16 to 24", "one of three" — are
# vocabulary, not a restated number, and would swamp the list.
_FIGURE = re.compile(
    r"\d[\d,.]*\s?(?:%|per cent|million|billion|thousand|bn)|\d[\d,]*\.\d+|\d{4,}|\d{1,3},\d{3}"
)
_PUNCT = re.compile(r"[^a-z0-9 ]+")
CLAUSE_N = 8


def normalise(sentence: str) -> str:
    return " ".join(_PUNCT.sub(" ", sentence.lower()).split())


def sentences(prose: str) -> list[str]:
    body = "\n".join(
        line for line in prose.splitlines() if not line.strip().startswith("#")
    )
    return [s.strip() for s in _SENTENCE.split(body) if len(s.strip()) > 25]


def repetition(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the deterministic repetition list: sentences and figures in >1 section."""
    by_sentence: dict[str, set[str]] = defaultdict(set)
    by_clause: dict[str, set[str]] = defaultdict(set)
    by_figure: dict[str, set[str]] = defaultdict(set)
    for b in blocks:
        for s in sentences(b["prose"]):
            by_sentence[normalise(s)].add(b["title"])
        # Normalised-substring match: an eight-word run shared by two sections is the same
        # statement restated, whether or not the whole sentence matches.
        words = normalise(b["prose"]).split()
        for i in range(len(words) - CLAUSE_N + 1):
            by_clause[" ".join(words[i : i + CLAUSE_N])].add(b["title"])
        for f in _FIGURE.findall(b["prose"]):
            f = f.strip()
            if len(f) > 1:
                by_figure[f].add(b["title"])
    repeated_sentences = sorted(
        (
            {"text": k, "sections": sorted(v)}
            for k, v in by_sentence.items()
            if len(v) > 1
        ),
        key=lambda r: r["text"],
    )
    repeated_figures = sorted(
        (
            {"figure": k, "sections": sorted(v)}
            for k, v in by_figure.items()
            if len(v) > 1
        ),
        key=lambda r: r["figure"],
    )
    # Collapse overlapping n-grams: keep the longest run per section pair.
    hits = sorted((k for k, v in by_clause.items() if len(v) > 1))
    merged: list[str] = []
    for clause in hits:
        if not any(clause in longer for longer in merged):
            merged = [m for m in merged if m not in clause]
            merged.append(clause)
    repeated_clauses = sorted(
        ({"text": c, "sections": sorted(by_clause[c])} for c in merged),
        key=lambda r: r["text"],
    )
    return {
        "repeated_sentences": repeated_sentences,
        "repeated_clauses": repeated_clauses,
        "repeated_figures": repeated_figures,
        "n_repeated_sentences": len(repeated_sentences),
        "n_repeated_clauses": len(repeated_clauses),
        "n_repeated_figures": len(repeated_figures),
    }


def takeaway(prose: str) -> str:
    ss = sentences(prose)
    return ss[0] if ss else ""


def cmd_compare(data: Path, corpus_name: str) -> None:
    d = out_dir(data, corpus_name)
    seq = json.loads((d / "sequential.json").read_text())
    par = json.loads((d / "parallel.json").read_text())
    reps = {
        "sequential": repetition(seq["blocks"]),
        "parallel": repetition(par["blocks"]),
    }

    lines = [
        f"# Check 7 — writing mode, {corpus_name}",
        "",
        CORPORA[corpus_name]["note"],
        "",
    ]
    lines += [
        "| | sequential | parallel |",
        "|---|---|---|",
        f"| wall clock total (s) | {seq['wall_s']} | {par['wall_s']} |",
        f"| slowest single section (s) | {max(seq['section_wall_s'].values())} "
        f"| {par['wall_s_slowest_section']} |",
        f"| generation calls | {sum(seq['call_counts'].values())} "
        f"| {sum(par['call_counts'].values())} |",
        f"| tokens (total) | {seq['summary']['usage_totals'].get('total')} "
        f"| {par['summary']['usage_totals'].get('total')} |",
        f"| repeated sentences | {reps['sequential']['n_repeated_sentences']} "
        f"| {reps['parallel']['n_repeated_sentences']} |",
        f"| repeated clauses (8-word runs) | {reps['sequential']['n_repeated_clauses']} "
        f"| {reps['parallel']['n_repeated_clauses']} |",
        f"| repeated figures | {reps['sequential']['n_repeated_figures']} "
        f"| {reps['parallel']['n_repeated_figures']} |",
        "",
        "## Per section",
        "",
        "| section | seq wall s | par wall s | seq claims | par claims | seq takeaway "
        "| par takeaway |",
        "|---|---|---|---|---|---|---|",
    ]
    seq_by_title = {b["title"]: b for b in seq["blocks"]}
    par_by_title = {b["title"]: b for b in par["blocks"]}
    for title in [*SECTION_TITLES, SOURCES_SECTION_TITLE]:
        sb, pb = seq_by_title.get(title), par_by_title.get(title)
        lines.append(
            f"| {title} "
            f"| {seq['section_wall_s'].get(title, '—')} "
            f"| {par['section_wall_s'].get(title, '—')} "
            f"| {sum((sb or {}).get('claim_counts_by_type', {}).values())} "
            f"| {sum((pb or {}).get('claim_counts_by_type', {}).values())} "
            f"| {takeaway((sb or {}).get('prose', ''))[:180]} "
            f"| {takeaway((pb or {}).get('prose', ''))[:180]} |"
        )
    for mode in ("sequential", "parallel"):
        lines += ["", f"## Repetition list — {mode}", ""]
        for r in reps[mode]["repeated_sentences"]:
            lines.append(f"- sentence in {', '.join(r['sections'])}: {r['text'][:240]}")
        for r in reps[mode]["repeated_clauses"]:
            lines.append(f"- clause in {', '.join(r['sections'])}: {r['text'][:240]}")
        for r in reps[mode]["repeated_figures"]:
            lines.append(f"- figure `{r['figure']}` in {', '.join(r['sections'])}")
        if not any(
            reps[mode][k]
            for k in ("repeated_sentences", "repeated_clauses", "repeated_figures")
        ):
            lines.append("- none")
    lines += ["", "No model judge: the two artefacts are read by the lead.", ""]
    (d / "compare.md").write_text("\n".join(lines), encoding="utf-8")
    save_json(d / "compare.json", reps)
    print("wrote", d / "compare.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sequential", "parallel", "compare"])
    ap.add_argument("corpus", choices=sorted(CORPORA))
    ap.add_argument("--data", required=True)
    ap.add_argument("--depth", choices=["standard", "rapid"], default="standard")
    a = ap.parse_args()
    global DEPTH
    DEPTH = a.depth
    data = Path(a.data)
    {"sequential": cmd_sequential, "parallel": cmd_parallel, "compare": cmd_compare}[
        a.cmd
    ](data, a.corpus)


if __name__ == "__main__":
    main()
