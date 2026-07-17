"""Pure tests for extraction profile/refresh directive parsing."""

from __future__ import annotations

import pytest

from policy_atlas.evidence_base.extract.extract import (
    EXTRACTION_REFRESH_VALUES,
    KNOWN_PROFILE_IDS,
    ExtractError,
    _parse_extraction_directive,
)

IOF_PROFILE_ID, ICF_PROFILE_ID = KNOWN_PROFILE_IDS


def test_extraction_directive_defaults_to_iof_only_when_absent() -> None:
    assert _parse_extraction_directive(None) == ((IOF_PROFILE_ID,), None)
    assert _parse_extraction_directive({}) == ((IOF_PROFILE_ID,), None)


def test_extraction_directive_canonicalises_profile_order() -> None:
    assert _parse_extraction_directive(
        {"profiles": [ICF_PROFILE_ID, IOF_PROFILE_ID]}
    ) == ((IOF_PROFILE_ID, ICF_PROFILE_ID), None)


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ({"profiles": []}, "must not be empty"),
        ({"profiles": ["not-a-profile"]}, "not-a-profile"),
        ({"profiles": [IOF_PROFILE_ID, IOF_PROFILE_ID]}, "duplicate"),
        ({"profiles": [ICF_PROFILE_ID]}, "must include"),
        ({"bogus": True}, "unknown keys"),
    ],
)
def test_extraction_directive_rejects_malformed_profiles(
    raw: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ExtractError, match=match):
        _parse_extraction_directive(raw)


# --- D3 refresh: fail-closed matrix ---


@pytest.mark.parametrize("refresh", EXTRACTION_REFRESH_VALUES)
def test_extraction_directive_accepts_valid_refresh(refresh: str) -> None:
    assert _parse_extraction_directive({"refresh": refresh}) == ((IOF_PROFILE_ID,), refresh)


def test_extraction_directive_refresh_alongside_profiles() -> None:
    assert _parse_extraction_directive(
        {"profiles": [IOF_PROFILE_ID, ICF_PROFILE_ID], "refresh": "all"}
    ) == ((IOF_PROFILE_ID, ICF_PROFILE_ID), "all")


@pytest.mark.parametrize(
    "raw",
    [
        {"refresh": "everything"},
        {"refresh": 1},
        {"refresh": None},
        {"refresh": ["all"]},
    ],
)
def test_extraction_directive_rejects_malformed_refresh(raw: dict[str, object]) -> None:
    with pytest.raises(ExtractError, match="refresh"):
        _parse_extraction_directive(raw)
