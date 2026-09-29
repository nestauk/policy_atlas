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

The same names drive :func:`strip_place` (task 046, S6), which takes the
place out of a plan text before it reaches the longlist: the country and
sub-national names only, never the nationality adjectives.
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

#: Country names (lower case) → ISO-3166 alpha-2. Every OECD member, the
#: United Kingdom and a short list of countries that recur in policy
#: evidence. Multi-word entries that contain another entry ("north korea",
#: "united states of america") are matched first, so the longer place wins.
COUNTRY_NAMES: dict[str, str] = {
    # The United Kingdom.
    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    # North Korea is not South Korea (the OECD member): matched before "korea".
    "north korea": "KP",
    "democratic people's republic of korea": "KP",
    "dprk": "KP",
    # OECD members.
    "australia": "AU",
    "austria": "AT",
    "belgium": "BE",
    "canada": "CA",
    "chile": "CL",
    "colombia": "CO",
    "costa rica": "CR",
    "czech republic": "CZ",
    "czechia": "CZ",
    "denmark": "DK",
    "estonia": "EE",
    "finland": "FI",
    "france": "FR",
    "germany": "DE",
    "greece": "GR",
    "hungary": "HU",
    "iceland": "IS",
    "ireland": "IE",
    "israel": "IL",
    "italy": "IT",
    "japan": "JP",
    "south korea": "KR",
    "republic of korea": "KR",
    "korea": "KR",
    "latvia": "LV",
    "lithuania": "LT",
    "luxembourg": "LU",
    "mexico": "MX",
    "netherlands": "NL",
    "holland": "NL",
    "new zealand": "NZ",
    "norway": "NO",
    "poland": "PL",
    "portugal": "PT",
    "slovakia": "SK",
    "slovenia": "SI",
    "spain": "ES",
    "sweden": "SE",
    "switzerland": "CH",
    "turkey": "TR",
    "türkiye": "TR",
    "united states": "US",
    "united states of america": "US",
    # Outside the OECD, recurring in policy evidence.
    "argentina": "AR",
    "bangladesh": "BD",
    "brazil": "BR",
    "china": "CN",
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

#: Recurring sub-national places (lower case) → the ISO-3166 alpha-2 code of
#: their country (task 046, item 26): the United Kingdom's nations, the
#: English regions and the largest cities and combined authorities; the US
#: states; the Canadian provinces and territories; the Australian states and
#: territories. Deliberately modest. A name that is also a country
#: ("Georgia") or recurs as a city elsewhere ("Birmingham", "Newcastle") is
#: left out: it would guess.
SUBNATIONAL_PLACES: dict[str, str] = {
    # The United Kingdom's nations.
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "northern ireland": "GB",
    # English regions.
    "north east england": "GB",
    "north west england": "GB",
    "yorkshire and the humber": "GB",
    "yorkshire": "GB",
    "east midlands": "GB",
    "west midlands": "GB",
    "east of england": "GB",
    "south east england": "GB",
    "south west england": "GB",
    "greater london": "GB",
    # The largest UK cities and combined authorities.
    "london": "GB",
    "greater manchester": "GB",
    "manchester": "GB",
    "liverpool city region": "GB",
    "merseyside": "GB",
    "liverpool": "GB",
    "west yorkshire": "GB",
    "leeds": "GB",
    "south yorkshire": "GB",
    "sheffield": "GB",
    "tyne and wear": "GB",
    "bristol": "GB",
    "glasgow": "GB",
    "edinburgh": "GB",
    "cardiff": "GB",
    "belfast": "GB",
    # US states (Georgia is left out: it is also a country).
    "alabama": "US",
    "alaska": "US",
    "arizona": "US",
    "arkansas": "US",
    "california": "US",
    "colorado": "US",
    "connecticut": "US",
    "delaware": "US",
    "florida": "US",
    "hawaii": "US",
    "idaho": "US",
    "illinois": "US",
    "indiana": "US",
    "iowa": "US",
    "kansas": "US",
    "kentucky": "US",
    "louisiana": "US",
    "maine": "US",
    "maryland": "US",
    "massachusetts": "US",
    "michigan": "US",
    "minnesota": "US",
    "mississippi": "US",
    "missouri": "US",
    "montana": "US",
    "nebraska": "US",
    "nevada": "US",
    "new hampshire": "US",
    "new jersey": "US",
    "new mexico": "US",
    "new york": "US",
    "north carolina": "US",
    "north dakota": "US",
    "ohio": "US",
    "oklahoma": "US",
    "oregon": "US",
    "pennsylvania": "US",
    "rhode island": "US",
    "south carolina": "US",
    "south dakota": "US",
    "tennessee": "US",
    "texas": "US",
    "utah": "US",
    "vermont": "US",
    "virginia": "US",
    "west virginia": "US",
    "washington state": "US",
    "wisconsin": "US",
    "wyoming": "US",
    "new england": "US",
    # Canadian provinces and territories.
    "alberta": "CA",
    "british columbia": "CA",
    "manitoba": "CA",
    "new brunswick": "CA",
    "newfoundland and labrador": "CA",
    "newfoundland": "CA",
    "nova scotia": "CA",
    "ontario": "CA",
    "prince edward island": "CA",
    "quebec": "CA",
    "québec": "CA",
    "saskatchewan": "CA",
    "yukon": "CA",
    "nunavut": "CA",
    "northwest territories": "CA",
    # Australian states and territories.
    "new south wales": "AU",
    "victoria": "AU",
    "queensland": "AU",
    "western australia": "AU",
    "south australia": "AU",
    "tasmania": "AU",
    "northern territory": "AU",
    "australian capital territory": "AU",
}

#: Nationality and country adjectives (lower case) → ISO-3166 alpha-2. They
#: place a study ("a Danish cohort") but also name a population ("Polish
#: migrant workers"), so the place strip never uses them. Adjectives that
#: name a language or a wider region as often as a country ("English",
#: "American", "Indian") are left out: they would guess.
COUNTRY_ADJECTIVES: dict[str, str] = {
    "british": "GB",
    "scottish": "GB",
    "welsh": "GB",
    "north korean": "KP",
    "australian": "AU",
    "austrian": "AT",
    "belgian": "BE",
    "canadian": "CA",
    "chilean": "CL",
    "colombian": "CO",
    "costa rican": "CR",
    "czech": "CZ",
    "danish": "DK",
    "estonian": "EE",
    "finnish": "FI",
    "french": "FR",
    "german": "DE",
    "greek": "GR",
    "hungarian": "HU",
    "icelandic": "IS",
    "irish": "IE",
    "israeli": "IL",
    "italian": "IT",
    "japanese": "JP",
    "korean": "KR",
    "latvian": "LV",
    "lithuanian": "LT",
    "mexican": "MX",
    "dutch": "NL",
    "norwegian": "NO",
    "polish": "PL",
    "portuguese": "PT",
    "slovak": "SK",
    "slovenian": "SI",
    "spanish": "ES",
    "swedish": "SE",
    "swiss": "CH",
    "turkish": "TR",
    "brazilian": "BR",
    "chinese": "CN",
}

#: Every name the matcher reads a geography by: the places, then the
#: adjectives. Longer entries are matched first, so the longer place wins.
COUNTRY_GROUPS: dict[str, str] = {
    **COUNTRY_NAMES,
    **SUBNATIONAL_PLACES,
    **COUNTRY_ADJECTIVES,
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


# --- The place strip (task 046, S6; PA11) -----------------------------------

#: The prepositions that lead a place the strip removes (contract PA11).
#: "from" is not one: an origin defines a population ("migrants from
#: India"). "living in" comes before "in" in the alternation by length, so
#: the longer lead is removed whole.
PLACE_PREPOSITIONS: tuple[str, ...] = ("living in", "in", "across", "within")

_PREPOSITION = "(?i:{})".format(
    "|".join(
        r"\s+".join(re.escape(word) for word in phrase.split())
        for phrase in sorted(PLACE_PREPOSITIONS, key=len, reverse=True)
    )
)
_ARTICLE = r"(?i:the\s+)?"
# A place is a country or sub-national name (case-insensitive) or an
# abbreviation (case-sensitive: "us" is a pronoun). Never an adjective, and
# never the head of a compound ("UK-wide", "London-based").
_PLACE = (
    rf"(?:(?i:{_alternation([*COUNTRY_NAMES, *SUBNATIONAL_PLACES])})(?![\w-])"
    rf"|(?<![\w.])(?:{_alternation(ABBREVIATIONS)})(?![\w-]))"
)
# "in Greater Manchester and Lancashire" keeps "and Lancashire" (not a known
# place); "across England and Wales" and "in Leeds, UK" go whole.
_PLACE_LIST = rf"{_ARTICLE}{_PLACE}(?:\s*(?:,|(?i:and|or)|&)\s*{_ARTICLE}{_PLACE})*"
_LED_PLACE_RE = re.compile(rf"(?<![\w])(?:{_PREPOSITION})\s+{_PLACE_LIST}")
_TRAILING_PREPOSITION_RE = re.compile(rf"\s+(?:{_PREPOSITION})\s*(?=[.;:!?]?\s*$)")


def _tidy(text: str) -> str:
    """Collapse the whitespace and punctuation a removal leaves behind."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", text)
    text = re.sub(r"[,;:]\s*(?=[.!?]|$)", "", text)
    # "… in the last two years and living in X" leaves a conjunction with
    # nothing after it; "the most deprived areas of X" leaves an "of".
    text = re.sub(r"\s+(?i:and|or|of)(?:\s+(?i:the))?\s*(?=[.,;:!?]|$)", "", text)
    text = _TRAILING_PREPOSITION_RE.sub("", text)
    text = re.sub(r"^[\s,;:]+", "", text)
    text = re.sub(r"\(\s*\)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_place(text: str, where_text: str | None) -> tuple[str, list[str]]:
    """Remove the place from a plan text, never a population's nationality.

    Two removals, in order:

    1. the plan's Where text wherever it appears verbatim (case-insensitive,
       on word boundaries), with a leading preposition and article when one
       leads it ("in the United Kingdom" when Where is "United Kingdom");
    2. a place the where-tried matcher knows — a country or sub-national
       name, or an abbreviation ("UK") — **only when a preposition leads
       it** ("in", "living in", "across", "within"), removed with
       that preposition and a following "the"; a list of known places
       ("across England and Wales") goes whole.

    The matcher's adjective entries are never used, so "Polish migrant
    workers" keeps "Polish"; an unled place name ("UK adults") stays unless
    it is the Where text. The result has tidy whitespace, no space before a
    full stop or comma and no dangling preposition. A text with no place is
    returned unchanged.

    Args:
        text: The plan text (a target unit, an intended change, a question).
        where_text: The plan's Where, or ``None``.

    Returns:
        ``(cleaned, removed)``: the cleaned text and the removed spans, as
        they appeared, in removal order; ``(text, [])`` when nothing matched.
    """
    removed: list[str] = []

    def _record(match: re.Match[str]) -> str:
        removed.append(" ".join(match.group(0).split()))
        return " "

    cleaned = text
    where = " ".join((where_text or "").split())
    if where:
        where_pattern = r"\s+".join(re.escape(word) for word in where.split(" "))
        where_re = re.compile(
            rf"(?<![\w-])(?:(?:{_PREPOSITION})\s+)?{_ARTICLE}(?i:{where_pattern})(?![\w-])"
        )
        cleaned = where_re.sub(_record, cleaned)
    cleaned = _LED_PLACE_RE.sub(_record, cleaned)
    if not removed:
        return text, []
    return _tidy(cleaned), removed
