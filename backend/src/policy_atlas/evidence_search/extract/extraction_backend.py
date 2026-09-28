"""Extraction backend seams for the IOF and ICF extraction calls and the
intervention profile (see ``iof_prompt.PROMPT_VERSION``,
``icf_prompt.ICF_PROMPT_VERSION`` and
``extract_interventions_prompt.PROMPT_VERSION`` for the live prompt
versions)."""

from __future__ import annotations

from typing import Any, Protocol

import structlog
from langfuse import Langfuse

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import parse_structured, resolve_openai_client
from policy_atlas.core.usage import UsageResult, usage_details, usage_metadata
from policy_atlas.evidence_search.extract.extract_interventions_prompt import (
    INTERVENTIONS_MAX_OUTPUT_TOKENS,
    INTERVENTIONS_MODEL,
    build_interventions_messages,
)
from policy_atlas.evidence_search.extract.extract_interventions_prompt import (
    PROMPT_VERSION as INTERVENTIONS_PROMPT_VERSION,
)
from policy_atlas.evidence_search.extract.icf_prompt import (
    ICF_EXTRACT_MAX_OUTPUT_TOKENS,
    ICF_EXTRACTION_MODEL,
    ICF_PROMPT_VERSION,
    build_icf_extract_messages,
)
from policy_atlas.evidence_search.extract.icf_records import ICFExtractionResponse
from policy_atlas.evidence_search.extract.interventions_records import InterventionsResponse
from policy_atlas.evidence_search.extract.iof_prompt import (
    EXTRACT_MAX_OUTPUT_TOKENS,
    EXTRACTION_MODEL,
    PROMPT_VERSION,
    build_extract_messages,
)
from policy_atlas.evidence_search.extract.iof_records import (
    ExtractionResponse,
    ExtractionWindowPayload,
)

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
        return parse_structured(
            self._client,
            messages=messages,
            response_format=ExtractionResponse,
            usage_event="extraction.extract.usage",
            label="extraction",
            model=EXTRACTION_MODEL,
            max_completion_tokens=EXTRACT_MAX_OUTPUT_TOKENS,
        )

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
                usage_details=usage_details(usage),
                input={"messages": build_extract_messages(payload)},
                output={"findings": [f.model_dump() for f in response.findings]},
                model=EXTRACTION_MODEL,
                metadata={
                    "prompt_version": PROMPT_VERSION,
                    "tss_id": payload.tss_id,
                    "window_index": payload.window_index,
                    "segment_ids": [s["segment_id"] for s in payload.segments],
                    "finding_count": len(response.findings),
                    **usage_metadata(usage),
                },
            )

        response, usage = tracing.traced_call(
            self._langfuse_client,
            name="extract:iof_findings",
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
        return parse_structured(
            self._client,
            messages=messages,
            response_format=ICFExtractionResponse,
            usage_event="extraction.extract_icf.usage",
            label="ICF extraction",
            model=ICF_EXTRACTION_MODEL,
            max_completion_tokens=ICF_EXTRACT_MAX_OUTPUT_TOKENS,
        )

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
                usage_details=usage_details(usage),
                input={"messages": messages},
                output={"findings": [f.model_dump() for f in response.findings]},
                model=ICF_EXTRACTION_MODEL,
                metadata={
                    "prompt_version": ICF_PROMPT_VERSION,
                    "tss_id": payload.tss_id,
                    "window_index": payload.window_index,
                    "segment_ids": [s["segment_id"] for s in payload.segments],
                    "finding_count": len(response.findings),
                    **usage_metadata(usage),
                },
            )

        response, usage = tracing.traced_call(
            self._langfuse_client,
            name="extract:icf_findings",
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


# --- The intervention profile (task 045, ADR 0039 decision 6) ----------------

_INTERVENTIONS_RECORD_DEFAULTS: dict[str, Any] = {
    "design_features": [],
    "is_bundle": False,
    "components": [],
    "outcome": None,
    "population": None,
    "setting": None,
    "study_geography": None,
    "study_design": None,
}


class InterventionsBackend(Protocol):
    """The intervention profile seam: one call per document, title and abstract.

    The payload is the shared extraction payload; the profile reads only its
    ``title``, ``abstract`` and ``primary_evidence_type`` (never a segment of
    full text). A transport or parse failure raises so the caller applies the
    retry and per-document failure policy.
    """

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[InterventionsResponse]:
        """Profile one document's title and abstract.

        Args:
            payload: The document's single payload (window 0).

        Returns:
            The parsed profile plus token usage.
        """
        ...


class OpenAIInterventionsBackend:
    """Live OpenAI implementation of the intervention profile seam.

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
            backend_name="OpenAIInterventionsBackend",
            timeout=300.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[InterventionsResponse]:
        """Profile one document through structured OpenAI output.

        Args:
            payload: The document's single payload (window 0).

        Returns:
            The parsed profile plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed into the expected shape.
        """
        messages = build_interventions_messages(
            title=payload.title,
            abstract=payload.abstract,
            primary_evidence_type=payload.primary_evidence_type,
        )

        def _update(span: Any, result: UsageResult[InterventionsResponse]) -> None:
            response, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={"messages": messages},
                output=response.model_dump(),
                model=INTERVENTIONS_MODEL,
                metadata={
                    "prompt_version": INTERVENTIONS_PROMPT_VERSION,
                    "tss_id": payload.tss_id,
                    "record_count": len(response.records),
                    "covers_no_intervention": response.covers_no_intervention,
                    **usage_metadata(usage),
                },
            )

        response, usage = tracing.traced_call(
            self._langfuse_client,
            name="extract:interventions",
            as_type="generation",
            call=lambda: parse_structured(
                self._client,
                messages=messages,
                response_format=InterventionsResponse,
                usage_event="extraction.extract_interventions.usage",
                label="intervention profile",
                model=INTERVENTIONS_MODEL,
                max_completion_tokens=INTERVENTIONS_MAX_OUTPUT_TOKENS,
            ),
            update=_update,
        )
        return response, usage


class StubInterventionsBackend:
    """Deterministic zero-egress intervention profile backend for tests and local runs."""

    mode = "stub"

    def extract(self, payload: ExtractionWindowPayload) -> UsageResult[InterventionsResponse]:
        """Return the sentinel-driven profile from the payload's envelope metadata.

        Sentinels (stub only; never in a live prompt): ``_stub_interventions``
        — a list of records (``covers_no_intervention`` is then true exactly
        when the list is empty) or a full response object; a record may omit
        every nullable or list field. ``_stub_interventions_failed`` raises.
        No sentinel profiles the document as covering no intervention.

        Args:
            payload: The document's single payload.

        Returns:
            Deterministic profile output plus no token usage.

        Raises:
            RuntimeError: If ``_stub_interventions_failed`` is truthy.
        """
        if payload.metadata.get("_stub_interventions_failed"):
            raise RuntimeError("Stub intervention profile failure sentinel.")
        raw = payload.metadata.get("_stub_interventions")
        if raw is None:
            return InterventionsResponse(records=[], covers_no_intervention=True), None
        if isinstance(raw, list):
            raw = {"records": raw, "covers_no_intervention": not raw}
        records = [
            {**_INTERVENTIONS_RECORD_DEFAULTS, **record} if isinstance(record, dict) else record
            for record in raw.get("records", [])
        ]
        return (
            InterventionsResponse.model_validate({**raw, "records": records}),
            None,
        )
