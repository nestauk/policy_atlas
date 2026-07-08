"""Classification backend seam for the classify_v1 call."""

from __future__ import annotations

from typing import Any, Protocol, cast

from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from openai.types.completion_usage import CompletionUsage

from policy_atlas import tracing
from policy_atlas.classify_prompt import (
    CLASSIFY_MAX_OUTPUT_TOKENS,
    CLASSIFY_MODEL,
    CLASSIFY_PROMPT_VERSION,
    ClassifyEnvelopePayload,
    ClassifyWire,
    EvidenceType,
    build_classify_messages,
)
from policy_atlas.embeddings import log_usage, resolve_openai_client, usage_metadata
from policy_atlas.prompt_fields import confidence_is_valid, scrub_nul


class ClassificationBackend(Protocol):
    """The classification seam for document evidence-type calls.

    Backends return structurally parsed output only; a transport, parse, or
    code-side validation failure raises so the caller can apply retry and
    per-document failure policy.
    """

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def classify(self, payload: ClassifyEnvelopePayload) -> ClassifyWire:
        """Classify one document envelope.

        Args:
            payload: The document envelope plus provider priors.

        Returns:
            Raw structurally parsed classification output.

        Raises:
            RuntimeError: If the backend cannot produce a valid classification.
        """
        ...


def _scrub_classification(wire: ClassifyWire) -> ClassifyWire:
    return wire.model_copy(
        update={
            "reason": scrub_nul(wire.reason),
            "tags": [scrub_nul(tag) for tag in wire.tags],
        }
    )


class OpenAIClassificationBackend:
    """Live OpenAI implementation of the classification seam.

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
            backend_name="OpenAIClassificationBackend",
            timeout=180.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def _classify_once(
        self,
        messages: list[ChatCompletionMessageParam],
    ) -> tuple[ClassifyWire, CompletionUsage | None]:
        response = self._client.chat.completions.parse(
            model=CLASSIFY_MODEL,
            messages=messages,
            response_format=ClassifyWire,
            max_completion_tokens=CLASSIFY_MAX_OUTPUT_TOKENS,
        )
        log_usage("classification.classify.usage", response.usage)
        if not response.choices:
            raise RuntimeError("OpenAI classification response had no choices.")
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI classification response was not parsed.")
        parsed_model: ClassifyWire = parsed
        return _scrub_classification(parsed_model), response.usage

    def classify(self, payload: ClassifyEnvelopePayload) -> ClassifyWire:
        """Classify one document envelope through structured OpenAI output.

        Args:
            payload: The document envelope plus provider priors.

        Returns:
            Raw structurally parsed classification output.

        Raises:
            RuntimeError: If the response cannot be parsed or has invalid confidence.
        """
        messages = build_classify_messages(payload)
        langfuse_client = self._langfuse_client

        def _update(
            span: Any,
            result: tuple[ClassifyWire, CompletionUsage | None],
        ) -> None:
            wire, usage = result
            span.update(
                input={"messages": messages},
                output=wire.model_dump(),
                model=CLASSIFY_MODEL,
                metadata={
                    "prompt_version": CLASSIFY_PROMPT_VERSION,
                    "pss_id": payload.pss_id,
                    "tag_count": len(wire.tags),
                    **usage_metadata(usage),
                },
            )

        def _score_trace(
            _span: Any,
            result: tuple[ClassifyWire, CompletionUsage | None],
        ) -> None:
            if langfuse_client is None:
                return
            wire, _usage = result
            confidence = float(wire.confidence)
            langfuse_client.score_current_trace(
                name="classify_valid",
                value=1.0 if confidence_is_valid(confidence) else 0.0,
                data_type="NUMERIC",
            )
            langfuse_client.score_current_trace(
                name="classify_confidence",
                value=confidence,
                data_type="NUMERIC",
            )

        wire, _usage = tracing.traced_call(
            langfuse_client,
            name=f"classify:{payload.pss_id[:8]}",
            as_type="generation",
            call=lambda: self._classify_once(messages),
            update=_update,
            after=_score_trace,
        )
        if not confidence_is_valid(wire.confidence):
            raise RuntimeError(
                "OpenAI classification response confidence out of range "
                f"for pss_id={payload.pss_id!r}: {wire.confidence}."
            )
        return wire


# Maps metadata sentinel keys to evidence types; first matching sentinel wins.
# Values are taken from EVIDENCE_TYPES (the authoritative list in schema.py).
_STUB_MAP: tuple[tuple[str, EvidenceType], ...] = (
    ("_stub_non_evidence", "Other (Non-evidence documents)"),
    ("_stub_systematic_review", "Systematic Review and Meta-Analysis"),
    ("_stub_rct", "RCTs and Quasi-Experimental Studies"),
    ("_stub_observational", "Observational Research Studies"),
    ("_stub_modelling", "Modelling & Simulation"),
    ("_stub_policy_guidance", "Policy Syntheses & Guidance Documents"),
    ("_stub_qualitative", "Qualitative & Contextual Evidence"),
    ("_stub_expert_opinion", "Expert Opinion and Commentary"),
)
_UNKNOWN_EVIDENCE_TYPE: EvidenceType = "Unknown / Insufficient information"


def _stub_tags(metadata: dict[str, Any]) -> list[str]:
    if "_stub_tags" not in metadata:
        return []
    tags = metadata["_stub_tags"]
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise RuntimeError("_stub_tags sentinel must be a list of strings.")
    return cast(list[str], tags)


class StubClassificationBackend:
    """Deterministic zero-egress classification backend for tests and local runs."""

    mode = "stub"

    def classify(self, payload: ClassifyEnvelopePayload) -> ClassifyWire:
        """Return sentinel-driven classification output.

        Args:
            payload: The document envelope. ``metadata`` carries stub sentinels;
                it never enters live prompts.

        Returns:
            Deterministic classification output driven by ``payload.metadata``.

        Raises:
            RuntimeError: If ``_stub_classify_failed`` is truthy.
        """
        metadata = payload.metadata
        if metadata.get("_stub_classify_failed"):
            raise RuntimeError("Stub classification failure sentinel.")

        tags = _stub_tags(metadata)
        for sentinel, evidence_type in _STUB_MAP:
            if metadata.get(sentinel):
                return ClassifyWire(
                    primary_evidence_type=evidence_type,
                    tags=tags,
                    confidence=0.9,
                    reason="Deterministic stub classification.",
                )
        return ClassifyWire(
            primary_evidence_type=_UNKNOWN_EVIDENCE_TYPE,
            tags=tags,
            confidence=0.9,
            reason="Deterministic stub classification.",
        )
