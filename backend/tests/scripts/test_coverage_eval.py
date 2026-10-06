"""Mocked tests for the coverage and prominence evaluator (`scripts/evals/coverage/`).

Nothing here touches the network or the database. The judge is a recorded
fake, so these tests prove the plumbing (gates, parsing, validation, scoring,
comparison), not the judge's reliability.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from policy_atlas.evidence_search.synthesis import grounding_judge
from tests.helpers import FakeChoice, FakeParsedMessage, FakeParseResponse, fake_parse_client

_ROOT = Path(__file__).resolve().parents[3] / "scripts" / "evals" / "coverage"


def _load() -> tuple[ModuleType, ModuleType]:
    spec = importlib.util.spec_from_file_location("coverage_cli", _ROOT / "cli.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["coverage_cli"] = module
    spec.loader.exec_module(module)
    return module, sys.modules["coverage_lib"]


cli, lib = _load()

QUERY = "Does X improve Y?"
REVIEW = (
    "[P01] In twelve trials, X improved Y by about 3 points (moderate certainty).\n"
    "[P02] The effect was absent in adults over 65 (low certainty).\n"
    "[P03] No trial followed people beyond one year.\n"
)

REPORT = (
    "# Report\n\n**Question:** Does X improve Y?\n\n"
    "## Key findings\n\n"
    "- X raises Y by roughly three points, with moderate certainty, "
    "and this held across the twelve trials.\n"
    "- The gain disappears in adults over 65.\n\n"
    "## Evidence\n\n"
    "Across the twelve trials X improved Y by about 3 points with moderate certainty, "
    "while no effect was seen in adults over 65 (low certainty).\n\n"
    "## Limitations\n\n"
    "No trial followed participants beyond one year, so persistence is unknown.\n\n"
    "## Something else entirely\n\n"
    "The report also discusses the price of tea, which is not in the checklist.\n"
)


def _finding(
    fid: str, text: str, excerpt: str, *, essential: bool, kf: bool, quals: list[str] | None = None
) -> Any:
    return lib.Finding(
        finding_id=fid,
        finding_text=text,
        necessary_qualifications=quals or [],
        sources=[lib.SourcePassage(passage_id="P01", excerpt=excerpt)],
        priority="essential" if essential else "supporting",
        priority_rationale="r",
        expected_in_key_findings=kf,
        key_findings_rationale="r",
    )


def _findings() -> list[Any]:
    return [
        _finding(
            "F1",
            "X improves Y by about 3 points.",
            "X improved Y by about 3 points",
            essential=True,
            kf=True,
            quals=["moderate certainty"],
        ),
        _finding(
            "F2",
            "No effect in adults over 65.",
            "The effect was absent in adults over 65",
            essential=True,
            kf=True,
            quals=["low certainty"],
        ),
        _finding(
            "F3",
            "No trial followed people beyond one year.",
            "No trial followed people beyond one year",
            essential=False,
            kf=False,
        ),
    ]


def _reference(findings: list[Any] | None = None, *, approved: bool = True) -> Any:
    ref = lib.Reference(
        case_id="case1",
        review_citation="Synthetic",
        query=QUERY,
        reference_version="v1",
        findings=findings if findings is not None else _findings(),
    )
    if approved:
        ref.approval = lib.Approval(
            status="approved", reviewer="t", content_hash=lib.reference_content_hash(ref)
        )
    return ref


def _package(report: str = REPORT, *, expected: bool | None = True, run_id: str = "r1") -> Any:
    return cli.package_from_text(
        report,
        case_id="case1",
        run_id=run_id,
        reference_version="v1",
        expected_key_findings=expected,
        generation=lib.Generation(),
    )


def _j(
    fid: str,
    section: str,
    label: str,
    quotes: list[str] | None = None,
    missing: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "finding_id": fid,
        "section": section,
        "label": label,
        "passages": [{"quote": q} for q in (quotes or [])],
        "missing_or_changed_qualifications": missing or [],
        "explanation": "because",
    }


def _wire(*rows: dict[str, Any]) -> Any:
    return lib.JudgeResponseWire.model_validate({"judgements": list(rows)})


KF_F1 = "X raises Y by roughly three points, with moderate certainty"
KF_F2 = "The gain disappears in adults over 65."
BODY_F1 = "X improved Y by about 3 points with moderate certainty"
BODY_F2 = "no effect was seen in adults over 65 (low certainty)"
BODY_F3 = "No trial followed participants beyond one year, so persistence is unknown"

GOOD = [
    _j("F1", "full_report", "adequate", [BODY_F1]),
    _j("F1", "key_findings", "adequate", [KF_F1]),
    _j("F2", "full_report", "adequate", [BODY_F2]),
    _j("F2", "key_findings", "partial", [KF_F2], ["low certainty"]),
    _j("F3", "full_report", "adequate", [BODY_F3]),
]


def _score(rows: list[dict[str, Any]], ref: Any | None = None, package: Any | None = None) -> Any:
    ref = ref or _reference()
    package = package or _package()
    located = lib.validate_response(
        _wire(*rows),
        expected=lib.expected_pairs(ref.findings, package.key_findings.status),
        report_text=package.report_text,
        key_findings=package.key_findings,
    )
    context = {"case_id": "case1", "run_id": "r1", "reference_version": "v1", "reference_hash": "h"}
    judgements = lib.to_judgements(located, ref.findings, context)
    if package.key_findings.status == "absent":
        judgements += lib.rule_judgements_for_absent_section(ref.findings, context)
    return lib.score_run(ref, judgements, package.key_findings, condition="c")


# --------------------------------------------------------------------------
# Reference gates
# --------------------------------------------------------------------------


def test_unapproved_reference_is_rejected() -> None:
    assert lib.approval_problems(_reference(approved=False)) == [
        "reference is not approved (approval.status is not 'approved')"
    ]


def test_changed_reference_is_rejected() -> None:
    ref = _reference()
    assert lib.approval_problems(ref) == []
    ref.findings[0].finding_text = "edited after approval"
    problems = lib.approval_problems(ref)
    assert len(problems) == 1 and "changed since approval" in problems[0]


def test_hash_ignores_key_order_and_approval_block() -> None:
    ref = _reference()
    reordered = lib.Reference.model_validate(
        json.loads(json.dumps(ref.model_dump(mode="json"), sort_keys=True))
    )
    reordered.approval = lib.Approval()
    assert lib.reference_content_hash(reordered) == lib.reference_content_hash(ref)


def test_structural_problems_catch_unfilled_fields_and_bad_excerpts() -> None:
    findings = _findings()
    findings[0].priority = None
    findings[1].expected_in_key_findings = None
    findings[2].sources[0].excerpt = "this sentence is not in the review at all"
    findings.append(
        _finding("F1", "dup", "X improved Y by about 3 points", essential=True, kf=False)
    )
    problems = lib.structural_problems(
        lib.Reference(
            case_id="c", review_citation="s", query=QUERY, reference_version="v1", findings=findings
        ),
        REVIEW,
    )
    assert any("duplicate finding ids" in p for p in problems)
    assert any(p.startswith("F1: priority not set") for p in problems)
    assert any(p.startswith("F2: expected_in_key_findings not set") for p in problems)
    assert any(p.startswith("F3: excerpt not found") for p in problems)


# --------------------------------------------------------------------------
# Key findings section parsing
# --------------------------------------------------------------------------


def test_section_present_from_heading() -> None:
    span = lib.find_key_findings(REPORT, expected=True)
    assert span.status == "present"
    assert REPORT[span.start : span.end].startswith("## Key findings")
    assert "## Evidence" not in REPORT[span.start : span.end]


def test_section_absent_only_when_database_confirms() -> None:
    text = REPORT.replace("## Key findings", "## Summary")
    assert lib.find_key_findings(text, expected=False).status == "absent"
    assert lib.find_key_findings(text, expected=None).status == "unresolved"
    assert lib.find_key_findings(text, expected=True).status == "unresolved"


def test_ambiguous_boundary_is_unresolved_not_absent() -> None:
    text = REPORT + "\n## Key findings\n\nA second heading.\n"
    span = lib.find_key_findings(text, expected=True)
    assert span.status == "unresolved" and "2 headings" in span.reason


def test_heading_present_but_database_says_none_is_unresolved() -> None:
    assert lib.find_key_findings(REPORT, expected=False).status == "unresolved"


# --------------------------------------------------------------------------
# Expected pairs and validation
# --------------------------------------------------------------------------


def test_non_designated_findings_never_enter_key_findings() -> None:
    pairs = lib.expected_pairs(_findings(), "present")
    assert ("F3", "key_findings") not in pairs
    assert pairs == {
        ("F1", "full_report"),
        ("F2", "full_report"),
        ("F3", "full_report"),
        ("F1", "key_findings"),
        ("F2", "key_findings"),
    }
    assert lib.expected_pairs(_findings(), "absent") == {
        ("F1", "full_report"),
        ("F2", "full_report"),
        ("F3", "full_report"),
    }
    assert lib.expected_pairs(_findings(), "unresolved") == lib.expected_pairs(
        _findings(), "absent"
    )


def _problems(rows: list[dict[str, Any]], package: Any | None = None) -> list[str]:
    package = package or _package()
    with pytest.raises(lib.JudgeValidationError) as exc:
        lib.validate_response(
            _wire(*rows),
            expected=lib.expected_pairs(_findings(), package.key_findings.status),
            report_text=package.report_text,
            key_findings=package.key_findings,
        )
    problems: list[str] = exc.value.problems
    return problems


def test_duplicate_and_missing_pairs_are_rejected() -> None:
    problems = _problems(GOOD[:1] + GOOD[:1])
    assert any("duplicate pairs" in p for p in problems)
    assert any("missing pairs" in p for p in problems)


def test_unexpected_pair_is_rejected() -> None:
    extra = _j("F3", "key_findings", "absent")
    assert any("unexpected pairs" in p for p in _problems(GOOD + [extra]))


def test_absent_with_passage_and_adequate_without_passage_are_rejected() -> None:
    rows = [dict(r) for r in GOOD]
    rows[0] = _j("F1", "full_report", "adequate")
    rows[4] = _j("F3", "full_report", "absent", [BODY_F3])
    problems = _problems(rows)
    assert any("needs at least one passage" in p for p in problems)
    assert any("must not carry passages" in p for p in problems)


def test_short_and_invented_quotes_are_rejected() -> None:
    rows = [dict(r) for r in GOOD]
    rows[0] = _j("F1", "full_report", "adequate", ["X improved Y"])
    rows[2] = _j("F2", "full_report", "adequate", ["this sentence was never written in the report"])
    problems = _problems(rows)
    assert any("shorter than" in p for p in problems)
    assert any("not found in the report" in p for p in problems)


def test_key_findings_quote_must_sit_inside_the_section() -> None:
    rows = [dict(r) for r in GOOD]
    rows[1] = _j(
        "F1", "key_findings", "adequate", [BODY_F1]
    )  # true in the body, not in the summary
    assert any("not inside the Key findings section" in p for p in _problems(rows))


def test_quotes_match_after_documented_normalisation_only() -> None:
    package = _package()
    curly = "X raises Y by roughly three points,  with moderate certainty"  # double space
    rows = [dict(r) for r in GOOD]
    rows[1] = _j("F1", "key_findings", "adequate", [curly])
    located = lib.validate_response(
        _wire(*rows),
        expected=lib.expected_pairs(_findings(), "present"),
        report_text=package.report_text,
        key_findings=package.key_findings,
    )
    passage = located[1][1][0]
    assert (
        passage.match == "normalised" and package.report_text[passage.start : passage.end] == KF_F1
    )
    # Negation is never folded away.
    rows[1] = _j(
        "F1",
        "key_findings",
        "adequate",
        ["X raises Y by roughly three points, without moderate certainty"],
    )
    assert any("not inside" in p for p in _problems(rows))


# --------------------------------------------------------------------------
# Scoring scenarios
# --------------------------------------------------------------------------


def test_faithful_paraphrase_and_combined_findings_score_full_credit() -> None:
    rows = [dict(r) for r in GOOD]
    rows[3] = _j("F2", "key_findings", "adequate", [KF_F2])
    s = _score(rows)
    assert (s.full_report_coverage.numerator, s.full_report_coverage.denominator) == (3, 3)
    assert s.essential_full_report_coverage.rate == 1.0
    assert s.key_findings_coverage.rate == 1.0
    assert s.prominence_gap_ids == [] and s.essential_absent_ids == [] and s.unresolved == []


def test_qualification_lost_in_key_findings_is_a_prominence_gap() -> None:
    s = _score(GOOD)
    assert s.full_report_coverage.rate == 1.0
    assert (s.key_findings_coverage.numerator, s.key_findings_coverage.denominator) == (1, 2)
    assert s.prominence_gap_ids == ["F2"]
    assert s.key_findings_coverage.label_counts["partial"] == 1


def test_essential_finding_entirely_absent() -> None:
    rows = [dict(r) for r in GOOD]
    rows[2] = _j("F2", "full_report", "absent")
    rows[3] = _j("F2", "key_findings", "absent")
    s = _score(rows)
    assert s.essential_absent_ids == ["F2"]
    assert s.essential_full_report_coverage.rate == 0.5
    assert s.prominence_gap_ids == []  # absent everywhere is an omission, not a prominence gap


def test_present_in_body_but_absent_from_key_findings() -> None:
    rows = [dict(r) for r in GOOD]
    rows[3] = _j("F2", "key_findings", "absent")
    s = _score(rows)
    assert s.prominence_gap_ids == ["F2"] and s.key_findings_coverage.rate == 0.5


def test_partial_and_misrepresented_stay_separate_and_earn_nothing() -> None:
    rows = [dict(r) for r in GOOD]
    rows[0] = _j("F1", "full_report", "partial", [BODY_F1])
    rows[2] = _j("F2", "full_report", "misrepresented", [BODY_F2])
    s = _score(rows)
    counts = s.full_report_coverage.label_counts
    assert counts == {"adequate": 1, "partial": 1, "absent": 0, "misrepresented": 1, "uncertain": 0}
    assert s.full_report_coverage.rate == pytest.approx(1 / 3)
    assert s.full_report_coverage.denominator == 3


def test_conflicting_representations_carry_both_passages() -> None:
    conflict = REPORT.replace(
        "## Limitations",
        "## Also\n\nElsewhere the report claims X lowers Y by 3 points in every trial."
        "\n\n## Limitations",
    )
    package = _package(conflict)
    rows = [dict(r) for r in GOOD]
    rows[0] = _j(
        "F1", "full_report", "misrepresented", [BODY_F1, "X lowers Y by 3 points in every trial"]
    )
    located = lib.validate_response(
        _wire(*rows),
        expected=lib.expected_pairs(_findings(), "present"),
        report_text=package.report_text,
        key_findings=package.key_findings,
    )
    assert len(located[0][1]) == 2
    assert _score(rows, package=package).full_report_coverage.label_counts["misrepresented"] == 1


def test_uncertain_stays_in_denominator_and_is_listed_as_unresolved() -> None:
    rows = [dict(r) for r in GOOD]
    rows[3] = _j("F2", "key_findings", "uncertain", [KF_F2])
    s = _score(rows)
    assert s.key_findings_coverage.denominator == 2 and s.key_findings_coverage.numerator == 1
    assert s.unresolved == ["F2:key_findings"] and s.prominence_gap_ids == []


def test_no_required_key_findings_gives_null_not_100_percent() -> None:
    findings = [
        _finding("F3", "t", "No trial followed people beyond one year", essential=False, kf=False)
    ]
    ref = _reference(findings)
    s = _score([_j("F3", "full_report", "adequate", [BODY_F3])], ref=ref)
    assert s.key_findings_coverage.rate is None and s.key_findings_coverage.numerator is None
    assert s.key_findings_coverage.reason == "no findings are required in Key findings"
    assert s.essential_full_report_coverage.rate is None
    assert s.essential_full_report_coverage.reason == "denominator is zero"


def test_absent_section_scores_zero_by_rule() -> None:
    package = _package(REPORT.replace("## Key findings", "## Summary"), expected=False)
    assert package.key_findings.status == "absent"
    rows = [GOOD[0], GOOD[2], GOOD[4]]
    s = _score(rows, package=package)
    assert (
        s.key_findings_coverage.numerator,
        s.key_findings_coverage.denominator,
        s.key_findings_coverage.rate,
    ) == (0, 2, 0.0)
    assert s.prominence_gap_ids == ["F1", "F2"]


def test_unresolved_section_blocks_prominence_scoring_visibly() -> None:
    package = _package(REPORT + "\n## Key findings\n\nagain\n", expected=True)
    assert package.key_findings.status == "unresolved"
    s = _score([GOOD[0], GOOD[2], GOOD[4]], package=package)
    assert s.key_findings_coverage.rate is None and "unresolved" in (
        s.key_findings_coverage.reason or ""
    )
    assert s.full_report_coverage.rate == 1.0
    assert "unresolved" in lib.render_summary_md([s], lib.aggregate([s], []))


def test_extra_report_content_is_never_audited() -> None:
    # The report's tea-price paragraph is outside the checklist: no pair exists for it,
    # and a judge that returns one is rejected rather than scored.
    assert all(fid in {"F1", "F2", "F3"} for fid, _ in lib.expected_pairs(_findings(), "present"))
    assert any(
        "unexpected pairs" in p for p in _problems(GOOD + [_j("TEA", "full_report", "absent")])
    )


def test_aggregate_weights_reviews_equally_and_reports_nulls() -> None:
    a1 = _score(GOOD)
    rows = [dict(r) for r in GOOD]
    rows[0] = _j("F1", "full_report", "absent")
    rows[1] = _j("F1", "key_findings", "absent")
    a2 = _score(rows)
    b = _score(GOOD).model_copy(update={"case_id": "case2"})
    summary = lib.aggregate([a1, a2, b], [{"case_id": "case2", "run_id": "x", "error": "boom"}])
    case_a = next(c for c in summary.cases if c.case_id == "case1")
    assert case_a.n_runs == 2 and case_a.metrics["full_report_coverage"].mean == pytest.approx(
        (1 + 2 / 3) / 2
    )
    group = summary.groups[0]
    assert group.cases == ["case1", "case2"] and group.n_failed_runs == 1
    assert group.metrics["full_report_coverage"].mean == pytest.approx(((1 + 2 / 3) / 2 + 1) / 2)
    md = lib.render_summary_md([a1, a2, b], summary)
    assert "boom" in md and "| " not in summary.groups[0].group


# --------------------------------------------------------------------------
# The judge call: retries, truncation, cache, and the grounding judge is never touched
# --------------------------------------------------------------------------


@dataclass
class _Choice(FakeChoice):
    finish_reason: str | None = None


class _SeqClient:
    """A fake OpenAI client that returns a different reply on each call."""

    def __init__(self, replies: list[Any]) -> None:
        self._replies = list(replies)
        self.calls: list[dict[str, Any]] = []
        self.chat = self
        self.completions = self

    def parse(self, **kwargs: Any) -> FakeParseResponse:
        self.calls.append(kwargs)
        reply = self._replies.pop(0)
        if isinstance(reply, FakeParseResponse):
            return reply
        return FakeParseResponse(choices=[FakeChoice(message=FakeParsedMessage(reply))])


def _judge_kwargs(tmp_path: Path) -> dict[str, Any]:
    config, text = cli.load_prompt_file(cli.ALIGN_PROMPT)
    return {
        "prompt_text": text,
        "config": config,
        "cache_dir": tmp_path / "cache",
        "offline": False,
    }


def test_valid_reply_is_cached_and_replayed_offline(tmp_path: Path) -> None:
    client = fake_parse_client(parsed=_wire(*GOOD))
    first = cli.judge_run(_reference(), _package(), client=client, **_judge_kwargs(tmp_path))
    assert len(first) == 5 and len(client.chat.completions.calls) == 1
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1
    again = cli.judge_run(
        _reference(), _package(), client=None, **{**_judge_kwargs(tmp_path), "offline": True}
    )
    assert [j.label for j in again] == [j.label for j in first]


def test_offline_cache_miss_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="--offline"):
        cli.judge_run(
            _reference(), _package(), client=None, **{**_judge_kwargs(tmp_path), "offline": True}
        )


def test_invalid_reply_is_retried_once_then_fails(tmp_path: Path) -> None:
    bad = _wire(*GOOD[:1])
    client = _SeqClient([bad, _wire(*GOOD)])
    judgements = cli.judge_run(_reference(), _package(), client=client, **_judge_kwargs(tmp_path))
    assert len(judgements) == 5 and len(client.calls) == 2
    assert "rejected" in client.calls[1]["messages"][-1]["content"]
    assert (
        len(list((tmp_path / "cache").glob("*.json"))) == 1
    )  # stored under the first request's key

    client = _SeqClient([bad, bad])
    with pytest.raises(lib.JudgeValidationError, match="missing pairs"):
        cli.judge_run(
            _reference(),
            _package(),
            client=client,
            **{**_judge_kwargs(tmp_path), "cache_dir": tmp_path / "c2"},
        )
    assert not (tmp_path / "c2").exists()


def test_truncated_reply_is_an_error_not_a_score(tmp_path: Path) -> None:
    cut = FakeParseResponse(
        choices=[_Choice(message=FakeParsedMessage(_wire(*GOOD)), finish_reason="length")]
    )
    with pytest.raises(RuntimeError, match="cut off"):
        cli.judge_run(_reference(), _package(), client=_SeqClient([cut]), **_judge_kwargs(tmp_path))


def test_oversized_prompt_fails_instead_of_truncating(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="over the"):
        cli.judge_run(
            _reference(),
            _package(),
            client=fake_parse_client(parsed=_wire(*GOOD)),
            max_input_chars=100,
            **_judge_kwargs(tmp_path),
        )


def test_batching_sends_full_report_with_every_batch(tmp_path: Path) -> None:
    client = _SeqClient([_wire(*GOOD[:2]), _wire(GOOD[2], GOOD[3]), _wire(GOOD[4])])
    judgements = cli.judge_run(
        _reference(), _package(), client=client, findings_per_call=1, **_judge_kwargs(tmp_path)
    )
    assert len(judgements) == 5 and len(client.calls) == 3
    assert all(
        "The report also discusses the price of tea" in c["messages"][0]["content"]
        for c in client.calls
    )


def _write_case(root: Path, ref: Any, packages: list[Any]) -> None:
    case_dir = root / ref.case_id
    (case_dir / "runs").mkdir(parents=True)
    cli.save_reference(case_dir, ref)
    for p in packages:
        (case_dir / "runs" / f"{p.run_id}.json").write_text(json.dumps(p.model_dump(mode="json")))


def test_evaluate_end_to_end_never_calls_the_grounding_judge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: Any, **__: Any) -> Any:
        raise AssertionError("the grounding judge must not be called by the coverage evaluator")

    monkeypatch.setattr(grounding_judge.OpenAIGroundingJudgeBackend, "judge_block", boom)
    monkeypatch.setattr(grounding_judge, "build_judge_messages", boom)
    cases = tmp_path / "cases"
    _write_case(
        cases,
        _reference(),
        [
            _package(),
            _package(REPORT.replace("## Key findings", "## Summary"), expected=False, run_id="r2"),
        ],
    )
    client = _SeqClient([_wire(*GOOD), _wire(GOOD[0], GOOD[2], GOOD[4])])
    args = cli.build_parser().parse_args(
        [
            "evaluate",
            "--cases",
            str(cases),
            "--results",
            str(tmp_path / "results"),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--label",
            "t",
        ]
    )
    assert cli.cmd_evaluate(args, client=client, langfuse=None) == 0
    assert len(client.calls) == 2
    out = tmp_path / "results" / "t"
    scores = json.loads((out / "scores.json").read_text())
    assert [r["key_findings_status"] for r in scores["runs"]] == ["present", "absent"]
    assert scores["runs"][1]["key_findings_coverage"]["rate"] == 0.0
    judgements = json.loads((out / "judgements.json").read_text())["judgements"]
    assert sum(1 for j in judgements if j["source"] == "rule") == 2
    assert (
        (out / "judgements.csv").exists()
        and (out / "scores.csv").exists()
        and (out / "summary.md").exists()
    )
    assert (out / "calls.jsonl").read_text().count("\n") == 2


def test_evaluate_records_failed_runs_without_scores(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    _write_case(
        cases,
        _reference(),
        [_package(), _package(run_id="r2").model_copy(update={"report_text": "   "})],
    )
    client = _SeqClient(
        [_wire(*GOOD[:1]), _wire(*GOOD[:1])]
    )  # invalid twice for r1; r2 is an input error
    args = cli.build_parser().parse_args(
        [
            "evaluate",
            "--cases",
            str(cases),
            "--results",
            str(tmp_path / "r"),
            "--cache-dir",
            str(tmp_path / "c"),
            "--label",
            "t",
        ]
    )
    assert cli.cmd_evaluate(args, client=client, langfuse=None) == 1
    scores = json.loads((tmp_path / "r" / "t" / "scores.json").read_text())
    assert scores["runs"] == []
    errors = {f["run_id"]: f["error"] for f in scores["summary"]["failed_runs"]}
    assert "missing pairs" in errors["r1"] and "input error" in errors["r2"]


def test_evaluate_refuses_unapproved_and_mismatched_versions(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    _write_case(cases, _reference(approved=False), [_package()])
    args = cli.build_parser().parse_args(
        [
            "evaluate",
            "--cases",
            str(cases),
            "--results",
            str(tmp_path / "r"),
            "--cache-dir",
            str(tmp_path / "c"),
            "--label",
            "t",
        ]
    )
    client = fake_parse_client(parsed=_wire(*GOOD))
    assert cli.cmd_evaluate(args, client=client, langfuse=None) == 1
    assert client.chat.completions.calls == []
    failed = json.loads((tmp_path / "r" / "t" / "scores.json").read_text())["summary"][
        "failed_runs"
    ]
    assert "not approved" in failed[0]["error"]


def test_dry_run_calls_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cases = tmp_path / "cases"
    _write_case(cases, _reference(), [_package()])
    args = cli.build_parser().parse_args(
        ["evaluate", "--cases", str(cases), "--results", str(tmp_path / "r"), "--dry-run"]
    )
    client = fake_parse_client(parsed=_wire(*GOOD))
    assert cli.cmd_evaluate(args, client=client) == 0
    assert client.chat.completions.calls == [] and not (tmp_path / "r").exists()
    assert "F1 / key_findings" in capsys.readouterr().out


# --------------------------------------------------------------------------
# Drafting a reference
# --------------------------------------------------------------------------


def test_draft_refuses_a_report_and_only_sees_the_review(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case = tmp_path / "c1"
    case.mkdir()
    (case / "review.md").write_text(REPORT)  # a rendered report, not a review
    args = cli.build_parser().parse_args(
        [
            "draft-reference",
            "--case",
            str(case),
            "--query",
            QUERY,
            "--cache-dir",
            str(tmp_path / "cache"),
        ]
    )
    client = fake_parse_client(parsed=lib.DraftWire(findings=[]))
    assert cli.cmd_draft(args, client=client) == 2
    assert "looks like a generated Policy Atlas report" in capsys.readouterr().out
    assert client.chat.completions.calls == []

    (case / "review.md").write_text(REVIEW)
    draft = lib.DraftWire(
        findings=[
            lib.DraftFindingWire(
                kind="finding",
                finding_text="X improves Y.",
                necessary_qualifications=["moderate certainty"],
                source_passage_ids=["P01"],
                source_excerpts=["X improved Y by about 3 points"],
            ),
            lib.DraftFindingWire(
                kind="evidence_gap",
                finding_text="Nothing beyond a year.",
                necessary_qualifications=[],
                source_passage_ids=["P03"],
                source_excerpts=["this excerpt is invented"],
            ),
        ]
    )
    client = fake_parse_client(parsed=draft)
    assert cli.cmd_draft(args, client=client) == 0
    sent = client.chat.completions.calls[0]["messages"][0]["content"]
    assert REVIEW in sent and "price of tea" not in sent
    ref = cli.load_reference(case)
    assert ref.approval.status == "draft" and ref.approval.content_hash is None
    assert [f.priority for f in ref.findings] == [None, None]
    assert "excerpt not found" in capsys.readouterr().out
    assert any("F02: excerpt not found" in p for p in lib.structural_problems(ref, REVIEW))


def test_approve_command_stamps_hash_and_refuses_unfilled(tmp_path: Path) -> None:
    case = tmp_path / "c1"
    case.mkdir()
    (case / "review.md").write_text(REVIEW)
    ref = _reference(approved=False)
    ref.findings[0].priority = None
    cli.save_reference(case, ref)
    args = cli.build_parser().parse_args(["approve", "--case", str(case), "--reviewer", "Rosie"])
    assert cli.cmd_approve(args) == 1
    ref.findings[0].priority = "essential"
    cli.save_reference(case, ref)
    assert cli.cmd_approve(args) == 0
    approved = cli.load_reference(case)
    assert approved.approval.status == "approved" and approved.approval.reviewer == "Rosie"
    assert lib.approval_problems(approved) == []


# --------------------------------------------------------------------------
# Comparing with human labels
# --------------------------------------------------------------------------


def _ann(
    fid: str,
    section: str,
    label: str,
    *,
    annotator: str = "a1",
    run: str = "r1",
    version: str = "v1",
    status: str = "final",
) -> Any:
    return lib.AnnotationRow(
        case_id="case1",
        run_id=run,
        reference_version=version,
        finding_id=fid,
        section=section,
        label=label,
        annotator=annotator,
        status=status,
    )


def test_compare_flags_versions_duplicates_and_missing_and_prefers_adjudication() -> None:
    s = _score(GOOD)  # noqa: F841  (builds judgements through the same path)
    context = {"case_id": "case1", "run_id": "r1", "reference_version": "v1", "reference_hash": "h"}
    located = lib.validate_response(
        _wire(*GOOD),
        expected=lib.expected_pairs(_findings(), "present"),
        report_text=REPORT,
        key_findings=_package().key_findings,
    )
    judgements = lib.to_judgements(located, _findings(), context)
    annotations = [
        _ann("F1", "full_report", "adequate"),
        _ann("F1", "key_findings", "adequate", version="v0"),  # version mismatch
        _ann("F2", "full_report", "adequate"),
        _ann("F2", "full_report", "adequate"),  # duplicate from the same annotator
        _ann("F2", "key_findings", "absent"),
        _ann("F2", "key_findings", "adequate", annotator="a2"),  # disagreement...
        _ann(
            "F2", "key_findings", "partial", annotator="adjudication", status="adjudicated"
        ),  # ...resolved
        _ann("F9", "full_report", "absent"),  # no judgement for this pair
    ]  # F3/full_report was judged but never annotated
    result = lib.compare(judgements, annotations)
    flags = {(f["kind"], f["pair"]) for f in result["flags"]}
    assert flags == {
        ("version_mismatch", "case1/r1/F1/key_findings"),
        ("duplicate", "case1/r1/F2/full_report"),
        ("missing_llm", "case1/r1/F9/full_report"),
        ("missing_human", "case1/r1/F3/full_report"),
    }
    assert result["n_compared"] == 2
    kf = result["sections"]["key_findings"]
    assert kf["confusion"] == {"partial->partial": 1} and kf["agreement"] == 1.0
    full = result["sections"]["full_report"]
    assert full["confusion"] == {"adequate->adequate": 1}
    assert full["per_label"]["adequate"]["precision"] == 1.0
    assert full["per_label"]["absent"]["recall"] is None
    md = lib.render_comparison_md(result)
    assert "version_mismatch" in md and "| human \\ judge |" in md


def test_compare_detects_essential_omissions_and_prominence_gaps_and_counts_abstentions() -> None:
    context = {"case_id": "case1", "run_id": "r1", "reference_version": "v1", "reference_hash": "h"}
    rows = [dict(r) for r in GOOD]
    rows[2] = _j("F2", "full_report", "uncertain", [BODY_F2])
    rows[3] = _j("F2", "key_findings", "absent")
    located = lib.validate_response(
        _wire(*rows),
        expected=lib.expected_pairs(_findings(), "present"),
        report_text=REPORT,
        key_findings=_package().key_findings,
    )
    judgements = lib.to_judgements(located, _findings(), context)
    rule = lib.rule_judgements_for_absent_section(_findings(), {**context, "run_id": "r2"})
    annotations = [
        _ann("F1", "full_report", "adequate"),
        _ann("F1", "key_findings", "partial"),  # human sees a gap the judge missed
        _ann("F2", "full_report", "absent"),  # human: essential omission; judge abstained
        _ann("F2", "key_findings", "absent"),
        _ann("F3", "full_report", "adequate"),
    ]
    result = lib.compare(judgements + rule, annotations)
    assert result["n_rule_rows_skipped"] == 2
    assert result["sections"]["full_report"]["abstentions"] == {
        "human_uncertain": 0,
        "llm_uncertain": 1,
    }
    omissions = result["essential_omissions"]
    assert (omissions["human_positive"], omissions["llm_positive"], omissions["detected"]) == (
        1,
        0,
        0,
    )
    assert omissions["recall"] == 0.0 and omissions["precision"] is None
    gaps = result["prominence_gaps"]
    assert (
        gaps["human_positive"] == 1
        and gaps["llm_positive"] == 0
        and gaps["missed"] == ["case1/r1/F1/key_findings"]
    )


# --------------------------------------------------------------------------
# The shipped synthetic example runs offline from its cache
# --------------------------------------------------------------------------


def test_shipped_example_runs_offline(tmp_path: Path) -> None:
    case = _ROOT / "cases" / "example_synthetic"
    ref = cli.load_reference(case)
    assert lib.approval_problems(ref) == []
    assert lib.structural_problems(ref, (case / "review.md").read_text()) == []
    args = cli.build_parser().parse_args(
        [
            "evaluate",
            "--cases",
            str(_ROOT / "cases"),
            "--cache-dir",
            str(case / "cache"),
            "--offline",
            "--results",
            str(tmp_path),
            "--label",
            "x",
        ]
    )
    assert cli.cmd_evaluate(args, client=None, langfuse=None) == 0
    scores = {
        r["run_id"]: r for r in json.loads((tmp_path / "x" / "scores.json").read_text())["runs"]
    }
    assert scores["run_a"]["full_report_coverage"]["numerator"] == 5
    assert scores["run_a"]["key_findings_coverage"]["numerator"] == 1
    assert scores["run_a"]["prominence_gap_ids"] == ["F02", "F04"]
    assert scores["run_b"]["essential_absent_ids"] == ["F02"]
    assert scores["run_b"]["unresolved"] == ["F05:full_report"]
    cmp_args = cli.build_parser().parse_args(
        [
            "compare",
            "--judgements",
            str(tmp_path / "x" / "judgements.json"),
            "--annotations",
            str(case / "annotations" / "human.csv"),
        ]
    )
    assert cli.cmd_compare(cmp_args) == 0
    result = json.loads((tmp_path / "x" / "comparison.json").read_text())
    assert result["flags"] == [] and result["prominence_gaps"]["detected"] == 2
