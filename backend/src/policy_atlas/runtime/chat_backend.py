"""The chat moment's backend seam and its deterministic stub (task 029).

The live OpenAI adapter arrives with the streaming phase (plan D1) behind the
provider-neutral wire pin; until then every test path runs on the stub. The
loop mechanics live in the shared bounded tool-loop kernel
(``run_tool_loop``) with ``emit_answer`` as the chat moment's final emitter.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypedDict

from policy_atlas.core.usage import TokenUsage, UsageResult
from policy_atlas.evidence_base.synthesis.synthesis_tools import ToolExchange
from policy_atlas.runtime.chat_prompt import ChatAnswerWire, ChatCitationWire, ChatClaimWire

_NO_USAGE = TokenUsage(prompt=None, completion=None, total=None)


class ChatTurn(TypedDict):
    """One backend turn: exactly one of ``tool_calls`` or ``answer``."""

    answer: ChatAnswerWire | None
    tool_calls: list[dict[str, Any]]


class ChatBackend(Protocol):
    """The chat writer seam — one schema-constrained provider call per turn."""

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def chat_turn(
        self,
        messages: list[dict[str, str]],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
        max_output_tokens: int | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> UsageResult[ChatTurn]:
        """Produce one loop turn: read-tool calls, or the answer emission.

        Args:
            messages: Assembled chat messages (frame + window + question).
            transcript: Executed tool exchanges so far this turn.
            force_emit: True on the final turn — the backend must emit.
            max_output_tokens: Generated-answer ceiling the provider call
                must honour (plan pin 4096); the stub records it only.
            on_delta: Optional provider-neutral prose callback for the final
                emission only.

        Returns:
            The turn plus token usage.
        """
        ...


class StubChatBackend:
    """Deterministic chat backend for tests: one search, then a cited answer.

    Turn 1 issues one ``search_chunks`` call for the question text; the next
    turn emits a one-claim answer citing the first chunk the loop returned.
    With no returned chunks it emits an honest evidence-not-held answer with
    zero citations. No provider, no network.
    """

    mode = "stub"

    def chat_turn(
        self,
        messages: list[dict[str, str]],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
        max_output_tokens: int | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> UsageResult[ChatTurn]:
        del max_output_tokens, on_delta  # recorded by test doubles; no provider to cap
        question = messages[-1]["content"] if messages else ""
        if not transcript and not force_emit:
            return (
                {
                    "answer": None,
                    "tool_calls": [
                        {"tool": "search_chunks", "arguments": {"query": question[:200]}}
                    ],
                },
                _NO_USAGE,
            )
        chunk_id = _first_chunk_id(transcript)
        if chunk_id is None:
            answer = ChatAnswerWire(
                prose="The evidence base does not hold material on this question.",
                citations=[],
                claims=[],
                evidence_not_held=True,
            )
        else:
            claim_text = "The committed evidence addresses this question"
            answer = ChatAnswerWire(
                prose=f"{claim_text} [1].",
                citations=[ChatCitationWire(id=chunk_id, quote="stub quote")],
                claims=[ChatClaimWire(text=claim_text, citation_indexes=[1])],
            )
        return {"answer": answer, "tool_calls": []}, _NO_USAGE


def _first_chunk_id(transcript: list[ToolExchange]) -> str | None:
    """Return the first chunk id a ``search_chunks`` exchange returned."""
    for exchange in transcript:
        if exchange["tool"] != "search_chunks":
            continue
        chunks = exchange["result"].get("chunks", [])
        if isinstance(chunks, list):
            for chunk in chunks:
                if (
                    isinstance(chunk, dict)
                    and isinstance(chunk.get("chunk_record_id"), str)
                    and not chunk.get("skipped_over_budget")
                ):
                    return str(chunk["chunk_record_id"])
    return None
