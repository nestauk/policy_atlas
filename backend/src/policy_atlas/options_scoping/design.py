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

from typing import Annotated

import structlog
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from policy_atlas.core.prompt_fields import scrub_nul
from policy_atlas.runtime.option_design_prompt import OptionDesignWire

log = structlog.get_logger()

#: A stored design string is bounded so a runaway model output cannot bloat
#: every plan version that carries it. Generous: the prompt asks for 80/240.
DESIGN_TEXT_MAX = 2_000


#: A design text: stripped, never blank, at most :data:`DESIGN_TEXT_MAX` characters.
DesignText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=DESIGN_TEXT_MAX)
]


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

    name: DesignText
    description: DesignText
    design_features: list[DesignText] = Field(min_length=1)
    outcomes_served: list[DesignText] = Field(default_factory=list)
    assumed: list[DesignText] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)

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
        """Build a design from the ``option_design_prompt`` output, fail-closed.

        An ``assumed`` entry that does not match a feature is dropped (and
        logged) rather than failing the whole proposal: the features are the
        design; ``assumed`` only marks which of them to show as supplied.

        The design names no place (task 046, R31): the design is the option's
        search query, and evidence from any country is wanted. The rule is
        words in the design prompt (R74); no code strip backs it (the strip
        was deleted on the owner's ruling at the review, 2026-10-12). A
        feature left empty is dropped.

        Args:
            wire: The parsed model output.

        Returns:
            The validated design at version 1.

        Raises:
            ValueError: If the wire carries no usable name, description or
                feature.
        """

        def _placeless(value: str) -> str:
            return scrub_nul(value).strip()

        features = [_placeless(item) for item in wire.design_features]
        features = [item for item in features if item]
        assumed = [_placeless(item) for item in wire.assumed]
        kept = [item for item in assumed if item in features]
        if len(kept) != len([item for item in assumed if item]):
            log.warning(
                "option_design_assumed_mismatch",
                dropped=len([item for item in assumed if item]) - len(kept),
            )
        outcomes = [scrub_nul(item).strip() for item in wire.outcomes_served]
        return cls.model_validate(
            {
                "name": _placeless(wire.name),
                "description": _placeless(wire.description),
                "design_features": features,
                "outcomes_served": [item for item in outcomes if item],
                "assumed": kept,
            }
        )
