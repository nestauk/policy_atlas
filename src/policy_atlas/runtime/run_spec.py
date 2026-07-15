"""Plan → config compile.

Plan is the human-readable object; Config is the machine execution spec compiled from it.
Both are pydantic models, so an unknown component or missing required field is rejected
with a ``ValidationError`` at construction — before the harness ever runs.
"""

import uuid
from typing import Literal

from pydantic import BaseModel, model_validator

COMPONENT_REGISTRY: dict[str, dict[str, list[str]]] = {
    "acquire":  {"requires": ["evidence_scope_id"]},
    "screen":   {"requires": ["evidence_scope_id"]},
    "classify": {"requires": ["evidence_scope_id"]},
    "appraise": {"requires": ["evidence_scope_id"]},
    "ingest_full_text": {"requires": ["evidence_scope_id"]},
    "characterise": {"requires": ["evidence_scope_id"]},
    "select": {"requires": ["evidence_scope_id", "characterisation_run_id"]},
    "extract": {"requires": ["evidence_scope_id", "selection_run_id"]},
    "group": {"requires": ["evidence_scope_id", "extraction_run_id"]},
    # synthesise: all four run references optional — deepest-given resolves
    # the rest transitively at execution.
    "synthesise": {"requires": ["evidence_scope_id"]},
}
VALID_COMPONENTS = set(COMPONENT_REGISTRY.keys())


class _ValidatedRunSpec(BaseModel):
    component: str
    search_backend_scope: Literal["academic_only", "grey_lit_only", "both"] = "both"
    evidence_scope_id: uuid.UUID | None = None
    # select stratifies over an explicitly referenced characterisation — compile
    # fails closed without it; required-by-registry for select only.
    characterisation_run_id: uuid.UUID | None = None
    # extract reads an explicitly referenced selection — compile fails closed
    # without it; required-by-registry for extract only.
    selection_run_id: uuid.UUID | None = None
    # group reads an explicitly referenced extraction — compile fails closed
    # without it; required-by-registry for group only.
    extraction_run_id: uuid.UUID | None = None
    # synthesise may reference an executed grouping — optional; deepest-given
    # resolves upstream transitively at execution.
    grouping_run_id: uuid.UUID | None = None

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
    """Compile a validated Plan into a machine-level Config.

    Args:
        plan: Human-readable, already-validated plan.

    Returns:
        The equivalent machine-level Config.
    """
    return Config.model_validate(plan.model_dump())
