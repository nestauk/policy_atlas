"""Generic ordered segment windowing helpers."""

from __future__ import annotations


def _split_oversize(
    segment_id: str,
    content: str,
    *,
    char_budget: int,
    oversize_overlap_chars: int,
) -> list[tuple[str, str]]:
    parts: list[tuple[str, str]] = []
    index = 0
    start = 0
    length = len(content)
    while start < length:
        parts.append((f"{segment_id}#p{index}", content[start : start + char_budget]))
        index += 1
        if start + char_budget >= length:
            break
        # max(1, ...) guards termination if overlap is configured at or above
        # the window budget. Extraction relies on this when tests shrink budgets.
        start = start + max(1, char_budget - oversize_overlap_chars)
    return parts


def greedy_windows(
    segments: list[tuple[str, str]],
    *,
    char_budget: int,
    overlap_segments: int,
    oversize_overlap_chars: int = 0,
) -> list[list[tuple[str, str]]]:
    """Build greedy ordered windows over text segments.

    Oversize segments are first split into deterministic ``#pN`` sub-segments
    using the same character-overlap policy as extraction. The window pass then
    packs segments in input order until adding the next segment would exceed
    ``char_budget``; adjacent windows repeat the requested number of trailing
    segments while still always making progress.

    Args:
        segments: Ordered ``(segment_id, content)`` pairs.
        char_budget: Maximum total character count per window.
        overlap_segments: Number of trailing segments to repeat in the next
            window.
        oversize_overlap_chars: Character overlap used when splitting a single
            segment longer than ``char_budget``.

    Returns:
        A list of ordered windows, each containing ``(segment_id, content)``
        pairs.

    Raises:
        ValueError: If a numeric parameter is outside its supported range.
    """
    if char_budget <= 0:
        raise ValueError("char_budget must be positive")
    if overlap_segments < 0:
        raise ValueError("overlap_segments must be non-negative")
    if oversize_overlap_chars < 0:
        raise ValueError("oversize_overlap_chars must be non-negative")

    split_segments: list[tuple[str, str]] = []
    for segment_id, content in segments:
        if len(content) <= char_budget:
            split_segments.append((segment_id, content))
        else:
            split_segments.extend(
                _split_oversize(
                    segment_id,
                    content,
                    char_budget=char_budget,
                    oversize_overlap_chars=oversize_overlap_chars,
                )
            )

    windows: list[list[tuple[str, str]]] = []
    i = 0
    n = len(split_segments)
    while i < n:
        window: list[tuple[str, str]] = []
        total = 0
        j = i
        while j < n:
            seg_len = len(split_segments[j][1])
            if window and total + seg_len > char_budget:
                break
            window.append(split_segments[j])
            total += seg_len
            j += 1
        windows.append(window)
        if j >= n:
            break
        i = max(j - overlap_segments, i + 1)
    return windows
