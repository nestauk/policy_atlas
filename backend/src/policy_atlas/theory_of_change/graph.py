"""The theory-of-change graph: shapes, structure checks, item text and hash (task 054, S8).

Pure code, no database. The draft, discover and merge steps build a
:class:`Graph` from rows or from a model's answer and run :func:`check_graph`
(the E1 structure checks) before writing. :func:`item_text` is the text the
evidence check searches and judges for a link; :func:`item_hash` is what a
judgement is bound to, so an edit to the link or to a box at either end makes
the link *Edited · check pending* (C19), while a plan change does not.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

Layer = Literal["input", "output", "outcome", "impact", "failure_outcome"]
LinkState = Literal["unchecked", "checking", "checked", "pending", "kept", "no_change"]

#: Layer order for the "layers in order" check. A failure outcome ends a route.
LAYER_RANK: dict[str, int] = {
    "input": 0,
    "output": 1,
    "outcome": 2,
    "impact": 3,
    "failure_outcome": 4,
}

#: The limits on kept pathways (C6).
MAX_SUCCESS_PATHWAYS = 6
MAX_FAILURE_PATHWAYS = 3

#: At most this many conditions on one link; a condition sits on one link only.
MAX_CONDITIONS_PER_LINK = 2


@dataclass
class Box:
    """One element in a layer."""

    key: str
    layer: str
    text: str


@dataclass
class Link:
    """One causal step."""

    key: str
    source: str
    target: str
    sentence: str = ""
    if_text: str = ""
    for_text: str = ""
    then_text: str = ""
    because_text: str = ""
    conditions: list[str] = field(default_factory=list)


@dataclass
class Pathway:
    """One ordered route of links."""

    key: str
    kind: str
    links: list[str]
    status: str = "kept"


@dataclass
class Graph:
    """A whole theory, keyed by local keys or row ids."""

    boxes: dict[str, Box]
    links: dict[str, Link]
    pathways: list[Pathway]


def link_problem(source_layer: str, target_layer: str) -> str | None:
    """Return why a step between two layers is not allowed, or ``None``.

    A step goes to the same or a later layer: input to output, output to
    outcome, outcome to outcome, outcome to impact. Same-layer steps are
    allowed between outcomes only; an input never leads straight to an impact;
    nothing leads on from an impact or a failure outcome.
    """
    if source_layer in ("impact", "failure_outcome"):
        return f"a step cannot start at {source_layer.replace('_', ' ')}"
    if target_layer == "input":
        return "a step cannot lead to an input"
    if target_layer == "failure_outcome":
        return None
    if LAYER_RANK[target_layer] < LAYER_RANK[source_layer]:
        return f"a step goes backwards, {source_layer} to {target_layer}"
    if source_layer == target_layer and source_layer != "outcome":
        return f"a step stays inside the {source_layer} layer"
    if source_layer == "input" and target_layer == "impact":
        return "an input cannot lead straight to an impact"
    return None


def pathway_problem(graph: Graph, pathway: Pathway) -> str | None:
    """Return why a pathway is not a connected route, or ``None``."""
    if not pathway.links:
        return f"pathway {pathway.key} has no steps"
    missing = [key for key in pathway.links if key not in graph.links]
    if missing:
        return f"pathway {pathway.key} names unknown steps {missing}"
    steps = [graph.links[key] for key in pathway.links]
    for before, after in zip(steps, steps[1:], strict=False):
        if before.target != after.source:
            return f"pathway {pathway.key} is broken between {before.key} and {after.key}"
    first = graph.boxes.get(steps[0].source)
    last = graph.boxes.get(steps[-1].target)
    if first is None or first.layer != "input":
        return f"pathway {pathway.key} does not start at an input"
    end = "impact" if pathway.kind == "success" else "failure_outcome"
    if last is None or last.layer != end:
        return f"{pathway.kind} pathway {pathway.key} does not end at {end.replace('_', ' ')}"
    return None


def check_graph(graph: Graph) -> list[str]:
    """Run the E1 structure checks.

    Checks: every link joins known boxes with layers in order; no link has
    more than two conditions and no condition sits on two links (case and
    spacing ignored); no box is an orphan; every kept pathway is a
    connected route from an input to an impact (success) or a failure outcome
    (failure); at least one kept failure pathway.

    Args:
        graph: The theory.

    Returns:
        Plain-language problems; empty when the graph passes.
    """
    problems: list[str] = []
    first_seen: dict[str, str] = {}
    for link in graph.links.values():
        conditions = [c for c in link.conditions if c.strip()]
        if len(conditions) > MAX_CONDITIONS_PER_LINK:
            problems.append(
                f"step {link.key} has more than {MAX_CONDITIONS_PER_LINK} conditions"
            )
        for condition in conditions:
            owner = first_seen.setdefault(_norm(condition), link.key)
            if owner != link.key:
                problems.append(f"step {link.key} repeats a condition of step {owner}")
        source, target = graph.boxes.get(link.source), graph.boxes.get(link.target)
        if source is None or target is None:
            problems.append(f"step {link.key} joins an unknown box")
            continue
        if link.source == link.target:
            problems.append(f"step {link.key} leads to the box it starts from")
        reason = link_problem(source.layer, target.layer)
        if reason:
            problems.append(f"step {link.key}: {reason}")
    linked = {key for link in graph.links.values() for key in (link.source, link.target)}
    problems.extend(f"box {key} is on no step" for key in graph.boxes if key not in linked)
    kept = [p for p in graph.pathways if p.status == "kept"]
    for pathway in kept:
        reason = pathway_problem(graph, pathway)
        if reason:
            problems.append(reason)
    if not any(p.kind == "failure" for p in kept):
        problems.append("there is no failure pathway")
    if not any(p.kind == "success" for p in kept):
        problems.append("there is no success pathway")
    return problems


def assumption_type(source_layer: str, target_layer: str) -> str:
    """The Magenta Book assumption type of a link's conditions, from its layers.

    Args:
        source_layer: The source box's layer.
        target_layer: The target box's layer.

    Returns:
        ``delivery`` · ``take-up`` · ``behaviour change`` · ``benefits and side
        effects`` · ``if it goes wrong``.
    """
    if target_layer == "failure_outcome":
        return "if it goes wrong"
    if target_layer == "output":
        return "delivery"
    if target_layer == "impact":
        return "benefits and side effects"
    if source_layer == "outcome":
        return "behaviour change"
    return "take-up"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def trim_conditions(
    conditions_per_link: list[list[str]], *, existing: Iterable[str] = ()
) -> list[list[str]]:
    """Apply the conditions rule to links in order (code, not the prompt).

    Drops blank conditions and any condition whose normalised text already
    appeared, in ``existing``, on an earlier link or earlier on the same one,
    then keeps the first :data:`MAX_CONDITIONS_PER_LINK` of each link.

    Args:
        conditions_per_link: Each link's conditions, links in draft order.
        existing: Conditions already in the theory (discovered links).

    Returns:
        The trimmed lists, same order and length.
    """
    seen = {_norm(c) for c in existing}
    trimmed: list[list[str]] = []
    for conditions in conditions_per_link:
        kept: list[str] = []
        for condition in conditions:
            key = _norm(condition)
            if key and key not in seen and len(kept) < MAX_CONDITIONS_PER_LINK:
                seen.add(key)
                kept.append(condition)
        trimmed.append(kept)
    return trimmed


def item_hash(link: Link, source_text: str, target_text: str) -> str:
    """The hash a judgement is bound to (C19).

    Covers the link's own fields, both box texts and the conditions, each
    normalised (case and spacing ignored). Plan-scope fields are not in it, so
    a plan change flags no link.

    Args:
        link: The link.
        source_text: Its source box's text.
        target_text: Its target box's text.

    Returns:
        A sha256 hex digest.
    """
    payload = [
        _norm(link.sentence),
        _norm(link.if_text),
        _norm(link.for_text),
        _norm(link.then_text),
        _norm(link.because_text),
        _norm(source_text),
        _norm(target_text),
        [_norm(c) for c in link.conditions],
    ]
    return hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()


def item_text(
    link: Link,
    *,
    source_text: str,
    target_text: str,
    population: str,
    place: str | None,
) -> str:
    """The text the evidence check searches and judges for one link.

    Args:
        link: The link.
        source_text: Its source box's text.
        target_text: Its target box's text.
        population: The plan's target population.
        place: The plan's place, or ``None``.

    Returns:
        The item text; the same graph always gives the same text.
    """
    lines = [
        link.sentence.strip(),
        f"From: {source_text.strip()}",
        f"To: {target_text.strip()}",
        f"If {link.if_text.strip()}, for {link.for_text.strip()}, then "
        f"{link.then_text.strip()}, because {link.because_text.strip()}.",
    ]
    conditions = [c.strip() for c in link.conditions if c.strip()]
    if conditions:
        lines.append("It needs: " + "; ".join(conditions) + ".")
    where = place.strip() if place else "the stated place"
    lines.append(
        f"Did this work where it was tried, and does it hold for {population.strip()} "
        f"in {where} now?"
    )
    return "\n".join(line for line in lines if line)


def link_state(
    *,
    current_hash: str,
    counted_hash: str | None,
    kept_hash: str | None,
    kept_by: str | None,
    checking: bool,
) -> LinkState:
    """A link's state by the C19 transition table; computed, never stored.

    Args:
        current_hash: :func:`item_hash` of the link as it is now.
        counted_hash: The hash whose judgements count, or ``None`` before any.
        kept_hash: The hash the evidence was kept for, or ``None``.
        kept_by: ``user`` · ``check`` · ``choose``, or ``None``.
        checking: Whether an active walk names the link and has no judgement
            of it yet.

    Returns:
        ``checking`` · ``checked`` · ``pending`` · ``kept`` · ``no_change``, or
        ``unchecked`` when nothing has judged it and no walk is running.
    """
    if checking:
        return "checking"
    if counted_hash is None:
        return "unchecked"
    if current_hash == counted_hash:
        return "checked"
    if current_hash == kept_hash:
        return {"user": "kept", "check": "no_change"}.get(kept_by or "", "checked")  # type: ignore[return-value]
    return "pending"
