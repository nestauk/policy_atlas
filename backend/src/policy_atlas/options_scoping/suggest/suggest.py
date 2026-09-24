"""The ``suggest`` component: the longlist walk's entrants (task 045, S10).

Contract D7 and A15, ADR 0039: the longlist walk's second step (after
``inherit``, non-spine) makes **one** judgment-model call over the plan, the
baseline's sections and each linked Evidence search report
(``longlist_suggest_v1``), and mints the **entrants** as option rows:

- each suggestion, ``origin="suggested"`` (source ``model``) or
  ``origin="from_evidence_search"`` (source ``linked_report``, the report
  section named), up to :data:`SUGGEST_BOUND`;
- each of the plan's own options (*Options you already have in mind*),
  ``origin="added_by_you"``, with the design ``option_design_v1`` proposed
  back when the plan version was approved.

The report is context for the model, never a source of records: nothing
here writes a profile record, a membership or anything else from report
text (owner: "the source would be the AI written synthesis").

**Rebuild** (D14): the model is shown every option already on the task
(``existing_options``) and told not to propose one again; in code, a
suggestion whose name or description matches an existing option's
(case-insensitive, whitespace collapsed) is dropped, so a rebuild mints only
genuinely new suggestions — the existing options stay as they are (ids,
state, design) and reach the longlist as its seeds. The plan's own options
are matched by ``(origin, name)``: an existing row is kept and is an entrant
again; no duplicate is minted.

**Where the report section lives.** The ``option`` table has no provenance
column, and the design column holds a strict :class:`OptionDesign`; the
section is therefore recorded in this run's ``component.completed`` summary
under ``report_sections`` (``{option_id: heading}``), which the row's
``created_by_run_id`` finds for a row this run minted. No schema change.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.prompt_fields import scrub_nul
from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    option,
    runs,
    synthesis_result,
    task_plan,
)
from policy_atlas.options_scoping.design import DESIGN_TEXT_MAX, OptionDesign
from policy_atlas.options_scoping.suggest.suggest_prompt import (
    SUGGEST_BOUND,
    LinkedReportContext,
    SuggestedOptionWire,
    SuggestPlanContext,
    SuggestResponse,
)
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, validate_plan
from policy_atlas.runtime.inherit import linked_reports, report_sections_from_blocks
from policy_atlas.runtime.scoping_plan import ScopingPlan, YourOption

log = structlog.get_logger()

EntrantOrigin = Literal["added_by_you", "from_evidence_search", "suggested"]

#: Entrant order in ``entrants``: the user's own, then the report's, then the
#: model's — the order the option-search cap keeps (A16: the user's and the
#: report's are never dropped).
ENTRANT_ORDER: tuple[EntrantOrigin, ...] = ("added_by_you", "from_evidence_search", "suggested")


class SuggestBackend(Protocol):
    """The judgment-model seam the ``suggest`` step calls.

    Satisfied by :class:`~policy_atlas.runtime.agent_backend.OpenAIAgentBackend`
    (live) and :class:`~policy_atlas.runtime.agent_backend.StubAgentBackend`.
    """

    def suggest_options(
        self,
        *,
        plan: SuggestPlanContext,
        baseline_sections: list[tuple[str, str]],
        linked_reports: list[LinkedReportContext],
        bound: int = SUGGEST_BOUND,
        session_id: uuid.UUID | None = None,
    ) -> SuggestResponse:
        """Return the model's suggested options.

        Args:
            plan: The plan fields the step reads.
            baseline_sections: ``(title, markdown)`` per baseline section.
            linked_reports: One entry per linked report, in link order.
            bound: The suggestion bound.
            session_id: Optional Langfuse session id (the task id).

        Returns:
            The parsed suggestions.
        """
        ...


@dataclass
class SuggestContext:
    """Scope-level input to a ``suggest`` run.

    Attributes:
        scope_id: The longlist walk's intent record.
        intent: Its intent text (unused: the plan is read whole).
        context: Its context JSONB (unused: ``suggest`` reads no directive).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass(frozen=True)
class _Entrant:
    origin: EntrantOrigin
    design: OptionDesign
    report_section: str | None = None


def walk_plan(
    conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID, scope_id: uuid.UUID
) -> ScopingPlan:
    """Read the scoping plan the walk runs on.

    The walk's own plan version (``capability_run.plan_id`` through the run
    row), else the intent record's ``plan_id``.

    Args:
        conn: Open connection.
        task_id: The scoping task.
        run_id: This component run.
        scope_id: The walk's intent record.

    Returns:
        The validated plan.

    Raises:
        ValueError: If no plan version can be found for the walk.
    """
    plan_id = conn.execute(
        select(capability_run.c.plan_id)
        .select_from(
            runs.join(
                capability_run,
                (capability_run.c.capability_run_id == runs.c.capability_run_id)
                & (capability_run.c.task_id == runs.c.task_id),
            )
        )
        .where(runs.c.run_id == run_id, runs.c.task_id == task_id)
    ).scalar_one_or_none()
    if plan_id is None:
        plan_id = conn.execute(
            select(evidence_scope.c.plan_id).where(
                evidence_scope.c.evidence_scope_id == scope_id,
                evidence_scope.c.task_id == task_id,
            )
        ).scalar_one_or_none()
    payload = (
        conn.execute(
            select(task_plan.c.payload).where(
                task_plan.c.plan_id == plan_id, task_plan.c.task_id == task_id
            )
        ).scalar_one_or_none()
        if plan_id is not None
        else None
    )
    if payload is None:
        raise ValueError("suggest: no plan version found for the walk")
    plan = validate_plan(OPTIONS_SCOPING, payload)
    if not isinstance(plan, ScopingPlan):  # pragma: no cover - the registry's model
        raise ValueError("suggest: the walk's plan is not a scoping plan")
    return plan


def suggest_plan_context(
    plan: ScopingPlan, existing_options: list[dict[str, str]] | None = None
) -> SuggestPlanContext:
    """Project the plan onto the fields the suggest prompt reads.

    Args:
        plan: The scoping plan.
        existing_options: The task's option rows already on the longlist
            (``{"name", "description"}`` each), which the model must not
            propose again; empty on a first build.

    Returns:
        The question, intended change, target unit, outcomes, the requirement
        constraints' texts, Your context's texts, the user's own options as
        ``{text, design}`` data and the existing options.
    """
    return SuggestPlanContext(
        question=plan.question,
        intended_change=plan.intended_change.text,
        target_unit=plan.target_unit.text,
        outcomes=[outcome.text for outcome in plan.outcomes],
        requirements=[c.text for c in plan.constraints if c.kind == "requirement"],
        your_context=[entry.text for entry in plan.your_context],
        your_options=[
            {
                "text": own.text,
                "design": own.design.model_dump(mode="json") if own.design else None,
            }
            for own in plan.your_options
        ],
        existing_options=list(existing_options or []),
    )


def baseline_sections(conn: Connection, task_id: uuid.UUID) -> list[tuple[str, str]]:
    """Return the task's baseline as ``(title, markdown)`` sections.

    The baseline is the scoping task's Result artefact — the latest synthesis
    the task holds, the one ``artefact_out`` renders (a scoping task
    synthesises only in its baseline walk). Rendered like a linked report.

    Args:
        conn: Open connection.
        task_id: The scoping task.

    Returns:
        One pair per baseline section in document order; empty when there is
        no baseline.
    """
    blocks = conn.execute(
        select(synthesis_result.c.blocks)
        .where(synthesis_result.c.task_id == task_id)
        .order_by(
            synthesis_result.c.created_at.desc(),
            synthesis_result.c.synthesis_result_id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    return report_sections_from_blocks(conn, blocks)


def _own_option_design(own: YourOption) -> tuple[OptionDesign, bool]:
    """Return the design an own option enters with, and whether it fell back.

    The design is normally present: ``ensure_option_designs`` runs when a plan
    version is approved. A failed proposal leaves it ``None``; the step runs
    inside the component transaction, so it does not call the model again —
    the option still becomes an entrant, on a design read straight from the
    user's words (name, description and one feature: the words; nothing
    assumed), so its option search searches on the words.
    """
    if own.design is not None:
        return own.design, False
    words = " ".join(own.text.split())[:DESIGN_TEXT_MAX]
    return (
        OptionDesign(name=words, description=words, design_features=[words], assumed=[]),
        True,
    )


def _headings(reports: list[LinkedReportContext]) -> dict[str, str]:
    """Each linked report's section headings, keyed by a normalised form."""
    headings: dict[str, str] = {}
    for report in reports:
        for line in report.report_markdown.splitlines():
            if line.startswith("## ") and line[3:].strip():
                heading = line[3:].strip()
                headings.setdefault(_norm(heading), heading)
    return headings


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def _suggested_entrant(
    wire: SuggestedOptionWire,
    *,
    headings: dict[str, str],
    has_reports: bool,
) -> _Entrant | None:
    """Turn one suggestion into an entrant, or ``None`` when it is unusable."""
    try:
        design = OptionDesign(
            name=scrub_nul(wire.name),
            description=scrub_nul(wire.description),
            design_features=[scrub_nul(item) for item in wire.design_features if item.strip()],
            outcomes_served=[
                scrub_nul(item) for item in wire.outcomes_served if item.strip()
            ],
            assumed=[],
        )
    except ValidationError:
        log.warning("suggest.suggestion_invalid")
        return None
    if wire.source == "model":
        return _Entrant(origin="suggested", design=design)
    if not has_reports:
        # Nothing was linked, so nothing can be "from your evidence search".
        log.warning("suggest.report_source_without_report")
        return _Entrant(origin="suggested", design=design)
    section = headings.get(_norm(wire.report_section or ""))
    if section is None:
        log.warning("suggest.report_section_unmatched")
    return _Entrant(origin="from_evidence_search", design=design, report_section=section)


def _mint(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    entrant: _Entrant,
    existing: dict[tuple[str, str], uuid.UUID],
) -> tuple[uuid.UUID, bool]:
    """Insert one entrant's option row, or return the existing one (D14)."""
    key = (entrant.origin, entrant.design.name)
    if key in existing:
        return existing[key], False
    option_id = uuid.uuid4()
    now = datetime.now(UTC)
    conn.execute(
        option.insert().values(
            option_id=option_id,
            task_id=task_id,
            name=entrant.design.name,
            description=entrant.design.description,
            design=entrant.design.model_dump(mode="json"),
            design_version=entrant.design.version,
            outcomes=list(entrant.design.outcomes_served),
            origin=entrant.origin,
            state="included",
            secondary_lever_types=[],
            created_by_run_id=run_id,
            created_at=now,
            updated_at=now,
        )
    )
    existing[key] = option_id
    return option_id, True


def suggest_options(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: SuggestContext,
    backend: SuggestBackend,
) -> dict[str, Any]:
    """Suggest options and mint the longlist walk's entrants.

    The plan's own options are minted **before** the model call: a failed
    call fails the step (non-spine, so the walk degrades) but the harness
    commits the step's transaction with its failure record, so the user's own
    options still stand as ``added_by_you`` rows for the option searches.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The scoping task.
        run_id: This ``suggest`` run (``option.created_by_run_id``).
        context: The walk's intent record.
        backend: The judgment-model seam.

    Returns:
        The component summary: ``suggested``, ``from_report`` and
        ``added_by_you`` (entrants of each origin this run), ``minted`` and
        ``kept`` (new rows and rows a rebuild kept), ``dropped`` (unusable,
        repeated or over-bound suggestions), ``own_without_design`` (own
        options that entered on their words), ``entrants`` (option ids as
        strings: the user's first, then the report's, then the model's) and
        ``report_sections`` (``{option_id: heading}`` for the report's; a
        heading the model named but no linked report carries is ``None``).
    """
    plan = walk_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    # Every option already on the task, every origin, in creation order: on a
    # rebuild the model is shown them and must not propose one again; a
    # suggestion repeating one by name or description is dropped in code too.
    prior_rows = conn.execute(
        select(option.c.option_id, option.c.origin, option.c.name, option.c.description)
        .where(option.c.task_id == task_id)
        .order_by(option.c.created_at, option.c.option_id)
    ).all()
    existing: dict[tuple[str, str], uuid.UUID] = {
        (row.origin, row.name): row.option_id
        for row in prior_rows
        if row.origin in ENTRANT_ORDER
    }
    existing_options = [
        {"name": row.name, "description": row.description} for row in prior_rows
    ]
    prior_descriptions = {_norm(row.description) for row in prior_rows}
    counts = dict.fromkeys(ENTRANT_ORDER, 0)
    minted = 0
    minted_ids: dict[EntrantOrigin, list[str]] = {origin: [] for origin in ENTRANT_ORDER}
    report_sections: dict[str, str | None] = {}

    def _enter(entrant: _Entrant) -> None:
        nonlocal minted
        option_id, created = _mint(
            conn, task_id=task_id, run_id=run_id, entrant=entrant, existing=existing
        )
        minted += int(created)
        counts[entrant.origin] += 1
        minted_ids[entrant.origin].append(str(option_id))
        if entrant.origin == "from_evidence_search":
            report_sections[str(option_id)] = entrant.report_section

    taken: set[str] = {_norm(row.name) for row in prior_rows}
    own_taken: set[str] = set()
    fallback_designs = 0
    for own in plan.your_options:
        design, fell_back = _own_option_design(own)
        if _norm(design.name) in own_taken:
            continue
        own_taken.add(_norm(design.name))
        taken.add(_norm(design.name))
        fallback_designs += int(fell_back)
        _enter(_Entrant(origin="added_by_you", design=design))
    if fallback_designs:
        log.warning("suggest.own_option_without_design", count=fallback_designs)

    reports = [
        LinkedReportContext(title=title, report_markdown=markdown)
        for title, markdown in linked_reports(conn, task_id)
    ]
    response = backend.suggest_options(
        plan=suggest_plan_context(plan, existing_options),
        baseline_sections=baseline_sections(conn, task_id),
        linked_reports=reports,
        bound=SUGGEST_BOUND,
        session_id=task_id,
    )

    headings = _headings(reports)
    dropped = max(len(response.options) - SUGGEST_BOUND, 0)
    for wire in response.options[:SUGGEST_BOUND]:
        entrant = _suggested_entrant(wire, headings=headings, has_reports=bool(reports))
        if (
            entrant is None
            or _norm(entrant.design.name) in taken
            or _norm(entrant.design.description) in prior_descriptions
        ):
            dropped += 1
            continue
        taken.add(_norm(entrant.design.name))
        prior_descriptions.add(_norm(entrant.design.description))
        _enter(entrant)

    log.info(
        "suggest.entrants",
        task_id=str(task_id),
        suggested=counts["suggested"],
        from_report=counts["from_evidence_search"],
        added_by_you=counts["added_by_you"],
        minted=minted,
        dropped=dropped,
    )
    entrants = [option_id for origin in ENTRANT_ORDER for option_id in minted_ids[origin]]
    return {
        "suggested": counts["suggested"],
        "from_report": counts["from_evidence_search"],
        "added_by_you": counts["added_by_you"],
        "minted": minted,
        "kept": len(entrants) - minted,
        "dropped": dropped,
        "own_without_design": fallback_designs,
        "entrants": entrants,
        "report_sections": report_sections,
    }
