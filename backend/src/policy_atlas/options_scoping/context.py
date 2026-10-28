"""The scope-level input every options-scoping step takes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class ScopeContext:
    """The walk's intent record, as the harness hands it to a step.

    Attributes:
        scope_id: The longlist walk's intent record.
        intent: Its intent text (unused: the steps read the plan whole).
        context: Its context JSONB (unused: no step reads a directive).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]
