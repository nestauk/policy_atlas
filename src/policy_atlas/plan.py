"""Plan → config compile.

Plan is the human-readable object; Config is the machine execution spec compiled from it.
Both are pydantic models, so an unknown component or missing required field is rejected
with a ``ValidationError`` at construction — before the harness ever runs.
"""

import uuid

from pydantic import BaseModel, model_validator

COMPONENT_REGISTRY: dict[str, dict[str, list[str]]] = {
    "echo":     {"requires": ["source_snapshot_id"]},
    "acquire":  {"requires": ["evidence_scope_id"]},
    "screen":   {"requires": ["evidence_scope_id"]},
    "classify": {"requires": ["evidence_scope_id"]},
    "appraise": {"requires": ["evidence_scope_id"]},
}
VALID_COMPONENTS = set(COMPONENT_REGISTRY.keys())


class _ValidatedRunSpec(BaseModel):
    component: str
    source_snapshot_id: uuid.UUID | None = None
    evidence_scope_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def validate_fields(self) -> "_ValidatedRunSpec":
        if self.component not in VALID_COMPONENTS:
            raise ValueError(f"Unknown component {self.component!r}. Valid: {VALID_COMPONENTS}")
        for field in COMPONENT_REGISTRY[self.component]["requires"]:
            if getattr(self, field) is None:
                raise ValueError(f"{field} is required for component {self.component!r}")
        return self


class Plan(_ValidatedRunSpec):
    """Human-readable plan for one harness run."""


class Config(_ValidatedRunSpec):
    """Machine-level execution spec compiled from a Plan."""


def compile(plan: Plan) -> Config:  # noqa: A001
    """Compile a validated Plan into a machine-level Config."""
    return Config(
        component=plan.component,
        source_snapshot_id=plan.source_snapshot_id,
        evidence_scope_id=plan.evidence_scope_id,
    )
