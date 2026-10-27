"""The maturity rung of an option (task 055, items 7; contract A3).

How well tried an option is, read from its stored coverage alone: no model
call, the same coverage always gives the same answer. The rung is display
only; it is not a score and not a ranking.

The four rungs, highest first: *reviewed* (a systematic review or
meta-analysis evaluated it), *evaluated* (at least one document measured an
effect), *described* (documents describe or recommend it), *proposal only*
(no document does).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

#: A latest evaluation older than this many years before today is "stale".
MATURITY_RECENT_YEARS = 5

#: The evidence type (in ``core.schema.EVIDENCE_TYPES``) that lifts an option to "reviewed".
REVIEW_EVIDENCE_TYPE = "Systematic Review and Meta-Analysis"

Rung = Literal["proposal_only", "described", "evaluated", "reviewed"]


@dataclass(frozen=True)
class Maturity:
    """One option's maturity rung and its two modifiers.

    Attributes:
        rung: The rung.
        design_mix: The evaluating documents' evidence types as text, most
            frequent first, for example "1 RCT, 2 observational"; empty when
            none evaluated the option.
        none_in_your_setting: Documents evaluated the option but none in the
            plan's Where country.
        latest_evaluation_year: The newest evaluating document's year, or
            ``None``.
        stale: The newest evaluation is more than
            :data:`MATURITY_RECENT_YEARS` years old.
    """

    rung: Rung
    design_mix: str
    none_in_your_setting: bool
    latest_evaluation_year: int | None
    stale: bool


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def maturity_of(
    coverage: Mapping[str, Any], *, where_country: str | None, today_year: int
) -> Maturity | None:
    """Read the rung from an option's coverage.

    Args:
        coverage: The option's stored coverage entry.
        where_country: The plan's Where as one country's short name, or
            ``None`` when the plan names none.
        today_year: The current calendar year.

    Returns:
        The maturity, or ``None`` when the coverage predates the
        ``evaluating_evidence_type`` key (an older row not yet recomputed).
    """
    if "evaluating_evidence_type" not in coverage:
        return None
    evaluating = coverage.get("evaluating_evidence_type") or {}
    role = coverage.get("role") or {}
    evaluated = _count(role.get("evaluated"))
    described = _count(role.get("described")) + _count(role.get("recommended"))

    rung: Rung
    if REVIEW_EVIDENCE_TYPE in evaluating:
        rung = "reviewed"
    elif evaluated > 0:
        rung = "evaluated"
    elif described > 0:
        rung = "described"
    else:
        rung = "proposal_only"

    ordered = sorted(evaluating.items(), key=lambda item: (-_count(item[1]), item[0]))
    design_mix = ", ".join(f"{_count(n)} {kind}" for kind, n in ordered)

    countries = {
        str(entry.get("country", "")).casefold()
        for entry in coverage.get("evaluated_countries") or []
        if isinstance(entry, Mapping)
    }
    none_in_setting = (
        evaluated > 0
        and where_country is not None
        and where_country.casefold() not in countries
    )

    latest = coverage.get("latest_evaluation_year")
    latest_year = latest if isinstance(latest, int) and not isinstance(latest, bool) else None
    stale = latest_year is not None and latest_year < today_year - MATURITY_RECENT_YEARS
    return Maturity(
        rung=rung,
        design_mix=design_mix,
        none_in_your_setting=none_in_setting,
        latest_evaluation_year=latest_year,
        stale=stale,
    )
