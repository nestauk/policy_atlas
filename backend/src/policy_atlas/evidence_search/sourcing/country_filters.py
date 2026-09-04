"""Static country filter tables and fail-closed helpers.

``ISO_3166_ALPHA2`` is a generated literal from
``$TMP/country_list.csv`` (datasets/country-list, fetched 2026-07-12).
``OVERTON_COUNTRY_DISPLAY`` is generated from the lead-probed
``$TMP/overton_country_probe.json`` accepted map (probed 2026-07-12,
keyword query=climate pp=1, first-nonzero-total-wins). M49 regional groups
come from ``$TMP/m49_tables.json``; institutional groups are the
lead-verified 2026-07-12 tables from the task brief.
"""

from __future__ import annotations

from collections.abc import Iterable


class SearchDirectiveError(ValueError):
    """Raised when a search directive or country filter fails closed."""


ISO_3166_ALPHA2: dict[str, str] = {
    "AD": "Andorra",
    "AE": "United Arab Emirates (the)",
    "AF": "Afghanistan",
    "AG": "Antigua and Barbuda",
    "AI": "Anguilla",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AQ": "Antarctica",
    "AR": "Argentina",
    "AS": "American Samoa",
    "AT": "Austria",
    "AU": "Australia",
    "AW": "Aruba",
    "AX": "\u00c5land Islands",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BI": "Burundi",
    "BJ": "Benin",
    "BL": "Saint Barth\u00e9lemy",
    "BM": "Bermuda",
    "BN": "Brunei Darussalam",
    "BO": "Bolivia (Plurinational State of)",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "BR": "Brazil",
    "BS": "Bahamas (The)",
    "BT": "Bhutan",
    "BV": "Bouvet Island",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    "CA": "Canada",
    "CC": "Cocos (Keeling) Islands (the)",
    "CD": "Congo (the Democratic Republic of the)",
    "CF": "Central African Republic (the)",
    "CG": "Congo (the)",
    "CH": "Switzerland",
    "CI": "C\u00f4te d'Ivoire",
    "CK": "Cook Islands (the)",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cabo Verde",
    "CW": "Cura\u00e7ao",
    "CX": "Christmas Island",
    "CY": "Cyprus",
    "CZ": "Czechia",
    "DE": "Germany",
    "DJ": "Djibouti",
    "DK": "Denmark",
    "DM": "Dominica",
    "DO": "Dominican Republic (the)",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "EH": "Western Sahara*",
    "ER": "Eritrea",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FJ": "Fiji",
    "FK": "Falkland Islands (the) [Malvinas]",
    "FM": "Micronesia (Federated States of)",
    "FO": "Faroe Islands (the)",
    "FR": "France",
    "GA": "Gabon",
    "GB": "United Kingdom of Great Britain and Northern Ireland (the)",
    "GD": "Grenada",
    "GE": "Georgia",
    "GF": "French Guiana",
    "GG": "Guernsey",
    "GH": "Ghana",
    "GI": "Gibraltar",
    "GL": "Greenland",
    "GM": "Gambia (the)",
    "GN": "Guinea",
    "GP": "Guadeloupe",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "GS": "South Georgia and the South Sandwich Islands",
    "GT": "Guatemala",
    "GU": "Guam",
    "GW": "Guinea-Bissau",
    "GY": "Guyana",
    "HK": "Hong Kong",
    "HM": "Heard Island and McDonald Islands",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IM": "Isle of Man",
    "IN": "India",
    "IO": "British Indian Ocean Territory (the)",
    "IQ": "Iraq",
    "IR": "Iran (Islamic Republic of)",
    "IS": "Iceland",
    "IT": "Italy",
    "JE": "Jersey",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KI": "Kiribati",
    "KM": "Comoros (the)",
    "KN": "Saint Kitts and Nevis",
    "KP": "Korea (the Democratic People's Republic of)",
    "KR": "Korea (the Republic of)",
    "KW": "Kuwait",
    "KY": "Cayman Islands (the)",
    "KZ": "Kazakhstan",
    "LA": "Lao People's Democratic Republic (the)",
    "LB": "Lebanon",
    "LC": "Saint Lucia",
    "LI": "Liechtenstein",
    "LK": "Sri Lanka",
    "LR": "Liberia",
    "LS": "Lesotho",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova (the Republic of)",
    "ME": "Montenegro",
    "MF": "Saint Martin (French part)",
    "MG": "Madagascar",
    "MH": "Marshall Islands (the)",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MO": "Macao",
    "MP": "Northern Mariana Islands (the)",
    "MQ": "Martinique",
    "MR": "Mauritania",
    "MS": "Montserrat",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NC": "New Caledonia",
    "NE": "Niger (the)",
    "NF": "Norfolk Island",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands (Kingdom of the)",
    "NO": "Norway",
    "NP": "Nepal",
    "NR": "Nauru",
    "NU": "Niue",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PF": "French Polynesia",
    "PG": "Papua New Guinea",
    "PH": "Philippines (the)",
    "PK": "Pakistan",
    "PL": "Poland",
    "PM": "Saint Pierre and Miquelon",
    "PN": "Pitcairn",
    "PR": "Puerto Rico",
    "PS": "Palestine, State of",
    "PT": "Portugal",
    "PW": "Palau",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RE": "R\u00e9union",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russian Federation (the)",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan (the)",
    "SE": "Sweden",
    "SG": "Singapore",
    "SH": "Saint Helena, Ascension and Tristan da Cunha",
    "SI": "Slovenia",
    "SJ": "Svalbard and Jan Mayen",
    "SK": "Slovakia",
    "SL": "Sierra Leone",
    "SM": "San Marino",
    "SN": "Senegal",
    "SO": "Somalia",
    "SR": "Suriname",
    "SS": "South Sudan",
    "ST": "Sao Tome and Principe",
    "SV": "El Salvador",
    "SX": "Sint Maarten (Dutch part)",
    "SY": "Syrian Arab Republic (the)",
    "SZ": "Eswatini",
    "TC": "Turks and Caicos Islands (the)",
    "TD": "Chad",
    "TF": "French Southern Territories (the)",
    "TG": "Togo",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TK": "Tokelau",
    "TL": "Timor-Leste",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "T\u00fcrkiye",
    "TT": "Trinidad and Tobago",
    "TV": "Tuvalu",
    "TW": "Taiwan (Province of China)",
    "TZ": "Tanzania, the United Republic of",
    "UA": "Ukraine",
    "UG": "Uganda",
    "UM": "United States Minor Outlying Islands (the)",
    "US": "United States of America (the)",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VA": "Holy See (the)",
    "VC": "Saint Vincent and the Grenadines",
    "VE": "Venezuela (Bolivarian Republic of)",
    "VG": "Virgin Islands (British)",
    "VI": "Virgin Islands (U.S.)",
    "VN": "Viet Nam",
    "VU": "Vanuatu",
    "WF": "Wallis and Futuna",
    "WS": "Samoa",
    "YE": "Yemen",
    "YT": "Mayotte",
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}

OVERTON_COUNTRY_DISPLAY: dict[str, str] = {
    "AD": "Andorra",
    "AE": "United Arab Emirates",
    "AF": "Afghanistan",
    "AL": "Albania",
    "AM": "Armenia",
    "AO": "Angola",
    "AR": "Argentina",
    "AT": "Austria",
    "AU": "Australia",
    "AZ": "Azerbaijan",
    "BA": "Bosnia and Herzegovina",
    "BB": "Barbados",
    "BD": "Bangladesh",
    "BE": "Belgium",
    "BF": "Burkina Faso",
    "BG": "Bulgaria",
    "BH": "Bahrain",
    "BI": "Burundi",
    "BJ": "Benin",
    "BN": "Brunei",
    "BO": "Bolivia",
    "BR": "Brazil",
    "BS": "Bahamas",
    "BT": "Bhutan",
    "BW": "Botswana",
    "BY": "Belarus",
    "BZ": "Belize",
    "CA": "Canada",
    "CF": "Central African Republic",
    "CH": "Switzerland",
    "CI": "Ivory Coast",
    "CL": "Chile",
    "CM": "Cameroon",
    "CN": "China",
    "CO": "Colombia",
    "CR": "Costa Rica",
    "CU": "Cuba",
    "CV": "Cape Verde",
    "CY": "Cyprus",
    "CZ": "Czech Republic",
    "DE": "Germany",
    "DJ": "Djibouti",
    "DK": "Denmark",
    "DO": "Dominican Republic",
    "DZ": "Algeria",
    "EC": "Ecuador",
    "EE": "Estonia",
    "EG": "Egypt",
    "ER": "Eritrea",
    "ES": "Spain",
    "ET": "Ethiopia",
    "FI": "Finland",
    "FJ": "Fiji",
    "FM": "Micronesia",
    "FR": "France",
    "GB": "UK",
    "GE": "Georgia",
    "GH": "Ghana",
    "GM": "Gambia",
    "GN": "Guinea",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "GT": "Guatemala",
    "GY": "Guyana",
    "HN": "Honduras",
    "HR": "Croatia",
    "HT": "Haiti",
    "HU": "Hungary",
    "ID": "Indonesia",
    "IE": "Ireland",
    "IL": "Israel",
    "IN": "India",
    "IQ": "Iraq",
    "IR": "Iran",
    "IS": "Iceland",
    "IT": "Italy",
    "JM": "Jamaica",
    "JO": "Jordan",
    "JP": "Japan",
    "KE": "Kenya",
    "KG": "Kyrgyzstan",
    "KH": "Cambodia",
    "KI": "Kiribati",
    "KM": "Comoros",
    "KN": "Saint Kitts and Nevis",
    "KP": "North Korea",
    "KR": "South Korea",
    "KW": "Kuwait",
    "KZ": "Kazakhstan",
    "LA": "Laos",
    "LB": "Lebanon",
    "LI": "Liechtenstein",
    "LK": "Sri Lanka",
    "LR": "Liberia",
    "LS": "Lesotho",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "LY": "Libya",
    "MA": "Morocco",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MG": "Madagascar",
    "MH": "Marshall Islands",
    "MK": "North Macedonia",
    "ML": "Mali",
    "MM": "Myanmar",
    "MN": "Mongolia",
    "MR": "Mauritania",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "MW": "Malawi",
    "MX": "Mexico",
    "MY": "Malaysia",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NE": "Niger",
    "NG": "Nigeria",
    "NI": "Nicaragua",
    "NL": "Netherlands",
    "NO": "Norway",
    "NP": "Nepal",
    "NR": "Nauru",
    "NZ": "New Zealand",
    "OM": "Oman",
    "PA": "Panama",
    "PE": "Peru",
    "PG": "Papua New Guinea",
    "PH": "Philippines",
    "PK": "Pakistan",
    "PL": "Poland",
    "PS": "Palestine",
    "PT": "Portugal",
    "PW": "Palau",
    "PY": "Paraguay",
    "QA": "Qatar",
    "RO": "Romania",
    "RS": "Serbia",
    "RU": "Russia",
    "RW": "Rwanda",
    "SA": "Saudi Arabia",
    "SB": "Solomon Islands",
    "SC": "Seychelles",
    "SD": "Sudan",
    "SE": "Sweden",
    "SG": "Singapore",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SL": "Sierra Leone",
    "SM": "San Marino",
    "SN": "Senegal",
    "SO": "Somalia",
    "SR": "Suriname",
    "SS": "South Sudan",
    "ST": "Sao Tome and Principe",
    "SV": "El Salvador",
    "SY": "Syria",
    "SZ": "Eswatini",
    "TD": "Chad",
    "TG": "Togo",
    "TH": "Thailand",
    "TJ": "Tajikistan",
    "TM": "Turkmenistan",
    "TN": "Tunisia",
    "TO": "Tonga",
    "TR": "Turkey",
    "TT": "Trinidad and Tobago",
    "TV": "Tuvalu",
    "TW": "Taiwan",
    "TZ": "Tanzania",
    "UA": "Ukraine",
    "UG": "Uganda",
    "US": "USA",
    "UY": "Uruguay",
    "UZ": "Uzbekistan",
    "VA": "Vatican City",
    "VE": "Venezuela",
    "VN": "Vietnam",
    "VU": "Vanuatu",
    "WS": "Samoa",
    "YE": "Yemen",
    "ZA": "South Africa",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
}
OVERTON_DISPLAY_ALLOWLIST: frozenset[str] = frozenset(OVERTON_COUNTRY_DISPLAY.values())

TIER1_GROUPS: dict[str, tuple[str, ...]] = {
    "OECD members": (
        "AT", "AU", "BE", "CA", "CH", "CL", "CO", "CR", "CZ", "DE", "DK", "EE",
        "ES", "FI", "FR", "GB", "GR", "HU", "IE", "IL", "IS", "IT", "JP", "KR",
        "LT", "LU", "LV", "MX", "NL", "NO", "NZ", "PL", "PT", "SE", "SI", "SK",
        "TR", "US",
    ),
    "G7": ("CA", "DE", "FR", "GB", "IT", "JP", "US"),
    "G20": (
        "AR", "AU", "BR", "CA", "CN", "DE", "FR", "GB", "ID", "IN", "IT", "JP",
        "KR", "MX", "RU", "SA", "TR", "US", "ZA",
    ),
    "EU27": (
        "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
        "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO",
        "SE", "SI", "SK",
    ),
    "EEA": (
        "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR",
        "HR", "HU", "IE", "IS", "IT", "LI", "LT", "LU", "LV", "MT", "NL", "NO",
        "PL", "PT", "RO", "SE", "SI", "SK",
    ),
    "Europe": (
        "AD", "AL", "AT", "AX", "BA", "BE", "BG", "BY", "CH", "CZ", "DE", "DK",
        "EE", "ES", "FI", "FO", "FR", "GB", "GG", "GI", "GR", "HR", "HU", "IE",
        "IM", "IS", "IT", "JE", "LI", "LT", "LU", "LV", "MC", "MD", "ME", "MK",
        "MT", "NL", "NO", "PL", "PT", "RO", "RS", "RU", "SE", "SI", "SJ", "SK",
        "SM", "UA", "VA",
    ),
    "North America": (
        "AG", "AI", "AW", "BB", "BL", "BM", "BQ", "BS", "BZ", "CA", "CR", "CU",
        "CW", "DM", "DO", "GD", "GL", "GP", "GT", "HN", "HT", "JM", "KN", "KY",
        "LC", "MF", "MQ", "MS", "MX", "NI", "PA", "PM", "PR", "SV", "SX", "TC",
        "TT", "US", "VC", "VG", "VI",
    ),
    "Oceania": (
        "AS", "AU", "CC", "CK", "CX", "FJ", "FM", "GU", "HM", "KI", "MH", "MP",
        "NC", "NF", "NR", "NU", "NZ", "PF", "PG", "PN", "PW", "SB", "TK", "TO",
        "TV", "UM", "VU", "WF", "WS",
    ),
}

OVERTON_COUNTRY_HINTS: dict[str, str] = {
    "GB": "UK",
    "UK": "UK",
    "United Kingdom": "UK",
    "United Kingdom of Great Britain and Northern Ireland": "UK",
    "US": "USA",
    "USA": "USA",
    "United States": "USA",
    "United States of America": "USA",
}


def validate_iso_alpha2(codes: Iterable[str]) -> list[str]:
    """Validate and normalise ISO-3166 alpha-2 country codes.

    Args:
        codes: Candidate country codes.

    Returns:
        The validated codes, normalised to upper-case and preserving order.

    Raises:
        SearchDirectiveError: If the list is empty, malformed, duplicated, or
            contains a code outside ``ISO_3166_ALPHA2``.
    """
    if isinstance(codes, str):
        raise SearchDirectiveError("country codes must be a non-empty list")
    normalised: list[str] = []
    seen: set[str] = set()
    for code in codes:
        if not isinstance(code, str):
            raise SearchDirectiveError("country codes must contain strings")
        candidate = code.upper()
        if len(candidate) != 2 or not candidate.isalpha():
            raise SearchDirectiveError("country codes must be 2-letter alphabetic codes")
        if candidate not in ISO_3166_ALPHA2:
            raise SearchDirectiveError(f"unknown ISO-3166 alpha-2 country code: {candidate}")
        if candidate in seen:
            raise SearchDirectiveError("country codes must not contain duplicates")
        seen.add(candidate)
        normalised.append(candidate)
    if not normalised:
        raise SearchDirectiveError("country codes must be a non-empty list")
    return normalised


def expand_tier1(label: str) -> tuple[str, ...]:
    """Expand a pinned Tier-1 group label to its deterministic member codes.

    Args:
        label: Pinned country-group label.

    Returns:
        The group's sorted ISO-3166 alpha-2 member tuple.

    Raises:
        SearchDirectiveError: If ``label`` is not a pinned Tier-1 group.
    """
    try:
        return TIER1_GROUPS[label]
    except KeyError as exc:
        raise SearchDirectiveError(f"unknown Tier-1 country group: {label}") from exc


def overton_display_names(iso_codes: Iterable[str]) -> set[str]:
    """Map ISO codes to Overton-accepted display names.

    Unmapped valid ISO codes are skipped: the OpenAlex leg can still filter
    them, while Overton post-filter matching only uses names proven accepted by
    the 2026-07-12 probe.

    Args:
        iso_codes: Candidate country codes.

    Returns:
        A set of Overton display names accepted by ``source_country``.

    Raises:
        SearchDirectiveError: If any code is not a valid ISO-3166 alpha-2 code.
    """
    valid_codes = validate_iso_alpha2(iso_codes)
    return {
        OVERTON_COUNTRY_DISPLAY[code]
        for code in valid_codes
        if code in OVERTON_COUNTRY_DISPLAY
    }


def validate_overton_display_name(value: str, *, field_name: str) -> str:
    """Validate a single Overton display-country value against the probe allowlist.

    Args:
        value: Candidate Overton display country.
        field_name: Name to use in error messages.

    Returns:
        The validated display country.

    Raises:
        SearchDirectiveError: If the value was not accepted by the Overton probe.
    """
    if value not in OVERTON_DISPLAY_ALLOWLIST:
        hint = OVERTON_COUNTRY_HINTS.get(value)
        suffix = f"; use {hint!r}" if hint is not None else ""
        raise SearchDirectiveError(
            f"{field_name} must be an Overton-supported display country{suffix}"
        )
    return value
