"""The plan-stage sense check: can this intervention cause this goal at all? (task 054, red team).

When the Task Agent makes a theory-of-change plan ready, one quick OpenAlex
search on the whole intervention (two queries, six results each) and one
frontier call (``toc_sense_check_v2``) answer two questions: is the route from
the intervention to the goal plausible (logic), and what do evaluations of the
whole programme say (evidence)?

- **Implausible mechanism:** the Task Agent's reply gets a warning with the
  sources it rests on, and offers to draft anyway or change the plan.
- **Plausible, evidence against:** a plain note on what evaluations found.
  Nothing is blocked: the user decides.
- **Stored** as a ``toc.sense_check`` event, keyed by the plan's intervention,
  goal, population and place, so the same plan is checked once; the theory
  verdict after the evidence check reads the latest one, because the
  whole-programme evaluations it finds can be missed by the step-by-step search.
- **Never breaks a turn:** a failed search or call is logged and skipped.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core import events
from policy_atlas.core.schema import event_log
from policy_atlas.evidence_search.extract.quote_verify import QuoteMatcher, build_basis
from policy_atlas.evidence_search.sourcing.acquire import _reconstruct_abstract
from policy_atlas.theory_of_change.backend import TocBackend

log = structlog.get_logger()

SENSE_CHECK_EVENT = "toc.sense_check"
#: Results per search query; two queries.
RESULTS_PER_QUERY = 6
#: Sources the chat warning lists.
SOURCES_SHOWN = 3
_PLAN_KEYS = (
    "intervention",
    "intended_change",
    "target_population",
    "where",
    "time_horizon",
    "dosage",
)

#: One semantic search: text → raw OpenAlex works.
Search = Callable[[str], list[dict[str, Any]]]


def plan_fields(plan: Any) -> dict[str, str]:
    """The plan fields the check reads, from a ``TocPlan`` or a dict."""
    values = plan if isinstance(plan, dict) else plan.model_dump(mode="json")
    return {key: str(values[key]) for key in _PLAN_KEYS if values.get(key)}


def _key(fields: dict[str, str]) -> str:
    wanted = {
        k: fields.get(k, "")
        for k in ("intervention", "intended_change", "target_population", "where")
    }
    return hashlib.sha256(json.dumps(wanted, sort_keys=True).encode()).hexdigest()[:16]


def latest(conn: Connection, task_id: uuid.UUID) -> dict[str, Any] | None:
    """The task's latest sense check payload, or ``None``."""
    return conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id, event_log.c.event_type == SENSE_CHECK_EVENT)
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()


def _documents(fields: dict[str, str], search: Search) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for text in (
        f"{fields['intervention']} effect on {fields.get('intended_change', '')}",
        f"effectiveness of {fields['intervention']}",
    ):
        for work in search(text)[:RESULTS_PER_QUERY]:
            key = str(work.get("id") or "").rsplit("/", 1)[-1]
            if key and key not in found:
                found[key] = {
                    "id": key,
                    "title": str(work.get("title") or work.get("display_name") or ""),
                    "abstract": _reconstruct_abstract(work.get("abstract_inverted_index")) or "",
                    "year": str(work.get("publication_year") or ""),
                    "url": str(work.get("doi") or work.get("id") or ""),
                }
    return list(found.values())


class CitedNote(str):
    """A Task Agent line whose ``[n]`` markers point at ``sources``, for the citation sidebar."""

    sources: list[dict[str, Any]]

    def __new__(cls, text: str, sources: list[dict[str, Any]]) -> CitedNote:
        line = super().__new__(cls, text)
        line.sources = sources
        return line


_AFTER_STOP = re.compile(r"([.!?]) \[(\d+(?:,\d+)*)\]")
_MARKER = re.compile(r"\s*\[([A-Za-z0-9_]+(?:\s*,\s*[A-Za-z0-9_]+)*)\]")


def _verified_quotes(response_quotes: list[Any], documents: list[dict[str, str]]) -> dict[str, str]:
    """The quotes found word for word in their document's title or abstract, by id."""
    texts = {d["id"]: f"{d['title']}. {d['abstract']}" for d in documents}
    return {
        q.id: q.quote
        for q in response_quotes
        if q.id in texts
        and q.quote.strip()
        and QuoteMatcher(build_basis([(None, texts[q.id])])).find(q.quote).status != "failed"
    }


def _cite(text: str, payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Number the ``[id]`` markers with a verified quote; drop the others."""
    docs = {d["id"]: d for d in payload.get("documents", [])}
    quotes = payload.get("quotes") or {}
    numbers: dict[str, int] = {}
    sources: list[dict[str, Any]] = []

    def number(match: re.Match[str]) -> str:
        found = []
        for key in (part.strip() for part in match.group(1).split(",")):
            if key not in docs or key not in quotes:
                continue
            if key not in numbers:
                numbers[key] = len(numbers) + 1
                doc = docs[key]
                sources.append(
                    {
                        "n": numbers[key],
                        "title": doc["title"],
                        "url": doc.get("url") or None,
                        "year": doc.get("year") or None,
                        "quote": quotes[key],
                    }
                )
            found.append(numbers[key])
        return f" [{','.join(map(str, found))}]" if found else ""

    cited = _MARKER.sub(number, text)
    # "found it. [1]" reads as the report does: "found it [1]."
    return _AFTER_STOP.sub(r" [\2]\1", cited), sources


def note(payload: dict[str, Any]) -> CitedNote | None:
    """What the Task Agent adds: a warning (implausible), a note (evidence against), or nothing.

    Its ``[id]`` markers become numbers that open the chat's citation sidebar
    (``CitedNote.sources``). A check stored before quotes were asked for lists
    the documents its reasons cite instead.
    """
    if payload.get("mechanism") == "implausible" and payload.get("warning"):
        lead = f"Before I draft it: {payload['warning']}"
    elif payload.get("evidence") == "against" and payload.get("note"):
        lead = f"Before you start: {payload['note']}"
    else:
        return None
    text, sources = _cite(lead, payload)
    if sources:
        return CitedNote(text, sources)
    lines = [text]
    reasons = f"{payload.get('mechanism_reason', '')} {payload.get('evidence_reason', '')}"
    cited = [doc for doc in payload.get("documents", []) if f"[{doc['id']}]" in reasons]
    if cited:
        lines.append(
            "What this rests on: "
            + "; ".join(
                f"{doc['title']}" + (f" ({doc['year']})" if doc.get("year") else "")
                for doc in cited[:SOURCES_SHOWN]
            )
            + "."
        )
    return CitedNote("\n\n".join(lines), [])


def run_sense_check(
    engine: Engine, *, task_id: uuid.UUID, plan: Any, backend: TocBackend, search: Search
) -> CitedNote | None:
    """Check the plan once, store the result, and return the chat warning if any.

    Args:
        engine: Database engine.
        task_id: The task.
        plan: The ready ``TocPlan`` (or its fields as a dict).
        backend: The ToC model seam.
        search: One OpenAlex semantic search.

    Returns:
        The warning to add to the Task Agent's reply, or ``None`` (plausible,
        already checked, or the check failed).
    """
    fields = plan_fields(plan)
    if not fields.get("intervention"):
        return None
    key = _key(fields)
    with engine.connect() as conn:
        previous = latest(conn, task_id)
    if previous is not None and previous.get("key") == key:
        return None
    try:
        documents = _documents(fields, search)
        response, _usage = backend.sense_check(
            plan=dict(fields),
            documents=[{k: d[k] for k in ("id", "title", "abstract")} for d in documents],
        )
    except Exception:  # noqa: BLE001 - a sense check must never break the turn
        log.exception("toc_sense_check.failed", task_id=str(task_id))
        return None
    payload = {
        "key": key,
        **response.model_dump(exclude={"quotes"}),
        "documents": [{k: d[k] for k in ("id", "title", "year", "url")} for d in documents],
        # Only quotes found word for word in their document count (C20).
        "quotes": _verified_quotes(response.quotes, documents),
    }
    with engine.begin() as conn:
        events.append(
            conn, task_id=task_id, run_id=None, event_type=SENSE_CHECK_EVENT, payload=payload
        )
    log.info(
        "toc_sense_check.done",
        task_id=str(task_id),
        mechanism=response.mechanism,
        evidence=response.evidence,
    )
    return note(payload)


def for_verdict(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """What the theory verdict reads from a stored check: both answers, reasons, cited titles."""
    if payload is None or "mechanism" not in payload:
        return None
    reasons = f"{payload.get('mechanism_reason', '')} {payload.get('evidence_reason', '')}"
    return {
        "mechanism": payload["mechanism"],
        "mechanism_reason": payload.get("mechanism_reason"),
        "evidence": payload.get("evidence"),
        "evidence_reason": payload.get("evidence_reason"),
        "documents": {
            doc["id"]: doc["title"]
            for doc in payload.get("documents", [])
            if f"[{doc['id']}]" in reasons
        },
    }
