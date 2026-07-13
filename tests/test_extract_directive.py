"""Pure tests for extraction profile directive parsing."""

from __future__ import annotations

import pytest

from policy_atlas.extract import (
    KNOWN_PROFILE_IDS,
    ExtractError,
    _parse_extraction_directive,
)

IOF_PROFILE_ID, ICF_PROFILE_ID = KNOWN_PROFILE_IDS


def test_extraction_directive_defaults_to_iof_only_when_absent() -> None:
    assert _parse_extraction_directive(None) == (IOF_PROFILE_ID,)
    assert _parse_extraction_directive({}) == (IOF_PROFILE_ID,)


def test_extraction_directive_canonicalises_profile_order() -> None:
    assert _parse_extraction_directive(
        {"profiles": [ICF_PROFILE_ID, IOF_PROFILE_ID]}
    ) == (IOF_PROFILE_ID, ICF_PROFILE_ID)


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ({"profiles": []}, "must not be empty"),
        ({"profiles": ["not-a-profile"]}, "not-a-profile"),
        ({"profiles": [IOF_PROFILE_ID, IOF_PROFILE_ID]}, "duplicate"),
        ({"profiles": [ICF_PROFILE_ID]}, "must include"),
    ],
)
def test_extraction_directive_rejects_malformed_profiles(
    raw: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ExtractError, match=match):
        _parse_extraction_directive(raw)
