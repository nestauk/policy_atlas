"""Relevance-annotator backend seam — the B2′ sibling pass (024 / ADR 0023).

The verdict-fenced home of extraction relevance emphasis. Extraction and vetting
run entirely unguided — user emphasis NEVER enters those prompts or the
extraction fingerprint. Only *after* vetting, and only when the user supplied
``extraction.relevance_emphasis``, does this small annotator read the surviving
finding rows and mark each ``priority`` or ``normal`` against the stated
emphasis. Marking is emphasis for presentation, never a quality or truth
judgment, and never a filter.

Mirrors ``finding_vetter.py``'s shape (Protocol + deterministic stub + OpenAI
impl returning ``UsageResult``, structured outputs via ``parse_structured``,
optional Langfuse tracing). Two differences from the vetter, both deliberate:

- Coverage is keyed by ``finding_id`` (a stable persisted id), not the vetter's
  positional ``index`` — the annotator reads *persisted* finding rows, so it
  addresses them by their durable ids.
- The pass is fail-open at the caller: any backend error, parse failure or
  coverage violation leaves the extraction unannotated with a flag, never a
  failed extraction (emphasis is presentation, not substrate). This module owns
  only the seams, the coverage validator and their wire shapes; ``extract.py``
  applies the fail-open policy and the run-scoped persistence.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any, Protocol

from langfuse import Langfuse

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import openai_kwargs, parse_structured, resolve_openai_client
from policy_atlas.core.usage import UsageResult, usage_metadata
from policy_atlas.evidence_base.extract.relevance_prompt import (
    FINDING_RELEVANCE_PROMPT_VERSION,
    FindingRelevanceWire,
    RelevanceAnnotationWire,
    build_relevance_messages,
)
from policy_atlas.evidence_base.extract.relevance_prompt import (
    RELEVANCE_MAX_OUTPUT_TOKENS as RELEVANCE_ANNOTATOR_MAX_OUTPUT_TOKENS,
)

# Mini-class model, env-overridable — the same convention as the vetter's model
# constant, with the contract's B2′ env name (model route: mini-class).
RELEVANCE_ANNOTATOR_MODEL = os.environ.get("POLICY_ATLAS_RELEVANCE_MODEL", "gpt-5.4-mini")
# Effort per the vetter precedent (xhigh exhausts completion caps on 5.4-mini
# judgment calls); the marking task is lighter than vetting, but the ceiling is
# shared for consistency.
RELEVANCE_ANNOTATOR_REASONING_EFFORT = "high"


class RelevanceAnnotatorBackend(Protocol):
    """The relevance-annotator seam for the extract post-vetting pass.

    Backends return structurally parsed output only; a transport, parse or
    code-side validation failure raises so the caller (``extract.py``) applies
    its fail-open policy — an annotator failure never blocks extraction.
    """

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def annotate(self, payload: dict[str, Any]) -> UsageResult[RelevanceAnnotationWire]:
        """Mark one run's surviving findings against the user emphasis.

        Args:
            payload: ``{"emphasis": [...], "findings": [...]}`` — the parsed
                emphasis sentences and the id-keyed finding digests built by the
                caller (see ``relevance_prompt.build_relevance_messages``).

        Returns:
            Raw structurally parsed annotations plus token usage.

        Raises:
            RuntimeError: If the backend cannot produce a valid response.
        """
        ...


def validate_annotation_coverage(
    findings: Sequence[dict[str, Any]], annotations: Sequence[FindingRelevanceWire]
) -> None:
    """Raise unless ``annotations`` covers each input ``finding_id`` exactly once.

    Code-side validation (the vetter validator pattern, ADR 0023): a coverage
    violation — a missing, duplicated or invented finding id — is an annotator
    failure, not a partial result. The caller treats it as such and fails open
    (the extraction persists unannotated with a flag).

    Args:
        findings: The id-keyed finding digests sent to the annotator; each
            carries a ``finding_id``.
        annotations: The parsed response's annotations.

    Raises:
        RuntimeError: If any finding id is missing, duplicated, or invented.
    """
    expected = sorted(str(finding["finding_id"]) for finding in findings)
    got = sorted(annotation.finding_id for annotation in annotations)
    if got != expected:
        raise RuntimeError(
            "relevance annotator response does not cover each input finding id "
            f"exactly once: expected {expected}, got {got}."
        )


class OpenAIRelevanceAnnotatorBackend:
    """Live OpenAI implementation of the relevance-annotator seam.

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
            backend_name="OpenAIRelevanceAnnotatorBackend",
            timeout=180.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def annotate(self, payload: dict[str, Any]) -> UsageResult[RelevanceAnnotationWire]:
        """Mark the run's findings through schema-constrained structured output.

        Args:
            payload: ``{"emphasis": [...], "findings": [...]}`` as built by the
                caller.

        Returns:
            Raw structurally parsed annotations plus token usage.

        Raises:
            RuntimeError: If the response cannot be parsed.
        """
        emphasis = list(payload.get("emphasis", []))
        findings = list(payload.get("findings", []))
        messages = build_relevance_messages(emphasis, findings)

        def _annotate_once() -> UsageResult[RelevanceAnnotationWire]:
            return parse_structured(
                self._client,
                messages=messages,
                response_format=RelevanceAnnotationWire,
                usage_event="relevance_annotator.annotate.usage",
                label="relevance annotator",
                **openai_kwargs(
                    RELEVANCE_ANNOTATOR_MODEL,
                    reasoning_effort=RELEVANCE_ANNOTATOR_REASONING_EFFORT,
                ),
                max_completion_tokens=RELEVANCE_ANNOTATOR_MAX_OUTPUT_TOKENS,
            )

        def _update(span: Any, result: UsageResult[RelevanceAnnotationWire]) -> None:
            response, usage = result
            span.update(
                input={"messages": messages},
                output=response.model_dump(),
                model=RELEVANCE_ANNOTATOR_MODEL,
                metadata={
                    "prompt_version": FINDING_RELEVANCE_PROMPT_VERSION,
                    "finding_count": len(findings),
                    **usage_metadata(usage),
                },
            )

        return tracing.traced_call(
            self._langfuse_client,
            name="relevance_annotator:annotate",
            as_type="generation",
            call=_annotate_once,
            update=_update,
        )


class StubRelevanceAnnotatorBackend:
    """Deterministic zero-egress relevance-annotator backend for tests and local runs.

    Marks every finding id listed in ``priority_ids`` ``"priority"`` and every
    other finding ``"normal"`` — an all-``"normal"`` pass by default (the
    presentation-neutral stub), configurable per test to exercise the priority
    path. Coverage is exact by construction (one annotation per input finding).

    Args:
        priority_ids: Finding ids to mark ``"priority"``; all others ``"normal"``.
    """

    mode = "stub"

    def __init__(self, priority_ids: set[str] | frozenset[str] = frozenset()) -> None:
        self._priority_ids = frozenset(priority_ids)

    def annotate(self, payload: dict[str, Any]) -> UsageResult[RelevanceAnnotationWire]:
        """Return one annotation per input finding, covering every id exactly once.

        Args:
            payload: ``{"emphasis": [...], "findings": [...]}`` as built by the
                caller.

        Returns:
            Deterministic annotations plus no token usage.
        """
        findings = payload.get("findings", [])
        annotations = [
            FindingRelevanceWire(
                finding_id=str(finding["finding_id"]),
                relevance=(
                    "priority" if str(finding["finding_id"]) in self._priority_ids else "normal"
                ),
            )
            for finding in findings
        ]
        return RelevanceAnnotationWire(annotations=annotations), None
