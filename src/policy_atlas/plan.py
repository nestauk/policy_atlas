"""Plan → config compile.

Plan is the human-readable object; Config is the machine execution spec compiled from it.
Both are pydantic models, so an unknown component or missing required field is rejected
with a ``ValidationError`` at construction — before the harness ever runs.
"""

import uuid

from pydantic import BaseModel, model_validator

COMPONENT_REGISTRY: dict[str, dict[str, list[str]]] = {
    "echo":   {"requires": ["source_snapshot_id"]},
    "screen": {"requires": ["screening_scope_id"]},
}
VALID_COMPONENTS = set(COMPONENT_REGISTRY.keys())


class Plan(BaseModel):
    """Human-readable plan for one harness run."""

    component: str
    source_snapshot_id: uuid.UUID | None = None
    screening_scope_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "Plan":
        if self.component not in VALID_COMPONENTS:
            raise ValueError(f"Unknown component {self.component!r}. Valid: {VALID_COMPONENTS}")
        for field in COMPONENT_REGISTRY[self.component]["requires"]:
            if getattr(self, field) is None:
                raise ValueError(f"{field} is required for component {self.component!r}")
        return self


class Config(BaseModel):
    """Machine-level execution spec compiled from a Plan."""

    component: str
    source_snapshot_id: uuid.UUID | None = None
    screening_scope_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "Config":
        if self.component not in VALID_COMPONENTS:
            raise ValueError(f"Unknown component {self.component!r}. Valid: {VALID_COMPONENTS}")
        for field in COMPONENT_REGISTRY[self.component]["requires"]:
            if getattr(self, field) is None:
                raise ValueError(f"{field} is required for component {self.component!r}")
        return self


def compile(plan: Plan) -> Config:  # noqa: A001
    """Compile a validated Plan into a machine-level Config."""
    return Config(
        component=plan.component,
        source_snapshot_id=plan.source_snapshot_id,
        screening_scope_id=plan.screening_scope_id,
    )
