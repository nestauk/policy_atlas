"""The demo orchestrator voice: real 017 planner turns + demo-only narration.

Planning is the REAL backend: `planner.OpenAIPlannerBackend` produces
`PlanDraftWire` drafts that validate fail-closed into `OrchestrationPlan`
(the same path as `python -m policy_atlas.orchestrate`). What stays demo-only
glue — by explicit product-owner decision, since 017 defers the narration and
clarify-escalate surfaces — is the LLM prose: `narrate()` for stage
completions and `checkin_prose()` wrapping the runner's deterministic
check-in render. Prompt-bearing — lead-authored, never delegated.
"""

import json
import os
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from policy_atlas import tracing
from policy_atlas.orchestrate import _build_plan
from policy_atlas.orchestration_plan import OrchestrationPlan, compose
from policy_atlas.planner import OpenAIPlannerBackend, PlannerTurnWire

NARRATION_MODEL = os.environ.get("DEMO_ORCHESTRATOR_MODEL", "gpt-5.5")

_client: OpenAI | None = None
_planner: OpenAIPlannerBackend | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def planner() -> OpenAIPlannerBackend:
    global _planner
    if _planner is None:
        _planner = OpenAIPlannerBackend(langfuse_client=tracing.get_langfuse())
    return _planner


def plan_turn(
    turns: list[dict[str, str]], previous_draft: dict[str, Any] | None
) -> PlannerTurnWire:
    """One real planner turn: `[{"role": "user"|"planner", "text": ...}]` in."""
    return planner().plan_turn(turns, previous_draft)


def build_plan(draft: PlannerTurnWire | Any) -> OrchestrationPlan:
    """Validate a ready draft into the executable plan, fail-closed."""
    return _build_plan(draft.plan_draft if hasattr(draft, "plan_draft") else draft)


# --- stage vocabulary (user-facing labels; component names never reach the UI) ---

STAGES: dict[str, tuple[str, str]] = {
    "acquire": ("Searching sources", "Queries out to academic and policy databases"),
    "screen": ("Screening for relevance", "Every title and abstract, against your question"),
    "classify": ("Sorting by evidence type", "Trial, review, evaluation — each source labelled"),
    "appraise": ("Appraising quality", "How much weight each source can bear"),
    "ingest_full_text": ("Reading in full", "Fetching the documents; paywalls noted, not hidden"),
    "screen_stage2": ("Screening the full texts", "A second relevance pass, now over the "
                      "documents themselves"),
    "characterise": ("Mapping the landscape", "What the evidence covers, and where it's thin"),
    "select": ("Shortlisting", "The strongest, most varied set for close reading"),
    "extract": ("Extracting findings", "Each claim pulled out with its exact quote"),
    "group": ("Grouping findings", "Findings that answer the same question, together"),
    "synthesise": ("Writing the evidence base", "Cited, checked, ready to challenge"),
}


def plan_steps(plan: OrchestrationPlan) -> list[dict[str, str]]:
    """Deterministic user-facing step list: the REAL composed chain, demo labels."""
    return [
        {"label": STAGES[c][0], "blurb": STAGES[c][1], "stage": c}
        for c in compose(plan).components
    ]


# --- wire shape for the frontend plan pane ---

EMPTY_PLAN: dict[str, Any] = {
    "title": None,
    "question": None,
    "scoping_notes": [],
    "screening_criteria": [],
    "backend_scope": None,
    "scope_constraints": {},
    "search_effort": None,
    "analysis_depth": None,
    "components": [],
    "component_rationale": {},
    "steering_mode": None,
    "assumptions": [],
    "expected_artefact_shape": None,
    "time_band": None,
    "steps": [],  # the frontend maps over this — never omit it
    "ready": False,
}

_PLAN_WIRE_FIELDS = [k for k in EMPTY_PLAN if k not in ("steps", "ready")]


def plan_payload(
    draft: dict[str, Any] | None, validated: OrchestrationPlan | None
) -> dict[str, Any]:
    """The plan dict the frontend renders: draft fields, real derived fields
    and the composed step list once the plan validates."""
    out = {**EMPTY_PLAN}
    if draft:
        out.update({k: draft[k] for k in _PLAN_WIRE_FIELDS if draft.get(k) is not None})
    if validated is not None:
        dumped = validated.model_dump(mode="json")
        out.update({k: dumped[k] for k in _PLAN_WIRE_FIELDS if k in dumped})
        out["steps"] = plan_steps(validated)
        out["ready"] = True
    return out


def validation_reply(exc: ValidationError) -> str:
    """Honest, terse surface for a plan that failed fail-closed validation."""
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first.get("loc", ())) or "plan"
    return (
        f"The proposed plan didn't validate ({where}: {first.get('msg', 'invalid')}) "
        "and was not accepted. Tell me what to change and I'll rework it."
    )


# --- demo-only LLM prose (017 defers narration/clarify-escalate surfaces) ---

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
        model=NARRATION_MODEL,
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
the senior policy-maker you're running it for. You are given the deterministic pause \
report (exact counts — restate them plainly, never invent numbers) and the decision on \
the table. Write 2–3 sentences ending in the question. Terse, no internal vocabulary \
(say screening, quality-check, shortlist, read in full), no bullets, no exclamation \
marks. The options themselves are shown as buttons — do not enumerate them.
"""


def checkin_prose(question: str, render: str, kind: str) -> str:
    """Wrap the runner's deterministic check-in render in the orchestrator's voice.

    Demo-only glue: the CONTENT (counts, component, status) is the real
    steering render; only the phrasing is LLM-authored.
    """
    decision = {
        "steer_point": "The close-reading shortlist has been chosen — the user can steer "
        "what gets read in depth before the deep reading begins.",
        "check_in": "About to write the evidence base — a moment to pause before the write-up.",
    }.get(kind, kind)
    response = client().chat.completions.create(
        model=NARRATION_MODEL,
        messages=[
            {"role": "system", "content": _CHECKIN_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Evidence question: {question}\nDecision on the table: {decision}\n"
                    f"Pause report:\n{render[:4000]}"
                ),
            },
        ],
    )
    return response.choices[0].message.content.strip()
