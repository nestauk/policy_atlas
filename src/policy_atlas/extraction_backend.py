"""Extraction backend seam for the extract_iof IOF extraction call (see
``extract_prompt.PROMPT_VERSION`` for the live prompt version)."""

from __future__ import annotations

from typing import Any, Protocol

import structlog
from langfuse import Langfuse

from policy_atlas import tracing
from policy_atlas.extract_prompt import (
    EXTRACT_MAX_OUTPUT_TOKENS,
    EXTRACTION_MODEL,
    PROMPT_VERSION,
    build_extract_messages,
)
from policy_atlas.extraction_records import ExtractionResponse, ExtractionWindowPayload
from policy_atlas.implementation_context_prompt import (
    ICF_EXTRACT_MAX_OUTPUT_TOKENS,
    ICF_EXTRACTION_MODEL,
    ICF_PROMPT_VERSION,
    build_icf_extract_messages,
)
from policy_atlas.implementation_context_records import ICFExtractionResponse
from policy_atlas.openai_client import resolve_openai_client
from policy_atlas.usage import UsageResult, log_usage, token_usage_from_provider, usage_metadata

log = structlog.get_logger()


def _with_iof_defaults(raw_findings: Any) -> Any:
    """Default legacy stub sentinel records to the current wire shape."""
    if not isinstance(raw_findings, list):
        return raw_findings
    defaulted: list[Any] = []
    for record in raw_findings:
        if isinstance(record, dict):
            updated = dict(record)
            updated.setdefault("setting", None)
            updated.setdefault("study_geography", None)
            updated.setdefault("effect_basis", None)
            defaulted.append(updated)
            continue
        defaulted.append(record)
    return defaulted


def _with_icf_defaults(raw_findings: Any) -> Any:
    """Default legacy ICF stub sentinel records to the current wire shape."""
    if not isinstance(raw_findings, list):
        return raw_findings
    defaulted: list[Any] = []
    for record in raw_findings:
        if isinstance(record, dict):
            updated = dict(record)
            updated.setdefault("context_label", None)
            defaulted.append(updated)
            continue
        defaulted.append(record)
    return defaulted


class ExtractionBackend(Protocol):
    """The extraction seam.

    Backends return structurally parsed output only; a transport or parse
    failure raises so the caller can apply retry and per-document failure
    policy.
    """

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[ExtractionResponse]:
        """Extract findings from one window of one document's basis text.

        Args:
            payload: The window's basis segments plus envelope context.

        Returns:
            Raw structurally parsed extraction output plus token usage.
        """
        ...


class OpenAIExtractionBackend:
    """Live OpenAI implementation of the extraction seam.

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
            backend_name="OpenAIExtractionBackend",
            timeout=300.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def _extract_once(
        self,
        payload: ExtractionWindowPayload,
    ) -> UsageResult[ExtractionResponse]:
        messages = build_extract_messages(payload)
        response = self._client.chat.completions.parse(
            model=EXTRACTION_MODEL,
            messages=messages,
            response_format=ExtractionResponse,
            max_completion_tokens=EXTRACT_MAX_OUTPUT_TOKENS,
        )
        log_usage("extraction.extract.usage", response.usage)
        if not response.choices:
            raise RuntimeError("OpenAI extraction response had no choices.")
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI extraction response was not parsed.")
        parsed_model: ExtractionResponse = parsed
        return parsed_model, token_usage_from_provider(response.usage)

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[ExtractionResponse]:
        """Extract findings through structured OpenAI output.

        Args:
            payload: The window's basis segments plus envelope context.

        Returns:
            Raw structurally parsed extraction output plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed into the expected shape.
        """
        def _update(
            span: Any, result: UsageResult[ExtractionResponse]
        ) -> None:
            response, usage = result
            span.update(
                input={"messages": build_extract_messages(payload)},
                output={"findings": [f.model_dump() for f in response.findings]},
                model=EXTRACTION_MODEL,
                metadata={
                    "prompt_version": PROMPT_VERSION,
                    "pss_id": payload.pss_id,
                    "window_index": payload.window_index,
                    "segment_ids": [s["segment_id"] for s in payload.segments],
                    "finding_count": len(response.findings),
                    **usage_metadata(usage),
                },
            )

        response, usage = tracing.traced_call(
            self._langfuse_client,
            name=f"extract:{payload.pss_id[:8]}:w{payload.window_index}",
            as_type="generation",
            call=lambda: self._extract_once(payload),
            update=_update,
        )
        return response, usage


class OpenAIICFExtractionBackend:
    """Live OpenAI implementation of the ICF extraction seam.

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
            backend_name="OpenAIICFExtractionBackend",
            timeout=300.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def _extract_once(
        self,
        payload: ExtractionWindowPayload,
    ) -> UsageResult[ICFExtractionResponse]:
        messages = build_icf_extract_messages(payload)
        response = self._client.chat.completions.parse(
            model=ICF_EXTRACTION_MODEL,
            messages=messages,
            response_format=ICFExtractionResponse,
            max_completion_tokens=ICF_EXTRACT_MAX_OUTPUT_TOKENS,
        )
        log_usage("extraction.extract_icf.usage", response.usage)
        if not response.choices:
            raise RuntimeError("OpenAI ICF extraction response had no choices.")
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI ICF extraction response was not parsed.")
        parsed_model: ICFExtractionResponse = parsed
        return parsed_model, token_usage_from_provider(response.usage)

    def extract(
        self, payload: ExtractionWindowPayload
    ) -> UsageResult[ICFExtractionResponse]:
        """Extract ICF findings through structured OpenAI output.

        Args:
            payload: The window's basis segments plus envelope context.

        Returns:
            Raw structurally parsed ICF extraction output plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed into the expected shape.
        """
        messages = build_icf_extract_messages(payload)

        def _update(
            span: Any, result: UsageResult[ICFExtractionResponse]
        ) -> None:
            response, usage = result
            span.update(
                input={"messages": messages},
                output={"findings": [f.model_dump() for f in response.findings]},
                model=ICF_EXTRACTION_MODEL,
                metadata={
                    "prompt_version": ICF_PROMPT_VERSION,
                    "pss_id": payload.pss_id,
                    "window_index": payload.window_index,
                    "segment_ids": [s["segment_id"] for s in payload.segments],
                    "finding_count": len(response.findings),
                    **usage_metadata(usage),
                },
            )

        response, usage = tracing.traced_call(
            self._langfuse_client,
            name=f"extract_icf:{payload.pss_id[:8]}:w{payload.window_index}",
            as_type="generation",
            call=lambda: self._extract_once(payload),
            update=_update,
        )
        return response, usage


class StubExtractionBackend:
    """Deterministic zero-egress extraction backend for tests and local runs."""

    mode = "stub"

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[ExtractionResponse]:
        """Return sentinel-driven findings from the payload's envelope metadata.

        Args:
            payload: The window's basis segments plus envelope context. The
                ``metadata`` dict (the envelope snapshot metadata) carries the
                stub's ``_stub_*`` sentinels; it never enters the live prompt.

        Returns:
            Deterministic extraction output plus no token usage.

        Raises:
            RuntimeError: If ``_stub_extract_failed`` is truthy.
        """
        if payload.metadata.get("_stub_extract_failed"):
            raise RuntimeError("Stub extraction failure sentinel.")

        if "_stub_iof_windows" in payload.metadata:
            windows = payload.metadata["_stub_iof_windows"]
            return (
                ExtractionResponse.model_validate(
                    {
                        "findings": _with_iof_defaults(
                            windows.get(str(payload.window_index), [])
                        )
                    }
                ),
                None,
            )

        if "_stub_iof" in payload.metadata:
            if payload.window_index == 0:
                return (
                    ExtractionResponse.model_validate(
                        {
                            "findings": _with_iof_defaults(payload.metadata["_stub_iof"])
                        }
                    ),
                    None,
                )
            return ExtractionResponse(findings=[]), None

        return ExtractionResponse(findings=[]), None


class StubICFExtractionBackend:
    """Deterministic zero-egress ICF extraction backend for tests and local runs."""

    mode = "stub"

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[ICFExtractionResponse]:
        """Return sentinel-driven ICF findings from the payload metadata.

        Args:
            payload: The window's basis segments plus envelope context. The
                ``metadata`` dict carries ``_stub_icf*`` sentinels for the
                stub only; it never enters a live prompt.

        Returns:
            Deterministic ICF extraction output plus no token usage.

        Raises:
            RuntimeError: If ``_stub_icf_extract_failed`` is truthy.
        """
        if payload.metadata.get("_stub_icf_extract_failed"):
            raise RuntimeError("Stub ICF extraction failure sentinel.")

        if "_stub_icf_windows" in payload.metadata:
            windows = payload.metadata["_stub_icf_windows"]
            return (
                ICFExtractionResponse.model_validate(
                    {
                        "findings": _with_icf_defaults(
                            windows.get(str(payload.window_index), [])
                        )
                    }
                ),
                None,
            )

        if "_stub_icf" in payload.metadata:
            if payload.window_index == 0:
                return (
                    ICFExtractionResponse.model_validate(
                        {
                            "findings": _with_icf_defaults(
                                payload.metadata["_stub_icf"]
                            )
                        }
                    ),
                    None,
                )
            return ICFExtractionResponse(findings=[]), None

        return ICFExtractionResponse(findings=[]), None
