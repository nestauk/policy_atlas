"""The size of change (task 054, C37): the number checks, the range bounds and the step."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.routers.toc import toc_evidence_out
from policy_atlas.core.schema import toc_figure, toc_item_evidence
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.theory_of_change.backend import StubTocBackend
from policy_atlas.theory_of_change.evidence.figures_prompt import FiguresResponse, FigureWire
from policy_atlas.theory_of_change.figures import CheckedFigure, check_figure, number_in_quote
from tests.theory_of_change.test_check_steps import _summary
from tests.theory_of_change.test_walks import Records, _start, seed_toc


@pytest.mark.parametrize(
    ("value", "quote", "found"),
    [
        (40000, "about 40,000 children took part", True),  # thousands separator
        ("40000", "about 40 000 children took part", True),  # thin space as separator
        (1.05, "odds ratio 1·05 (0·99 to 1·12)", True),  # middle dot as decimal point
        ("45%", "exposure fell 45% in a year", True),  # the % sign
        (60.0, "intake rose by 60 kcal", True),  # a trailing .0
        ("1.50", "a ratio of 1.5", True),  # trailing zeros
        (-0.3, "a change of −0.3 points", True),  # unicode minus
        (-0.3, "fell by 0.3 points", True),  # sign is in the words
        ("- 2", "down 2 points", True),  # spaces
        (6, "about 60 adverts a day", False),  # a whole number, not a digit inside one
        (0.25, "standardised mean difference 0.35", False),
        ("a lot", "a lot more", False),  # no number at all
    ],
)
def test_the_number_must_be_in_the_quote(value: Any, quote: str, found: bool) -> None:
    assert number_in_quote(value, quote) is found


def _figure(**values: Any) -> FigureWire:
    base: dict[str, Any] = {
        "box": "link",
        "measure": "more calories eaten after food adverts",
        "effect_size": "60",
        "ci_lower": None,
        "ci_upper": None,
        "unit": "kcal",
        "effect_size_type": "absolute_change",
        "population": "children",
        "place": None,
        "year": None,
        "n": None,
        "k": None,
        "quote": "intake rose by 60 kcal (95% CI 3·1 to 116·9; 11 studies)",
        "statement": "Children ate 60 more calories after seeing food adverts than without them.",
    }
    return FigureWire(**{**base, **values})


TEXT = (
    "A review. TV food ads raised intake by 60 kcal. "
    "intake rose by 60 kcal (95% CI 3·1 to 116·9; 11 studies)"
)


def test_a_figure_is_kept_parsed_and_its_reported_text_kept() -> None:
    checked = check_figure(_figure(ci_lower="3·1", ci_upper="116·9", k="11", n="1,200"), TEXT)
    assert isinstance(checked, CheckedFigure)
    values = checked.values
    assert (values["value_text"], values["value"]) == ("60", 60.0)
    assert (values["ci_lower_text"], values["ci_lower"]) == ("3·1", 3.1)
    assert (values["ci_upper_text"], values["ci_upper"]) == ("116·9", 116.9)
    assert (values["k"], values["n"]) == (11, 1200)
    assert not checked.range_dropped


def test_a_range_with_lower_above_upper_is_dropped_and_the_figure_kept() -> None:
    checked = check_figure(_figure(ci_lower=120, ci_upper=3.1), TEXT)
    assert isinstance(checked, CheckedFigure) and checked.range_dropped
    values = checked.values
    assert values["ci_lower"] is values["ci_upper"] is None
    assert values["ci_lower_text"] is values["ci_upper_text"] is None
    assert values["value"] == 60.0


def test_a_figure_whose_quote_or_number_does_not_check_is_dropped() -> None:
    assert check_figure(_figure(quote="intake rose by 90 kcal in a trial"), TEXT) == "quote"
    assert check_figure(_figure(effect_size=45), TEXT) == "number"


class _Figures(StubTocBackend):
    """Per document: a kept figure (with a reversed range), a bad quote and a bad number.

    The seeded titles end in a number ("Advertising ban study … 3"), so the
    title is a quote that holds its number.
    """

    def figures(self, **kwargs: Any) -> Any:
        self._next("figures", kwargs)
        title = str(kwargs["title"])
        number = title.split()[-1]
        good = _figure(
            box="source",
            measure="adverts seen a day",
            effect_size=number,
            ci_lower=9,
            ci_upper=1,
            unit=None,
            effect_size_type="level",
            quote=title,
        )
        return FiguresResponse(
            figures=[
                good,
                _figure(quote="this passage is in no document at all"),
                good.model_copy(update={"effect_size": "123456"}),
            ]
        ), None


def _check_walk(
    engine: Engine, cleanup: list[uuid.UUID], backend: StubTocBackend, runs: int
) -> Any:
    task_id, plan_row = seed_toc(engine)
    cleanup.append(task_id)
    for _ in range(runs):
        _start(engine, task_id, plan_row, RunnerBackends(search_backends=[Records(2)], toc=backend))
    return task_id


def test_the_step_stores_checked_figures_and_the_read_attaches_them_to_the_box(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = _Figures()
    task_id = _check_walk(engine, cleanup, backend, runs=1)
    summary = _summary(engine, task_id, "toc_figures")
    calls = backend.calls["figures"]
    assert calls > 0 and summary["calls"] == calls and summary["failed_calls"] == 0
    assert summary["figures"] == calls
    assert summary["dropped_quote_not_in_text"] == summary["dropped_number_not_in_quote"] == calls
    assert summary["ranges_dropped"] == calls
    # The calls get the link's boxes and the plan's population.
    sent = backend.inputs["figures"][0]
    assert sent["source"] and sent["target"] and sent["population"]
    with engine.connect() as conn:
        rows = conn.execute(select(toc_figure).where(toc_figure.c.task_id == task_id)).all()
        evidence = toc_evidence_out(conn, task_id)
    assert len(rows) == calls
    assert all(row.box == "source" and row.ci_lower is None for row in rows)
    assert all(row.statement and row.statement.startswith("Children ate") for row in rows)
    # A source-box figure belongs to the link's source box, with its document's citation.
    box_figures = [figure for box in evidence.boxes for figure in box.figures]
    assert len(box_figures) == calls
    assert all(f.source_title.startswith("Advertising ban study") for f in box_figures)
    assert all(f.statement and f.evidence_id for f in box_figures)
    assert all(not link.figures for link in evidence.links)  # none were link effects


def test_a_judgement_already_done_is_not_asked_again(
    engine: Engine, cleanup: list[uuid.UUID]
) -> None:
    backend = _Figures()
    task_id = _check_walk(engine, cleanup, backend, runs=2)
    with engine.connect() as conn:
        on_topic = conn.execute(
            select(toc_item_evidence.c.figures_checked_at).where(
                toc_item_evidence.c.task_id == task_id,
                toc_item_evidence.c.support != "not_about",
            )
        ).scalars().all()
    # Every on-topic judgement asked once: the second walk asked only about new ones.
    assert on_topic and all(stamp is not None for stamp in on_topic)
    assert backend.calls["figures"] == len(on_topic)
    assert _summary(engine, task_id, "toc_figures")["already_done"] > 0
