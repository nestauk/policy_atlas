"""The lever-type taxonomy — one versioned list for every domain (task 045, D8).

A lever type names the instrument the state uses, never the subject, which
is what makes one list serve every policy domain and what fixes the
shortlist's coverage denominator (task 3). Each option carries one primary
type from this list, or *none fits* with a reason (counted and shown so the
list can be revised on evidence); every option records the version it was
typed under. The list is a Python constant, not prompt-internal text
(closes OS open question 5). "Lever family" never appears user-facing.

The ten entries are ruling 11's curated list as the 035 feasibility check
ran it (check 3), with the definitions the typing prompt renders as data.

v2 (task 046, item 7): "provide a service" is direct delivery by the state;
funding a provider is "subsidise"; buying from a provider is "procure or
commission". The keys are unchanged. v1 stays as :data:`LEVER_TYPES_V1`, so
the page can show an option typed under v1 with v1's definitions (AM19).
"""

from __future__ import annotations

from dataclasses import dataclass

TAXONOMY_VERSION = "lever_types_v2"
TAXONOMY_VERSION_V1 = "lever_types_v1"


@dataclass(frozen=True)
class LeverType:
    """One lever type.

    Attributes:
        key: The stored value and the label the prompts copy exactly.
        definition: One line saying how the state acts under this type.
    """

    key: str
    definition: str


# Frontend coupling: the keys below are mirrored by hand in
# frontend/src/views/longlist/longlistPresentation.ts (`leverNoun`, the noun
# a theme heading uses per lever type) and in frontend/src/mock/fixtures.ts
# (`mockLonglist`). The definitions reach the page through the longlist read
# model (`lever_type_definitions`), so only the keys need a matching edit
# there when this list changes.
LEVER_TYPES_V1: tuple[LeverType, ...] = (
    LeverType(
        "regulate",
        "set or change rules, standards, bans, licensing or planning requirements",
    ),
    LeverType(
        "subsidise",
        "pay for, grant-fund, discount or otherwise lower the price of something "
        "for people or providers",
    ),
    LeverType(
        "tax or charge",
        "raise the price of something through a tax, levy, fee or charge",
    ),
    LeverType(
        "inform",
        "give information, advice, campaigns, labelling or guidance to change behaviour",
    ),
    LeverType(
        "provide a service",
        "deliver or fund a service or programme directly to people (a scheme, a "
        "programme, a facility)",
    ),
    LeverType(
        "enforce existing powers",
        "apply, inspect or enforce rules and duties that already exist",
    ),
    LeverType(
        "devolve",
        "move a decision, budget or power to a lower tier of government or a local body",
    ),
    LeverType(
        "change who runs the system",
        "reorganise institutions, commissioning, ownership or accountability for a service",
    ),
    LeverType(
        "build or change infrastructure",
        "create or alter physical environments, routes, facilities or estates",
    ),
    LeverType(
        "procure or commission",
        "use public purchasing or commissioning rules to change what is bought or from whom",
    ),
)

LEVER_TYPES: tuple[LeverType, ...] = (
    LeverType(
        "regulate",
        "set or change rules, standards, bans, licensing or planning requirements",
    ),
    LeverType(
        "subsidise",
        "pay for, grant-fund, discount or otherwise lower the price of something "
        "for people, or fund a provider to deliver it",
    ),
    LeverType(
        "tax or charge",
        "raise the price of something through a tax, levy, fee or charge",
    ),
    LeverType(
        "inform",
        "give information, advice, campaigns, labelling or guidance to change behaviour",
    ),
    LeverType(
        "provide a service",
        "deliver a service or programme to people directly, by the state's own "
        "bodies and staff (a public service, a facility, a scheme run by a public body)",
    ),
    LeverType(
        "enforce existing powers",
        "apply, inspect or enforce rules and duties that already exist",
    ),
    LeverType(
        "devolve",
        "move a decision, budget or power to a lower tier of government or a local body",
    ),
    LeverType(
        "change who runs the system",
        "reorganise institutions, commissioning, ownership or accountability for a service",
    ),
    LeverType(
        "build or change infrastructure",
        "create or alter physical environments, routes, facilities or estates",
    ),
    LeverType(
        "procure or commission",
        "buy a service or goods from a provider, or use public purchasing or "
        "commissioning rules to change what is bought or from whom",
    ),
)

LEVER_TYPE_KEYS: tuple[str, ...] = tuple(lever.key for lever in LEVER_TYPES)

def lever_types_by_version() -> dict[str, tuple[LeverType, ...]]:
    """Every taxonomy version an option can carry, with its list.

    Returns:
        ``{version: lever types}``, the current version first.
    """
    return {TAXONOMY_VERSION: LEVER_TYPES, TAXONOMY_VERSION_V1: LEVER_TYPES_V1}


def lever_types_as_data() -> list[dict[str, str]]:
    """Render the list for a prompt's data block.

    Returns:
        ``[{"key": ..., "definition": ...}, ...]`` in taxonomy order.
    """
    return [{"key": lever.key, "definition": lever.definition} for lever in LEVER_TYPES]
