"""The ``suggest`` component (task 045 Phase 4.2, S10; contract D7, A15).

The contract's suggest bullet: the step reads the plan, the baseline and the
linked report and yields at most the bound, each with a design, labelled
*suggested by Policy Atlas* or *from your evidence search* with the report
section named; no profile record is ever created from the report; the plan's
own options become entrants labelled *added by you*; a rebuild keeps the
existing option ids. Seeded on the transactional ``conn`` fixture.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    artefact,
    block,
    capability_run,
    evidence_scope,
    intervention_profile_record,
    option,
    option_membership,
    runs,
    synthesis_result,
    task,
    task_plan,
    task_source_snapshot,
)
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.options_scoping.suggest.suggest import SuggestContext, suggest_options
from policy_atlas.options_scoping.suggest.suggest_prompt import (
    SUGGEST_BOUND,
    SuggestedOptionWire,
    SuggestResponse,
)
from policy_atlas.runtime.agent_backend import StubAgentBackend
from policy_atlas.runtime.scoping_plan import (
    ScopingPlan,
    YourContextEntry,
    YourOption,
)
from tests.helpers import now
from tests.runtime.test_baseline_gate import scoping_plan
from tests.runtime.test_inherit import _seed_linked_source

REPORT_SECTION = "Employment programmes"

_DESIGNED = OptionDesign(
    name="Youth guarantee",
    description="Every 16 to 24 year old is offered a job, training or education place.",
    design_features=["guaranteed offer", "within four months", "delivered by Jobcentres"],
    outcomes_served=["the NEET rate"],
    assumed=["within four months"],
)


def _plan(**updates: Any) -> ScopingPlan:
    plan = scoping_plan(
        constraints=[
            {
                "text": "Delivered through schools",
                "kind": "requirement",
                "checked_at": "longlist",
                "origin": "your_call",
            }
        ]
    )
    defaults: dict[str, Any] = {
        "your_context": [
            YourContextEntry(
                text="We already fund careers advice", type="present_fact", turn_index=0
            )
        ],
        "your_options": [
            YourOption(text="a youth guarantee", design=_DESIGNED, turn_index=0),
            YourOption(text="free bus passes for apprentices", turn_index=0),
        ],
    }
    defaults.update(updates)
    return plan.model_copy(update=defaults)


class _Walk:
    """A scoping task with a longlist walk (plan, intent record, walk, run)."""

    def __init__(self, conn: Connection, plan: ScopingPlan) -> None:
        self.conn = conn
        self.task_id = uuid.uuid4()
        conn.execute(
            task.insert().values(
                task_id=self.task_id,
                created_at=now(),
                name="Youth employment options",
                status="active",
                updated_at=now(),
                capability="options_scoping",
            )
        )
        plan_id = uuid.uuid4()
        conn.execute(
            task_plan.insert().values(
                plan_id=plan_id,
                task_id=self.task_id,
                version=1,
                status="approved",
                payload=plan.model_dump(mode="json"),
                created_at=now(),
                created_by="task_agent",
            )
        )
        self.scope_id = uuid.uuid4()
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=self.scope_id,
                task_id=self.task_id,
                intent="longlist intent",
                context={},
                created_at=now(),
                purpose="longlist",
                plan_id=plan_id,
            )
        )
        self.walk_id = uuid.uuid4()
        conn.execute(
            capability_run.insert().values(
                capability_run_id=self.walk_id,
                task_id=self.task_id,
                evidence_scope_id=self.scope_id,
                capability="options_scoping",
                plan_id=plan_id,
                plan_version=1,
                status="running",
                started_at=now(),
            )
        )

    def run(self) -> uuid.UUID:
        run_id = uuid.uuid4()
        self.conn.execute(
            runs.insert().values(
                run_id=run_id,
                task_id=self.task_id,
                status="running",
                started_at=now(),
                capability_run_id=self.walk_id,
            )
        )
        return run_id

    def baseline(self, sections: list[tuple[str, str]]) -> None:
        run_id = self.run()
        artefact_id = uuid.uuid4()
        self.conn.execute(
            artefact.insert().values(
                artefact_id=artefact_id,
                task_id=self.task_id,
                capability_run_id=self.walk_id,
                title="Baseline",
                created_at=now(),
            )
        )
        specs = []
        for title, content in sections:
            block_id = uuid.uuid4()
            self.conn.execute(
                block.insert().values(
                    block_id=block_id,
                    artefact_id=artefact_id,
                    content=content,
                    content_hash=str(uuid.uuid4()),
                    created_at=now(),
                )
            )
            specs.append({"block_id": str(block_id), "title": title, "role": "standard"})
        self.conn.execute(
            synthesis_result.insert().values(
                synthesis_result_id=uuid.uuid4(),
                task_id=self.task_id,
                evidence_scope_id=self.scope_id,
                run_id=run_id,
                artefact_id=artefact_id,
                synthesis_provenance={},
                blocks=specs,
                counts={},
                flags={},
                created_at=now(),
            )
        )

    def link_report(self) -> None:
        _seed_linked_source(
            self.conn,
            self.task_id,
            name="NEET evidence search",
            plan_payload={},
            block_specs=[(REPORT_SECTION, "Wage subsidies and work trials were evaluated.")],
        )

    def suggest(self, backend: StubAgentBackend) -> tuple[uuid.UUID, dict[str, Any]]:
        run_id = self.run()
        summary = suggest_options(
            self.conn,
            task_id=self.task_id,
            run_id=run_id,
            context=SuggestContext(scope_id=self.scope_id, intent="", context={}),
            backend=backend,
        )
        return run_id, summary

    def options(self) -> list[Any]:
        return list(
            self.conn.execute(
                select(option)
                .where(option.c.task_id == self.task_id)
                .order_by(option.c.created_at, option.c.name)
            ).mappings()
        )


def _wire(name: str, *, source: str = "model", section: str | None = None) -> SuggestedOptionWire:
    return SuggestedOptionWire(
        name=name,
        description=f"{name}, described in one sentence.",
        design_features=[f"{name} feature one", f"{name} feature two"],
        outcomes_served=["the NEET rate"],
        source=source,  # type: ignore[arg-type]
        report_section=section,
    )


def test_the_step_reads_the_plan_the_baseline_and_the_linked_report(conn: Connection) -> None:
    walk = _Walk(conn, _plan())
    walk.baseline([("What is in place", "Careers advice is funded."), ("The trend", "Rising.")])
    walk.link_report()
    backend = StubAgentBackend()

    walk.suggest(backend)

    assert backend.suggest_calls == 1
    [seen] = backend.suggest_inputs
    plan_context = seen["plan"]
    assert plan_context.question == "What could reduce the number of young people not in work?"
    assert plan_context.intended_change == "Reduce the number of young people not in work"
    assert plan_context.target_unit == "16 to 24 year olds"
    assert plan_context.outcomes == ["the NEET rate"]
    assert plan_context.requirements == ["Delivered through schools"]
    assert plan_context.your_context == ["We already fund careers advice"]
    assert plan_context.your_options == [
        {"text": "a youth guarantee", "design": _DESIGNED.model_dump(mode="json")},
        {"text": "free bus passes for apprentices", "design": None},
    ]
    assert seen["baseline_sections"] == [
        ("What is in place", "Careers advice is funded."),
        ("The trend", "Rising."),
    ]
    [report] = seen["linked_reports"]
    assert report.title == "NEET evidence search"
    assert f"## {REPORT_SECTION}" in report.report_markdown
    assert seen["bound"] == SUGGEST_BOUND


def test_suggestions_are_minted_labelled_each_with_a_design(conn: Connection) -> None:
    walk = _Walk(conn, _plan(your_options=[]))
    walk.link_report()
    backend = StubAgentBackend(
        suggest_responses=SuggestResponse(
            options=[
                _wire("Wage subsidy", source="linked_report", section=REPORT_SECTION),
                _wire("Mentoring scheme"),
            ]
        )
    )

    run_id, summary = walk.suggest(backend)

    by_name = {row["name"]: row for row in walk.options()}
    assert set(by_name) == {"Wage subsidy", "Mentoring scheme"}
    assert by_name["Wage subsidy"]["origin"] == "from_evidence_search"
    assert by_name["Mentoring scheme"]["origin"] == "suggested"
    for row in by_name.values():
        design = OptionDesign.model_validate(row["design"])
        assert design.name == row["name"]
        assert design.design_features == [
            f"{row['name']} feature one",
            f"{row['name']} feature two",
        ]
        assert design.assumed == []
        assert row["design_version"] == 1
        assert row["outcomes"] == ["the NEET rate"]
        assert row["state"] == "included"
        assert row["created_by_run_id"] == run_id
    report_id = str(by_name["Wage subsidy"]["option_id"])
    assert summary["report_sections"] == {report_id: REPORT_SECTION}
    assert (summary["suggested"], summary["from_report"], summary["added_by_you"]) == (1, 1, 0)
    # The report's entrants come before the model's.
    assert summary["entrants"] == [report_id, str(by_name["Mentoring scheme"]["option_id"])]


def test_at_most_the_bound_is_minted(conn: Connection) -> None:
    walk = _Walk(conn, _plan(your_options=[]))
    backend = StubAgentBackend(
        suggest_responses=SuggestResponse(
            options=[_wire(f"Option {index}") for index in range(SUGGEST_BOUND + 2)]
        )
    )

    _run_id, summary = walk.suggest(backend)

    assert len(walk.options()) == SUGGEST_BOUND
    assert summary["suggested"] == SUGGEST_BOUND
    assert summary["dropped"] == 2


def test_no_profile_record_is_ever_created_from_the_report(conn: Connection) -> None:
    walk = _Walk(conn, _plan())
    walk.link_report()
    backend = StubAgentBackend(
        suggest_responses=SuggestResponse(
            options=[_wire("Wage subsidy", source="linked_report", section=REPORT_SECTION)]
        )
    )

    walk.suggest(backend)

    for table in (intervention_profile_record, option_membership, task_source_snapshot):
        count = conn.execute(
            select(func.count()).select_from(table).where(table.c.task_id == walk.task_id)
        ).scalar_one()
        assert count == 0, table.name


def test_the_plan_s_own_options_become_added_by_you_entrants(conn: Connection) -> None:
    walk = _Walk(conn, _plan())
    backend = StubAgentBackend(suggest_responses=SuggestResponse(options=[_wire("Mentoring")]))

    _run_id, summary = walk.suggest(backend)

    own = {row["name"]: row for row in walk.options() if row["origin"] == "added_by_you"}
    assert set(own) == {"Youth guarantee", "free bus passes for apprentices"}
    assert OptionDesign.model_validate(own["Youth guarantee"]["design"]) == _DESIGNED
    # A design that failed to be proposed: the entrant stands on the words.
    fallback = OptionDesign.model_validate(own["free bus passes for apprentices"]["design"])
    assert fallback.design_features == ["free bus passes for apprentices"]
    assert fallback.assumed == []
    assert fallback.as_intent().startswith("free bus passes for apprentices.")
    assert summary["added_by_you"] == 2
    assert summary["own_without_design"] == 1
    # The user's own come first (never dropped by the option-search cap).
    assert summary["entrants"][:2] == [
        str(own["Youth guarantee"]["option_id"]),
        str(own["free bus passes for apprentices"]["option_id"]),
    ]


def test_a_rebuild_keeps_the_existing_option_ids(conn: Connection) -> None:
    walk = _Walk(conn, _plan())
    walk.link_report()
    response = SuggestResponse(
        options=[
            _wire("Wage subsidy", source="linked_report", section=REPORT_SECTION),
            _wire("Mentoring scheme"),
        ]
    )
    first_run, first = walk.suggest(StubAgentBackend(suggest_responses=response))
    before = {row["option_id"]: row for row in walk.options()}

    _second_run, second = walk.suggest(StubAgentBackend(suggest_responses=response))

    after = {row["option_id"]: row for row in walk.options()}
    assert set(after) == set(before)
    assert {row["created_by_run_id"] for row in after.values()} == {first_run}
    # The user's own are entrants again (kept); the repeated suggestions are
    # dropped — they stay on the task and reach the longlist as seeds.
    assert second["entrants"] == first["entrants"][:2]
    assert (second["minted"], second["kept"], second["dropped"]) == (0, 2, 2)


def test_a_rebuild_adds_a_new_suggestion_beside_the_kept_ones(conn: Connection) -> None:
    walk = _Walk(conn, _plan(your_options=[]))
    walk.suggest(StubAgentBackend(suggest_responses=SuggestResponse(options=[_wire("A")])))
    [kept] = walk.options()

    _run, summary = walk.suggest(
        StubAgentBackend(suggest_responses=SuggestResponse(options=[_wire("A"), _wire("B")]))
    )

    rows = {row["name"]: row["option_id"] for row in walk.options()}
    assert rows["A"] == kept["option_id"]
    assert set(rows) == {"A", "B"}
    assert (summary["minted"], summary["kept"], summary["dropped"]) == (1, 0, 1)
    assert summary["entrants"] == [str(rows["B"])]


def test_a_rebuild_shows_the_model_the_existing_options_and_drops_repeats(
    conn: Connection,
) -> None:
    """The live-check defect: a rebuild re-proposed the report's options under
    new names. The model now sees every existing option, and a suggestion
    repeating one by name or by description mints nothing."""
    walk = _Walk(conn, _plan(your_options=[]))
    walk.link_report()
    first_names = [f"Existing option {index}" for index in range(7)]
    walk.suggest(
        StubAgentBackend(
            suggest_responses=SuggestResponse(
                options=[
                    _wire(name, source="linked_report", section=REPORT_SECTION)
                    for name in first_names
                ]
            )
        )
    )
    before = {row["option_id"] for row in walk.options()}
    assert len(before) == 7

    renamed = _wire("A new name for the same thing", source="linked_report")
    renamed = renamed.model_copy(
        update={"description": "  existing OPTION 0,   described in one sentence. "}
    )
    backend = StubAgentBackend(
        suggest_responses=SuggestResponse(
            options=[
                _wire("EXISTING   option 3"),  # same name, other case and spacing
                renamed,  # same description, new name
                _wire("A genuinely new option"),
            ]
        )
    )

    _run, summary = walk.suggest(backend)

    [seen] = backend.suggest_inputs
    assert seen["plan"].existing_options == [
        {"name": name, "description": f"{name}, described in one sentence."}
        for name in first_names
    ]
    new_rows = [row for row in walk.options() if row["option_id"] not in before]
    assert [row["name"] for row in new_rows] == ["A genuinely new option"]
    assert (summary["minted"], summary["dropped"]) == (1, 2)
    assert summary["entrants"] == [str(new_rows[0]["option_id"])]


def test_a_first_build_shows_the_model_no_existing_options(conn: Connection) -> None:
    walk = _Walk(conn, _plan())
    backend = StubAgentBackend()
    walk.suggest(backend)
    assert backend.suggest_inputs[0]["plan"].existing_options == []


def test_a_report_label_without_a_linked_report_is_suggested(conn: Connection) -> None:
    walk = _Walk(conn, _plan(your_options=[]))
    backend = StubAgentBackend(
        suggest_responses=SuggestResponse(
            options=[_wire("Wage subsidy", source="linked_report", section=REPORT_SECTION)]
        )
    )

    _run, summary = walk.suggest(backend)

    [row] = walk.options()
    assert row["origin"] == "suggested"
    assert summary["report_sections"] == {}


def test_a_section_the_report_does_not_carry_is_not_recorded(conn: Connection) -> None:
    walk = _Walk(conn, _plan(your_options=[]))
    walk.link_report()
    backend = StubAgentBackend(
        suggest_responses=SuggestResponse(
            options=[_wire("Wage subsidy", source="linked_report", section="Invented heading")]
        )
    )

    _run, summary = walk.suggest(backend)

    [row] = walk.options()
    assert row["origin"] == "from_evidence_search"
    assert summary["report_sections"] == {str(row["option_id"]): None}


def test_a_suggestion_repeating_the_user_s_option_is_dropped(conn: Connection) -> None:
    walk = _Walk(conn, _plan())
    backend = StubAgentBackend(
        suggest_responses=SuggestResponse(options=[_wire("youth guarantee"), _wire("Other")])
    )

    _run, summary = walk.suggest(backend)

    assert sorted(row["name"] for row in walk.options()) == [
        "Other",
        "Youth guarantee",
        "free bus passes for apprentices",
    ]
    assert summary["dropped"] == 1


def test_the_stub_default_mints_one_of_each_label(conn: Connection) -> None:
    walk = _Walk(conn, _plan(your_options=[]))
    walk.link_report()

    _run, summary = walk.suggest(StubAgentBackend())

    origins = sorted(row["origin"] for row in walk.options())
    assert origins == ["from_evidence_search", "suggested"]
    assert list(summary["report_sections"].values()) == [REPORT_SECTION]


def test_a_failed_suggestion_call_still_leaves_the_user_s_own_options(
    conn: Connection,
) -> None:
    """Own options are minted before the model call; the harness commits them
    with the failure record, so the option searches still have them."""

    class _Down(StubAgentBackend):
        def suggest_options(self, **kwargs: Any) -> SuggestResponse:
            raise RuntimeError("model unavailable")

    walk = _Walk(conn, _plan())
    try:
        walk.suggest(_Down())
    except RuntimeError:
        pass
    else:  # pragma: no cover - the call must fail
        raise AssertionError("suggest did not fail")

    assert sorted((row["origin"], row["name"]) for row in walk.options()) == [
        ("added_by_you", "Youth guarantee"),
        ("added_by_you", "free bus passes for apprentices"),
    ]
