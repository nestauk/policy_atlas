"""Plan → config compile.

Plan is the human-readable object; Config is the machine execution spec compiled from it.
Both are pydantic models, so an unknown component is rejected with a ``ValidationError``
at construction — before the harness ever runs. Source referential integrity is enforced
by the DB FK on citation.chunk_id, not by a static allowlist.
"""

import uuid

from pydantic import BaseModel, model_validator

VALID_COMPONENTS = {"echo"}


class Plan(BaseModel):
    """Trivial plan for the walking-skeleton thread."""

    component: str
    source_snapshot_id: uuid.UUID

    @model_validator(mode="after")
    def validate_fields(self) -> "Plan":
        """Reject unknown component."""
        if self.component not in VALID_COMPONENTS:
            raise ValueError(f"Unknown component {self.component!r}. Valid: {VALID_COMPONENTS}")
        return self


class Config(BaseModel):
    """Machine-level execution spec compiled from a Plan."""

    component: str
    source_snapshot_id: uuid.UUID

    @model_validator(mode="after")
    def validate_fields(self) -> "Config":
        """Reject unknown component."""
        if self.component not in VALID_COMPONENTS:
            raise ValueError(f"Unknown component {self.component!r}. Valid: {VALID_COMPONENTS}")
        return self


def compile(plan: Plan) -> Config:  # noqa: A001
    """Compile a validated Plan into a machine-level Config.

    Args:
        plan: A Plan already validated by Pydantic at construction.

    Returns:
        The Config mirroring the plan's component and source snapshot ID.
    """
    return Config(component=plan.component, source_snapshot_id=plan.source_snapshot_id)
