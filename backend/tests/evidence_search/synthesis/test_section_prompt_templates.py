"""The template-keyed section writer (task 044, owner ruling 2026-09-09 — option 2).

One writer, one shared core, a preamble per output kind. The Evidence search
report's assembled prompt is pinned byte for byte to its current version
(``synthesise_section_v12``; it was ``v10`` before the split, and the words
changed once since, in task 058); the baseline preamble is the only other
template in this slice.
"""

from __future__ import annotations

import hashlib

import pytest

from policy_atlas.evidence_search.synthesis import section_prompt as sb
from policy_atlas.evidence_search.synthesis.baseline_prompt import BASELINE_SECTION_PREAMBLE

# sha256 of SECTION_SYSTEM_PROMPT as pinned for synthesise_section_v12 (task 058,
# 2026-11-05: the "How to work" bullet names write_section), with and without the
# v8 priority block. Recorded from the live module, not retyped. The v10 values
# (commit 91beec2a, before the split) were 87126525… and e38e6c1e….
_V12_SHA256 = "0a1ea1045eba7aeb5057a10b3dd15c3f95f6145e90b8e37eb3da690cbf3beafb"
_V12_WITH_PRIORITY_SHA256 = "ca63de3ab2c04ec5e44631aab3205b266ebcfa04b6a1709f4900188133911e41"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_section_system_prompt_report_is_byte_identical_to_v12() -> None:
    assert _sha(sb.SECTION_SYSTEM_PROMPT) == _V12_SHA256
    assert _sha(sb._section_system_prompt({})) == _V12_SHA256
    assert _sha(sb._section_system_prompt({"template": "report"})) == _V12_SHA256
    assert _sha(sb._section_system_prompt({"priority_block_active": True})) == (
        _V12_WITH_PRIORITY_SHA256
    )


def test_baseline_template_swaps_only_the_preamble() -> None:
    baseline = sb._section_system_prompt({"template": "baseline"})
    assert baseline == BASELINE_SECTION_PREAMBLE + sb.SECTION_CORE
    assert baseline.startswith("You are writing one section of a BASELINE")
    assert "evidence report" not in BASELINE_SECTION_PREAMBLE
    # The core is shared verbatim: every rule the report writer follows, the
    # baseline writer follows.
    assert sb.SECTION_CORE in sb.SECTION_SYSTEM_PROMPT
    assert sb.SECTION_PREAMBLES.keys() == {"report", "baseline"}


def test_unknown_template_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown synthesis template"):
        sb._section_system_prompt({"template": "profile"})
