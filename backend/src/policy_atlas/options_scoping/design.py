"""The specified design: an option's defining features (task 045).

One model, three readers: the plan slot *Options you already have in mind*
(``ScopingPlan.your_options[].design``), the option row (Phase 5) and the
option search tool (Phase 4), which runs a targeted walk whose intent is
:meth:`OptionDesign.as_intent`. Support binds to the design, not the name
(ruling 36): two options can share a name and differ by one feature.

The design is Policy Atlas's *reading* of an option — proposed back from the
user's words by ``option_design_v1`` (see
:mod:`policy_atlas.runtime.option_design_prompt`) — so it carries which of
its features were supplied rather than stated (``assumed``), and the product
shows them as such.
"""

from __future__ import annotations

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from policy_atlas.core.prompt_fields import scrub_nul
from policy_atlas.runtime.option_design_prompt import OptionDesignWire

log = structlog.get_logger()

#: A stored design string is bounded so a runaway model output cannot bloat
#: every plan version that carries it. Generous: the prompt asks for 80/240.
DESIGN_TEXT_MAX = 2_000


def _clean(value: str, *, field_name: str) -> str:
    """Return ``value`` stripped, refusing a blank or oversized string."""
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be blank")
    if len(text) > DESIGN_TEXT_MAX:
        raise ValueError(f"{field_name} exceeds {DESIGN_TEXT_MAX} characters")
    return text


class OptionDesign(BaseModel):
    """A specified design: what the option is, as one searchable thing.

    Args:
        name: A short option name a policy reader would recognise.
        description: One sentence: what is done, by whom, for whom.
        design_features: The features that define the option (the offer, the
            obligation, who delivers it …). At least one.
        outcomes_served: Which of the plan's outcomes the option is for.
        assumed: The features Policy Atlas supplied rather than the user
            stated; always a subset of ``design_features``.
        version: The design's version. ``1`` in this slice; a design edit is
            task 3's variant path.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str
    description: str
    design_features: list[str] = Field(min_length=1)
    outcomes_served: list[str] = Field(default_factory=list)
    assumed: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)

    @field_validator("name", "description")
    @classmethod
    def validate_text(cls, value: str, info: object) -> str:
        """Validate a required text field.

        Args:
            value: Candidate text.
            info: Pydantic field metadata.

        Returns:
            The stripped text.

        Raises:
            ValueError: If it is blank or oversized.
        """
        return _clean(value, field_name=getattr(info, "field_name", "design"))

    @field_validator("design_features", "outcomes_served", "assumed")
    @classmethod
    def validate_items(cls, values: list[str], info: object) -> list[str]:
        """Validate a list of short phrases.

        Args:
            values: Candidate phrases.
            info: Pydantic field metadata.

        Returns:
            The stripped phrases, in order.

        Raises:
            ValueError: If a phrase is blank or oversized.
        """
        name = getattr(info, "field_name", "design")
        return [_clean(value, field_name=name) for value in values]

    @model_validator(mode="after")
    def validate_assumed_subset(self) -> OptionDesign:
        """Refuse an ``assumed`` feature the design does not carry.

        Returns:
            The validated design.

        Raises:
            ValueError: If an assumed entry is not one of the design features.
        """
        stray = [item for item in self.assumed if item not in self.design_features]
        if stray:
            raise ValueError(f"assumed names features the design does not carry: {stray}")
        return self

    def as_intent(self) -> str:
        """Return the deterministic intent text a targeted scope searches on.

        One plain paragraph: the name, the one-sentence description, then the
        design features in order. Deterministic — the same design always gives
        the same intent — so an option search is reproducible from the design
        alone (plan S2). Outcomes are not included: the targeted chain's
        screening criteria carry the plan's outcomes.

        Returns:
            The intent paragraph.
        """
        name = self.name.rstrip(" .")
        description = self.description.rstrip()
        if description[-1] not in ".!?":
            description = f"{description}."
        features = "; ".join(feature.rstrip(" .;") for feature in self.design_features)
        return f"{name}. {description} Design features: {features}."

    @classmethod
    def from_wire(cls, wire: OptionDesignWire) -> OptionDesign:
        """Build a design from the ``option_design_v1`` output, fail-closed.

        An ``assumed`` entry that does not match a feature is dropped (and
        logged) rather than failing the whole proposal: the features are the
        design; ``assumed`` only marks which of them to show as supplied.

        Args:
            wire: The parsed model output.

        Returns:
            The validated design at version 1.

        Raises:
            ValueError: If the wire carries no usable name, description or
                feature.
        """
        features = [scrub_nul(item).strip() for item in wire.design_features]
        features = [item for item in features if item]
        assumed = [scrub_nul(item).strip() for item in wire.assumed]
        kept = [item for item in assumed if item in features]
        if len(kept) != len([item for item in assumed if item]):
            log.warning(
                "option_design_assumed_mismatch",
                dropped=len([item for item in assumed if item]) - len(kept),
            )
        outcomes = [scrub_nul(item).strip() for item in wire.outcomes_served]
        return cls.model_validate(
            {
                "name": scrub_nul(wire.name),
                "description": scrub_nul(wire.description),
                "design_features": features,
                "outcomes_served": [item for item in outcomes if item],
                "assumed": kept,
            }
        )
