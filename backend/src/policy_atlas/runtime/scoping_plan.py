"""The options-scoping plan model and its deterministic chain composer.

The second plan payload shape in the same ``plan`` table (task 044, D1). It is
validated and composed exclusively through
:mod:`policy_atlas.runtime.capability_registry`, so no reader ever guesses
which of the two models a stored payload belongs to (C9).

Where the Evidence search plan is a set of rungs the user turns, the scoping
plan is a *description of the problem*: what we are trying to change, who or
what should change, where, and against which outcomes — each tagged with where
it came from, so a thin-context plan stays honest (a guess shown as a guess is
a fine plan; a guess shown as a fact is not).

The chain it compiles to is fixed: ``acquire → screen_abstract → classify →
appraise → ingest_full_text → synthesise``, with synthesise in baseline mode.
Only the baseline runs in this slice; the longlist and the shortlist are
described in :data:`SCOPING_STEPS` and not composed.

This module deliberately does **not** import the capability registry (the
registry imports the plan models, so the dependency runs one way only). The
scoping steer-point names are therefore pinned here as a literal frozenset, in
the way ``task_plan.STEER_POINTS`` is; a guard test asserts the two agree with
the registry's ``options_scoping`` entry.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from policy_atlas.api.contract.task_agent import PlanStep
from policy_atlas.evidence_search.sourcing.country_filters import TIER1_GROUPS
from policy_atlas.evidence_search.synthesis.baseline_prompt import (
    BASELINE_PROPOSED_SECTIONS_MAX,
    BASELINE_SECTIONS,
    BASELINE_TEMPLATE_KEY,
    SOURCES_SECTION_NAV_LABEL,
    SOURCES_SECTION_TITLE,
)
from policy_atlas.runtime.task_agent_scoping_prompt import (
    ScopingConstraintWire,
    ScopingPlanDraftWire,
    TaggedText,
)
from policy_atlas.runtime.task_plan import (
    ComponentStep,
    ComposedChain,
    CountryGroup,
    ScopeConstraints,
    SteeringMode,
    _require_clean_string,
)

#: Where one plan field came from. Shown to the user beside the field.
Origin = Literal["from_your_question", "assumed", "your_call"]

#: What a constraint sentence is *about* — the option's design, what the option
#: does or costs, or where evidence may come from.
ConstraintKind = Literal["requirement", "preference", "evidence_restriction"]

#: When a constraint bites. Fixed by the kind, never chosen independently.
CheckedAt = Literal["longlist", "assessment", "retrieval"]

#: kind → the one stage it is checked at (contract § Plan object). A constraint
#: typed one way and checked at another silently changes what the run excludes,
#: so the pairing is validated rather than trusted.
CHECKED_AT_BY_KIND: dict[ConstraintKind, CheckedAt] = {
    "requirement": "longlist",
    "preference": "assessment",
    "evidence_restriction": "retrieval",
}

#: The scoping steering lattice's point names. Pinned here (not imported from
#: the registry, which imports this module); ``test_scoping_plan.py`` asserts
#: equality with ``steer_points_for("options_scoping")``.
SCOPING_STEER_POINTS: frozenset[str] = frozenset({"baseline_confirm"})

#: The one steer point this slice's chain carries.
BASELINE_CONFIRM = "baseline_confirm"

#: The baseline's per-backend acquisition target by depth (contract § Plan
#: object: execution-bearing, not a plan field). A narrow question about the
#: status quo, not a broad search — the latency lever D7 names first. Phase 7
#: measured one target of 25 (baselines of 4.3 to 7.5 minutes); phase 8 keys it
#: on depth (owner, 2026-09-17: "targets 20 and 10").
BASELINE_ACQUISITION_TARGETS: dict[str, int] = {"standard": 20, "rapid": 10}

#: The coarse band the plan document shows. Replaced by the lead after the
#: Phase 7 measurement; never a promise of a number.
BASELINE_TIME_BAND = "A few minutes · then a check-in"

#: The default jurisdiction, tagged ``assumed`` so the user is asked to check it.
DEFAULT_WHERE_TEXT = "United Kingdom"

#: The six components a scoping walk runs in this slice.
SCOPING_SPINE: tuple[str, ...] = (
    "acquire",
    "screen_abstract",
    "classify",
    "appraise",
    "ingest_full_text",
    "synthesise",
)

#: The three steps the plan document shows. Code-supplied, never authored by
#: the Task Agent: only the first runs in this slice, and a model that could
#: write these sentences could promise work the build does not do.
SCOPING_STEPS: tuple[PlanStep, ...] = (
    PlanStep(
        label="Baseline",
        blurb=(
            "What is in place, the trend, who is affected and what is "
            "contested, from Overton and OpenAlex. The run pauses for you to "
            "question it and confirm the plan."
        ),
        stage="synthesise",
    ),
    PlanStep(
        label="Longlist",
        blurb=(
            "Retrieve, screen on titles and abstracts, read each abstract for "
            "the interventions it names, cluster the mentions into options, "
            "apply the constraints. Not in this release."
        ),
        stage="acquire",
    ),
    PlanStep(
        label="Shortlist and assessment",
        blurb=(
            "Review the proposed reading set. Assessment runs only when you "
            "say so. Not in this release."
        ),
        stage="select",
    ),
)


class Tagged(BaseModel):
    """One plan field with the origin tag the user sees.

    Args:
        text: The field's content, in plain words.
        origin: Where it came from.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    text: str
    origin: Origin

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Validate the field text.

        Args:
            value: Candidate text.

        Returns:
            The validated text.

        Raises:
            ValueError: If it is empty or padded with whitespace.
        """
        return _require_clean_string(value, field_name="text")


class ScopingConstraint(BaseModel):
    """One constraint or preference, typed by what it is about.

    The retrieval fields (``country_group``, the publication-date bounds,
    ``languages``) belong to an evidence restriction alone; a requirement or a
    preference carrying them would claim to filter retrieval and would not.

    Args:
        text: The user's ask, in their words or a plain paraphrase.
        kind: What the constraint is about.
        origin: Where it came from.
        checked_at: When it bites. Pinned to ``kind``.
        country_group: Source-origin restriction, as the ES takes it.
        published_after: ISO date floor for a year restriction.
        published_before: ISO date ceiling for a year restriction.
        languages: Language names. **Stored and shown as not yet applied at
            retrieval** — the ES search grammar has no language filter (C8).
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    text: str
    kind: ConstraintKind
    origin: Origin
    checked_at: CheckedAt
    country_group: CountryGroup | None = None
    published_after: str | None = None
    published_before: str | None = None
    languages: list[str] | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Validate the constraint sentence.

        Args:
            value: Candidate text.

        Returns:
            The validated text.

        Raises:
            ValueError: If it is empty or padded with whitespace.
        """
        return _require_clean_string(value, field_name="constraint.text")

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, value: list[str] | None) -> list[str] | None:
        """Validate the stored language list.

        Args:
            value: Candidate language names, or ``None``.

        Returns:
            The validated list, or ``None``.

        Raises:
            ValueError: If the list is empty or an entry is blank.
        """
        if value is None:
            return None
        if not value:
            raise ValueError("constraint.languages must not be empty; omit the field instead")
        return [_require_clean_string(item, field_name="constraint.languages") for item in value]

    @model_validator(mode="after")
    def validate_kind_pairing(self) -> Self:
        """Pin ``checked_at`` to ``kind`` and fence the retrieval fields.

        Returns:
            The validated constraint.

        Raises:
            ValueError: If ``checked_at`` does not match ``kind``, or a
                non-restriction carries a retrieval field.
        """
        expected = CHECKED_AT_BY_KIND[self.kind]
        if self.checked_at != expected:
            raise ValueError(
                f"constraint kind {self.kind!r} is checked at {expected!r}, "
                f"not {self.checked_at!r}"
            )
        if self.kind != "evidence_restriction":
            supplied = [
                name
                for name in ("country_group", "published_after", "published_before", "languages")
                if getattr(self, name) is not None
            ]
            if supplied:
                raise ValueError(
                    f"only an evidence_restriction may carry {sorted(supplied)}; "
                    f"kind is {self.kind!r}"
                )
        return self


class YourContextEntry(BaseModel):
    """One entry of the user's own context, kept verbatim.

    Args:
        text: The user's words, exactly as written.
        type: Something true now, or something they plan or promise.
        turn_index: The Task Agent turn the entry came from. Kept at entry
            grain (not field grain) because the trust rules read it (C16).
        test_as_condition: True only when the user asked for it to be tested
            against the evidence.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    text: str
    type: Literal["present_fact", "commitment"]
    turn_index: int = Field(ge=0)
    test_as_condition: bool = False

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        """Validate the verbatim entry.

        Args:
            value: Candidate text.

        Returns:
            The text, unchanged — not stripped, not tidied.

        Raises:
            ValueError: If it is blank.
        """
        if not value.strip():
            raise ValueError("your_context.text must not be blank")
        return value


class ScopingSteerPointDefault(BaseModel):
    """A pre-declared standing instruction for a scoping check-in point.

    The Evidence search ``SteerPointDefault`` shape, validated against the
    *scoping* steer points rather than the ES ones (A18d): a flat, global
    point table would let an ES plan pre-declare ``baseline_confirm`` and a
    scoping plan pre-declare ``synthesis_shape``, neither of which their chain
    ever reaches.

    Args:
        steer_point: The point the rule covers.
        action: ``proceed_flag`` — continue and flag. The scoping lattice's only
            point is the baseline gate, and an unattended scoping run always
            records, flags and CONTINUES there (D11, A9), so the hard ``stop``
            the Evidence search table allows is not a declarable scoping action.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    steer_point: str
    action: Literal["proceed_flag"]

    @field_validator("steer_point")
    @classmethod
    def validate_steer_point(cls, value: str) -> str:
        """Validate the point name against the scoping lattice.

        Args:
            value: Candidate point name.

        Returns:
            The validated name.

        Raises:
            ValueError: If it is not a scoping steer point.
        """
        value = _require_clean_string(value, field_name="steer_point")
        if value not in SCOPING_STEER_POINTS:
            raise ValueError(f"steer_point must be one of {sorted(SCOPING_STEER_POINTS)}")
        return value


class BaselineConfirmed(BaseModel):
    """The user's record that a plan version was confirmed against a baseline.

    Written by ``POST /tasks/{id}/plan/confirm-baseline`` as a new approved
    plan version, because the confirmation is plan-scoped: the walk has already
    ended, so there is no ``capability_run`` for a steering event to hang on
    (S4, X5).

    Args:
        artefact_id: The baseline artefact the user read.
        plan_version: The plan version they confirmed.
    """

    # Not strict: this model round-trips through the stored JSON payload, where
    # a UUID is a string. Every other scoping model stays strict.
    model_config = ConfigDict(extra="forbid")

    artefact_id: uuid.UUID
    plan_version: int = Field(ge=1)


class ScopingPlan(BaseModel):
    """The approved options-scoping proposal, compiled into a baseline walk.

    Args:
        title: Short user-visible name for the task.
        question: The user's ask.
        intended_change: What we are trying to change, as one plain sentence.
        target_unit: Who or what should change.
        where: The jurisdiction the policy would apply to.
        outcomes: The outcomes evidence is read against; at least one.
        depth: ``rapid`` or ``standard`` (D6). Depth sets the baseline's
            acquisition target and whether proposed sections are allowed (D7
            as revised 2026-09-17); the seven sections are the same at both.
            Tasks 2 and 3 read it too.
        constraints: Typed constraints and preferences.
        your_context: The user's own situation, verbatim.
        entry_branch: ``explore`` is the only branch in this slice.
        linked_task_ids: The Evidence search tasks this plan starts from.
        steering_mode: As the ES. The scoping default is ``moderate``.
        steer_point_defaults: Standing instructions; ``baseline_confirm``
            accepts one only under ``unattended`` (D11).
        assumptions: Every guess the plan is making, stated plainly.
        steps: The three display steps. Code-supplied.
        time_band: The coarse compute band. Code-supplied.
        source_turn_index: The Task Agent turn that approved this version.
        baseline_confirmed: The confirm-baseline record, once written.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    title: str
    question: str
    intended_change: Tagged
    target_unit: Tagged
    where: Tagged = Field(
        default_factory=lambda: Tagged(text=DEFAULT_WHERE_TEXT, origin="assumed")
    )
    outcomes: list[Tagged] = Field(min_length=1)
    depth: Literal["rapid", "standard"]
    constraints: list[ScopingConstraint] = Field(default_factory=list)
    your_context: list[YourContextEntry] = Field(default_factory=list)
    entry_branch: Literal["explore"] = "explore"
    # Lax for the same reason ``BaselineConfirmed`` is: the stored payload
    # carries these as strings. The relaxation must sit on the ITEM type — a
    # ``strict=False`` on the list field alone leaves the inner UUID strict, and
    # the 044 live check's first linked plan could not be read back (500 on
    # ``GET /plan``).
    linked_task_ids: list[Annotated[uuid.UUID, Field(strict=False)]] = Field(
        default_factory=list
    )
    steering_mode: SteeringMode = "moderate"
    steer_point_defaults: list[ScopingSteerPointDefault] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=lambda: list(SCOPING_STEPS))
    time_band: str = BASELINE_TIME_BAND
    source_turn_index: int | None = None
    baseline_confirmed: BaselineConfirmed | None = None

    @field_validator("title", "question")
    @classmethod
    def validate_required_text(cls, value: str, info: Any) -> str:
        """Validate the required text fields.

        Args:
            value: Candidate value.
            info: Pydantic field metadata.

        Returns:
            The validated string.

        Raises:
            ValueError: If it is empty or padded with whitespace.
        """
        return _require_clean_string(value, field_name=info.field_name)

    @field_validator("assumptions")
    @classmethod
    def validate_assumptions(cls, values: list[str]) -> list[str]:
        """Validate the assumptions list.

        Args:
            values: Candidate assumptions.

        Returns:
            The validated list.

        Raises:
            ValueError: If an entry is empty or padded with whitespace.
        """
        return [_require_clean_string(value, field_name="assumptions") for value in values]

    @model_validator(mode="after")
    def validate_standing_defaults(self) -> Self:
        """Bind the ``baseline_confirm`` standing default to unattended (D11).

        The baseline gate pauses in every attended mode, so a standing default
        there would be a rule that never fires — and, worse, would read on the
        plan as though the run might not stop. Under ``unattended`` the
        converse holds: the run does not pause, and an *undeclared* default
        never happens here, so the rule must be written down.

        Returns:
            The validated plan.

        Raises:
            ValueError: If unattended omits the default, an attended mode
                carries one, or a point is declared twice.
        """
        points = [rule.steer_point for rule in self.steer_point_defaults]
        if len(set(points)) != len(points):
            raise ValueError("steer_point_defaults must not declare a point twice")
        declared = BASELINE_CONFIRM in points
        if self.steering_mode == "unattended" and not declared:
            raise ValueError(
                "an unattended scoping plan must declare a "
                f"{BASELINE_CONFIRM!r} standing default: the run will not pause "
                "at the baseline, and an undeclared default never happens"
            )
        if self.steering_mode != "unattended" and declared:
            raise ValueError(
                f"a {BASELINE_CONFIRM!r} standing default is only valid under "
                f"steering_mode 'unattended'; {self.steering_mode!r} pauses at "
                "the baseline"
            )
        return self


def _tagged_from_wire(value: TaggedText, *, field_name: str) -> Tagged:
    """Map one wire-tagged field onto the closed plan vocabulary.

    Args:
        value: The Task Agent's loose ``{text, origin}`` pair.
        field_name: The plan field, for the error message.

    Returns:
        The validated tagged value.

    Raises:
        ValueError: If ``origin`` is not one of the three tags.
    """
    if value.origin not in ("from_your_question", "assumed", "your_call"):
        raise ValueError(f"{field_name}.origin {value.origin!r} is not a known origin tag")
    return Tagged.model_validate({"text": value.text, "origin": value.origin})


def _constraint_from_wire(wire: ScopingConstraintWire, index: int) -> ScopingConstraint:
    """Map one wire constraint onto the closed plan vocabulary, fail-closed.

    Args:
        wire: The Task Agent's constraint.
        index: Position in the list, for the error message.

    Returns:
        The validated constraint.

    Raises:
        ValueError: If the kind, origin or checked_at is not a known value, or
            the pairing rules reject it.
    """
    if wire.kind not in CHECKED_AT_BY_KIND:
        raise ValueError(f"constraints[{index}].kind {wire.kind!r} is not a known kind")
    group = None
    if wire.country_group is not None:
        raw = wire.country_group.model_dump(exclude_none=True)
        # A pinned Tier-1 label's membership comes from the pinned table, not
        # from the Task Agent, and ``CountryGroup`` refuses any other claim
        # about where it came from.
        raw.setdefault(
            "authorship",
            "pinned-table" if raw.get("label") in TIER1_GROUPS else "planner-proposed",
        )
        group = CountryGroup.model_validate(raw)
    return ScopingConstraint.model_validate(
        {
            "text": wire.text,
            "kind": wire.kind,
            "origin": wire.origin,
            "checked_at": wire.checked_at,
            "country_group": group,
            "published_after": wire.published_after,
            "published_before": wire.published_before,
            "languages": wire.languages,
        }
    )


# The six inputs the baseline is built from (contract deliverable 8, plan S4):
# a change to any of them leaves the baseline stale against the plan that did
# not produce it. Compared deterministically between plan versions; the
# sentence is code-authored so the Task Agent never guesses at it.
BASELINE_INPUT_NAMES: dict[str, str] = {
    "question": "the question",
    "intended_change": "the intended change",
    "target_unit": "who or what should change",
    "where": "Where",
    "outcomes": "the outcomes",
    "evidence_restrictions": "an evidence restriction",
    "depth": "the depth",
}


def baseline_inputs_changed(previous: ScopingPlan, current: ScopingPlan) -> list[str]:
    """Return the screen names of the baseline inputs that differ between two plans.

    Args:
        previous: The plan version the baseline was built from.
        current: The plan version just approved.

    Returns:
        Names in ``BASELINE_INPUT_NAMES`` order; empty when no input moved.
    """

    def restrictions(plan: ScopingPlan) -> list[tuple[Any, ...]]:
        return sorted(
            (
                c.text,
                c.country_group.model_dump(mode="json") if c.country_group else None,
                c.published_after,
                c.published_before,
                tuple(c.languages or ()),
            )
            for c in plan.constraints
            if c.kind == "evidence_restriction"
        )

    probes: dict[str, tuple[Any, Any]] = {
        "question": (previous.question, current.question),
        "intended_change": (previous.intended_change.text, current.intended_change.text),
        "target_unit": (previous.target_unit.text, current.target_unit.text),
        "where": (previous.where.text, current.where.text),
        "outcomes": ([o.text for o in previous.outcomes], [o.text for o in current.outcomes]),
        "evidence_restrictions": (restrictions(previous), restrictions(current)),
        "depth": (previous.depth, current.depth),
    }
    return [BASELINE_INPUT_NAMES[k] for k, (a, b) in probes.items() if a != b]


def baseline_inputs_sentence(changed: list[str], built_from: int) -> str:
    """The code-authored sentence the Task Agent's reply carries after a plan change.

    Args:
        changed: The output of :func:`baseline_inputs_changed`.
        built_from: The plan version the existing baseline was built from.
    """
    if changed:
        return (
            f"This change touches what the baseline (built from plan version {built_from}) "
            f"was built from: {', '.join(changed)}. You can rebuild the baseline, or confirm "
            "the plan against it as it stands."
        )
    return (
        f"This change does not touch what the baseline (built from plan version {built_from}) "
        "was built from. You can confirm the plan against it as it stands, or rebuild it."
    )


def wire_draft_from_plan(plan: ScopingPlan) -> dict[str, Any]:
    """Project an approved scoping plan back into the Task Agent's wire draft.

    The successor conversation after a finished walk is seeded from the
    executed plan (as the Evidence search seeds from ``TaskPlan``): the draft
    the model sees is the plan's own fields in ``ScopingPlanDraftWire`` shape,
    so an edit after the baseline starts from what ran, not from nothing.

    Args:
        plan: The approved scoping plan.

    Returns:
        A ``ScopingPlanDraftWire``-shaped dict (JSON types only).
    """
    payload = plan.model_dump(mode="json")
    constraints = []
    for c in payload.get("constraints", []):
        group = c.get("country_group")
        constraints.append(
            {
                "text": c["text"],
                "kind": c["kind"],
                "origin": c["origin"],
                "checked_at": c["checked_at"],
                "country_group": (
                    {"label": group["label"], "countries": group.get("countries")}
                    if isinstance(group, dict)
                    else None
                ),
                "published_after": c.get("published_after"),
                "published_before": c.get("published_before"),
                "languages": c.get("languages"),
            }
        )
    return {
        "title": payload.get("title"),
        "question": payload.get("question"),
        "intended_change": payload.get("intended_change"),
        "target_unit": payload.get("target_unit"),
        "where": payload.get("where"),
        "outcomes": payload.get("outcomes"),
        "depth": payload.get("depth"),
        "constraints": constraints,
        "your_context": [
            {"text": e["text"], "type": e["type"], "test_as_condition": e["test_as_condition"]}
            for e in payload.get("your_context", [])
        ],
        "steering_mode": payload.get("steering_mode"),
        "steer_point_defaults": [
            {"steer_point": d["steer_point"], "action": d["action"]}
            for d in payload.get("steer_point_defaults", [])
        ]
        or None,
        "assumptions": payload.get("assumptions") or None,
    }


def build_scoping_plan(
    draft: ScopingPlanDraftWire,
    *,
    linked_task_ids: list[uuid.UUID] | None = None,
    source_turn_index: int | None = None,
) -> ScopingPlan:
    """Build the executable scoping plan from a ready draft, fail-closed.

    Mirrors ``agent.build_plan``: the Task Agent's draft is loose (every field
    optional, every enum a bare string) and this is where it becomes a plan or
    fails. It supplies the code-owned fields — the three steps, the time band
    and the default ``where`` — which the prompt is explicitly told not to
    author.

    Args:
        draft: The Task Agent's ready plan draft.
        linked_task_ids: The tasks this plan starts from, from ``task_link``.
        source_turn_index: The turn that produced this payload.

    Returns:
        The validated scoping plan.

    Raises:
        ValueError: If a wire enum string is not a known value.
        ValidationError: If the draft is not a complete scoping plan (no
            depth, no target unit, no outcomes, an unattended plan without its
            standing default, …).
    """
    data: dict[str, Any] = {
        "title": draft.title or (draft.question or "").strip()[:80] or "Options scoping",
        "question": draft.question,
        "depth": draft.depth,
        "steps": [step.model_dump() for step in SCOPING_STEPS],
        "time_band": BASELINE_TIME_BAND,
        "linked_task_ids": list(linked_task_ids or []),
        "source_turn_index": source_turn_index,
    }
    if draft.intended_change is not None:
        data["intended_change"] = _tagged_from_wire(
            draft.intended_change, field_name="intended_change"
        )
    if draft.target_unit is not None:
        data["target_unit"] = _tagged_from_wire(draft.target_unit, field_name="target_unit")
    data["where"] = (
        _tagged_from_wire(draft.where, field_name="where")
        if draft.where is not None
        else Tagged(text=DEFAULT_WHERE_TEXT, origin="assumed")
    )
    if draft.outcomes is not None:
        data["outcomes"] = [
            _tagged_from_wire(item, field_name=f"outcomes[{i}]")
            for i, item in enumerate(draft.outcomes)
        ]
    if draft.constraints is not None:
        data["constraints"] = [
            _constraint_from_wire(wire, index) for index, wire in enumerate(draft.constraints)
        ]
    if draft.your_context is not None:
        data["your_context"] = [
            YourContextEntry.model_validate(
                {
                    "text": entry.text,
                    "type": entry.type,
                    "turn_index": source_turn_index or 0,
                    "test_as_condition": entry.test_as_condition,
                }
            )
            for entry in draft.your_context
        ]
    if draft.steering_mode is not None:
        data["steering_mode"] = draft.steering_mode
    if draft.steer_point_defaults is not None:
        data["steer_point_defaults"] = [
            {"steer_point": rule.steer_point, "action": rule.action}
            for rule in draft.steer_point_defaults
        ]
    if draft.assumptions is not None:
        data["assumptions"] = list(draft.assumptions)
    return ScopingPlan.model_validate({k: v for k, v in data.items() if v is not None})


def scope_constraints_for(plan: ScopingPlan) -> ScopeConstraints:
    """Compile the plan's evidence restrictions into the ES search grammar.

    Only the two dimensions the ES search grammar actually has survive:
    source-origin groups and publication years. A **language restriction is
    deliberately not passed** (C8) — the grammar has no language filter, and
    compiling one into a filter it does not have would claim a narrowing the
    run never performs. It stays on the plan and is shown as *not yet applied
    at retrieval*.

    Args:
        plan: The validated scoping plan.

    Returns:
        The compiled constraints; empty when the plan restricts nothing.
    """
    values: dict[str, Any] = {}
    for constraint in plan.constraints:
        if constraint.kind != "evidence_restriction":
            continue
        if constraint.country_group is not None:
            values["country_group"] = constraint.country_group
        if constraint.published_after is not None:
            values["published_after"] = constraint.published_after
        if constraint.published_before is not None:
            values["published_before"] = constraint.published_before
    return ScopeConstraints.model_validate(values)


def _baseline_section_directives() -> list[dict[str, Any]]:
    """Return the supplied baseline section specs, in the ruled order.

    Returns:
        One ``{title, focus, nav_label, turn_cap}`` object per model-written
        section, with the code-rendered Sources section last. The per-section
        turn cap travels with the section rather than being inferred at
        execution: the plan's directive is the whole of what synthesise runs.
    """
    sections: list[dict[str, Any]] = [
        {
            "title": s.title,
            "focus": s.focus,
            "nav_label": s.nav_label,
            "turn_cap": s.turn_cap,
        }
        for s in BASELINE_SECTIONS
    ]
    sections.append(
        {
            "title": SOURCES_SECTION_TITLE,
            "focus": "rendered by code",
            "nav_label": SOURCES_SECTION_NAV_LABEL,
        }
    )
    return sections


def _screening_criteria(plan: ScopingPlan) -> list[str]:
    """Compose the baseline's visible screening criteria.

    One status-quo criterion always, plus each source-origin restriction as a
    setting criterion — mirroring the Evidence search's own OECD pattern, and
    only for restrictions the ES already expresses that way. A year restriction
    is already a retrieval filter; repeating it as a screening sentence would
    have the model re-judge what the search grammar has excluded. A language
    restriction is not a criterion at all (C8).

    Args:
        plan: The validated scoping plan.

    Returns:
        The screening criteria, in order.
    """
    criteria = [
        "The document reports on the current situation, trend or drivers for "
        f"{plan.target_unit.text} in {plan.where.text}, or on the same problem "
        "in a comparable setting."
    ]
    for constraint in plan.constraints:
        if constraint.kind == "evidence_restriction" and constraint.country_group is not None:
            criteria.append(constraint.text)
    return criteria


def _scoping_directive_delta(component: str, plan: ScopingPlan) -> dict[str, Any]:
    if component == "acquire":
        search: dict[str, Any] = {
            "depth": "rapid",
            "record_cap": BASELINE_ACQUISITION_TARGETS[plan.depth],
        }
        filters = scope_constraints_for(plan).to_filters()
        if filters:
            search["filters"] = filters
        return {"search": search}
    if component == "screen_abstract":
        return {"screening": {"criteria": _screening_criteria(plan)}}
    if component == "synthesise":
        synthesis: dict[str, Any] = {
            "template": BASELINE_TEMPLATE_KEY,
            "sections": _baseline_section_directives(),
        }
        # Proposed sections are a standard-depth allowance; a rapid directive
        # carries no budget and synthesise makes no proposal call (phase 8).
        if plan.depth == "standard":
            synthesis["section_budget"] = BASELINE_PROPOSED_SECTIONS_MAX
        return {"synthesis": synthesis}
    return {}


def compose_scoping(plan: ScopingPlan) -> ComposedChain:
    """Compose an approved scoping plan into the fixed baseline chain.

    Args:
        plan: The validated scoping plan.

    Returns:
        The six-step chain ``acquire → screen_abstract → classify → appraise →
        ingest_full_text → synthesise`` and nothing else. There are no
        discretionary components. Depth (D7, revised 2026-09-17) changes the
        acquire target and the proposed-section allowance inside the
        directives, never the chain or the section list.
    """
    return ComposedChain(
        steps=[
            ComponentStep(
                component=component,
                directive_delta=_scoping_directive_delta(component, plan),
                reference_rule=(
                    "deepest_successful_reference" if component == "synthesise" else None
                ),
            )
            for component in SCOPING_SPINE
        ]
    )
