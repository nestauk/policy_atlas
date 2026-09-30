"""The longlist walk's model seam (task 045, S8), shared by its components.

``longlist``, ``option_profile``, ``constrain`` and ``theme`` share this one
backend (task 046, S20). Each call has one lead-authored prompt builder
(:mod:`~policy_atlas.options_scoping.longlist.longlist_cluster_prompt`,
:mod:`~policy_atlas.options_scoping.theme.longlist_theme_prompt`,
:mod:`~policy_atlas.options_scoping.option_profile.lever_typing_prompt`,
:mod:`~policy_atlas.options_scoping.constrain.constrain_prompt`):

- ``discover`` — seeded option discovery over the plan, the baseline, the
  seeds and the corpus digest (judgment model);
- ``assign`` — one assignment batch (mini model);
- ``discover_themes`` / ``assign_themes`` — themes over the options
  (judgment model; the contract's model route puts theme grouping there);
- ``type_options`` — one lever-typing batch, with the plan and the baseline
  (judgment model; batches run in a thread pool), the ``option_profile``
  step's (task 046, S20; its Langfuse name stays ``longlist:type``);
- ``profile_line`` / ``profile_ambition`` / ``profile_setting`` — the
  ``option_profile`` step's ten calls over the whole list: one per line of
  "What it would take", the ambition and the delivery setting (judgment
  model; task 046, R36, R40, R41;
  :mod:`~policy_atlas.options_scoping.option_profile.option_profile_prompt`);
- ``constrain`` — one constraint-judgement batch with the plan and the
  baseline (judgment model; batches run in a thread pool), the walk's
  ``constrain`` step (S9) on the same seam
  (:mod:`~policy_atlas.options_scoping.constrain.constrain_prompt`);
- ``distinct`` — the constrain step's one duplicate check over the whole list
  (judgment model; task 046, S13);
- ``authority`` — the constrain step's one authority-label call over the
  whole list, made only when the plan holds a consideration on "who decides"
  (judgment model; task 046, R38, S18);
- ``fold`` — one of the ``option_profile`` step's two folding calls over the
  list's distinct record words, one per facet (Tried on: the ``unit`` words;
  Measures: the ``outcome`` words), word → kind (mini model; task 046,
  amendment 3, R54, R55;
  :mod:`~policy_atlas.options_scoping.option_profile.folding_prompt`).

Backends parse structurally and return the wire; the component and the shared
clustering engine own every semantic check. :class:`StubLonglistBackend` is
deterministic and makes no call.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import parse_structured, resolve_openai_client
from policy_atlas.core.usage import UsageResult, usage_details, usage_metadata
from policy_atlas.evidence_search.assess.screen_prompt import SCREEN_MODEL
from policy_atlas.options_scoping.constrain.constrain_prompt import (
    AUTHORITY_MAX_OUTPUT_TOKENS,
    CONSTRAIN_MAX_OUTPUT_TOKENS,
    CONSTRAIN_PROMPT_VERSION,
    DISTINCT_MAX_OUTPUT_TOKENS,
    AuthorityResponse,
    AuthorityWire,
    ConstrainResponse,
    ConstraintJudgementWire,
    DistinctResponse,
    OptionConstrainWire,
    ReasonedGuessWire,
    build_authority_messages,
    build_constrain_messages,
    build_distinct_messages,
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
from policy_atlas.options_scoping.option_profile.folding_prompt import (
    FOLDING_PROMPT_VERSION,
    Facet,
    FoldingResponse,
    FoldWire,
    build_folding_messages,
)
from policy_atlas.options_scoping.option_profile.lever_typing_prompt import (
    LEVER_TYPING_MAX_OUTPUT_TOKENS,
    LEVER_TYPING_PROMPT_VERSION,
    LeverTypingResponse,
    LeverTypingWire,
    build_lever_typing_messages,
)
from policy_atlas.options_scoping.option_profile.option_profile_prompt import (
    OPTION_PROFILE_MAX_OUTPUT_TOKENS,
    OPTION_PROFILE_PROMPT_VERSION,
    AmbitionResponse,
    AmbitionWire,
    MarkedLineResponse,
    MarkedLineWire,
    PlainLineResponse,
    PlainLineWire,
    SettingResponse,
    SettingWire,
    build_ambition_messages,
    build_line_messages,
    build_setting_messages,
    line_is_marked,
)
from policy_atlas.options_scoping.theme.longlist_theme_prompt import (
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
#: The output ceiling of one folding call (one short entry per distinct word).
FOLDING_MAX_OUTPUT_TOKENS = 16_000


class LonglistBackend(Protocol):
    """The longlist component's model seam."""

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``."""
        ...

    def discover(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        seeds: list[dict[str, object]],
        digest: list[dict[str, object]],
        target_size: int,
        max_new: int,
        residual: bool = False,
    ) -> UsageResult[OptionDiscoveryResponse]:
        """Discover options beyond the seeds, and fold suggested seeds.

        Args:
            plan: The plan fields as data, place stripped.
            baseline_sections: ``(title, markdown)`` per baseline section.
            seeds: The seed options as data, each with its ``origin`` word.
            digest: The corpus digest (never the unit records).
            target_size: The list's target size, seeds included.
            max_new: The ceiling on new options.
            residual: True for the residual pass.

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
        self,
        *,
        options: list[dict[str, object]],
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
    ) -> UsageResult[LeverTypingResponse]:
        """Type one batch of options (the lever type).

        Called from a thread pool: one call per batch, several at once.

        Args:
            options: The batch's options as data, keyed by ``unit_id``.
            plan: The plan fields as data, place stripped.
            baseline_sections: ``(title, markdown)`` per baseline section.

        Returns:
            The parsed typings and token usage.
        """
        ...

    def profile_line(
        self,
        *,
        line_key: str,
        plan: dict[str, object],
        where: str | None,
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[MarkedLineResponse | PlainLineResponse]:
        """Write one line of "What it would take" for every option (R36, S16).

        One call over the whole list; the ten profile calls run at one time.

        Args:
            line_key: One of the eight line keys.
            plan: The plan fields as data, place stripped.
            where: The plan's Where for ``who_decides``; ``None`` otherwise.
            baseline_sections: ``(title, markdown)`` per baseline section.
            options: Every option as data, keyed by its short ``option_id``.

        Returns:
            A :class:`MarkedLineResponse` on a marked line, else a
            :class:`PlainLineResponse`, and token usage.
        """
        ...

    def profile_ambition(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[AmbitionResponse]:
        """Write the ambition of every option (R40, S16).

        Args:
            plan: The plan fields as data, place stripped.
            baseline_sections: ``(title, markdown)`` per baseline section.
            options: Every option as data, keyed by its short ``option_id``.

        Returns:
            The parsed ambitions and token usage.
        """
        ...

    def profile_setting(
        self, *, plan: dict[str, object], options: list[dict[str, object]]
    ) -> UsageResult[SettingResponse]:
        """Name the delivery setting of every option (R41, S16).

        Args:
            plan: The plan fields as data, place stripped.
            options: Every option as data, keyed by its short ``option_id``.

        Returns:
            The parsed settings and token usage.
        """
        ...

    def fold(
        self, *, facet: Facet, plan: dict[str, object], words: dict[str, str]
    ) -> UsageResult[FoldingResponse]:
        """Fold the list's distinct words of one facet into kinds (R54, R55; S21).

        Args:
            facet: ``"tried_on"`` (the records' ``unit`` words) or
                ``"measures"`` (their ``outcome`` words).
            plan: The plan fields as data, place stripped (``target_unit``
                and ``outcomes`` are read).
            words: Short id (``w1`` … ``wN``) → distinct word.

        Returns:
            The parsed word → kind entries and token usage.
        """
        ...

    def constrain(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        requirements: list[dict[str, str]],
        preferences: list[dict[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[ConstrainResponse]:
        """Judge one batch of options against the constraints (S9).

        Called from a thread pool: one call per batch, several at once.

        Args:
            plan: The plan fields as data, place stripped.
            baseline_sections: ``(title, markdown)`` per baseline section.
            requirements: The requirement constraints, then the default screens.
            preferences: The preferences, the transferability preference removed.
            options: The batch's options as data, keyed by ``option_id``.

        Returns:
            The parsed judgements and guesses and token usage.
        """
        ...

    def distinct(self, *, options: list[dict[str, object]]) -> UsageResult[DistinctResponse]:
        """Report the options that duplicate another, over the whole list (S13).

        Args:
            options: Every option on the list that is not merged, as data.

        Returns:
            The parsed duplicate pairs and token usage.
        """
        ...

    def authority(
        self, *, considerations: list[str], options: list[dict[str, object]]
    ) -> UsageResult[AuthorityResponse]:
        """Label every option by who can adopt it, over the whole list (R38, S18).

        Args:
            considerations: The texts of the plan's considerations on "who
                decides", in plan order; never empty.
            options: Every option on the list that is not merged and that has
                a profile, as data: ``option_id``, ``label``,
                ``description``, ``design_features`` and ``who_decides``.

        Returns:
            The parsed labels and token usage.
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
        metadata: dict[str, str] | None = None,
    ) -> UsageResult[T]:
        def _update(span: Any, result: UsageResult[T]) -> None:
            parsed, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=parsed.model_dump(),
                model=model,
                metadata={
                    "prompt_version": prompt_version,
                    **(metadata or {}),
                    **usage_metadata(usage),
                },
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
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        seeds: list[dict[str, object]],
        digest: list[dict[str, object]],
        target_size: int,
        max_new: int,
        residual: bool = False,
    ) -> UsageResult[OptionDiscoveryResponse]:
        """Seeded discovery on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_longlist_discovery_messages(
                plan=plan,
                baseline_sections=baseline_sections,
                seeds=seeds,
                digest=digest,
                target_size=target_size,
                max_new=max_new,
                residual=residual,
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
        self,
        *,
        options: list[dict[str, object]],
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
    ) -> UsageResult[LeverTypingResponse]:
        """One typing batch on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_lever_typing_messages(
                options=options, plan=plan, baseline_sections=baseline_sections
            ),
            response_format=LeverTypingResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=LEVER_TYPING_MAX_OUTPUT_TOKENS,
            name="longlist:type",
            prompt_version=LEVER_TYPING_PROMPT_VERSION,
        )

    def profile_line(
        self,
        *,
        line_key: str,
        plan: dict[str, object],
        where: str | None,
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[MarkedLineResponse | PlainLineResponse]:
        """One line call on the judgment model (see :class:`LonglistBackend`).

        The Langfuse name is static; the line key rides in the metadata.
        """
        messages = build_line_messages(
            line_key=line_key,
            plan=plan,
            where=where,
            baseline_sections=baseline_sections,
            options=options,
        )
        settings: dict[str, Any] = {
            "model": LONGLIST_JUDGMENT_MODEL,
            "max_output_tokens": OPTION_PROFILE_MAX_OUTPUT_TOKENS,
            "name": "option_profile:line",
            "prompt_version": OPTION_PROFILE_PROMPT_VERSION,
            "metadata": {"line_key": line_key},
        }
        if line_is_marked(line_key):
            return self._call(messages, response_format=MarkedLineResponse, **settings)
        return self._call(messages, response_format=PlainLineResponse, **settings)

    def profile_ambition(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[AmbitionResponse]:
        """The ambition call on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_ambition_messages(
                plan=plan, baseline_sections=baseline_sections, options=options
            ),
            response_format=AmbitionResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=OPTION_PROFILE_MAX_OUTPUT_TOKENS,
            name="option_profile:ambition",
            prompt_version=OPTION_PROFILE_PROMPT_VERSION,
        )

    def profile_setting(
        self, *, plan: dict[str, object], options: list[dict[str, object]]
    ) -> UsageResult[SettingResponse]:
        """The setting call on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_setting_messages(plan=plan, options=options),
            response_format=SettingResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=OPTION_PROFILE_MAX_OUTPUT_TOKENS,
            name="option_profile:setting",
            prompt_version=OPTION_PROFILE_PROMPT_VERSION,
        )

    def fold(
        self, *, facet: Facet, plan: dict[str, object], words: dict[str, str]
    ) -> UsageResult[FoldingResponse]:
        """One folding call on the mini model (see :class:`LonglistBackend`).

        The Langfuse name is static; the facet rides in the metadata.
        """
        return self._call(
            build_folding_messages(facet=facet, plan=plan, words=words),
            response_format=FoldingResponse,
            model=LONGLIST_ASSIGNMENT_MODEL,
            max_output_tokens=FOLDING_MAX_OUTPUT_TOKENS,
            name="option_profile:fold",
            prompt_version=FOLDING_PROMPT_VERSION,
            metadata={"facet": facet},
        )

    def constrain(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        requirements: list[dict[str, str]],
        preferences: list[dict[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[ConstrainResponse]:
        """One constrain batch on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_constrain_messages(
                plan=plan,
                baseline_sections=baseline_sections,
                requirements=requirements,
                preferences=preferences,
                options=options,
            ),
            response_format=ConstrainResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=CONSTRAIN_MAX_OUTPUT_TOKENS,
            name="longlist:constrain",
            prompt_version=CONSTRAIN_PROMPT_VERSION,
        )

    def distinct(self, *, options: list[dict[str, object]]) -> UsageResult[DistinctResponse]:
        """The distinct call on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_distinct_messages(options=options),
            response_format=DistinctResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=DISTINCT_MAX_OUTPUT_TOKENS,
            name="longlist:distinct",
            prompt_version=CONSTRAIN_PROMPT_VERSION,
        )

    def authority(
        self, *, considerations: list[str], options: list[dict[str, object]]
    ) -> UsageResult[AuthorityResponse]:
        """The authority call on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_authority_messages(considerations=considerations, options=options),
            response_format=AuthorityResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=AUTHORITY_MAX_OUTPUT_TOKENS,
            name="longlist:authority",
            prompt_version=CONSTRAIN_PROMPT_VERSION,
        )


#: The stub's one discovered option.
STUB_DISCOVERED_LABEL = "Stub discovered option"
#: The stub's one theme.
STUB_THEME_LABEL = "Stub theme"


def _casefold(value: object) -> str:
    return " ".join(str(value).split()).casefold()


#: A line call's response: marked on six lines, plain on two.
type _LineResponse = MarkedLineResponse | PlainLineResponse


class StubLonglistBackend:
    """Deterministic zero-egress longlist backend for tests and local runs.

    - ``discover`` proposes :data:`STUB_DISCOVERED_LABEL` when some digest
      name matches no seed label and ``max_new`` allows one; otherwise
      nothing. It folds no seed.
    - ``assign`` places a record whose ``intervention`` equals an option label
      (case-insensitively) under that option; any other record under the
      discovered option when it is listed, else ``ungroupable``.
    - ``discover_themes`` proposes :data:`STUB_THEME_LABEL`;
      ``assign_themes`` puts every option in it.
    - ``type_options`` types every option ``provide a service``.
    - ``profile_line``, ``profile_ambition`` and ``profile_setting`` answer
      from their own FIFO queues as ``constrain`` does (``profile_line`` has
      one queue per line key). With none: every option gets the sentence
      ``"Stub <line key> sentence."`` and no mark; the ambition reason
      ``"Stub ambition."`` and no mark; the setting ``"stub setting"`` and no
      second setting. Their calls and inputs are recorded under the lock.
    - ``constrain`` answers from a FIFO queue of canned responses (the last
      one repeats once the queue drains, the ``StubAgentBackend`` pattern);
      with none, every option passes every requirement and screen and every
      guess is ``cannot_say``. Its calls and inputs are recorded. Batches
      call it from a thread pool: the queue and the records are guarded by a
      lock, and with several batches in flight the queue answers in call
      order.
    - ``distinct`` answers the same way from its own queue; with none, it
      reports no duplicate. Its calls and inputs are recorded.
    - ``authority`` answers the same way from its own queue; with none, every
      option is ``unclear`` with no body and the reason ``"Stub: unclear."``.
      Its calls and inputs are recorded under the lock.
    - ``fold`` answers from its facet's own FIFO queue the same way; with
      none, each word's kind is its own text lower-cased, except a word that
      equals (case-folded) a plan outcome or the plan's target unit, whose
      kind is that plan text. Its calls and inputs are recorded under the lock.

    Args:
        constrain_responses: Canned :class:`ConstrainResponse` value(s), or
            ``None`` for the deterministic default.
        distinct_responses: Canned :class:`DistinctResponse` value(s), or
            ``None`` for the deterministic default (no duplicate).
        authority_responses: Canned :class:`AuthorityResponse` value(s), or
            ``None`` for the deterministic default (every option unclear).
        line_responses: Per line key, canned line response(s), or ``None``
            for the deterministic default on every line.
        ambition_responses: Canned :class:`AmbitionResponse` value(s), or
            ``None`` for the deterministic default.
        setting_responses: Canned :class:`SettingResponse` value(s), or
            ``None`` for the deterministic default.
        fold_responses: Per facet, canned :class:`FoldingResponse` value(s),
            or ``None`` for the deterministic default on both facets.
    """

    mode = "stub"

    def __init__(
        self,
        *,
        constrain_responses: ConstrainResponse | list[ConstrainResponse] | None = None,
        distinct_responses: DistinctResponse | list[DistinctResponse] | None = None,
        authority_responses: AuthorityResponse | list[AuthorityResponse] | None = None,
        line_responses: Mapping[str, _LineResponse | list[_LineResponse]] | None = None,
        ambition_responses: AmbitionResponse | list[AmbitionResponse] | None = None,
        setting_responses: SettingResponse | list[SettingResponse] | None = None,
        fold_responses: Mapping[str, FoldingResponse | list[FoldingResponse]] | None = None,
    ) -> None:
        self._constrain_queue: list[ConstrainResponse] = _queue(constrain_responses)
        self._distinct_queue: list[DistinctResponse] = _queue(distinct_responses)
        self._authority_queue: list[AuthorityResponse] = _queue(authority_responses)
        self._line_queues: dict[str, list[_LineResponse]] = {
            key: _queue(value) for key, value in (line_responses or {}).items()
        }
        self._ambition_queue: list[AmbitionResponse] = _queue(ambition_responses)
        self._setting_queue: list[SettingResponse] = _queue(setting_responses)
        self._fold_queues: dict[str, list[FoldingResponse]] = {
            key: _queue(value) for key, value in (fold_responses or {}).items()
        }
        self._lock = threading.Lock()
        self.constrain_calls = 0
        self.constrain_inputs: list[dict[str, Any]] = []
        self.distinct_calls = 0
        self.distinct_inputs: list[list[dict[str, object]]] = []
        self.authority_calls = 0
        self.authority_inputs: list[dict[str, Any]] = []
        self.line_calls: dict[str, int] = {}
        self.line_inputs: list[dict[str, Any]] = []
        self.ambition_calls = 0
        self.ambition_inputs: list[dict[str, Any]] = []
        self.setting_calls = 0
        self.setting_inputs: list[dict[str, Any]] = []
        self.fold_calls: dict[str, int] = {}
        self.fold_inputs: list[dict[str, Any]] = []

    def discover(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        seeds: list[dict[str, object]],
        digest: list[dict[str, object]],
        target_size: int,
        max_new: int,
        residual: bool = False,
    ) -> UsageResult[OptionDiscoveryResponse]:
        """Propose the one stub option when a digest name matches no seed; fold none."""
        del plan, baseline_sections, target_size, residual
        seed_labels = {_casefold(seed["label"]) for seed in seeds}
        unmatched = any(_casefold(entry.get("name", "")) not in seed_labels for entry in digest)
        options = (
            [
                DiscoveredOptionWire(
                    label=STUB_DISCOVERED_LABEL,
                    description="A stub option for records no seed names.",
                    design_features=["stub design feature"],
                )
            ]
            if unmatched and max_new > 0
            else []
        )
        return OptionDiscoveryResponse(options=options, folds=[]), None

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
        self,
        *,
        options: list[dict[str, object]],
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
    ) -> UsageResult[LeverTypingResponse]:
        """Type every option ``provide a service``."""
        del plan, baseline_sections
        return (
            LeverTypingResponse(
                typings=[
                    LeverTypingWire(
                        unit_id=str(o["unit_id"]),
                        lever_reason="Stub lever reason.",
                        primary_lever_type="provide a service",
                        secondary_lever_types=[],
                        runner_up_lever_type=None,
                        none_fits_reason=None,
                    )
                    for o in options
                ]
            ),
            None,
        )

    def constrain(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        requirements: list[dict[str, str]],
        preferences: list[dict[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[ConstrainResponse]:
        """Answer from the queue, else pass everything and guess ``cannot_say``."""
        with self._lock:
            self.constrain_calls += 1
            self.constrain_inputs.append(
                {
                    "plan": plan,
                    "baseline_sections": list(baseline_sections),
                    "requirements": list(requirements),
                    "preferences": list(preferences),
                    "options": list(options),
                }
            )
            return _next_response(
                self._constrain_queue,
                lambda: _pass_everything(requirements, preferences, options),
            ), None

    def distinct(self, *, options: list[dict[str, object]]) -> UsageResult[DistinctResponse]:
        """Answer from the queue, else report no duplicate."""
        with self._lock:
            self.distinct_calls += 1
            self.distinct_inputs.append(list(options))
            return _next_response(
                self._distinct_queue, lambda: DistinctResponse(duplicates=[])
            ), None

    def authority(
        self, *, considerations: list[str], options: list[dict[str, object]]
    ) -> UsageResult[AuthorityResponse]:
        """Answer from the queue, else every option ``unclear``."""
        with self._lock:
            self.authority_calls += 1
            self.authority_inputs.append(
                {"considerations": list(considerations), "options": list(options)}
            )
            return _next_response(
                self._authority_queue,
                lambda: AuthorityResponse(
                    options=[
                        AuthorityWire(
                            option_id=str(o["option_id"]),
                            reason="Stub: unclear.",
                            label="unclear",
                            body=None,
                        )
                        for o in options
                    ]
                ),
            ), None

    def profile_line(
        self,
        *,
        line_key: str,
        plan: dict[str, object],
        where: str | None,
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[MarkedLineResponse | PlainLineResponse]:
        """Answer from the line's queue, else a stub sentence and no mark."""
        with self._lock:
            self.line_calls[line_key] = self.line_calls.get(line_key, 0) + 1
            self.line_inputs.append(
                {
                    "line_key": line_key,
                    "plan": plan,
                    "where": where,
                    "baseline_sections": list(baseline_sections),
                    "options": list(options),
                }
            )
            response = _next_response(
                self._line_queues.setdefault(line_key, []),
                lambda: _stub_line(line_key, options),
            )
        return response, None

    def profile_ambition(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[AmbitionResponse]:
        """Answer from the queue, else a stub reason and no mark."""
        with self._lock:
            self.ambition_calls += 1
            self.ambition_inputs.append(
                {
                    "plan": plan,
                    "baseline_sections": list(baseline_sections),
                    "options": list(options),
                }
            )
            return _next_response(
                self._ambition_queue,
                lambda: AmbitionResponse(
                    options=[
                        AmbitionWire(
                            option_id=str(o["option_id"]),
                            reason="Stub ambition.",
                            stands_out="no",
                        )
                        for o in options
                    ]
                ),
            ), None

    def profile_setting(
        self, *, plan: dict[str, object], options: list[dict[str, object]]
    ) -> UsageResult[SettingResponse]:
        """Answer from the queue, else ``stub setting`` and no second setting."""
        with self._lock:
            self.setting_calls += 1
            self.setting_inputs.append({"plan": plan, "options": list(options)})
            return _next_response(
                self._setting_queue,
                lambda: SettingResponse(
                    options=[
                        SettingWire(
                            option_id=str(o["option_id"]),
                            main_setting="stub setting",
                            second_setting=None,
                        )
                        for o in options
                    ]
                ),
            ), None

    def fold(
        self, *, facet: Facet, plan: dict[str, object], words: dict[str, str]
    ) -> UsageResult[FoldingResponse]:
        """Answer from the facet's queue, else each word lower-cased or its plan text."""
        with self._lock:
            self.fold_calls[facet] = self.fold_calls.get(facet, 0) + 1
            self.fold_inputs.append({"facet": facet, "plan": plan, "words": dict(words)})
            return _next_response(
                self._fold_queues.setdefault(facet, []),
                lambda: _stub_folds(plan, words),
            ), None


def _stub_folds(plan: dict[str, object], words: dict[str, str]) -> FoldingResponse:
    outcomes = plan.get("outcomes")
    references = [
        text
        for text in [plan.get("target_unit"), *(outcomes if isinstance(outcomes, list) else [])]
        if isinstance(text, str) and text.strip()
    ]
    by_key = {_casefold(text): text for text in references}
    return FoldingResponse(
        folds=[
            FoldWire(word_id=word_id, kind=by_key.get(_casefold(word), word.lower()))
            for word_id, word in words.items()
        ]
    )


def _stub_line(line_key: str, options: list[dict[str, object]]) -> _LineResponse:
    sentence = f"Stub {line_key} sentence."
    if line_is_marked(line_key):
        return MarkedLineResponse(
            options=[
                MarkedLineWire(option_id=str(o["option_id"]), answer=sentence, stands_out="no")
                for o in options
            ]
        )
    return PlainLineResponse(
        options=[PlainLineWire(option_id=str(o["option_id"]), answer=sentence) for o in options]
    )


def _queue[T](responses: T | list[T] | None) -> list[T]:
    if responses is None:
        return []
    if isinstance(responses, list):
        return list(responses)
    return [responses]


def _next_response[T](queue: list[T], default: Callable[[], T]) -> T:
    if not queue:
        return default()
    if len(queue) == 1:
        return queue[0]
    return queue.pop(0)


def _pass_everything(
    requirements: list[dict[str, str]],
    preferences: list[dict[str, str]],
    options: list[dict[str, object]],
) -> ConstrainResponse:
    return ConstrainResponse(
        options=[
            OptionConstrainWire(
                option_id=str(o["option_id"]),
                judgements=[
                    ConstraintJudgementWire(
                        constraint_id=r["id"], verdict="passes", reason="Stub: passes."
                    )
                    for r in requirements
                ],
                guesses=[
                    ReasonedGuessWire(
                        constraint_id=p["id"],
                        guess="May or may not meet it.",
                        leaning="cannot_say",
                    )
                    for p in preferences
                ],
            )
            for o in options
        ]
    )
