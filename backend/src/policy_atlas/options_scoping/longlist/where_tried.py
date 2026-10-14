"""Where tried: two levels read from the record (task 046, amendment 3; R59, R72).

The top level comes from the record's ``study_country`` (every country the
study names, separated by ";", each its short English name); the level
below is the record's ``study_geography`` as written. No fixed list of
names decides the top level, and nothing else of the document (publisher,
journal, institutions, publication country) is read.

Per document (:func:`document_where`): one country when every record that has a country
gives the same one; "multiple countries" when they give two or more between
them, or any gives "multiple"; else "other" when any record states a place;
else "not stated". Countries compare with case folded only.

The name tables below drive :func:`names_place` and :func:`named_place`
(the setting pass). The plan-text place strip of S6 is gone (R74; the
owner's ruling at the review, 2026-10-12): the place rule is words in the
prompts. Task 046, amendment 4 (R87; S29a,
S32): :data:`COUNTRY_NAMES` holds every ISO-3166 country, and one resolver
(:func:`resolve_country`) maps a place text to one country code and one
short English name (:data:`COUNTRY_DISPLAY_NAMES`), so "UK", "England" and
"Britain" are the United Kingdom; coverage reads the signal's countries and
the place checks (:func:`country_level`, :func:`place_key`) through it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from policy_atlas.evidence_search.sourcing.country_filters import ISO_3166_ALPHA2
from policy_atlas.options_scoping.text import clean_text

#: The top level of a record or document naming two or more countries.
MULTIPLE_COUNTRIES = "multiple countries"

#: The top level of a stated place with no country.
OTHER_PLACE = "other"

#: The top level when nothing is stated.
NOT_STATED = "not stated"

#: The ``study_country`` part that names a group of countries.
_MULTIPLE = "multiple"


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
        name = clean_text(part)
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
    rows = list(records)
    countries, multiple = countries_named(";".join(country or "" for country, _ in rows))
    place = any(clean_text(geography) is not None for _, geography in rows)
    if multiple or len(countries) > 1:
        return MULTIPLE_COUNTRIES, countries
    if countries:
        return countries[0], countries
    return (OTHER_PLACE if place else NOT_STATED), countries


#: Country names and aliases (lower case) → ISO-3166 alpha-2, written here:
#: the names in common use that the ISO-3166 names below do not give
#: ("britain", "south korea", "vietnam", "drc"), merged over them. Multi-word
#: entries that contain another entry ("north korea", "united states of
#: america") are matched first, so the longer place wins.
_COUNTRY_ALIASES: dict[str, str] = {
    # The United Kingdom.
    "united kingdom": "GB",
    "great britain": "GB",
    "britain": "GB",
    # North Korea is not South Korea: matched before "korea".
    "north korea": "KP",
    "democratic people's republic of korea": "KP",
    "dprk": "KP",
    "south korea": "KR",
    "republic of korea": "KR",
    "korea": "KR",
    # Short names in common use.
    "czech republic": "CZ",
    "czechia": "CZ",
    "holland": "NL",
    "turkey": "TR",
    "türkiye": "TR",
    "turkiye": "TR",
    "united states": "US",
    "united states of america": "US",
    "russia": "RU",
    "vietnam": "VN",
    "viet nam": "VN",
    "laos": "LA",
    "lao pdr": "LA",
    "syria": "SY",
    "moldova": "MD",
    "republic of moldova": "MD",
    "tanzania": "TZ",
    "united republic of tanzania": "TZ",
    "venezuela": "VE",
    "bolivia": "BO",
    "iran": "IR",
    "taiwan": "TW",
    "ivory coast": "CI",
    "cote d'ivoire": "CI",
    "côte d'ivoire": "CI",
    "eswatini": "SZ",
    "swaziland": "SZ",
    "burma": "MM",
    "myanmar": "MM",
    "macedonia": "MK",
    "north macedonia": "MK",
    "gambia": "GM",
    "the gambia": "GM",
    "bahamas": "BS",
    "the bahamas": "BS",
    "micronesia": "FM",
    "palestine": "PS",
    "state of palestine": "PS",
    "vatican": "VA",
    "vatican city": "VA",
    "holy see": "VA",
    "congo": "CG",
    "republic of the congo": "CG",
    "congo-brazzaville": "CG",
    "democratic republic of the congo": "CD",
    "dr congo": "CD",
    "drc": "CD",
    "congo-kinshasa": "CD",
    "cape verde": "CV",
    "cabo verde": "CV",
    "east timor": "TL",
    "timor-leste": "TL",
    "brunei": "BN",
    "hong kong": "HK",
    "macau": "MO",
    "macao": "MO",
    "reunion": "RE",
    "réunion": "RE",
    "curacao": "CW",
    "curaçao": "CW",
    "british virgin islands": "VG",
    "us virgin islands": "VI",
    "u.s. virgin islands": "VI",
    "falkland islands": "FK",
    "saint helena": "SH",
    "st helena": "SH",
    "bonaire": "BQ",
    "western sahara": "EH",
    "united arab emirates": "AE",
    "dominican republic": "DO",
    "philippines": "PH",
}


def _iso_bare(name: str) -> tuple[str, str]:
    """An ISO-3166 name, lower case: ``(full name, bare name)``.

    The full name loses a trailing "(the)", a bracketed alternative
    ("[Malvinas]") and a trailing "*"; the bare name also loses every
    parenthesised qualifier ("Bolivia (Plurinational State of)" → "bolivia").
    """
    full = re.sub(r"\s*\[[^\]]*\]", "", name).replace("*", "")
    full = re.sub(r"\s*\(the\)\s*$", "", full, flags=re.IGNORECASE)
    full = " ".join(full.split()).casefold()
    bare = " ".join(re.sub(r"\([^)]*\)", "", full).split())
    return full, bare


def _iso_country_names() -> dict[str, str]:
    """Every ISO-3166 country by its full and its bare name (lower case).

    A bare name two codes share ("korea", "congo", "virgin islands") is left
    out here; the aliases name the one each means.
    """
    names: dict[str, str] = {}
    bare_codes: dict[str, set[str]] = {}
    for code, name in ISO_3166_ALPHA2.items():
        full, bare = _iso_bare(name)
        names[full] = code
        bare_codes.setdefault(bare, set()).add(code)
    for bare, codes in bare_codes.items():
        if len(codes) == 1:
            names.setdefault(bare, next(iter(codes)))
    return names


#: Country names (lower case) → ISO-3166 alpha-2: every country of the
#: ISO-3166 table the Evidence search sourcing holds, by its full and its
#: bare name, with the aliases above merged over them (task 046, amendment 4,
#: R87; S29a).
COUNTRY_NAMES: dict[str, str] = {**_iso_country_names(), **_COUNTRY_ALIASES}

#: The short English name per ISO-3166 code where the ISO name is not the
#: name in common use (task 046, amendment 4, R76; S29a).
_DISPLAY_OVERRIDES: dict[str, str] = {
    "GB": "United Kingdom",
    "US": "United States",
    "KR": "South Korea",
    "KP": "North Korea",
    "RU": "Russia",
    "IR": "Iran",
    "VN": "Vietnam",
    "TW": "Taiwan",
    "BO": "Bolivia",
    "VE": "Venezuela",
    "TZ": "Tanzania",
    "LA": "Laos",
    "SY": "Syria",
    "MD": "Moldova",
    "CZ": "Czech Republic",
    "TR": "Turkey",
    "NL": "Netherlands",
    "FM": "Micronesia",
    "PS": "Palestine",
    "VA": "Vatican City",
    "CD": "Democratic Republic of the Congo",
    "CG": "Republic of the Congo",
    "CI": "Côte d'Ivoire",
    "BN": "Brunei",
    "MK": "North Macedonia",
    "SZ": "Eswatini",
    "MM": "Myanmar",
    "CV": "Cape Verde",
    "TL": "Timor-Leste",
    "KN": "Saint Kitts and Nevis",
    "LC": "Saint Lucia",
    "VC": "Saint Vincent and the Grenadines",
    "TT": "Trinidad and Tobago",
    "VG": "British Virgin Islands",
    "VI": "US Virgin Islands",
    "BS": "Bahamas",
    "GM": "Gambia",
    "AE": "United Arab Emirates",
    "DO": "Dominican Republic",
    "PH": "Philippines",
    "MH": "Marshall Islands",
    "SB": "Solomon Islands",
    "KM": "Comoros",
    "NE": "Niger",
    "SD": "Sudan",
    "MP": "Northern Mariana Islands",
    "TC": "Turks and Caicos Islands",
    "CK": "Cook Islands",
    "FK": "Falkland Islands",
    "FO": "Faroe Islands",
    "KY": "Cayman Islands",
    "GS": "South Georgia and the South Sandwich Islands",
    "HM": "Heard Island and McDonald Islands",
    "UM": "United States Minor Outlying Islands",
    "IO": "British Indian Ocean Territory",
    "TF": "French Southern Territories",
    "SH": "Saint Helena, Ascension and Tristan da Cunha",
    "SJ": "Svalbard and Jan Mayen",
    "LY": "Libya",
    "SX": "Sint Maarten",
    "MF": "Saint Martin",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "BL": "Saint Barthélemy",
    "PM": "Saint Pierre and Miquelon",
    "WF": "Wallis and Futuna",
    "CC": "Cocos (Keeling) Islands",
    "CX": "Christmas Island",
    "NF": "Norfolk Island",
    "AX": "Åland Islands",
}


def _display_name(name: str) -> str:
    """An ISO-3166 name without "(the)", a bracketed alternative, a "*" or a qualifier."""
    text = re.sub(r"\s*\[[^\]]*\]", "", name).replace("*", "")
    text = re.sub(r"\s*\([^)]*\)", "", text)
    return " ".join(text.split())


#: ISO-3166 alpha-2 → one short English name per country (task 046,
#: amendment 4, R76; S29a): the signal's country words.
COUNTRY_DISPLAY_NAMES: dict[str, str] = {
    code: _DISPLAY_OVERRIDES.get(code, _display_name(name))
    for code, name in ISO_3166_ALPHA2.items()
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

#: The United Kingdom's four nations: sub-national, but each a country name
#: to the reader, so a ``study_geography`` naming one under the United
#: Kingdom is the country level, not a place below it (task 046,
#: amendment 4, R87; S32).
UK_NATIONS: frozenset[str] = frozenset({"england", "scotland", "wales", "northern ireland"})

_LEADING_THE_RE = re.compile(r"^the\s+", re.IGNORECASE)


def _lookup_text(text: str | None) -> str | None:
    """Whitespace collapsed, curly apostrophes straightened, a leading "the" stripped."""
    if text is None:
        return None
    cleaned = _LEADING_THE_RE.sub("", " ".join(text.replace("\u2019", "'").split()))
    return cleaned or None


def _resolve(text: str | None) -> tuple[str, str] | None:
    """``(code, table)`` for a place text: ``country``, ``abbreviation`` or ``subnational``."""
    cleaned = _lookup_text(text)
    if cleaned is None:
        return None
    key = cleaned.casefold()
    if key in COUNTRY_NAMES:
        return COUNTRY_NAMES[key], "country"
    if cleaned in ABBREVIATIONS:
        return ABBREVIATIONS[cleaned], "abbreviation"
    if key in SUBNATIONAL_PLACES:
        return SUBNATIONAL_PLACES[key], "subnational"
    return None


def resolve_country(text: str | None) -> tuple[str, str] | None:
    """The country a place text names, as one code and one short English name.

    The text has its whitespace collapsed and a leading "the" stripped; it
    is looked up case-folded in :data:`COUNTRY_NAMES`, then case-sensitively
    in :data:`ABBREVIATIONS` ("UK", "U.S."), then case-folded in
    :data:`SUBNATIONAL_PLACES` ("England", "New South Wales") (task 046,
    amendment 4, R87; S29a).

    Args:
        text: A country or place as written, or ``None``.

    Returns:
        ``(iso_alpha2, display_name)`` (display name from
        :data:`COUNTRY_DISPLAY_NAMES`), or ``None`` when the text names no
        country the tables know.
    """
    found = _resolve(text)
    if found is None:
        return None
    code = found[0]
    return code, COUNTRY_DISPLAY_NAMES.get(code, code)


def names_country(text: str | None) -> bool:
    """Whether a place text is itself a country name, not a place within one.

    A name or alias in :data:`COUNTRY_NAMES`, an abbreviation ("UK") or one
    of the United Kingdom's nations (:data:`UK_NATIONS`); a city, region or
    state ("London", "New South Wales") is a place within its country
    (task 046, amendment 4, R87; S32).

    Args:
        text: A place as written, or ``None``.

    Returns:
        True when the text is a country name.
    """
    found = _resolve(text)
    if found is None:
        return False
    if found[1] != "subnational":
        return True
    cleaned = _lookup_text(text)
    return cleaned is not None and cleaned.casefold() in UK_NATIONS


def place_key(text: str) -> str:
    """The key a place's spellings are grouped under (task 046, amendment 4, R87; S32).

    Case folded, a leading "the" stripped, hyphens and spaces removed, so
    "South West", "south-west" and "southwest" are one place.

    Args:
        text: A place or top level as written.

    Returns:
        The grouping key.
    """
    cleaned = _lookup_text(text) or ""
    return re.sub(r"[\s\-\u2010-\u2015]+", "", cleaned.casefold())


def country_level(
    study_country: str | None, study_geography: str | None
) -> tuple[str | None, str | None]:
    """A record's place with a geography that is a country read as the country.

    When ``study_geography`` is a country name (:func:`names_country`) and
    the record names no country, or names the one country it resolves to,
    the geography is the country level with nothing below it: ``("United
    Kingdom", "Scotland")`` → ``("United Kingdom", None)`` and ``(None,
    "France")`` → ``("France", None)``. A geography that resolves to another
    country ("Georgia" under the United Kingdom) or to no country is kept as
    written (task 046, amendment 4, R87; S32). Nothing is written back.

    Args:
        study_country: The record's ``study_country``.
        study_geography: The record's ``study_geography``.

    Returns:
        ``(study_country, study_geography)`` as coverage reads them.
    """
    geography = clean_text(study_geography)
    if geography is None or not names_country(geography):
        return study_country, study_geography
    countries, multiple = countries_named(study_country)
    if not countries and not multiple:
        return geography, None
    if multiple or len(countries) != 1:
        return study_country, study_geography
    own, named = resolve_country(countries[0]), resolve_country(geography)
    if own is not None and named is not None and own[0] == named[0]:
        return study_country, None
    return study_country, study_geography

def _alternation(phrases: Iterable[str]) -> str:
    ordered = sorted(phrases, key=lambda phrase: (-len(phrase), phrase))
    return "|".join(re.escape(phrase) for phrase in ordered)


# --- A place in a text (the setting pass; task 046, S11; R87) -----------------

# A place is a country or sub-national name (case-insensitive) or an
# abbreviation (case-sensitive: "us" is a pronoun). Never an adjective, and
# never the head of a compound ("UK-wide", "London-based").
#: Country names that are also common nouns or given names ("turkey farms",
#: "guinea pig", "a football jersey", "the Jordan model of care"): the matcher
#: reads them as a place only when capitalised (review of task 046,
#: 2026-10-12). The resolver (:func:`resolve_country`) still knows them.
AMBIGUOUS_COUNTRY_NAMES: frozenset[str] = frozenset(
    {"chad", "guinea", "jersey", "jordan", "niger", "turkey"}
)
_UNAMBIGUOUS_PLACES = [
    n for n in [*COUNTRY_NAMES, *SUBNATIONAL_PLACES] if n not in AMBIGUOUS_COUNTRY_NAMES
]
_PLACE = (
    rf"(?:(?i:{_alternation(_UNAMBIGUOUS_PLACES)})(?![\w-])"
    rf"|(?:{_alternation(n.title() for n in AMBIGUOUS_COUNTRY_NAMES)})(?![\w-])"
    rf"|(?<![\w.])(?:{_alternation(ABBREVIATIONS)})(?![\w-]))"
)
_ANY_PLACE_RE = re.compile(rf"(?<![\w-])(?:{_PLACE})")


def named_place(text: str | None) -> str | None:
    """The first place a text names, as written; ``None`` when it names none.

    The setting pass in ``coverage`` moves this, not the whole setting, into
    an empty geography ("community centres in Leeds" → "Leeds").
    """
    if not text:
        return None
    match = _ANY_PLACE_RE.search(text)
    return match.group(0) if match else None


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
