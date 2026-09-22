"""The longlist component's model seam (task 045, S8).

Five calls, each one lead-authored prompt builder
(:mod:`~policy_atlas.options_scoping.longlist.longlist_cluster_prompt`,
:mod:`~policy_atlas.options_scoping.longlist.longlist_theme_prompt`,
:mod:`~policy_atlas.options_scoping.longlist.lever_typing_prompt`):

- ``discover`` — seeded option discovery (judgment model);
- ``assign`` — one assignment batch (mini model);
- ``discover_themes`` / ``assign_themes`` — themes over the options
  (judgment model; the contract's model route puts theme grouping there);
- ``type_options`` — one lever-typing batch (judgment model).

Backends parse structurally and return the wire; the component and the shared
clustering engine own every semantic check. :class:`StubLonglistBackend` is
deterministic and makes no call.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import parse_structured, resolve_openai_client
from policy_atlas.core.usage import UsageResult, usage_details, usage_metadata
from policy_atlas.evidence_search.assess.screen_prompt import SCREEN_MODEL
from policy_atlas.options_scoping.longlist.lever_typing_prompt import (
    LEVER_TYPING_MAX_OUTPUT_TOKENS,
    LEVER_TYPING_PROMPT_VERSION,
    LeverTypingResponse,
    LeverTypingWire,
    build_lever_typing_messages,
)
from policy_atlas.options_scoping.longlist.longlist_cluster_prompt import (
    ASSIGNMENT_MAX_OUTPUT_TOKENS,
    DISCOVERY_MAX_OUTPUT_TOKENS,
    LONGLIST_CLUSTER_PROMPT_VERSION,
    DiscoveredOptionWire,
    OptionAssignmentsResponse,
    OptionAssignmentWire,
    OptionDiscoveryResponse,
    build_longlist_assignment_messages,
    build_longlist_discovery_messages,
)
from policy_atlas.options_scoping.longlist.longlist_theme_prompt import (
    LONGLIST_THEME_PROMPT_VERSION,
    THEME_MAX_OUTPUT_TOKENS,
    ThemeAssignmentsResponse,
    ThemeAssignmentWire,
    ThemeDiscoveryResponse,
    ThemeWire,
    build_theme_assignment_messages,
    build_theme_discovery_messages,
)
from policy_atlas.runtime.agent_backend import AGENT_MODEL

#: The judgment model (discovery, themes, typing) and the mini model
#: (assignment) — contract § Model route, the Task Agent's tiers.
LONGLIST_JUDGMENT_MODEL = AGENT_MODEL
LONGLIST_ASSIGNMENT_MODEL = SCREEN_MODEL


class LonglistBackend(Protocol):
    """The longlist component's model seam."""

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``."""
        ...

    def discover(
        self,
        *,
        question: str,
        seeds: list[dict[str, object]],
        records: list[dict[str, object]],
        max_new: int,
    ) -> UsageResult[OptionDiscoveryResponse]:
        """Discover options beyond the seeds.

        Args:
            question: The plan's question (context only).
            seeds: The seed options as data.
            records: Every unit's record, keyed by ``unit_id``.
            max_new: The ceiling on new options.

        Returns:
            The parsed discovery and token usage.
        """
        ...

    def assign(
        self, *, options: list[dict[str, object]], records: list[dict[str, object]]
    ) -> UsageResult[OptionAssignmentsResponse]:
        """Assign one batch of units to the fixed option list.

        Args:
            options: The fixed options as data.
            records: The batch's unit records.

        Returns:
            The parsed assignments and token usage.
        """
        ...

    def discover_themes(
        self, *, question: str, records: list[dict[str, object]], max_labels: int
    ) -> UsageResult[ThemeDiscoveryResponse]:
        """Discover themes over the options.

        Args:
            question: The plan's question (context only).
            records: The options as unit records.
            max_labels: The theme ceiling.

        Returns:
            The parsed themes and token usage.
        """
        ...

    def assign_themes(
        self, *, themes: list[dict[str, str]], records: list[dict[str, object]]
    ) -> UsageResult[ThemeAssignmentsResponse]:
        """Assign one batch of options to the fixed themes.

        Args:
            themes: The fixed themes as data.
            records: The batch's option records.

        Returns:
            The parsed assignments and token usage.
        """
        ...

    def type_options(
        self, *, options: list[dict[str, object]]
    ) -> UsageResult[LeverTypingResponse]:
        """Type one batch of options (lever type and ambition).

        Args:
            options: The batch's options as data, keyed by ``unit_id``.

        Returns:
            The parsed typings and token usage.
        """
        ...


class OpenAILonglistBackend:
    """Live OpenAI implementation of the longlist seam.

    Args:
        api_key: Optional OpenAI API key; ``OPENAI_API_KEY`` otherwise.
        langfuse_client: Optional Langfuse client; tracing is a no-op without one.
        session_id: Optional Langfuse session id.

    Raises:
        RuntimeError: If no OpenAI API key is provided or configured.
    """

    mode = "live"

    def __init__(
        self,
        api_key: str | None = None,
        langfuse_client: Langfuse | None = None,
        session_id: uuid.UUID | None = None,
    ) -> None:
        self._client = resolve_openai_client(
            api_key, backend_name="OpenAILonglistBackend", timeout=300.0, max_retries=2
        )
        self._langfuse_client = langfuse_client
        self._session_id = session_id

    def _call[T: BaseModel](
        self,
        messages: list[ChatCompletionMessageParam],
        *,
        response_format: type[T],
        model: str,
        max_output_tokens: int,
        name: str,
        prompt_version: str,
    ) -> UsageResult[T]:
        def _update(span: Any, result: UsageResult[T]) -> None:
            parsed, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=parsed.model_dump(),
                model=model,
                metadata={"prompt_version": prompt_version, **usage_metadata(usage)},
            )

        return tracing.traced_call(
            self._langfuse_client,
            name=name,
            as_type="generation",
            call=lambda: parse_structured(
                self._client,
                messages=messages,
                response_format=response_format,
                usage_event=f"{name.replace(':', '.')}.usage",
                label=name,
                model=model,
                max_completion_tokens=max_output_tokens,
            ),
            session_id=self._session_id,
            update=_update,
        )

    def discover(
        self,
        *,
        question: str,
        seeds: list[dict[str, object]],
        records: list[dict[str, object]],
        max_new: int,
    ) -> UsageResult[OptionDiscoveryResponse]:
        """Seeded discovery on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_longlist_discovery_messages(
                question=question, seeds=seeds, records=records, max_new=max_new
            ),
            response_format=OptionDiscoveryResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=DISCOVERY_MAX_OUTPUT_TOKENS,
            name="longlist:discover",
            prompt_version=LONGLIST_CLUSTER_PROMPT_VERSION,
        )

    def assign(
        self, *, options: list[dict[str, object]], records: list[dict[str, object]]
    ) -> UsageResult[OptionAssignmentsResponse]:
        """One assignment batch on the mini model (see :class:`LonglistBackend`)."""
        return self._call(
            build_longlist_assignment_messages(options=options, records=records),
            response_format=OptionAssignmentsResponse,
            model=LONGLIST_ASSIGNMENT_MODEL,
            max_output_tokens=ASSIGNMENT_MAX_OUTPUT_TOKENS,
            name="longlist:assign",
            prompt_version=LONGLIST_CLUSTER_PROMPT_VERSION,
        )

    def discover_themes(
        self, *, question: str, records: list[dict[str, object]], max_labels: int
    ) -> UsageResult[ThemeDiscoveryResponse]:
        """Theme discovery on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_theme_discovery_messages(
                question=question, records=records, max_labels=max_labels
            ),
            response_format=ThemeDiscoveryResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=THEME_MAX_OUTPUT_TOKENS,
            name="longlist:themes",
            prompt_version=LONGLIST_THEME_PROMPT_VERSION,
        )

    def assign_themes(
        self, *, themes: list[dict[str, str]], records: list[dict[str, object]]
    ) -> UsageResult[ThemeAssignmentsResponse]:
        """One theme assignment batch on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_theme_assignment_messages(themes=themes, records=records),
            response_format=ThemeAssignmentsResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=THEME_MAX_OUTPUT_TOKENS,
            name="longlist:assign_themes",
            prompt_version=LONGLIST_THEME_PROMPT_VERSION,
        )

    def type_options(
        self, *, options: list[dict[str, object]]
    ) -> UsageResult[LeverTypingResponse]:
        """One typing batch on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_lever_typing_messages(options=options),
            response_format=LeverTypingResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=LEVER_TYPING_MAX_OUTPUT_TOKENS,
            name="longlist:type",
            prompt_version=LEVER_TYPING_PROMPT_VERSION,
        )


#: The stub's one discovered option.
STUB_DISCOVERED_LABEL = "Stub discovered option"
#: The stub's one theme.
STUB_THEME_LABEL = "Stub theme"


def _casefold(value: object) -> str:
    return " ".join(str(value).split()).casefold()


class StubLonglistBackend:
    """Deterministic zero-egress longlist backend for tests and local runs.

    - ``discover`` proposes :data:`STUB_DISCOVERED_LABEL` when some record's
      ``intervention`` matches no seed label and ``max_new`` allows one;
      otherwise nothing.
    - ``assign`` places a record whose ``intervention`` equals an option label
      (case-insensitively) under that option; any other record under the
      discovered option when it is listed, else ``ungroupable``.
    - ``discover_themes`` proposes :data:`STUB_THEME_LABEL`;
      ``assign_themes`` puts every option in it.
    - ``type_options`` types every option ``provide a service`` /
      ``incremental``.
    """

    mode = "stub"

    def discover(
        self,
        *,
        question: str,
        seeds: list[dict[str, object]],
        records: list[dict[str, object]],
        max_new: int,
    ) -> UsageResult[OptionDiscoveryResponse]:
        """Propose the one stub option when an unmatched record exists."""
        del question
        seed_labels = {_casefold(seed["label"]) for seed in seeds}
        unmatched = any(_casefold(r.get("intervention", "")) not in seed_labels for r in records)
        options = (
            [
                DiscoveredOptionWire(
                    label=STUB_DISCOVERED_LABEL,
                    description="A stub option for records no seed names.",
                    design_features=["stub design feature"],
                    outcomes_served=[],
                    is_bundle=False,
                    components=[],
                )
            ]
            if unmatched and max_new > 0
            else []
        )
        return OptionDiscoveryResponse(options=options), None

    def assign(
        self, *, options: list[dict[str, object]], records: list[dict[str, object]]
    ) -> UsageResult[OptionAssignmentsResponse]:
        """Assign by name match, else to the stub option, else ungroupable."""
        by_name = {_casefold(o["label"]): str(o["label"]) for o in options}
        fallback = by_name.get(_casefold(STUB_DISCOVERED_LABEL), "ungroupable")
        assignments = []
        for record in records:
            label = by_name.get(_casefold(record.get("intervention", "")), fallback)
            assignments.append(
                OptionAssignmentWire(
                    unit_id=str(record["unit_id"]),
                    option_label=label,
                    reason="Stub assignment by name.",
                    design_feature_not_stated=False,
                )
            )
        return OptionAssignmentsResponse(assignments=assignments), None

    def discover_themes(
        self, *, question: str, records: list[dict[str, object]], max_labels: int
    ) -> UsageResult[ThemeDiscoveryResponse]:
        """Propose the one stub theme."""
        del question, records
        themes = (
            [ThemeWire(label=STUB_THEME_LABEL, description="Every option, for the stub.")]
            if max_labels > 0
            else []
        )
        return ThemeDiscoveryResponse(themes=themes), None

    def assign_themes(
        self, *, themes: list[dict[str, str]], records: list[dict[str, object]]
    ) -> UsageResult[ThemeAssignmentsResponse]:
        """Put every option in the first theme."""
        label = themes[0]["label"] if themes else "ungroupable"
        return (
            ThemeAssignmentsResponse(
                assignments=[
                    ThemeAssignmentWire(unit_id=str(r["unit_id"]), theme_label=label)
                    for r in records
                ]
            ),
            None,
        )

    def type_options(
        self, *, options: list[dict[str, object]]
    ) -> UsageResult[LeverTypingResponse]:
        """Type every option ``provide a service`` / ``incremental``."""
        return (
            LeverTypingResponse(
                typings=[
                    LeverTypingWire(
                        unit_id=str(o["unit_id"]),
                        primary_lever_type="provide a service",
                        secondary_lever_types=[],
                        runner_up_lever_type=None,
                        runner_up_reason=None,
                        none_fits_reason=None,
                        lever_reason="Stub typing.",
                        ambition="incremental",
                        ambition_reason="Stub ambition.",
                    )
                    for o in options
                ]
            ),
            None,
        )
