"""The word tokeniser shared by chunk retrieval and the embedding writer (task 057).

Retrieval scores a passage partly by word overlap: the share of the query's words
that also appear in the passage. This module holds the one rule that turns text
into those words, so the retriever (``evidence_search``) and the embedding writer
(``core.embeddings``, which stores each passage's words in
``chunk_embedding.tokens``) cannot drift apart. It lives in ``core`` because
``core`` must not import ``evidence_search``.

The rule: a word is a run of ASCII letters and digits (``[0-9A-Za-z]+``) found in
the original text, then lower-cased. Every other character, including accented
and other non-ASCII letters, separates words and is never part of one. Matching
happens before lower-casing on purpose: a few non-ASCII characters lower-case to
ASCII letters (the Kelvin sign ``K`` becomes ``k``), and lower-casing first would
turn them into words. The migration that backfills ``chunk_embedding.tokens``
(revision ``b7e2c4a9d1f3``) runs the same rule in SQL, and a test checks the two
agree.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[0-9A-Za-z]+")


def word_tokens(text: str) -> set[str]:
    """Return the set of distinct lower-cased words in ``text``.

    Args:
        text: Any text, such as a search query or a passage.

    Returns:
        The distinct words: runs of ASCII letters and digits, lower-cased. An
        empty set when the text has none.
    """
    # Every match is ASCII, so casefold() and lower() give the same result.
    return {match.group(0).casefold() for match in _WORD_RE.finditer(text)}
