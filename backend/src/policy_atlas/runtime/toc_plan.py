"""The theory-of-change plan model and its deterministic chain composer (task 054).

The third plan payload shape in the ``plan`` table, validated and composed only
through :mod:`policy_atlas.runtime.capability_registry` (the registry imports
this module, never the reverse).

A theory of change runs two walks (C3), told apart by the intent record's
``purpose = 'toc'`` and ``context.toc_walk``:

- ``draft``: ``inherit`` (only when the task starts from an option) →
  ``toc_draft``. Pasted text in the existing-theory entry point drafts too: the
  draft prompt keeps the user's words (``toc_import`` is increment 5).
- ``check``: ``toc_select → toc_discover → toc_merge → toc_search_new →
  toc_judge → classify → appraise → toc_choose → toc_summarise`` (C31, C32). With ``context.links``
  (Search for more) the same chain without discover, merge and choose.

The item searches a check walk dispatches are ``targeted`` walks with
``acquire_only`` in their context; each runs ``acquire`` alone at the
``link`` search depth (C27). They are a runner stage, not a chain step (S3).
``toc_select`` keeps every document they acquired, with no model call.

The lattice is empty (C12): a theory-of-change walk never pauses, so the plan
is always ``unattended`` and declares no standing defaults.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from policy_atlas.runtime.scoping_plan import (
    ACQUIRE_ONLY_KEY,
    TARGETED_PURPOSE,
    ScopingSteerPointDefault,
    _clean,
    _not_blank,
)
from policy_atlas.runtime.task_plan import (
    ComponentStep,
    ComposedChain,
    CountryGroup,
    ScopeConstraints,
)
from policy_atlas.theory_of_change.evidence.item_search_prompt import ITEM_SEARCH_GUIDANCE

#: The intent-record purpose of every main theory-of-change walk.
TOC_PURPOSE = "toc"

#: The intent-record context key that names the walk kind.
TOC_WALK_KEY = "toc_walk"

#: The walk kinds (C3, C19). ``recheck`` arrives in increment 2.
TOC_WALK_DRAFT = "draft"
TOC_WALK_CHECK = "check"
TOC_WALK_RECHECK = "recheck"

#: The intent-record context key naming the links a check walk covers.
TOC_LINKS_KEY = "links"

#: Records each item search may keep per backend: every distinct result of
#: its five calls (C27, C31). ``toc_select`` then picks the documents judged.
TOC_ITEM_RECORD_CAP = 60

#: Links judged per check walk at most (C5).
TOC_LINK_CAP = 80

#: The check walk's chain. Discover and summarise degrade the walk when they
#: fail; every other step fails it.
TOC_CHECK_CHAIN: tuple[tuple[str, bool], ...] = (
    ("toc_select", True),
    ("toc_discover", False),
    ("toc_merge", True),
    # The links discovery added get their own search and pick (C32).
    ("toc_search_new", False),
    ("toc_judge", True),
    # Classify and appraise read only what the judge found on topic (C31).
    ("classify", True),
    ("appraise", True),
    ("toc_choose", True),
    ("toc_summarise", False),
)

#: The steps a named-link check (Search for more) leaves out.
_NAMED_LINK_SKIPS = frozenset({"toc_discover", "toc_merge", "toc_search_new", "toc_choose"})

EntryPoint = Literal["outcome_first", "intervention_first", "existing_theory"]


class TocEvidenceRestriction(BaseModel):
    """Where evidence may come from: the retrieval half of the OS restriction.

    Args:
        country_group: Source-origin restriction, as the Evidence search takes it.
        published_after: ISO date floor.
        published_before: ISO date ceiling.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    country_group: CountryGroup | None = None
    published_after: str | None = None
    published_before: str | None = None

    @model_validator(mode="after")
    def validate_compiles(self) -> Self:
        """Fail at plan time on a value the search grammar would refuse.

        Returns:
            The validated restriction.
        """
        ScopeConstraints.model_validate(self.model_dump(exclude_none=True))
        return self


class TocFromOption(BaseModel):
    """The Options scoping option a theory starts from (C13; increment 7).

    Args:
        source_task_id: The options-scoping task.
        source_option_id: The option on it.
    """

    model_config = ConfigDict(extra="forbid")

    source_task_id: uuid.UUID
    source_option_id: uuid.UUID


class TocPlan(BaseModel):
    """The approved theory-of-change plan (S2; spec § Plan slots).

    Args:
        title: Short user-visible name for the task.
        question: The user's ask.
        entry_point: Where the theory starts from.
        intended_change: The impact, in measurable words.
        target_population: Who the change is for.
        intervention: The intervention; required for ``intervention_first``.
        dosage: How much of the intervention, when known.
        existing_theory_text: A pasted theory, kept verbatim.
        upload_id: An uploaded theory (increment 5).
        where: The place the theory is for. Steers the search; never excludes.
        time_horizon: When the impact is expected.
        context: What the user knows about the setting.
        evidence_restriction: Where evidence may come from.
        from_option: The option the task starts from; ``None`` until increment 7.
        steering_mode: Always ``unattended``: the lattice is empty (C12).
        steer_point_defaults: Always empty: there is no point to declare.
        source_turn_index: The Task Agent turn that approved this version.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    title: Annotated[str, _clean("title")]
    question: Annotated[str, _clean("question")]
    entry_point: EntryPoint
    intended_change: Annotated[str, _clean("intended_change")]
    target_population: Annotated[str, _clean("target_population")]
    intervention: Annotated[str, _clean("intervention")] | None = None
    dosage: Annotated[str, _clean("dosage")] | None = None
    existing_theory_text: Annotated[str, _not_blank("existing_theory_text")] | None = None
    # Lax: the stored payload carries UUIDs as strings (see ``ScopingPlan``).
    upload_id: Annotated[uuid.UUID, Field(strict=False)] | None = None
    where: Annotated[str, _clean("where")] | None = None
    time_horizon: Annotated[str, _clean("time_horizon")] | None = None
    context: Annotated[str, _clean("context")] | None = None
    evidence_restriction: TocEvidenceRestriction | None = None
    from_option: TocFromOption | None = None
    steering_mode: Literal["unattended"] = "unattended"
    steer_point_defaults: list[ScopingSteerPointDefault] = Field(
        default_factory=list, max_length=0
    )
    source_turn_index: int | None = None

    @property
    def ready(self) -> bool:
        """Whether the plan can start a draft (spec § Plan slots).

        ``intended_change`` and ``target_population`` are required fields, so
        what is left is the entry point's own slot: the intervention for
        ``intervention_first``, the theory itself for ``existing_theory``.

        Returns:
            True when the entry point's slot is filled.
        """
        if self.entry_point == "intervention_first":
            return self.intervention is not None
        if self.entry_point == "existing_theory":
            return self.existing_theory_text is not None or self.upload_id is not None
        return True


def toc_scope_constraints(plan: TocPlan) -> ScopeConstraints:
    """Compile the plan's evidence restriction into the Evidence search grammar.

    Args:
        plan: The validated plan.

    Returns:
        The compiled constraints; empty when the plan restricts nothing.
    """
    restriction = plan.evidence_restriction
    if restriction is None:
        return ScopeConstraints()
    return ScopeConstraints.model_validate(restriction.model_dump(exclude_none=True))


def _item_search_directive(plan: TocPlan) -> dict[str, Any]:
    """One item search's acquire directive (``depth · filters · guidance · record_cap``)."""
    search: dict[str, Any] = {
        "depth": "link",
        "record_cap": TOC_ITEM_RECORD_CAP,
        "guidance": list(ITEM_SEARCH_GUIDANCE),
    }
    filters = toc_scope_constraints(plan).to_filters()
    if filters:
        search["filters"] = filters
    return search


def _chain(steps: list[tuple[str, bool]], plan: TocPlan) -> ComposedChain:
    def delta(component: str) -> dict[str, Any]:
        if component == "acquire":
            return {"search": _item_search_directive(plan)}
        return {}

    return ComposedChain(
        steps=[
            ComponentStep(component=component, directive_delta=delta(component), spine=spine)
            for component, spine in steps
        ]
    )


def compose_toc(
    plan: TocPlan,
    purpose: str | None = None,
    context: Mapping[str, Any] | None = None,
) -> ComposedChain:
    """Compose an approved plan into the chain its intent record names (S3).

    Args:
        plan: The validated plan.
        purpose: The intent record's ``purpose``: ``toc`` for a main walk,
            ``targeted`` for an item search.
        context: The intent record's ``context``: ``toc_walk`` (and ``links``)
            for a main walk, ``acquire_only`` for an item search.

    Returns:
        The composed chain, every step with its spine flag.

    Raises:
        ValueError: If the purpose and context name no chain this build
            composes.
    """
    context = context or {}
    if purpose == TOC_PURPOSE:
        walk = context.get(TOC_WALK_KEY)
        if walk == TOC_WALK_DRAFT:
            steps = [("inherit", True)] if plan.from_option is not None else []
            return _chain([*steps, ("toc_draft", True)], plan)
        if walk == TOC_WALK_CHECK:
            if context.get(TOC_LINKS_KEY):
                return _chain(
                    [step for step in TOC_CHECK_CHAIN if step[0] not in _NAMED_LINK_SKIPS], plan
                )
            return _chain(list(TOC_CHECK_CHAIN), plan)
        if walk == TOC_WALK_RECHECK:
            raise ValueError("the recheck walk lands in increment 2")
        raise ValueError(f"no theory-of-change walk {walk!r}")
    if purpose == TARGETED_PURPOSE and context.get(ACQUIRE_ONLY_KEY) is True:
        return _chain([("acquire", True)], plan)
    raise ValueError(f"no theory-of-change chain for intent-record purpose {purpose!r}")
