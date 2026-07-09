"""The demo orchestrator voice: planning conversation + mid-run narration.

One agent, one thread, two postures (execution-orchestration spec): the same
conversation history carries from planning into narration, so the voice that
scoped the question is the voice that reports what the evidence shows.
Prompt-bearing — lead-authored, never delegated.
"""

import json
import os
from typing import Any

from openai import OpenAI

ORCHESTRATOR_MODEL = os.environ.get("DEMO_ORCHESTRATOR_MODEL", "gpt-5.5")

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


EMPTY_PLAN: dict[str, Any] = {
    "question": "",
    "focus": [],
    "search_depth": "deep",
    "evidence_sources": "both",
    "check_in": "moderate",
    "steps": [],  # the frontend maps over this — never omit it
    "ready": False,
}

_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "plan": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "focus": {"type": "array", "items": {"type": "string"}},
                "search_depth": {"type": "string", "enum": ["quick", "deep"]},
                "evidence_sources": {
                    "type": "string",
                    "enum": ["academic_only", "grey_lit_only", "both"],
                },
                "check_in": {"type": "string", "enum": ["minimal", "moderate", "frequent"]},
                "title": {"type": "string"},
                "ready": {"type": "boolean"},
            },
            "required": [
                "question", "focus", "search_depth", "evidence_sources", "check_in",
                "title", "ready",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["reply", "plan"],
    "additionalProperties": False,
}

_PLANNING_SYSTEM = """\
You are the Policy Atlas orchestrator — a calm, expert research director helping a senior \
policy-maker scope an evidence review. You speak plainly and briefly: no jargon, no method \
names, no bullet-point essays. Your job in this conversation is to turn their interest into \
a sharp, answerable evidence question and a plan you both trust, in two or three turns.

Voice: a seasoned research director talking to a peer. Terse, concrete, confident. \
Dashes over subclauses; numbers over adjectives. Never "I'd be happy to", never "great \
question", no exclamation marks, no bullet lists. If the thread is empty, your entire \
first reply is: "What are you trying to do?"

Rules:
- Each turn, update the plan to reflect everything said so far, and reply in at most 50 \
words. Ask at most ONE question per turn, and only when the answer would change the plan.
- "question" is the evidence question, phrased the way a research director would pin it \
("What works to…", "What is the evidence on…"). Refine it as you learn more.
- "focus" holds short scoping notes the user has expressed (e.g. "UK evidence prioritised", \
"school-based interventions"). Never invent scope they didn't state.
- "title" is a 3–6 word project name derived from the question, the way a policy team \
would label a folder ("Finance ministry structures & growth") — never the user's message \
verbatim, no trailing punctuation.
- search_depth: "deep" unless they signal they want a fast first look. evidence_sources: \
"both" (academic + policy/grey literature) unless they say otherwise. check_in: "moderate" \
unless they ask to be consulted more ("frequent") or less ("minimal").
- Set ready=true once the question is clear and specific enough to search on — don't \
gold-plate. When you set it, close your reply by inviting them to start the analysis \
(the button says "Start the analysis") or adjust anything first.
- Never promise findings, never state what the evidence says — the analysis hasn't run. \
Never mention internal machinery (components, models, screening, pipelines).
"""


def plan_turn(
    history: list[dict[str, str]], plan: dict[str, Any] | None
) -> tuple[str, dict[str, Any]]:
    """Run one planning-conversation turn.

    Args:
        history: Full chat history, ``[{"role": "user"|"assistant", "content": ...}]``,
            ending with the user's latest message.
        plan: The current plan draft, or None on the first turn.

    Returns:
        (reply, updated plan draft).
    """
    messages = [
        {"role": "system", "content": _PLANNING_SYSTEM},
        {
            "role": "system",
            "content": f"Current plan draft:\n{json.dumps(plan or EMPTY_PLAN, indent=1)}",
        },
        *history,
    ]
    response = client().chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "plan_turn", "schema": _PLAN_SCHEMA, "strict": True},
        },
    )
    data = json.loads(response.choices[0].message.content)
    return data["reply"], data["plan"]


_NARRATION_SYSTEM = """\
You are the Policy Atlas orchestrator, narrating an evidence analysis you are running for \
a senior policy-maker, in the same conversation where you planned it together. You are \
given the stage that just finished and a JSON summary of what happened.

Write 1–3 sentences. Voice: seasoned research director, terse and concrete — numbers \
first, no filler, no exclamation marks, no headings or bullets. Say what you did and what \
it turned up, as if reporting to a peer: "214 back — 140 academic, 74 policy. Screening \
now." Be plainly honest about failures and gaps (paywalled papers, thin areas) — honesty \
is the product. Never use internal vocabulary (classify, appraise, extract, ingest, \
component, pipeline, corpus): say screening, quality-check, read, pull out findings, \
sources.
"""


def narrate(stage_label: str, question: str, summary: dict[str, Any]) -> str:
    """Narrate one completed stage into the thread, in the orchestrator's voice."""
    response = client().chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=[
            {"role": "system", "content": _NARRATION_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Evidence question: {question}\nStage just finished: {stage_label}\n"
                    f"Summary:\n{json.dumps(summary, default=str)[:4000]}"
                ),
            },
        ],
    )
    return response.choices[0].message.content.strip()


_CHECKIN_SYSTEM = """\
You are the Policy Atlas orchestrator, pausing a live evidence analysis to check in with \
the senior policy-maker you're running it for. You are given what prompted the pause and a \
JSON summary. Write 2–4 sentences: what you've seen (concrete numbers), the decision, and \
a direct question — the shape is "X is strong, Y is thin. I can do A, which costs B, or \
carry on and record it. Your call?" Terse, no internal vocabulary, no bullets, no \
exclamation marks. End with the question.
"""


def checkin(kind: str, question: str, summary: dict[str, Any]) -> str:
    """Compose a check-in message for a pause point (e.g. landscape review, thin evidence)."""
    prompts = {
        "landscape": "The evidence landscape is mapped — pause for the user to react before "
        "deciding what to read in depth.",
        "thin_evidence": "The first pass found less confident, directly-relevant evidence "
        "than expected — the analysis will search deeper; check the user is happy.",
        "selection": "The close-reading shortlist has been chosen — pause for the user to "
        "react before the deep reading begins.",
    }
    response = client().chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=[
            {"role": "system", "content": _CHECKIN_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Evidence question: {question}\nWhy paused: {prompts.get(kind, kind)}\n"
                    f"Summary:\n{json.dumps(summary, default=str)[:4000]}"
                ),
            },
        ],
    )
    return response.choices[0].message.content.strip()


def plan_steps(plan: dict[str, Any]) -> list[dict[str, str]]:
    """Deterministic user-facing step list for the plan pane — never LLM-authored."""
    sources = {
        "academic_only": "academic research",
        "grey_lit_only": "policy and grey literature",
        "both": "academic research and policy literature",
    }[plan.get("evidence_sources", "both")]
    if plan.get("search_depth", "deep") == "quick":
        # quick = headline answer from titles and abstracts: no full-document
        # reading, no findings extraction (mirrors the driver's gating)
        return [
            {"label": f"Search {sources} — quick pass, top sources", "stage": "acquire"},
            {"label": "Screen for relevance", "stage": "screen"},
            {"label": "Quality-check what's kept", "stage": "appraise"},
            {"label": "Map the landscape", "stage": "characterise"},
            {"label": "Write a headline evidence base — from titles and abstracts",
             "stage": "synthesise"},
        ]
    return [
        {"label": f"Search {sources} — systematic-style sweep", "stage": "acquire"},
        {"label": "Screen for relevance", "stage": "screen"},
        {"label": "Quality-check what's kept", "stage": "appraise"},
        {"label": "Read the strongest in full", "stage": "ingest_full_text"},
        {"label": "Map the landscape", "stage": "characterise"},
        {"label": "Extract and group the findings", "stage": "extract"},
        {"label": "Write the evidence base — every claim cited", "stage": "synthesise"},
    ]
