"""Where tried: two levels read from the record (task 046, amendment 3; R59, R72).

The top level comes from the record's ``study_country`` (every country the
study names, separated by ";", each its short English name); the level
below is the record's ``study_geography`` as written. No fixed list of
names decides the top level, and nothing else of the document (publisher,
journal, institutions, publication country) is read.

Per record (:func:`record_where`): one country → that country; two or more,
or any part "multiple" → "multiple countries"; no country but a stated
geography → "other"; nothing → "not stated". Per document
(:func:`document_where`): one country when every record that has a country
gives the same one; "multiple countries" when they give two or more between
them, or any gives "multiple"; else "other" when any record states a place;
else "not stated". Countries compare with case folded only.

The name tables below drive :func:`strip_place` (task 046, S6), which takes
the place out of a plan text before it reaches the longlist, and
:func:`names_place` (the setting pass); they wait for Phase 18P.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: The top level of a record or document naming two or more countries.
MULTIPLE_COUNTRIES = "multiple countries"

#: The top level of a stated place with no country.
OTHER_PLACE = "other"

#: The top level when nothing is stated.
NOT_STATED = "not stated"

#: The ``study_country`` part that names a group of countries.
_MULTIPLE = "multiple"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split())
    return text or None


def countries_named(study_country: str | None) -> tuple[list[str], bool]:
    """The countries a record's ``study_country`` names.

    Args:
        study_country: The record's ``study_country`` ("United Kingdom;
            United States"), or ``None``.

    Returns:
        ``(countries, multiple)``: the named countries as written, one per
        case-folded name (the smallest spelling kept), in order, without
        "multiple"; and whether any part is "multiple" (case folded).
    """
    countries: list[str] = []
    seen: dict[str, int] = {}
    multiple = False
    for part in (study_country or "").split(";"):
        name = _clean(part)
        if name is None:
            continue
        key = name.casefold()
        if key == _MULTIPLE:
            multiple = True
        elif key not in seen:
            seen[key] = len(countries)
            countries.append(name)
        else:
            # One spelling per country, chosen without regard to row order (task 046,
            # amendment 3): the smallest spelling wins ("United Kingdom" < "united kingdom").
            countries[seen[key]] = min(countries[seen[key]], name)
    return countries, multiple


def record_where(study_country: str | None, study_geography: str | None) -> str:
    """One record's top level.

    Args:
        study_country: The record's ``study_country``.
        study_geography: The record's ``study_geography``.

    Returns:
        The country (as written) when one is named; "multiple countries"
        when two or more are, or any part is "multiple"; "other" when no
        country is named but the geography is stated; else "not stated".
    """
    countries, multiple = countries_named(study_country)
    if multiple or len(countries) > 1:
        return MULTIPLE_COUNTRIES
    if countries:
        return countries[0]
    return OTHER_PLACE if _clean(study_geography) is not None else NOT_STATED


def document_where(
    records: Iterable[tuple[str | None, str | None]],
) -> tuple[str, list[str]]:
    """One document's top level, from its records.

    Args:
        records: ``(study_country, study_geography)`` of each of the
            document's records (DOI-collapsed twins together).

    Returns:
        ``(top, countries)``: the top level (the one country, its smallest
        spelling, "multiple countries", "other" or "not stated") and every
        country its records name, one per case-folded name, in order.
    """
    countries: list[str] = []
    seen: dict[str, int] = {}
    multiple = False
    place = False
    for study_country, study_geography in records:
        named, group = countries_named(study_country)
        multiple = multiple or group
        place = place or _clean(study_geography) is not None
        for name in named:
            key = name.casefold()
            if key not in seen:
                seen[key] = len(countries)
                countries.append(name)
            else:
                countries[seen[key]] = min(countries[seen[key]], name)
    if multiple or len(countries) > 1:
        return MULTIPLE_COUNTRIES, countries
    if countries:
        return countries[0], countries
    return (OTHER_PLACE if place else NOT_STATED), countries


#: Country names (lower case) → ISO-3166 alpha-2: the United Kingdom, the
#: high-income democracies and a short list of countries that recur in
#: policy evidence. Multi-word entries that contain another entry ("north korea",
#: "united states of america") are matched first, so the longer place wins.
COUNTRY_NAMES: dict[str, str] = {
    # The United Kingdom.
    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    # North Korea is not South Korea: matched before "korea".
    "north korea": "KP",
    "democratic people's republic of korea": "KP",
    "dprk": "KP",
    # High-income democracies.
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
    # Others recurring in policy evidence.
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

#: Upper-case abbreviations, matched case-sensitively ("us" is a pronoun).
ABBREVIATIONS: dict[str, str] = {
    "UK": "GB",
    "U.K.": "GB",
    "US": "US",
    "U.S.": "US",
    "USA": "US",
    "U.S.A.": "US",
}

def _alternation(phrases: Iterable[str]) -> str:
    ordered = sorted(phrases, key=lambda phrase: (-len(phrase), phrase))
    return "|".join(re.escape(phrase) for phrase in ordered)


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


# --- A place in a setting (task 046, S11 setting pass) ------------------------

_ANY_PLACE_RE = re.compile(rf"(?<![\w-])(?:{_PLACE})")


def names_place(text: str | None) -> bool:
    """Whether a text names a place the matcher knows, led or not.

    A country or sub-national name, or an abbreviation ("UK"), anywhere in
    the text; never a nationality adjective ("Scottish schools" names no
    place) and never the head of a compound ("London-based"). The setting
    pass in ``coverage`` reads a setting that names a place as a geography.

    Args:
        text: The text, or ``None``.

    Returns:
        True when a known place is named.
    """
    if not text:
        return False
    return _ANY_PLACE_RE.search(text) is not None
