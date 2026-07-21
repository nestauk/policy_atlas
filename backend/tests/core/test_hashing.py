"""content_hash stability and normalisation."""

from policy_atlas.core.hashing import content_hash


def test_content_hash_stable() -> None:
    assert content_hash("hello world") == content_hash("hello world")


def test_content_hash_whitespace_insensitive() -> None:
    assert content_hash("hello  world") == content_hash("hello world")
