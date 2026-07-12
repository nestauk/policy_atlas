"""Helpers for reading old and profile-shaped extraction roll-ups.

Phase B writes extraction roll-ups keyed by extraction profile. Existing
downstream readers still consume IOF findings only, so these helpers project
new rows onto the IOF profile while leaving old flat rows unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from policy_atlas.extraction_records import PROFILE_ID as IOF_PROFILE_ID


def extraction_profile_counts(
    counts: Mapping[str, Any], profile_id: str = IOF_PROFILE_ID
) -> dict[str, Any]:
    """Return one profile's counts, or the old flat counts object.

    Args:
        counts: Stored ``extraction_result.counts`` or component summary counts.
        profile_id: Extraction profile id to project from a new-shaped row.

    Returns:
        Profile-local counts for new rows — with the shared doc-level keys
        (``selected``, ``basis``) merged in, so the projection reads like an
        old flat object; a copy of the flat object for old rows.
    """
    profiles = counts.get("profiles")
    if isinstance(profiles, Mapping):
        block = profiles.get(profile_id)
        projected = dict(block) if isinstance(block, Mapping) else {}
        for shared_key in ("selected", "basis"):
            if shared_key in counts:
                projected[shared_key] = counts[shared_key]
        return projected
    return dict(counts)


def extraction_profile_docs(
    docs: Sequence[Mapping[str, Any]], profile_id: str = IOF_PROFILE_ID
) -> list[dict[str, Any]]:
    """Return old-style document entries for one extraction profile.

    Args:
        docs: Stored ``extraction_result.docs``.
        profile_id: Extraction profile id to project from a new-shaped row.

    Returns:
        A list of document entries carrying ``pss_id``, ``basis`` and the
        profile-local outcome fields. Old flat entries are copied unchanged.
    """
    projected: list[dict[str, Any]] = []
    for doc in docs:
        profiles = doc.get("profiles")
        if not isinstance(profiles, Mapping):
            projected.append(dict(doc))
            continue
        block = profiles.get(profile_id)
        if not isinstance(block, Mapping):
            continue
        projected.append(
            {
                "pss_id": doc.get("pss_id"),
                "basis": doc.get("basis"),
                **cast("dict[str, Any]", dict(block)),
            }
        )
    return projected


def extraction_profile_provenance(
    provenance: Mapping[str, Any], profile_id: str = IOF_PROFILE_ID
) -> dict[str, Any]:
    """Return one profile's provenance, or the old flat provenance object.

    Args:
        provenance: Stored ``extraction_result.extraction_provenance``.
        profile_id: Extraction profile id to project from a new-shaped row.

    Returns:
        Profile-local provenance for new rows; a copy of the flat object for old rows.
    """
    profiles = provenance.get("profiles")
    if isinstance(profiles, Mapping):
        block = profiles.get(profile_id)
        return dict(block) if isinstance(block, Mapping) else {}
    return dict(provenance)
