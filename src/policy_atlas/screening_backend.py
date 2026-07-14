"""Screening backend seam for the screen_v2 and screen_fulltext_v1 calls."""

from __future__ import annotations

from typing import Any, Protocol

from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam

from policy_atlas import tracing
from policy_atlas.openai_client import parse_structured, resolve_openai_client
from policy_atlas.prompt_fields import confidence_is_valid, scrub_nul
from policy_atlas.screen_prompt import (
    SCREEN_FULLTEXT_PROMPT_VERSION,
    SCREEN_MAX_OUTPUT_TOKENS,
    SCREEN_MODEL,
    SCREEN_PROMPT_VERSION,
    ScreenEnvelopePayload,
    ScreenFullTextPayload,
    ScreenRepWire,
    build_screen_fulltext_messages,
    build_screen_messages,
)
from policy_atlas.usage import UsageResult, usage_metadata


class ScreeningBackend(Protocol):
    """The screening seam for metadata and full-text relevance calls.

    Backends return one structurally parsed rep per call; transport, parse, and
    code-side validation failures raise so the caller can apply retry and
    per-document failure policy.
    """

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def screen_envelope(
        self,
        payload: ScreenEnvelopePayload,
        *,
        rep_index: int = 0,
    ) -> UsageResult[ScreenRepWire]:
        """Screen one document metadata envelope.

        Args:
            payload: The document envelope plus scope intent for one screen rep.
            rep_index: Zero-based consensus rep index, recorded in traces only.

        Returns:
            One parsed screening rep plus token usage.

        Raises:
            RuntimeError: If the backend cannot produce a valid rep.
        """
        ...

    def screen_fulltext(
        self, payload: ScreenFullTextPayload
    ) -> UsageResult[ScreenRepWire]:
        """Screen one full-text window for stage-2 confirmation.

        Args:
            payload: The document title, scope intent, and full-text segments.

        Returns:
            One parsed screening rep plus token usage.

        Raises:
            RuntimeError: If the backend cannot produce a valid rep.
        """
        ...


def _scrub_rep(rep: ScreenRepWire) -> ScreenRepWire:
    return rep.model_copy(update={"reason": scrub_nul(rep.reason)})


class OpenAIScreeningBackend:
    """Live OpenAI implementation of the screening seam.

    Args:
        api_key: Optional OpenAI API key. If omitted, ``OPENAI_API_KEY`` is read
            from the environment; keys are never read from persistent config.
        langfuse_client: Optional Langfuse client. When omitted, tracing is a
            no-op and no Langfuse object is created.

    Raises:
        RuntimeError: If no OpenAI API key is provided or configured.
    """

    mode = "live"

    def __init__(
        self,
        api_key: str | None = None,
        langfuse_client: Langfuse | None = None,
    ) -> None:
        self._client = resolve_openai_client(
            api_key,
            backend_name="OpenAIScreeningBackend",
            timeout=120.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def _parse_once(
        self,
        *,
        messages: list[ChatCompletionMessageParam],
        usage_event: str,
    ) -> UsageResult[ScreenRepWire]:
        parsed, usage = parse_structured(
            self._client,
            messages=messages,
            response_format=ScreenRepWire,
            usage_event=usage_event,
            label="screening",
            model=SCREEN_MODEL,
            max_completion_tokens=SCREEN_MAX_OUTPUT_TOKENS,
        )
        return _scrub_rep(parsed), usage

    def screen_envelope(
        self,
        payload: ScreenEnvelopePayload,
        *,
        rep_index: int = 0,
    ) -> UsageResult[ScreenRepWire]:
        """Screen one document envelope through structured OpenAI output.

        Args:
            payload: The document envelope plus scope intent for one screen rep.
            rep_index: Zero-based consensus rep index, recorded in traces only.

        Returns:
            One parsed screening rep plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed or has invalid confidence.
        """
        messages = build_screen_messages(payload)
        langfuse_client = self._langfuse_client

        def _update(
            span: Any,
            result: UsageResult[ScreenRepWire],
        ) -> None:
            rep, usage = result
            span.update(
                input={"messages": messages},
                output=rep.model_dump(),
                model=SCREEN_MODEL,
                metadata={
                    "prompt_version": SCREEN_PROMPT_VERSION,
                    "pss_id": payload.pss_id,
                    "rep_index": rep_index,
                    **usage_metadata(usage),
                },
            )

        def _score_trace(
            _span: Any,
            result: UsageResult[ScreenRepWire],
        ) -> None:
            if langfuse_client is None:
                return
            rep, _usage = result
            confidence = float(rep.confidence)
            langfuse_client.score_current_trace(
                name="screen_rep_valid",
                value=1.0 if confidence_is_valid(confidence) else 0.0,
                data_type="NUMERIC",
            )
            langfuse_client.score_current_trace(
                name="screen_rep_confidence",
                value=confidence,
                data_type="NUMERIC",
            )

        rep, usage = tracing.traced_call(
            langfuse_client,
            name=f"screen:{payload.pss_id[:8]}:r{rep_index}",
            as_type="generation",
            call=lambda: self._parse_once(
                messages=messages,
                usage_event="screening.screen.usage",
            ),
            update=_update,
            after=_score_trace,
        )
        if not confidence_is_valid(rep.confidence):
            raise RuntimeError(
                "OpenAI screening response confidence out of range "
                f"for pss_id={payload.pss_id!r}, rep_index={rep_index}: {rep.confidence}."
            )
        return rep, usage

    def screen_fulltext(
        self, payload: ScreenFullTextPayload
    ) -> UsageResult[ScreenRepWire]:
        """Screen one full-text window through structured OpenAI output.

        Args:
            payload: The document title, scope intent, and full-text segments.

        Returns:
            One parsed screening rep plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed or has invalid confidence.
        """
        messages = build_screen_fulltext_messages(payload)
        langfuse_client = self._langfuse_client

        def _update(
            span: Any,
            result: UsageResult[ScreenRepWire],
        ) -> None:
            rep, usage = result
            span.update(
                input={"messages": messages},
                output=rep.model_dump(),
                model=SCREEN_MODEL,
                metadata={
                    "prompt_version": SCREEN_FULLTEXT_PROMPT_VERSION,
                    "pss_id": payload.pss_id,
                    "window_index": payload.window_index,
                    **usage_metadata(usage),
                },
            )

        def _score_trace(
            _span: Any,
            result: UsageResult[ScreenRepWire],
        ) -> None:
            if langfuse_client is None:
                return
            rep, _usage = result
            confidence = float(rep.confidence)
            langfuse_client.score_current_trace(
                name="screen_rep_valid",
                value=1.0 if confidence_is_valid(confidence) else 0.0,
                data_type="NUMERIC",
            )
            langfuse_client.score_current_trace(
                name="screen_rep_confidence",
                value=confidence,
                data_type="NUMERIC",
            )

        rep, usage = tracing.traced_call(
            langfuse_client,
            name=f"screen_fulltext:{payload.pss_id[:8]}",
            as_type="generation",
            call=lambda: self._parse_once(
                messages=messages,
                usage_event="screening.screen.usage",
            ),
            update=_update,
            after=_score_trace,
        )
        if not confidence_is_valid(rep.confidence):
            raise RuntimeError(
                "OpenAI full-text screening response confidence out of range "
                f"for pss_id={payload.pss_id!r}, window_index={payload.window_index}: "
                f"{rep.confidence}."
            )
        return rep, usage


class StubScreeningBackend:
    """Deterministic zero-egress screening backend for tests and local runs."""

    mode = "stub"

    def screen_envelope(
        self,
        payload: ScreenEnvelopePayload,
        *,
        rep_index: int = 0,
    ) -> UsageResult[ScreenRepWire]:
        """Return sentinel-driven metadata screening output.

        Args:
            payload: The document envelope. ``metadata`` carries stub sentinels;
                it never enters live prompts.
            rep_index: Accepted for protocol compatibility; ignored by the stub.

        Returns:
            Deterministic screening output plus no token usage.

        Raises:
            RuntimeError: If ``_stub_failed`` is truthy.
        """
        del rep_index
        metadata = payload.metadata
        if metadata.get("_stub_failed"):
            raise RuntimeError("Stub screening failure sentinel.")
        if metadata.get("_stub_not_relevant"):
            return (
                ScreenRepWire(
                    decision="not_relevant",
                    confidence=0.95,
                    reason="Deterministic stub exclusion.",
                ),
                None,
            )
        if metadata.get("_stub_unsure"):
            return (
                ScreenRepWire(
                    decision="unsure",
                    confidence=0.6,
                    reason="Deterministic stub unsure.",
                ),
                None,
            )

        confidence = (
            0.9
            if isinstance(payload.abstract, str) and bool(payload.abstract.strip())
            else 0.7
        )
        return (
            ScreenRepWire(
                decision="relevant",
                confidence=confidence,
                reason="Deterministic stub inclusion.",
            ),
            None,
        )

    def screen_fulltext(
        self, payload: ScreenFullTextPayload
    ) -> UsageResult[ScreenRepWire]:
        """Return sentinel-driven full-text screening output.

        Args:
            payload: The full-text screen payload. ``metadata`` carries stub
                sentinels; it never enters live prompts.

        Returns:
            Deterministic stage-2 screening output plus no token usage.

        Raises:
            RuntimeError: If ``_stub_stage2_failed`` is truthy.
        """
        metadata = payload.metadata
        if metadata.get("_stub_stage2_failed"):
            raise RuntimeError("Stub screening stage-2 failure sentinel.")
        if metadata.get("_stub_stage2_demote"):
            return (
                ScreenRepWire(
                    decision="not_relevant",
                    confidence=0.95,
                    reason="Deterministic stub stage-2 demotion.",
                ),
                None,
            )
        if metadata.get("_stub_stage2_unsure"):
            return (
                ScreenRepWire(
                    decision="unsure",
                    confidence=0.6,
                    reason="Deterministic stub stage-2 unsure.",
                ),
                None,
            )
        return (
            ScreenRepWire(
                decision="relevant",
                confidence=0.9,
                reason="Deterministic stub stage-2 confirmation.",
            ),
            None,
        )
