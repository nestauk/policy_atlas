"""Where tried: an option's study geographies grouped against the plan's Where.

Task 045, D20 (ADR 0039 decision 10). Where is out of the longlist's
retrieval chain; it comes back on the way out as *where tried*: the
countries an option's documents were studied in, read from each record's
``study_geography`` text, grouped against the plan's Where as

- ``where`` — a study in the plan's Where (shown under Where's own words,
  usually "United Kingdom");
- ``comparable`` — *comparable systems (OECD)*: a study in an OECD member
  (``TIER1_GROUPS["OECD members"]``), or one that says it spans OECD
  countries without naming them ("12 OECD countries");
- ``other`` — a study in a named country outside both;
- ``unknown`` — a geography that matches nothing below, or none stated.

A facet and a card line; never a filter, never a verdict. Deterministic: the
same text always gives the same group. The mapping is deliberately small and
honest — a geography it does not know is ``unknown``, never guessed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from policy_atlas.evidence_search.sourcing.country_filters import TIER1_GROUPS

WhereGroup = Literal["where", "comparable", "other", "unknown"]

#: The four groups in display order.
WHERE_GROUPS: tuple[WhereGroup, ...] = ("where", "comparable", "other", "unknown")

#: The fixed display labels; ``where`` is replaced by the plan's own words.
COMPARABLE_LABEL = "comparable systems (OECD)"

OECD_CODES: frozenset[str] = frozenset(TIER1_GROUPS["OECD members"])

#: Country names and adjectives (lower case) → ISO-3166 alpha-2. Every OECD
#: member, the United Kingdom's nations, and a short list of countries that
#: recur in policy evidence. Adjectives that name a language or a wider
#: region as often as a country ("English", "American", "Indian") are left
#: out: they would guess. Multi-word entries that contain another entry
#: ("new south wales", "northern ireland", "british columbia") are matched
#: first, so the longer place wins.
COUNTRY_GROUPS: dict[str, str] = {
    # The United Kingdom and its nations.
    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    "british": "GB",
    "england": "GB",
    "scotland": "GB",
    "scottish": "GB",
    "wales": "GB",
    "welsh": "GB",
    "northern ireland": "GB",
    "london": "GB",
    # Places whose names contain another entry.
    "new south wales": "AU",
    "new england": "US",
    "british columbia": "CA",
    "new mexico": "US",
    # North Korea is not South Korea (the OECD member): matched before "korea".
    "north korea": "KP",
    "north korean": "KP",
    "democratic people's republic of korea": "KP",
    "dprk": "KP",
    # OECD members.
    "australia": "AU",
    "australian": "AU",
    "austria": "AT",
    "austrian": "AT",
    "belgium": "BE",
    "belgian": "BE",
    "canada": "CA",
    "canadian": "CA",
    "chile": "CL",
    "chilean": "CL",
    "colombia": "CO",
    "colombian": "CO",
    "costa rica": "CR",
    "costa rican": "CR",
    "czech republic": "CZ",
    "czechia": "CZ",
    "czech": "CZ",
    "denmark": "DK",
    "danish": "DK",
    "estonia": "EE",
    "estonian": "EE",
    "finland": "FI",
    "finnish": "FI",
    "france": "FR",
    "french": "FR",
    "germany": "DE",
    "german": "DE",
    "greece": "GR",
    "greek": "GR",
    "hungary": "HU",
    "hungarian": "HU",
    "iceland": "IS",
    "icelandic": "IS",
    "ireland": "IE",
    "irish": "IE",
    "israel": "IL",
    "israeli": "IL",
    "italy": "IT",
    "italian": "IT",
    "japan": "JP",
    "japanese": "JP",
    "south korea": "KR",
    "republic of korea": "KR",
    "korea": "KR",
    "korean": "KR",
    "latvia": "LV",
    "latvian": "LV",
    "lithuania": "LT",
    "lithuanian": "LT",
    "luxembourg": "LU",
    "mexico": "MX",
    "mexican": "MX",
    "netherlands": "NL",
    "dutch": "NL",
    "holland": "NL",
    "new zealand": "NZ",
    "norway": "NO",
    "norwegian": "NO",
    "poland": "PL",
    "polish": "PL",
    "portugal": "PT",
    "portuguese": "PT",
    "slovakia": "SK",
    "slovak": "SK",
    "slovenia": "SI",
    "slovenian": "SI",
    "spain": "ES",
    "spanish": "ES",
    "sweden": "SE",
    "swedish": "SE",
    "switzerland": "CH",
    "swiss": "CH",
    "turkey": "TR",
    "türkiye": "TR",
    "turkish": "TR",
    "united states": "US",
    "united states of america": "US",
    # Outside the OECD, recurring in policy evidence.
    "argentina": "AR",
    "bangladesh": "BD",
    "brazil": "BR",
    "brazilian": "BR",
    "china": "CN",
    "chinese": "CN",
    "egypt": "EG",
    "ethiopia": "ET",
    "ghana": "GH",
    "hong kong": "HK",
    "india": "IN",
    "indonesia": "ID",
    "iran": "IR",
    "kenya": "KE",
    "malawi": "MW",
    "malaysia": "MY",
    "nepal": "NP",
    "nigeria": "NG",
    "pakistan": "PK",
    "peru": "PE",
    "philippines": "PH",
    "russia": "RU",
    "rwanda": "RW",
    "saudi arabia": "SA",
    "singapore": "SG",
    "south africa": "ZA",
    "sri lanka": "LK",
    "taiwan": "TW",
    "tanzania": "TZ",
    "thailand": "TH",
    "uganda": "UG",
    "vietnam": "VN",
    "zambia": "ZM",
    "zimbabwe": "ZW",
}

#: Upper-case abbreviations, matched case-sensitively ("us" is a pronoun).
ABBREVIATIONS: dict[str, str] = {
    "UK": "GB",
    "U.K.": "GB",
    "US": "US",
    "U.S.": "US",
    "USA": "US",
    "U.S.A.": "US",
}

#: Words that place a study in OECD countries without naming one.
OECD_MARKERS: tuple[str, ...] = ("oecd",)


def _alternation(phrases: Iterable[str]) -> str:
    ordered = sorted(phrases, key=lambda phrase: (-len(phrase), phrase))
    return "|".join(re.escape(phrase) for phrase in ordered)


# Boundaries are look-arounds, not ``\b``: an abbreviation ends in a full stop.
_NAMES_RE = re.compile(
    rf"(?<![\w])({_alternation([*COUNTRY_GROUPS, *OECD_MARKERS])})(?![\w])",
    re.IGNORECASE,
)
_ABBREVIATIONS_RE = re.compile(rf"(?<![\w.])({_alternation(ABBREVIATIONS)})(?![\w])")


def countries_in(text: str | None) -> tuple[frozenset[str], bool]:
    """Read the countries a geography text names.

    Args:
        text: A record's ``study_geography`` (or a plan's Where), or ``None``.

    Returns:
        ``(codes, oecd_marker)``: the ISO-3166 alpha-2 codes named, and
        whether the text places the study in OECD countries without naming
        them. Both empty when nothing matches.
    """
    if not text:
        return frozenset(), False
    codes: set[str] = set()
    oecd = False
    for match in _NAMES_RE.finditer(text):
        phrase = match.group(1).casefold()
        if phrase in OECD_MARKERS:
            oecd = True
        else:
            codes.add(COUNTRY_GROUPS[phrase])
    for match in _ABBREVIATIONS_RE.finditer(text):
        codes.add(ABBREVIATIONS[match.group(1)])
    return frozenset(codes), oecd


def where_codes(where_text: str | None) -> frozenset[str]:
    """The ISO codes a plan's Where names (empty when it names none this module knows).

    Args:
        where_text: The plan's Where.

    Returns:
        The codes; a Where that matches nothing leaves the ``where`` group empty.
    """
    codes, _oecd = countries_in(where_text)
    return codes


def where_group(geographies: Iterable[str | None], home: frozenset[str]) -> WhereGroup:
    """Group one document's study geographies against the plan's Where.

    Args:
        geographies: The ``study_geography`` texts of the document's records.
        home: The plan's Where as ISO codes (:func:`where_codes`).

    Returns:
        ``where`` when any named country is in Where; else ``comparable``
        when any is an OECD member or the text says OECD; else ``other``
        when any country is named; else ``unknown``.
    """
    codes: set[str] = set()
    oecd = False
    for text in geographies:
        found, marker = countries_in(text)
        codes |= found
        oecd = oecd or marker
    if codes & home:
        return "where"
    if codes & OECD_CODES or oecd:
        return "comparable"
    if codes:
        return "other"
    return "unknown"


def where_labels(where_text: str | None) -> dict[str, str]:
    """The display label of each group.

    Args:
        where_text: The plan's Where.

    Returns:
        ``{"where": <Where's words>, "comparable": "comparable systems (OECD)",
        "other": "other", "unknown": "unknown"}``.
    """
    return {
        "where": (where_text or "").strip() or "Where",
        "comparable": COMPARABLE_LABEL,
        "other": "other",
        "unknown": "unknown",
    }
