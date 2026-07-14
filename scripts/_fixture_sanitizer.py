"""Shared fabrication primitives for the OpenAlex/Overton fixture recorders.

Not part of the runtime package — never imported by policy_atlas. Stdlib only.
Deterministic (sha256-seeded) so re-running ``--resanitize`` on the same raw
recording reproduces byte-identical fixtures.
"""

import hashlib

# Deliberately neutral fake words — nothing domain-flavoured, so fabricated text can
# never collide with (or be mistaken for) a real record's words.
LEXICON = (
    "quartz", "meadow", "lantern", "willow", "cobalt", "harbor", "juniper", "marble",
    "ember", "sable", "orchid", "pigment", "tundra", "velvet", "saffron", "timber",
    "glacier", "mosaic", "pewter", "sonnet", "tapestry", "vertex", "zephyr", "cedar",
    "delta", "onyx", "prairie", "quill",
)
FIRST = ("Alex", "Sam", "Jordan", "Robin", "Casey", "Morgan", "Jamie", "Drew")
LAST = ("Sampleton", "Fixture", "Placeholder", "Mockford", "Fablewood", "Stubbs")


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def fake_words(s: str) -> str:
    n = min(max(len(s.split()), 3), 12)
    digest = h("words:" + s)
    words = [LEXICON[int(digest[i * 2 : i * 2 + 2], 16) % len(LEXICON)] for i in range(n)]
    return " ".join(words).capitalize()


def fake_name(s: str) -> str:
    digest = h("name:" + s)
    return f"{FIRST[int(digest[:2], 16) % len(FIRST)]} {LAST[int(digest[2:4], 16) % len(LAST)]}"


def fake_doi(s: str) -> str:
    return "10.99999/" + h("doi:" + s)[:10]


def fake_url(s: str) -> str:
    suffix = ".pdf" if s.lower().endswith(".pdf") else ""
    return "https://example.org/" + h("url:" + s)[:12] + suffix
