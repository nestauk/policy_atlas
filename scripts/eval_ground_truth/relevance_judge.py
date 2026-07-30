"""A ground-truth-blind relevance judge.

Given only a seed research query and a candidate's own title/abstract — never
told whether the candidate is in any ground-truth set — this judges plausible
relevance. Used two ways in run_and_score.py: (1) calibration, run over
screened-in results that ARE in the included-studies set, to measure the
judge's own agreement rate on knowns; (2) as a precision proxy, run over
screened-in results in neither ground-truth set. A review's own bibliography
is not a valid false-positive ground truth on its own (see the eval-pilot
plan), so this judge — not review membership — is what a precision-style
number is built on, and its calibration rate is the trust weight on it.
"""

from __future__ import annotations

from langfuse import Langfuse
from pydantic import BaseModel, ConfigDict, Field

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import openai_kwargs, parse_structured, resolve_openai_client
from policy_atlas.core.usage import usage_metadata

_JUDGE_MODEL = "gpt-5.4-mini"
_JUDGE_PROMPT_VERSION = "eval_judge_relevance_v1"

_SYSTEM = (
    "You judge whether a candidate document is plausibly relevant to a research "
    "question, given only its title and abstract. Judge from that text alone — "
    "you have no other context about where this candidate came from or why it "
    "is being asked about."
)


class RelevanceVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevant: bool = Field(description="Whether this document is plausibly relevant to the query.")
    confidence: float = Field(description="Probability, 0.0-1.0, that your verdict is correct.")
    reason: str = Field(description="One short sentence grounding the verdict.")


def judge_relevance(
    query: str, title: str, abstract: str | None, langfuse_client: Langfuse | None = None
) -> RelevanceVerdict:
    client = resolve_openai_client(None, backend_name="relevance_judge", timeout=60.0, max_retries=2)
    user_content = (
        f"Research question: {query}\n\n"
        f"Candidate title: {title}\n"
        f"Candidate abstract: {abstract or '(no abstract available)'}"
    )
    messages: list[object] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_content},
    ]

    def _update(span: object, result: object) -> None:
        wire, usage = result  # type: ignore[misc]
        span.update(  # type: ignore[attr-defined]
            input={"messages": messages},
            output=wire.model_dump(),
            model=_JUDGE_MODEL,
            metadata={"prompt_version": _JUDGE_PROMPT_VERSION, **usage_metadata(usage)},
        )

    wire, _usage = tracing.traced_call(
        langfuse_client,
        name="eval.judge_relevance",
        as_type="generation",
        call=lambda: parse_structured(
            client,
            messages=messages,
            response_format=RelevanceVerdict,
            usage_event="eval.judge_relevance",
            label="relevance judge",
            **openai_kwargs(_JUDGE_MODEL),
            max_completion_tokens=1_024,
        ),
        update=_update,
    )
    return wire
