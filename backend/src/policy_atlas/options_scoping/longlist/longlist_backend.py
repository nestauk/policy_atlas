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
- ``profile_line`` / ``profile_potential_impact`` / ``profile_ambition`` /
  ``profile_setting`` — the ``option_profile`` step's eleven calls over the
  whole list: one per line of "What it would take" (the Potential impact
  line has its own call, task 055), the ambition and the delivery setting (judgment
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
  :mod:`~policy_atlas.options_scoping.option_profile.folding_prompt`);
- ``place_sentences`` — the ``option_profile`` step's second wave: one call
  per option with evaluating documents, one sentence per place (mini model;
  task 046, amendment 4, R80; S31;
  :mod:`~policy_atlas.options_scoping.option_profile.place_sentences_prompt`);
- ``propose_shortlist`` — the ``shortlist`` step's one proposal call over the
  assembled messages (judgment model; task 055, P6;
  :mod:`~policy_atlas.options_scoping.shortlist.shortlist_prompt`). It takes
  the messages, not the data, so the step can append its re-ask turn.

Backends parse structurally and return the wire; the component and the shared
clustering engine own every semantic check. :class:`StubLonglistBackend` is
deterministic and makes no call.
"""

from __future__ import annotations

import os
import re
import threading
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from policy_atlas.core.openai_client import resolve_openai_client, traced_parse
from policy_atlas.core.usage import UsageResult
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
    PotentialImpactResponse,
    PotentialImpactWire,
    SettingResponse,
    SettingWire,
    build_ambition_messages,
    build_line_messages,
    build_potential_impact_messages,
    build_setting_messages,
    line_is_marked,
)
from policy_atlas.options_scoping.option_profile.place_sentences_prompt import (
    PLACE_SENTENCES_MAX_OUTPUT_TOKENS,
    PLACE_SENTENCES_PROMPT_VERSION,
    PlaceSentencesResponse,
    PlaceSentenceWire,
    build_place_sentences_messages,
)
from policy_atlas.options_scoping.shortlist.shortlist_prompt import (
    SHORTLIST_MAX_OUTPUT_TOKENS,
    SHORTLIST_PROMPT_VERSION,
    ShortlistPickWire,
    ShortlistWire,
)
from policy_atlas.options_scoping.text import fold_text
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
from policy_atlas.runtime.agent_backend import _as_queue, _next

#: The judgment model (discovery, themes, typing, the profile) and the small
#: model (assignment, folding, place sentences) — contract § Model route.
#: Env-overridable, the `SYNTHESIS_MODEL` pattern (owner, 2026-10-14: the
#: options scoping tiers moved from gpt-5.5 / gpt-5.4-mini to gpt-5.6-sol /
#: gpt-5.6-luna).
LONGLIST_JUDGMENT_MODEL = os.environ.get("POLICY_ATLAS_LONGLIST_JUDGMENT_MODEL", "gpt-5.6-sol")
LONGLIST_ASSIGNMENT_MODEL = os.environ.get("POLICY_ATLAS_LONGLIST_ASSIGNMENT_MODEL", "gpt-5.6-luna")
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
        considerations: list[str] | None = None,
    ) -> UsageResult[MarkedLineResponse | PlainLineResponse]:
        """Write one line of "What it would take" for every option (R36, S16).

        One call over the whole list; the ten profile calls run at one time.

        Args:
            line_key: One of the eight line keys.
            plan: The plan fields as data, place stripped.
            where: The plan's Where for ``who_decides``; ``None`` otherwise.
            baseline_sections: ``(title, markdown)`` per baseline section.
            options: Every option as data, keyed by its short ``option_id``.
            considerations: The texts of the plan's constraints on who can
                act, for ``who_decides`` only; ``None`` otherwise (task 046,
                amendment 4: R89; S35).

        Returns:
            A :class:`MarkedLineResponse` on a marked line, else a
            :class:`PlainLineResponse`, and token usage.
        """
        ...

    def profile_potential_impact(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[PotentialImpactResponse]:
        """Write the Potential impact line for every option (task 055, item 6).

        Args:
            plan: The plan fields as data, with Where, the target unit and
                the outcomes as written.
            baseline_sections: ``(title, markdown)`` per baseline section.
            options: Every option as data, with the units it was tried on,
                its evaluated countries and its role counts.

        Returns:
            One sentence per option and token usage.
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

    def place_sentences(
        self,
        *,
        option: dict[str, Any],
        plan: dict[str, Any],
        vocabulary: dict[str, list[str]],
        places: list[dict[str, Any]],
    ) -> UsageResult[PlaceSentencesResponse]:
        """One option's place sentences (task 046, amendment 4, R80; S31).

        Args:
            option: ``{"name", "description"}``.
            plan: ``{"target_unit", "outcomes"}``, place stripped.
            vocabulary: The list's folded kinds.
            places: One entry per place (``place_id``, ``place``,
                ``documents_total``, ``documents``).

        Returns:
            The parsed sentences and token usage.
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

    def propose_shortlist(
        self, *, messages: list[ChatCompletionMessageParam]
    ) -> UsageResult[ShortlistWire]:
        """Propose the shortlist's places over the assembled messages (task 055, P6).

        Args:
            messages: The system and user messages, plus, on the second
                attempt, the first answer and the re-ask turn.

        Returns:
            The parsed proposal and token usage.
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
        return traced_parse(
            self._client,
            self._langfuse_client,
            messages=messages,
            response_format=response_format,
            model=model,
            max_output_tokens=max_output_tokens,
            usage_event=f"{name.replace(':', '.')}.usage",
            label=name,
            name=name,
            prompt_version=prompt_version,
            session_id=self._session_id,
            metadata=metadata,
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
        considerations: list[str] | None = None,
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
            considerations=considerations,
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

    def profile_potential_impact(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[PotentialImpactResponse]:
        """The Potential impact call on the judgment model (see :class:`LonglistBackend`)."""
        return self._call(
            build_potential_impact_messages(
                plan=plan, baseline_sections=baseline_sections, options=options
            ),
            response_format=PotentialImpactResponse,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=OPTION_PROFILE_MAX_OUTPUT_TOKENS,
            name="option_profile:potential_impact",
            prompt_version=OPTION_PROFILE_PROMPT_VERSION,
        )

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

    def place_sentences(
        self,
        *,
        option: dict[str, Any],
        plan: dict[str, Any],
        vocabulary: dict[str, list[str]],
        places: list[dict[str, Any]],
    ) -> UsageResult[PlaceSentencesResponse]:
        """One option's place-sentence call on the mini model (see :class:`LonglistBackend`)."""
        return self._call(
            build_place_sentences_messages(
                option=option, plan=plan, vocabulary=vocabulary, places=places
            ),
            response_format=PlaceSentencesResponse,
            model=LONGLIST_ASSIGNMENT_MODEL,
            max_output_tokens=PLACE_SENTENCES_MAX_OUTPUT_TOKENS,
            name="option_profile:place_sentences",
            prompt_version=PLACE_SENTENCES_PROMPT_VERSION,
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

    def propose_shortlist(
        self, *, messages: list[ChatCompletionMessageParam]
    ) -> UsageResult[ShortlistWire]:
        """The proposal call on the judgment model (see :class:`LonglistBackend`).

        Its static Langfuse name is ``longlist:shortlist`` and its usage
        event ``longlist.shortlist.usage``.
        """
        return self._call(
            messages,
            response_format=ShortlistWire,
            model=LONGLIST_JUDGMENT_MODEL,
            max_output_tokens=SHORTLIST_MAX_OUTPUT_TOKENS,
            name="longlist:shortlist",
            prompt_version=SHORTLIST_PROMPT_VERSION,
        )


#: The stub's one discovered option.
STUB_DISCOVERED_LABEL = "Stub discovered option"
#: The stub's Potential impact sentence.
STUB_POTENTIAL_IMPACT = (
    "Moderate if it works: stub pathway; would apply to the target unit, tried on "
    "the records' units; the records describe proposals only."
)

#: The stub's one theme.
STUB_THEME_LABEL = "Stub theme"


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
      kind is that plan text; the kinds listed once each in first-seen order,
      each word answered by its kind's index. Its calls and inputs are
      recorded under the lock.
    - ``place_sentences`` answers from its own FIFO queue the same way (a
      queued exception is raised, so a test can fail a call); with none,
      each place in the input gets ``"{documents_total} evaluations in
      {place}."``, which passes the trace check. Its calls and inputs are
      recorded under the lock.
    - ``propose_shortlist`` answers from its own FIFO queue the same way (a
      queued exception is raised); with none, it picks the first N candidate
      ids in the order the user message lists them, N being the message's
      "Places to fill", each with the reason ``"stub reason"``, and the note
      ``"stub note"``. Its messages are recorded under ``inputs["shortlist"]``.

    Each call is counted in :attr:`calls` (``line`` and ``fold`` per key in
    :attr:`line_calls` and :attr:`fold_calls`) and its inputs appended to
    ``inputs[name]``, the name being ``constrain``, ``distinct``,
    ``authority``, ``line``, ``potential_impact``, ``ambition``, ``setting``,
    ``fold``, ``place_sentence`` or ``shortlist``.

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
        place_sentence_responses: Canned place-sentence answers (a
            :class:`PlaceSentencesResponse`, any other object to answer
            malformed, or an exception to raise), or ``None`` for the
            deterministic default.
        potential_impact_responses: Canned :class:`PotentialImpactResponse`
            value(s), or ``None`` for the deterministic default.
        shortlist_responses: Canned proposal answers (a
            :class:`ShortlistWire`, or an exception to raise), or ``None``
            for the deterministic default.
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
        place_sentence_responses: Any = None,
        potential_impact_responses: PotentialImpactResponse
        | list[PotentialImpactResponse]
        | None = None,
        shortlist_responses: Any = None,
    ) -> None:
        self._queues: dict[str, list[Any]] = {
            "constrain": _as_queue(constrain_responses),
            "distinct": _as_queue(distinct_responses),
            "authority": _as_queue(authority_responses),
            "ambition": _as_queue(ambition_responses),
            "setting": _as_queue(setting_responses),
            "place_sentence": _as_queue(place_sentence_responses),
            "potential_impact": _as_queue(potential_impact_responses),
            "shortlist": _as_queue(shortlist_responses),
            **{f"line:{k}": _as_queue(v) for k, v in (line_responses or {}).items()},
            **{f"fold:{k}": _as_queue(v) for k, v in (fold_responses or {}).items()},
        }
        self._lock = threading.Lock()
        self.calls: Counter[str] = Counter()
        self.line_calls: Counter[str] = Counter()
        self.fold_calls: Counter[str] = Counter()
        self.inputs: defaultdict[str, list[Any]] = defaultdict(list)

    def _answer[T](
        self, name: str, inputs: Any, default: Callable[[], T], *, key: str | None = None
    ) -> T:
        """Count the call and record its inputs, then answer from its queue or ``default``."""
        with self._lock:
            self.inputs[name].append(inputs)
            if key is None:
                self.calls[name] += 1
            else:
                (self.line_calls if name == "line" else self.fold_calls)[key] += 1
            queue = self._queues.setdefault(name if key is None else f"{name}:{key}", [])
            return cast(T, _next(queue, default))

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
        seed_labels = {fold_text(str(seed["label"])) for seed in seeds}
        unmatched = any(
            fold_text(str(entry.get("name", ""))) not in seed_labels for entry in digest
        )
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
        by_name = {fold_text(str(o["label"])): str(o["label"]) for o in options}
        fallback = by_name.get(fold_text(STUB_DISCOVERED_LABEL), "ungroupable")
        assignments = []
        for record in records:
            label = by_name.get(fold_text(str(record.get("intervention", ""))), fallback)
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
        inputs = {
            "plan": plan,
            "baseline_sections": list(baseline_sections),
            "requirements": list(requirements),
            "preferences": list(preferences),
            "options": list(options),
        }
        return self._answer(
            "constrain", inputs, lambda: _pass_everything(requirements, preferences, options)
        ), None

    def distinct(self, *, options: list[dict[str, object]]) -> UsageResult[DistinctResponse]:
        """Answer from the queue, else report no duplicate."""
        return self._answer(
            "distinct", list(options), lambda: DistinctResponse(duplicates=[])
        ), None

    def authority(
        self, *, considerations: list[str], options: list[dict[str, object]]
    ) -> UsageResult[AuthorityResponse]:
        """Answer from the queue, else every option ``unclear``."""
        return self._answer(
            "authority",
            {"considerations": list(considerations), "options": list(options)},
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
        considerations: list[str] | None = None,
    ) -> UsageResult[MarkedLineResponse | PlainLineResponse]:
        """Answer from the line's queue, else a stub sentence and no mark."""
        inputs = {
            "line_key": line_key,
            "plan": plan,
            "where": where,
            "baseline_sections": list(baseline_sections),
            "options": list(options),
            "considerations": considerations,
        }
        return self._answer(
            "line", inputs, lambda: _stub_line(line_key, options), key=line_key
        ), None

    def profile_potential_impact(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[PotentialImpactResponse]:
        """Answer from the queue, else one fixed sentence per option."""
        return self._answer(
            "potential_impact",
            {"plan": plan, "baseline_sections": list(baseline_sections), "options": list(options)},
            lambda: PotentialImpactResponse(
                options=[
                    PotentialImpactWire(option_id=str(o["option_id"]), answer=STUB_POTENTIAL_IMPACT)
                    for o in options
                ]
            ),
        ), None

    def profile_ambition(
        self,
        *,
        plan: dict[str, object],
        baseline_sections: list[tuple[str, str]],
        options: list[dict[str, object]],
    ) -> UsageResult[AmbitionResponse]:
        """Answer from the queue, else a stub reason and no mark."""
        return self._answer(
            "ambition",
            {"plan": plan, "baseline_sections": list(baseline_sections), "options": list(options)},
            lambda: AmbitionResponse(
                options=[
                    AmbitionWire(
                        option_id=str(o["option_id"]), reason="Stub ambition.", stands_out="no"
                    )
                    for o in options
                ]
            ),
        ), None

    def profile_setting(
        self, *, plan: dict[str, object], options: list[dict[str, object]]
    ) -> UsageResult[SettingResponse]:
        """Answer from the queue, else ``stub setting`` and no second setting."""
        return self._answer(
            "setting",
            {"plan": plan, "options": list(options)},
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
        return self._answer(
            "fold",
            {"facet": facet, "plan": plan, "words": dict(words)},
            lambda: _stub_folds(plan, words),
            key=facet,
        ), None

    def place_sentences(
        self,
        *,
        option: dict[str, Any],
        plan: dict[str, Any],
        vocabulary: dict[str, list[str]],
        places: list[dict[str, Any]],
    ) -> UsageResult[PlaceSentencesResponse]:
        """Answer from the queue (an exception is raised), else one stub sentence per place."""
        response: Any = self._answer(
            "place_sentence",
            {"option": option, "plan": plan, "vocabulary": vocabulary, "places": places},
            lambda: _stub_place_sentences(places),
        )
        if isinstance(response, BaseException):
            raise response
        return response, None

    def propose_shortlist(
        self, *, messages: list[ChatCompletionMessageParam]
    ) -> UsageResult[ShortlistWire]:
        """Answer from the queue (an exception is raised), else the first N candidates."""
        response: Any = self._answer(
            "shortlist", list(messages), lambda: _stub_shortlist(messages)
        )
        if isinstance(response, BaseException):
            raise response
        return response, None


#: The first user message's "Places to fill" line and its candidate id lines.
_STUB_TO_FILL = re.compile(r"^Places to fill \(data\): (\d+)$", re.MULTILINE)
_STUB_CANDIDATE_ID = re.compile(r"^id: (o\d+)$", re.MULTILINE)


def _stub_shortlist(messages: list[ChatCompletionMessageParam]) -> ShortlistWire:
    """The first N candidate ids of the first user message, in listed order."""
    text = next(
        str(message.get("content", "")) for message in messages if message["role"] == "user"
    )
    found = _STUB_TO_FILL.search(text)
    to_fill = int(found.group(1)) if found else 0
    candidates_at = text.find("Candidates (data")
    ids = _STUB_CANDIDATE_ID.findall(text[candidates_at:] if candidates_at >= 0 else "")
    return ShortlistWire(
        picks=[ShortlistPickWire(option_id=oid, reason="stub reason") for oid in ids[:to_fill]],
        note="stub note",
    )


def _stub_place_sentences(places: list[dict[str, Any]]) -> PlaceSentencesResponse:
    return PlaceSentencesResponse(
        places=[
            PlaceSentenceWire(
                place_id=str(place["place_id"]),
                sentence=f"{place['documents_total']} evaluations in {place['place']}.",
            )
            for place in places
        ]
    )


def _stub_folds(plan: dict[str, object], words: dict[str, str]) -> FoldingResponse:
    outcomes = plan.get("outcomes")
    references = [
        text
        for text in [plan.get("target_unit"), *(outcomes if isinstance(outcomes, list) else [])]
        if isinstance(text, str) and text.strip()
    ]
    by_key = {fold_text(text): text for text in references}
    kinds: list[str] = []
    folds: list[FoldWire] = []
    for word_id, word in words.items():
        kind = by_key.get(fold_text(word), word.lower())
        if kind not in kinds:
            kinds.append(kind)
        folds.append(FoldWire(word_id=word_id, kind=kinds.index(kind)))
    return FoldingResponse(kinds=kinds, folds=folds)


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
