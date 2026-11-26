"""Invite-code generation and normalisation."""

from __future__ import annotations

import pytest

from policy_atlas.core.invite_code import ALPHABET, CODE_LENGTH, display, new_code, normalise


def test_new_code_is_twelve_alphabet_characters_and_codes_differ() -> None:
    first, second = new_code(), new_code()
    assert len(first) == CODE_LENGTH
    assert set(first) <= set(ALPHABET)
    assert first != second
    assert normalise(display(first)) == first


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abcd-efgh-jkmn", "ABCDEFGHJKMN"),
        (" ABCD EFGH JKMN ", "ABCDEFGHJKMN"),
        ("ABCDEFGHJKMN", "ABCDEFGHJKMN"),
        (None, None),
        ("", None),
        ("ABCD-EFGH-JKM", None),
        ("ABCD-EFGH-JKMNP", None),
        ("ABCD-EFGH-JKM0", None),
        ("ABCD-EFGH-JKMI", None),
        ("ABCD_EFGH_JKMN", None),
    ],
)
def test_normalise_keeps_only_a_well_formed_code(raw: str | None, expected: str | None) -> None:
    assert normalise(raw) == expected
