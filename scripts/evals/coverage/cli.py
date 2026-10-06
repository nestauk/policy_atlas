"""Commands for the coverage and prominence evaluator.

Five subcommands, run from the repository root with
``uv run --project backend [--env-file backend/.env] python scripts/evals/coverage/cli.py``
``<command>``:

* ``draft-reference``: ask a model to draft expected findings from ``review.md``
  (never from a generated report). The result is unapproved.
* ``approve``: a named human freezes ``reference.json`` with a content hash.
* ``export``: save a report from the local database (or a markdown file) as a
  run package with its Key findings boundaries.
* ``evaluate``: run the alignment judge over run packages and compute the
  coverage metrics. Writes JSON, CSV and Markdown under ``results/<label>/``.
* ``compare``: measure agreement between judge labels and human labels.

The pure logic (shapes, gates, parser, scoring, comparison) is in
``coverage_lib.py``; this file does the file, model and database work.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))

from coverage_lib import (  # noqa: E402
    KEY_FINDINGS_TITLE,
    METRICS,
    MIN_QUOTE_CHARS,
    NORMALISATION,
    AnnotationRow,
    Approval,
    DraftWire,
    Finding,
    Generation,
    Judgement,
    JudgeResponseWire,
    JudgeValidationError,
    Reference,
    RunPackage,
    RunScores,
    aggregate,
    approval_problems,
    cache_key,
    compare,
    condition_key,
    draft_to_reference,
    expected_pairs,
    find_key_findings,
    nfc,
    reference_content_hash,
    render_comparison_md,
    render_summary_md,
    rule_judgements_for_absent_section,
    run_package_problems,
    score_run,
    structural_problems,
    to_judgements,
    validate_response,
)

from policy_atlas.core import tracing  # noqa: E402
from policy_atlas.core.hashing import content_hash  # noqa: E402
from policy_atlas.core.openai_client import require_parsed, resolve_openai_client  # noqa: E402
from policy_atlas.core.usage import token_usage_from_provider, usage_details  # noqa: E402

HERE = Path(__file__).parent
ALIGN_PROMPT = HERE / "judges" / "align_findings.md"
DRAFT_PROMPT = HERE / "judges" / "draft_reference.md"
DEFAULT_CASES = HERE / "cases"
DEFAULT_RESULTS = HERE / "results"
DEFAULT_MAX_INPUT_CHARS = 600_000
OBSERVATION_NAME = "judge:coverage_alignment"


# --------------------------------------------------------------------------
# Prompt files and the model call
# --------------------------------------------------------------------------


def load_prompt_file(path: Path) -> tuple[dict[str, str], str]:
    """Split a judge file into its front-matter config and the prompt text.

    The file starts with a block between two ``---`` lines of ``key: value``
    pairs (``name``, ``version``, ``model``, optionally ``reasoning_effort``
    and ``max_completion_tokens``). Everything after is the prompt.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path.name} must start with a '---' front-matter block")
    _, front, body = text.split("---\n", 2)
    config: dict[str, str] = {}
    for line in front.strip().splitlines():
        key, _, value = line.partition(":")
        config[key.strip()] = value.strip()
    for key in ("name", "version", "model"):
        if not config.get(key):
            raise ValueError(f"{path.name}: front matter needs '{key}'")
    return config, body.strip()


def model_kwargs(config: dict[str, str]) -> dict[str, Any]:
    """Request settings from the front matter, in the shape ``parse`` takes."""
    kwargs: dict[str, Any] = {"model": config["model"]}
    if config.get("reasoning_effort"):
        kwargs["reasoning_effort"] = config["reasoning_effort"]
    if config.get("max_completion_tokens"):
        kwargs["max_completion_tokens"] = int(config["max_completion_tokens"])
    return kwargs


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _append_jsonl(path: Path | None, row: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


@contextlib.contextmanager
def _observation(
    langfuse: Any | None,
    *,
    kwargs: dict[str, Any],
    messages: list[dict[str, Any]],
    meta: dict[str, Any],
) -> Iterator[Any]:
    """A Langfuse generation around one model call, or nothing when offline."""
    if langfuse is None:
        yield None
        return
    params = {k: v for k, v in kwargs.items() if k != "model"}
    with langfuse.start_as_current_observation(
        name=OBSERVATION_NAME,
        as_type="generation",
        model=kwargs["model"],
        model_parameters=params or None,
        input=messages,
        metadata=meta,
    ) as generation:
        yield generation


def call_model(
    client: Any | None,
    *,
    messages: list[dict[str, Any]],
    kwargs: dict[str, Any],
    response_format: type[Any],
    cache_dir: Path,
    offline: bool,
    langfuse: Any | None = None,
    log_path: Path | None = None,
    meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str, bool]:
    """One structured-output call, served from the cache when possible.

    Returns:
        ``(reply, key, cached)``: the reply as a plain dict, the cache key for
        this request, and whether it came from the cache. The caller stores
        the reply with :func:`store_cache` only after it validates.

    Raises:
        RuntimeError: No cached reply in ``--offline`` mode, no client, or the
            model's reply was cut off (``finish_reason == "length"``).
    """
    key = cache_key(messages, kwargs, response_format.model_json_schema())
    path = cache_dir / f"{key}.json"
    log_meta = {**(meta or {}), "cache_key": key, "at": datetime.now(UTC).isoformat()}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        _append_jsonl(log_path, {**log_meta, "cached": True, "latency_s": 0.0, "tokens": None})
        return data["reply"], key, True
    if offline:
        raise RuntimeError(f"--offline: no cached reply for this request (key {key[:12]})")
    if client is None:
        raise RuntimeError("OPENAI_API_KEY is not set; use --env-file backend/.env or --offline")
    started = time.perf_counter()
    try:
        with _observation(
            langfuse, kwargs=kwargs, messages=messages, meta=meta or {}
        ) as generation:
            response = client.chat.completions.parse(
                messages=messages, response_format=response_format, **kwargs
            )
            choice = response.choices[0] if response.choices else None
            if getattr(choice, "finish_reason", None) == "length":
                raise RuntimeError(
                    "the model's reply was cut off (finish_reason=length): raise "
                    "max_completion_tokens in the judge file or lower --findings-per-call"
                )
            parsed = require_parsed(response, label=OBSERVATION_NAME)
            usage = token_usage_from_provider(getattr(response, "usage", None))
            if generation is not None:
                generation.update(output=parsed.model_dump(), usage_details=usage_details(usage))
    except Exception as exc:
        _append_jsonl(
            log_path,
            {
                **log_meta,
                "cached": False,
                "latency_s": time.perf_counter() - started,
                "error": str(exc),
            },
        )
        raise
    _append_jsonl(
        log_path,
        {
            **log_meta,
            "cached": False,
            "latency_s": round(time.perf_counter() - started, 3),
            "tokens": None
            if usage is None
            else {"prompt": usage.prompt, "completion": usage.completion},
        },
    )
    reply: dict[str, Any] = parsed.model_dump()
    return reply, key, False


def store_cache(cache_dir: Path, key: str, reply: dict[str, Any], meta: dict[str, Any]) -> None:
    """Keep a validated reply so the same request is never paid for twice."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps({"meta": meta, "reply": reply}, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# --------------------------------------------------------------------------
# The alignment judge for one run
# --------------------------------------------------------------------------


def compile_alignment_prompt(
    prompt_text: str, ref: Reference, findings: Sequence[Finding], package: RunPackage
) -> str:
    """Fill the alignment prompt for one batch of findings against one report."""
    kf = package.key_findings
    present = kf.status == "present"
    findings_json = json.dumps(
        [
            {
                "finding_id": f.finding_id,
                "finding_text": f.finding_text,
                "necessary_qualifications": f.necessary_qualifications,
                "source_excerpts": [s.excerpt for s in f.sources],
                "required_in_key_findings": present and bool(f.expected_in_key_findings),
            }
            for f in findings
        ],
        indent=2,
        ensure_ascii=False,
    )
    pairs = sorted(expected_pairs(findings, kf.status))
    required = "\n".join(f"- {fid} / {section}" for fid, section in pairs)
    if present and kf.start is not None:
        kf_text = package.report_text[kf.start : kf.end]
    else:
        kf_text = f"{kf.status.upper()}: {kf.reason} No key_findings judgements are required."
    return (
        prompt_text.replace("{{query}}", ref.query)
        .replace("{{findings}}", findings_json)
        .replace("{{report}}", package.report_text)
        .replace("{{key_findings}}", kf_text)
        .replace("{{required_pairs}}", required)
    )


def _batches(findings: Sequence[Finding], size: int | None) -> list[list[Finding]]:
    if not size or size >= len(findings):
        return [list(findings)]
    return [list(findings[i : i + size]) for i in range(0, len(findings), size)]


def judge_run(
    ref: Reference,
    package: RunPackage,
    *,
    prompt_text: str,
    config: dict[str, str],
    client: Any | None,
    cache_dir: Path,
    offline: bool,
    findings_per_call: int | None = None,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
    langfuse: Any | None = None,
    log_path: Path | None = None,
) -> list[Judgement]:
    """Judge every expected finding-section pair for one run.

    Raises:
        RuntimeError: The prompt does not fit ``max_input_chars`` or the
            model could not be called.
        JudgeValidationError: The reply was still invalid after one retry.
    """
    kwargs = model_kwargs(config)
    context = {
        "case_id": package.case_id,
        "run_id": package.run_id,
        "reference_version": ref.reference_version,
        "reference_hash": reference_content_hash(ref),
    }
    meta = {
        **context,
        "prompt_name": config["name"],
        "prompt_version": config["version"],
        "report_hash": content_hash(package.report_text),
    }
    kf = package.key_findings
    judgements: list[Judgement] = []
    if kf.status == "absent":
        judgements += rule_judgements_for_absent_section(ref.findings, context)

    for batch in _batches(ref.findings, findings_per_call):
        expected = expected_pairs(batch, kf.status)
        compiled = compile_alignment_prompt(prompt_text, ref, batch, package)
        if len(compiled) > max_input_chars:
            raise RuntimeError(
                f"prompt is {len(compiled):,} characters, over the {max_input_chars:,} limit; "
                "use --findings-per-call to send fewer findings per call (the full report is "
                "always included) or raise --max-input-chars"
            )
        messages: list[dict[str, Any]] = [{"role": "user", "content": compiled}]
        first_key: str | None = None
        for attempt in (1, 2):
            reply, key, cached = call_model(
                client,
                messages=messages,
                kwargs=kwargs,
                response_format=JudgeResponseWire,
                cache_dir=cache_dir,
                offline=offline,
                langfuse=langfuse,
                log_path=log_path,
                meta={**meta, "attempt": attempt, "batch_ids": [f.finding_id for f in batch]},
            )
            first_key = first_key or key
            try:
                located = validate_response(
                    JudgeResponseWire.model_validate(reply),
                    expected=expected,
                    report_text=package.report_text,
                    key_findings=kf,
                )
            except JudgeValidationError as exc:
                if cached:
                    (cache_dir / f"{key}.json").unlink(missing_ok=True)
                _append_jsonl(log_path, {**meta, "attempt": attempt, "invalid": exc.problems})
                if attempt == 2:
                    raise
                messages = messages + [
                    {"role": "assistant", "content": json.dumps(reply, ensure_ascii=False)},
                    {
                        "role": "user",
                        "content": "Your reply was rejected for these reasons:\n- "
                        + "\n- ".join(exc.problems)
                        + "\nReturn the complete corrected JSON. Quote the report verbatim.",
                    },
                ]
                continue
            if not cached:
                store_cache(cache_dir, first_key, reply, meta)
            judgements += to_judgements(located, batch, context)
            break

    got = {(j.finding_id, j.section) for j in judgements if j.source == "judge"}
    want = expected_pairs(ref.findings, kf.status)
    if got != want:
        raise JudgeValidationError(
            [
                "after batching, judged pairs differ from expected: "
                f"missing {sorted(want - got)}, extra {sorted(got - want)}"
            ]
        )
    return judgements


# --------------------------------------------------------------------------
# File helpers
# --------------------------------------------------------------------------


def load_reference(case_dir: Path) -> Reference:
    return Reference.model_validate_json((case_dir / "reference.json").read_text(encoding="utf-8"))


def save_reference(case_dir: Path, ref: Reference) -> None:
    (case_dir / "reference.json").write_text(
        json.dumps(ref.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_run_packages(
    cases_dir: Path, case_ids: Sequence[str], run_ids: Sequence[str]
) -> list[RunPackage]:
    """Every ``cases/<case>/runs/*.json``, filtered by the ids given (if any)."""
    packages: list[RunPackage] = []
    for path in sorted(cases_dir.glob("*/runs/*.json")):
        package = RunPackage.model_validate_json(path.read_text(encoding="utf-8"))
        if case_ids and package.case_id not in case_ids:
            continue
        if run_ids and package.run_id not in run_ids:
            continue
        packages.append(package)
    return packages


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def judgement_csv_row(j: Judgement) -> dict[str, Any]:
    return {
        **j.model_dump(exclude={"passages", "missing_or_changed_qualifications"}),
        "passages": " | ".join(p.quote for p in j.passages),
        "passage_offsets": ";".join(f"{p.start}-{p.end}" for p in j.passages),
        "missing_or_changed_qualifications": " | ".join(j.missing_or_changed_qualifications),
    }


JUDGEMENT_COLUMNS = [
    "case_id",
    "run_id",
    "reference_version",
    "reference_hash",
    "finding_id",
    "section",
    "label",
    "priority",
    "expected_in_key_findings",
    "source",
    "passages",
    "passage_offsets",
    "missing_or_changed_qualifications",
    "explanation",
]


def scores_csv_row(s: RunScores) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_id": s.case_id,
        "run_id": s.run_id,
        "reference_version": s.reference_version,
        "condition": s.condition,
        "key_findings_status": s.key_findings_status,
        "essential_absent_ids": ";".join(s.essential_absent_ids),
        "prominence_gap_ids": ";".join(s.prominence_gap_ids),
        "unresolved": ";".join(s.unresolved),
    }
    for name in METRICS:
        rate = getattr(s, name)
        row[name] = "" if rate.rate is None else f"{rate.rate:.4f}"
        row[f"{name}_numerator"] = "" if rate.numerator is None else rate.numerator
        row[f"{name}_denominator"] = rate.denominator
        row[f"{name}_reason"] = rate.reason or ""
    return row


SCORE_COLUMNS = (
    ["case_id", "run_id", "reference_version", "condition", "key_findings_status"]
    + [f"{m}{suffix}" for m in METRICS for suffix in ("", "_numerator", "_denominator", "_reason")]
    + ["essential_absent_ids", "prominence_gap_ids", "unresolved"]
)


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def looks_like_report(text: str) -> bool:
    """A rendered Policy Atlas report, which must never feed the drafter."""
    head = "\n".join(text.splitlines()[:8])
    return "**Question:**" in head or f"## {KEY_FINDINGS_TITLE}".casefold() in text.casefold()


def cmd_draft(args: argparse.Namespace, client: Any | None = None) -> int:
    case_dir: Path = args.case
    review_path = case_dir / "review.md"
    target = case_dir / "reference.json"
    if target.exists() and not args.force:
        print(f"{target} exists; pass --force to overwrite the draft (never an approved file)")
        return 2
    if target.exists():
        existing = load_reference(case_dir)
        if existing.approval.status == "approved":
            print(f"{target} is approved; refusing to overwrite. Bump the version by hand.")
            return 2
    review = review_path.read_text(encoding="utf-8")
    if looks_like_report(review):
        print(f"{review_path} looks like a generated Policy Atlas report, not a review. Refusing.")
        return 2
    config, text = load_prompt_file(args.prompt_file)
    compiled = text.replace("{{query}}", args.query).replace("{{review}}", review)
    if args.dry_run:
        print(compiled)
        return 0
    if client is None and os.environ.get("OPENAI_API_KEY"):
        client = resolve_openai_client(
            None, backend_name="draft-reference", timeout=300.0, max_retries=2
        )
    reply, key, _ = call_model(
        client,
        messages=[{"role": "user", "content": compiled}],
        kwargs=model_kwargs(config),
        response_format=DraftWire,
        cache_dir=args.cache_dir,
        offline=False,
        langfuse=tracing.get_langfuse(),
        meta={
            "prompt_name": config["name"],
            "prompt_version": config["version"],
            "case_id": case_dir.name,
        },
    )
    ref, warnings = draft_to_reference(
        DraftWire.model_validate(reply),
        case_id=case_dir.name,
        query=args.query,
        review_citation=args.citation,
        review_text=review,
    )
    store_cache(
        args.cache_dir, key, reply, {"prompt_name": config["name"], "case_id": case_dir.name}
    )
    save_reference(case_dir, ref)
    print(f"wrote {target}: {len(ref.findings)} draft finding(s), status draft")
    for w in warnings:
        print(f"  WARNING {w}")
    print(
        "Next: review every finding, set priority and expected_in_key_findings, then run approve."
    )
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    case_dir: Path = args.case
    ref = load_reference(case_dir)
    review_path = case_dir / "review.md"
    review = review_path.read_text(encoding="utf-8") if review_path.exists() else None
    if review is None:
        print(f"WARNING {review_path} not found; excerpts cannot be checked")
    problems = structural_problems(ref, review)
    if ref.reference_version == "draft":
        problems.append("reference_version is still 'draft'; set a real version such as v1")
    if problems:
        print("cannot approve:")
        for p in problems:
            print(f"  - {p}")
        return 1
    ref.approval = Approval(
        status="approved",
        reviewer=args.reviewer,
        approved_at=datetime.now(UTC).isoformat(timespec="seconds"),
        content_hash=reference_content_hash(ref),
    )
    save_reference(case_dir, ref)
    print(
        f"approved {ref.case_id} {ref.reference_version} by {args.reviewer}: "
        f"{ref.approval.content_hash[:12]}"
    )
    return 0


def render_report(artefact: Any) -> str:
    """Render a report read model as plain markdown (same shape as the app shows)."""
    lines = [f"# {artefact.title}", "", f"**Question:** {artefact.question}", ""]
    if artefact.full_report_intro:
        lines += [artefact.full_report_intro.strip(), ""]
    for section in artefact.sections:
        lines += [f"## {section.title}", ""]
        for block in section.blocks:
            lines += [block.prose.strip(), ""]
        for card in section.cards:
            lines += [f"### {card.title}", "", card.prose.strip(), ""]
    if artefact.references:
        lines += ["## References", ""]
        for ref in artefact.references:
            bits = [ref.title]
            if ref.year:
                bits.append(f"({ref.year})")
            if ref.venue:
                bits.append(ref.venue)
            if ref.url:
                bits.append(ref.url)
            lines.append(f"{ref.n}. {' '.join(bits)}")
    return "\n".join(lines).rstrip() + "\n"


def package_from_text(
    text: str,
    *,
    case_id: str,
    run_id: str,
    reference_version: str,
    expected_key_findings: bool | None,
    key_findings_title: str = KEY_FINDINGS_TITLE,
    generation: Generation,
) -> RunPackage:
    """Build a run package from report text, locating the Key findings section."""
    text = nfc(text)
    span = find_key_findings(text, expected=expected_key_findings, title=key_findings_title)
    return RunPackage(
        case_id=case_id,
        run_id=run_id,
        reference_version=reference_version,
        report_text=text,
        key_findings=span,
        generation=generation,
    )


def _save_package(cases_dir: Path, package: RunPackage) -> Path:
    path = cases_dir / package.case_id / "runs" / f"{package.run_id}.json"
    write_json(path, package.model_dump(mode="json"))
    return path


def cmd_export(
    args: argparse.Namespace, artefact_loader: Callable[[str], Any] | None = None
) -> int:
    cases_dir: Path = args.cases
    commit = _git_commit()

    def generation(row: dict[str, str]) -> Generation:
        return Generation(
            depth=row.get("depth", ""),
            git_commit=commit,
            date_filter=args.date_filter,
            reference_review_excluded=args.reference_review_excluded,
            condition=row.get("condition", ""),
            extra={
                k: v for k, v in row.items() if k not in ("case_id", "run_id", "depth", "condition")
            },
        )

    if args.report_file:
        ref = load_reference(cases_dir / args.case_id)
        package = package_from_text(
            args.report_file.read_text(encoding="utf-8"),
            case_id=args.case_id,
            run_id=args.run_id or args.report_file.stem,
            reference_version=ref.reference_version,
            expected_key_findings=False if args.no_key_findings else None,
            generation=generation({"depth": args.depth, "condition": args.condition}),
        )
        path = _save_package(cases_dir, package)
        print(
            f"wrote {path}: key findings {package.key_findings.status} "
            f"{package.key_findings.reason}"
        )
        return 0

    with args.runs.open(newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if (r.get("task_id") or "").strip()]
    if artefact_loader is None:
        from policy_atlas.api.readmodels.repository import artefact_out
        from policy_atlas.core.db import get_engine

        engine = get_engine()

        def artefact_loader(task_id: str) -> Any:
            with engine.connect() as conn:
                return artefact_out(conn, uuid.UUID(task_id))

    for row in rows:
        case_id, task_id = row["case_id"].strip(), row["task_id"].strip()
        ref = load_reference(cases_dir / case_id)
        artefact = artefact_loader(task_id)
        if artefact is None:
            print(f"  SKIPPED {task_id}: no report in the database")
            continue
        kf_section = next((s for s in artefact.sections if s.role == "key_findings"), None)
        package = package_from_text(
            render_report(artefact),
            case_id=case_id,
            run_id=(row.get("run_id") or "").strip() or task_id,
            reference_version=ref.reference_version,
            expected_key_findings=kf_section is not None,
            key_findings_title=kf_section.title if kf_section else KEY_FINDINGS_TITLE,
            generation=generation({**row, "task_id": task_id, "question": artefact.question}),
        )
        path = _save_package(cases_dir, package)
        print(
            f"  wrote {path}: key findings {package.key_findings.status} "
            f"{package.key_findings.reason}"
        )
    return 0


def cmd_evaluate(
    args: argparse.Namespace, client: Any | None = None, langfuse: Any | None = None
) -> int:
    config, prompt_text = load_prompt_file(args.prompt_file)
    packages = load_run_packages(args.cases, args.case, args.run)
    if not packages:
        print(f"no run packages found under {args.cases}/*/runs/")
        return 1
    label = args.label or f"{date.today().isoformat()}-{_git_commit()[:7]}"
    out_dir: Path = args.results / label
    log_path = out_dir / "calls.jsonl"
    meta = {
        "label": label,
        "prompt_name": config["name"],
        "prompt_version": config["version"],
        "model": model_kwargs(config),
        "git_commit": _git_commit(),
        "normalisation": NORMALISATION,
        "min_quote_chars": MIN_QUOTE_CHARS,
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    references: dict[str, Reference] = {}
    judgements: list[Judgement] = []
    scores: list[RunScores] = []
    failed: list[dict[str, str]] = []
    if (
        not args.dry_run
        and not args.offline
        and client is None
        and os.environ.get("OPENAI_API_KEY")
    ):
        client = resolve_openai_client(
            None, backend_name="coverage evaluate", timeout=300.0, max_retries=2
        )
    if langfuse is None and not args.dry_run:
        langfuse = tracing.get_langfuse()

    for package in packages:
        tag = f"{package.case_id}/{package.run_id}"
        try:
            ref = references.get(package.case_id)
            if ref is None:
                ref = load_reference(args.cases / package.case_id)
                problems = approval_problems(ref)
                if problems:
                    raise RuntimeError("; ".join(problems))
                references[package.case_id] = ref
            if package.reference_version != ref.reference_version:
                raise RuntimeError(
                    f"run package is for reference {package.reference_version} but the approved "
                    f"reference is {ref.reference_version}; re-export the run"
                )
            problems = run_package_problems(package)
            if problems:
                raise RuntimeError("; ".join(problems))
            if args.dry_run:
                compiled = compile_alignment_prompt(prompt_text, ref, ref.findings, package)
                pairs = expected_pairs(ref.findings, package.key_findings.status)
                print(
                    f"--- {tag}: {len(compiled):,} chars, {len(pairs)} pair(s), "
                    f"key findings {package.key_findings.status} ---"
                )
                if package is packages[0]:
                    print(compiled)
                continue
            run_judgements = judge_run(
                ref,
                package,
                prompt_text=prompt_text,
                config=config,
                client=client,
                cache_dir=args.cache_dir,
                offline=args.offline,
                findings_per_call=args.findings_per_call,
                max_input_chars=args.max_input_chars,
                langfuse=langfuse,
                log_path=log_path,
            )
            run_scores = score_run(
                ref, run_judgements, package.key_findings, condition=condition_key(package)
            )
            judgements += run_judgements
            scores.append(run_scores)
            print(
                f"  {tag}: full {_frac(run_scores.full_report_coverage)}"
                f"  essential {_frac(run_scores.essential_full_report_coverage)}"
                f"  key findings {_frac(run_scores.key_findings_coverage)}"
                f" ({package.key_findings.status})"
            )
        except (RuntimeError, JudgeValidationError, ValueError, OSError) as exc:
            failed.append({"case_id": package.case_id, "run_id": package.run_id, "error": str(exc)})
            print(f"  FAILED {tag}: {exc}")
    if args.dry_run:
        print(f"\nDry run: {len(packages)} run package(s); no model calls, no files written.")
        return 0

    summary = aggregate(scores, failed)
    write_json(
        out_dir / "judgements.json",
        {"meta": meta, "judgements": [j.model_dump(mode="json") for j in judgements]},
    )
    write_csv(
        out_dir / "judgements.csv", [judgement_csv_row(j) for j in judgements], JUDGEMENT_COLUMNS
    )
    write_json(
        out_dir / "scores.json",
        {
            "meta": meta,
            "runs": [s.model_dump(mode="json") for s in scores],
            "summary": summary.model_dump(mode="json"),
        },
    )
    write_csv(out_dir / "scores.csv", [scores_csv_row(s) for s in scores], SCORE_COLUMNS)
    (out_dir / "summary.md").write_text(render_summary_md(scores, summary), encoding="utf-8")
    if langfuse is not None:
        tracing.flush(langfuse)
    print(f"\n{len(scores)} run(s) scored, {len(failed)} failed -> {out_dir}")
    return 1 if failed and not scores else 0


def _frac(rate: Any) -> str:
    return f"{rate.numerator}/{rate.denominator}"


def load_annotations(paths: Sequence[Path]) -> list[AnnotationRow]:
    rows: list[AnnotationRow] = []
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            for index, raw in enumerate(csv.DictReader(handle), start=2):
                try:
                    rows.append(
                        AnnotationRow.model_validate(
                            {k: v for k, v in raw.items() if v is not None}
                        )
                    )
                except ValueError as exc:
                    raise ValueError(f"{path.name} line {index}: {exc}") from exc
    return rows


def cmd_compare(args: argparse.Namespace) -> int:
    payload = json.loads(args.judgements.read_text(encoding="utf-8"))
    judgements = [Judgement.model_validate(j) for j in payload["judgements"]]
    annotations = load_annotations(args.annotations)
    result = compare(judgements, annotations)
    out_dir: Path = args.out or args.judgements.parent
    write_json(out_dir / "comparison.json", result)
    matrix_rows = [
        {
            "section": section,
            "human_label": pair.split("->")[0],
            "judge_label": pair.split("->")[1],
            "count": n,
        }
        for section, s in result["sections"].items()
        for pair, n in s["confusion"].items()
    ]
    write_csv(
        out_dir / "comparison.csv", matrix_rows, ["section", "human_label", "judge_label", "count"]
    )
    md = render_comparison_md(result)
    (out_dir / "comparison.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


# --------------------------------------------------------------------------
# Argument parsing
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "draft-reference", help="LLM draft of expected findings from review.md (unapproved)."
    )
    p.add_argument(
        "--case", type=Path, required=True, help="cases/<case_id> directory holding review.md"
    )
    p.add_argument("--query", required=True, help="The research question the reference answers.")
    p.add_argument("--citation", default="", help="How to cite the review.")
    p.add_argument("--prompt-file", type=Path, default=DRAFT_PROMPT)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_RESULTS / "cache")
    p.add_argument(
        "--force", action="store_true", help="Overwrite an existing draft (never an approved file)."
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Print the compiled prompt; call nothing."
    )
    p.set_defaults(func=cmd_draft)

    p = sub.add_parser(
        "approve", help="Freeze reference.json with a content hash, as a named human."
    )
    p.add_argument("--case", type=Path, required=True)
    p.add_argument("--reviewer", required=True, help="Your name; recorded in the approval block.")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("export", help="Save reports as run packages with Key findings boundaries.")
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    p.add_argument(
        "--runs", type=Path, help="CSV with case_id, task_id and optional run_id, depth, condition."
    )
    p.add_argument(
        "--report-file", type=Path, help="Import one markdown report instead of the database."
    )
    p.add_argument("--case-id", help="With --report-file: the case the report answers.")
    p.add_argument("--run-id", help="With --report-file: run id (default: the file name).")
    p.add_argument(
        "--no-key-findings",
        action="store_true",
        help="With --report-file: the report truly has no Key findings section.",
    )
    p.add_argument("--depth", default="")
    p.add_argument(
        "--condition", default="", help="Free label for a control arm, kept separate in summaries."
    )
    p.add_argument(
        "--date-filter", choices=["enforced", "not_enforced", "unknown"], default="unknown"
    )
    p.add_argument(
        "--reference-review-excluded",
        choices=["enforced", "not_enforced", "unknown"],
        default="unknown",
    )
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("evaluate", help="Run the alignment judge and compute coverage metrics.")
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    p.add_argument("--case", action="append", default=[], help="Only this case id (repeatable).")
    p.add_argument("--run", action="append", default=[], help="Only this run id (repeatable).")
    p.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    p.add_argument("--label", help="Output folder name under results/ (default: date and commit).")
    p.add_argument("--prompt-file", type=Path, default=ALIGN_PROMPT)
    p.add_argument("--cache-dir", type=Path, default=DEFAULT_RESULTS / "cache")
    p.add_argument(
        "--offline", action="store_true", help="Use cached replies only; fail on a cache miss."
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the compiled prompt for the first run; call nothing.",
    )
    p.add_argument(
        "--findings-per-call",
        type=int,
        default=None,
        help="Batch the findings; the full report goes with every batch.",
    )
    p.add_argument("--max-input-chars", type=int, default=DEFAULT_MAX_INPUT_CHARS)
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("compare", help="Agreement between judge labels and human labels.")
    p.add_argument("--judgements", type=Path, required=True, help="results/<label>/judgements.json")
    p.add_argument(
        "--annotations",
        type=Path,
        nargs="+",
        required=True,
        help="Human CSV file(s); include an adjudicated file if you have one.",
    )
    p.add_argument("--out", type=Path, help="Output folder (default: next to judgements.json).")
    p.set_defaults(func=cmd_compare)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export" and not (args.runs or args.report_file):
        build_parser().error("export needs --runs CSV or --report-file PATH")
    if args.command == "export" and args.report_file and not args.case_id:
        build_parser().error("--report-file needs --case-id")
    if args.command == "evaluate":
        os.environ.setdefault("LANGFUSE_RELEASE", _git_commit())
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    sys.exit(main())
