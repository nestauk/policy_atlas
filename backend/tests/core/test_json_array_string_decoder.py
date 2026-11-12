"""The string-array decoder hands back each string of one array as it closes (task 054)."""

from __future__ import annotations

import json

from policy_atlas.core.openai_client import JsonArrayStringDecoder


def _feed(text: str, size: int, field: str = "items") -> tuple[list[list[str]], bool]:
    decoder = JsonArrayStringDecoder(field)
    pieces = [decoder.feed(text[at : at + size]) for at in range(0, len(text), size)]
    return pieces, decoder.done


def test_each_string_comes_back_decoded_as_it_closes_in_any_piece_size() -> None:
    items = ["One [1].", 'Two "quoted" \\ ] , [', "café \U0001f600", "line\nbreak", ""]
    text = json.dumps({"before": ["no"], "items": items, "after": ["no"]})
    for size in (1, 2, 5, 64, len(text)):
        pieces, done = _feed(text, size)
        assert [item for piece in pieces for item in piece] == items
        assert done


def test_a_string_is_returned_in_the_piece_that_closes_it() -> None:
    pieces, _ = _feed('{"items": ["ab', 100)
    assert pieces == [[]]
    decoder = JsonArrayStringDecoder("items")
    assert decoder.feed('{"items": ["ab') == []
    assert decoder.feed('c", "d') == ["abc"]
    assert decoder.feed('"]}') == ["d"]
    assert decoder.done


def test_only_the_top_level_key_counts() -> None:
    text = json.dumps(
        {
            "nested": {"items": ["deeper"]},
            "note": 'has "items": ["fake"] inside',
            "items": ["real"],
        }
    )
    pieces, done = _feed(text, 3)
    assert [item for piece in pieces for item in piece] == ["real"] and done


def test_an_empty_array_closes_with_nothing() -> None:
    pieces, done = _feed('{"items": [], "z": 1}', 4)
    assert pieces and all(piece == [] for piece in pieces) and done


def test_a_missing_field_never_closes() -> None:
    pieces, done = _feed('{"other": ["x"]}', 4)
    assert all(piece == [] for piece in pieces) and not done
