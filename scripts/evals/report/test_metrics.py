"""Self-check for the parts that need no network and no database: the scripted
console, the report renderer, the prompt-file parser and the agreement maths.

Run: uv run --project backend python scripts/evals/report/test_metrics.py
"""

from __future__ import annotations

import uuid
from pathlib import Path

from build_dataset import build_item, render_report
from calibrate import (
    PROMPT_FILE,
    item_scores,
    load_prompt_file,
    self_agreement,
    spearman,
)
from run_queries import PLANNER_ANSWER, ScriptedConsole, intent_text

from policy_atlas.api.contract.read_models import (
    ArtefactOut,
    BlockOut,
    CoverageSnapshotOut,
    ReferenceOut,
    SectionOut,
)


def test_scripted_console_answers_every_prompt() -> None:
    console = ScriptedConsole("Q?")
    assert console.prompt("Describe the evidence review you want: ") == "Q?"
    assert console.prompt("> ") == PLANNER_ANSWER
    assert (
        console.prompt("Approve, edit, or abandon? [approve/edit/abandon]: ")
        == "approve"
    )
    assert (
        console.prompt("Describe a revision, or type 'abandon' to stop: ") == "abandon"
    )
    assert console.prompt("Apply this steering? [y/N]: ") == "n"
    assert console.prompt("Choose [1-4]: ") == "1"
    assert len(console.answers) == 6
    assert "Search effort: rapid" in intent_text(
        "Q?", "rapid"
    ) and "landscape" in intent_text("Q?", "rapid")


def test_render_report() -> None:
    artefact = ArtefactOut(
        artefact_id=uuid.uuid4(),
        title="T",
        question="Q",
        coverage_snapshot=CoverageSnapshotOut(),
        full_report_intro="Intro.",
        sections=[
            SectionOut(
                title="S1",
                role="standard",
                blocks=[
                    BlockOut(block_id=uuid.uuid4(), prose="P1"),
                    BlockOut(block_id=uuid.uuid4(), prose="P2"),
                ],
            ),
        ],
        references=[
            ReferenceOut(n=1, title="Ref", year=2020, venue="J", url="http://x")
        ],
    )
    text = render_report(artefact)
    assert text.startswith("# T\n\n**Question:** Q\n\nIntro.\n\n## S1\n\nP1\n\nP2\n")
    assert text.rstrip().endswith("## References\n\n1. Ref (2020) J http://x")


def test_build_item_shape() -> None:
    run = {
        "task_id": "abc",
        "question": "Q",
        "depth": "rapid",
        "conversation_id": "c",
        "git_commit": "g",
    }
    item = build_item(run, {"answer_relevance": "4", "comment": "ok"}, "R", "ds")
    assert item["id"] == "ds:abc"
    assert item["input"] == {"question": "Q", "report": "R"}
    assert item["expected_output"] == {"answer_relevance": 4}
    assert item["metadata"]["comment"] == "ok"
    fallback = build_item(
        {"task_id": "abc", "question": ""}, {"answer_relevance": "2"}, "R", "ds", "PQ"
    )
    assert (
        fallback["input"]["question"] == "PQ"
        and fallback["metadata"]["plan_question"] == "PQ"
    )


def test_prompt_file() -> None:
    config, text = load_prompt_file(PROMPT_FILE)
    assert config["name"] == "answer-relevance-judge" and config["model"]
    assert "{{question}}" in text and "{{report}}" in text
    assert "5 = Directly and fully relevant" in text
    try:
        load_prompt_file(Path(__file__))  # no front matter
    except ValueError:
        pass
    else:
        raise AssertionError("a file without front matter must be rejected")


def test_item_scores() -> None:
    scores = {
        e.name: e.value
        for e in item_scores(
            output={"score": 4, "reasoning": "r"},
            expected_output={"answer_relevance": 5},
        )
    }
    assert scores == {
        "answer_relevance": 4,
        "human_answer_relevance": 5,
        "exact_match": 0,
        "within_one": 1,
        "abs_error": 1,
    }


def test_spearman() -> None:
    assert abs(spearman([1, 2, 3, 4], [1, 2, 3, 4]) - 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9
    assert abs(spearman([1, 2, 2, 4], [1, 3, 3, 5]) - 1.0) < 1e-9  # ties handled
    assert spearman([3, 3, 3], [1, 2, 3]) is None  # no variance
    assert spearman([1], [1]) is None


def test_self_agreement() -> None:
    class R:
        def __init__(self, id_: str, score: int) -> None:
            self.item = type("I", (), {"id": id_})()
            self.output = {"score": score}

    floor = self_agreement([R("a", 3), R("b", 5)], [R("a", 3), R("b", 4)])
    assert floor == {"n": 2, "exact": 0.5, "within_one": 1.0}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
