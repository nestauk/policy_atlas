"""Inference routing seam.

InferenceProvider is the interface; StubEchoProvider is the no-egress implementation.
Real OpenAI→Bedrock wiring is a deferred, separately-gated follow-on.
"""

from typing import Protocol


class InferenceProvider(Protocol):
    """Interface for text completion providers."""

    def complete(self, prompt: str) -> str:
        """Return a completion for the given prompt.

        Args:
            prompt: Prompt text.

        Returns:
            The completion text.
        """
        ...


class StubEchoProvider:
    """Returns canned text. Zero runtime egress — no model call, no network I/O."""

    def complete(self, prompt: str) -> str:  # noqa: ARG002
        """Return canned text regardless of prompt; zero egress.

        Args:
            prompt: Ignored.

        Returns:
            A fixed evidence sentence.
        """
        return (
            "Evidence suggests that structured provenance tracking improves "
            "audit trail quality in policy research systems."
        )
