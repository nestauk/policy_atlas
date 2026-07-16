"""Input-side bounds for untrusted text entering product prompts (task 014).

The first product LLM reads of acquired third-party text (contract decision 7,
M10): every provider-derived field crosses into a prompt only through
``sanitize_prompt_field`` — length-capped and control-character-stripped at
prompt assembly. The caps are generous enough never to bite legitimate
envelopes; they bound adversarial payloads, not content.

Also hosts the wire-output hygiene shared by both LLM backends (NUL scrub,
confidence range) so the two seams cannot silently diverge.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from policy_atlas.core.tags import has_control_character

# Reason strings on both wire models (screen reps, classify) — the
# select-rerank bound (contract decision 3, rev 1.2).
REASON_MAX = 240

# Shared bound for Family B guidance channels (024 steering surface):
# search.guidance, grouping.guidance, characterise.guidance all carry this
# shape — a bounded list of user-intent sentences. Hoisted here (rather than
# duplicated per component) because all three parsers need byte-identical
# fail-closed semantics: anything outside the shape rejects, never truncates
# or silently drops.
GUIDANCE_MAX_ITEMS = 5


def metadata_dict(raw: Any) -> dict[str, Any]:
    """Coerce a stored envelope metadata column to a plain dict.

    Shared by every reader of the acquired-envelope ``metadata``/``payload``
    column (screen, classify, search_loop): non-dict storage (``None`` or a
    malformed row) degrades to empty rather than raising.

    Args:
        raw: Stored column value, expected to be a dict but not guaranteed.
    """
    return dict(raw) if isinstance(raw, dict) else {}


def sanitize_prompt_field(value: str, *, max_chars: int) -> str:
    """Cap and strip one untrusted field for prompt assembly.

    Strips every Unicode C-category (control/format) character except newline
    (legitimate in abstracts and full text; ``\\r\\n`` normalises to ``\\n``),
    then truncates to ``max_chars``.

    Args:
        value: Untrusted provider-derived text.
        max_chars: Hard cap applied after stripping.

    Returns:
        The sanitized field value.
    """
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    stripped = "".join(
        char
        for char in normalized
        if char == "\n" or not unicodedata.category(char).startswith("C")
    )
    return stripped[:max_chars]


def parse_guidance_channel(
    raw: Any,
    *,
    error: type[Exception],
    max_chars: int,
) -> list[str]:
    """Parse one Family B guidance channel, fail-closed.

    Shared shape (024 steering surface): a list of 1 to ``GUIDANCE_MAX_ITEMS``
    non-empty user-intent sentences, each at most ``max_chars`` characters and
    free of control characters. Anything outside this shape rejects — never
    truncated, never silently dropped.

    Args:
        raw: The raw ``guidance`` value from a component directive.
        error: Exception type raised for this component's directive grammar
            (e.g. ``SearchDirectiveError``, ``FacetDirectiveError``).
        max_chars: Maximum characters per guidance entry (``DIRECTIVE_STRING_MAX``).

    Returns:
        The validated guidance list, in order.

    Raises:
        error: If ``raw`` is not a list of 1 to ``GUIDANCE_MAX_ITEMS`` bounded,
            non-empty, control-character-free strings.
    """
    if not isinstance(raw, list) or not (1 <= len(raw) <= GUIDANCE_MAX_ITEMS):
        raise error(f"guidance must be a list of 1 to {GUIDANCE_MAX_ITEMS} strings")
    guidance: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise error("guidance entries must be non-empty strings")
        if len(item) > max_chars:
            raise error(f"guidance entries must be at most {max_chars} characters")
        if has_control_character(item):
            raise error("guidance entries must not contain control characters")
        guidance.append(item)
    return guidance


def scrub_nul(value: str) -> str:
    """Strip NUL bytes from one model-returned string (backend boundary)."""
    return value.replace("\x00", "")


def confidence_is_valid(confidence: float) -> bool:
    """Whether a model-returned confidence is in the persistable [0, 1] range."""
    return 0.0 <= confidence <= 1.0


def clamp_reason(reason: str) -> str:
    """Bound an untrusted model ``reason`` for event-payload/trace recording.

    Reasons are display-only (never a decision surface, never a column), so an
    overlong reason truncates rather than failing the call — failing a screen
    rep over auxiliary text would spend quorum for nothing.

    Args:
        reason: The model-returned reason string.

    Returns:
        The reason stripped of control characters and capped at ``REASON_MAX``.
    """
    return sanitize_prompt_field(reason.replace("\n", " ").strip(), max_chars=REASON_MAX)
