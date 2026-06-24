"""Plan → config compile.

Plan is the human-readable object; Config is the machine execution spec compiled from it.
Both are pydantic models, so an unknown component or source_ref is rejected with a
``ValidationError`` at construction — before the harness ever runs. There is no silent or
partial run.
"""

from pydantic import BaseModel, model_validator

VALID_COMPONENTS = {"echo"}
VALID_SOURCES = {"syn-001"}


def _validate_refs(component: str, source_ref: str) -> None:
    """Reject an unknown component or source reference.

    Args:
        component: Declared component name.
        source_ref: Known source reference.

    Raises:
        ValueError: If ``component`` or ``source_ref`` is not declared.
    """
    if component not in VALID_COMPONENTS:
        raise ValueError(f"Unknown component {component!r}. Valid: {VALID_COMPONENTS}")
    if source_ref not in VALID_SOURCES:
        raise ValueError(f"Unknown source_ref {source_ref!r}. Valid: {VALID_SOURCES}")


class Plan(BaseModel):
    """Trivial plan for the walking-skeleton thread."""

    component: str    # must be a declared component name
    source_ref: str   # must be a known source reference

    @model_validator(mode="after")
    def validate_fields(self) -> "Plan":
        """Reject unknown component or source references."""
        _validate_refs(self.component, self.source_ref)
        return self


class Config(BaseModel):
    """Machine-level execution spec compiled from a Plan."""

    component: str
    source_ref: str

    @model_validator(mode="after")
    def validate_fields(self) -> "Config":
        """Reject unknown component or source references."""
        _validate_refs(self.component, self.source_ref)
        return self


def compile(plan: Plan) -> Config:  # noqa: A001
    """Compile a validated Plan into a machine-level Config.

    Args:
        plan: A Plan already validated by Pydantic at construction.

    Returns:
        The Config mirroring the plan's component and source reference.
    """
    return Config(component=plan.component, source_ref=plan.source_ref)
