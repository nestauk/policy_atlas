"""The template-keyed section writer (task 044, owner ruling 2026-09-09 — option 2).

One writer, one shared core, a preamble per output kind. The Evidence search
report's assembled prompt must stay byte-identical to ``synthesise_section_v10``
as it was before the split; the baseline preamble is the only other template
in this slice.
"""

from __future__ import annotations

import hashlib

import pytest

from policy_atlas.evidence_search.synthesis import synthesis_backend as sb
from policy_atlas.evidence_search.synthesis.baseline_prompt import BASELINE_SECTION_PREAMBLE

# sha256 of SECTION_SYSTEM_PROMPT at commit 91beec2a (before the split), with and
# without the v8 priority block. Recorded from the live module, not retyped.
_V10_SHA256 = "87126525d75f0d49ba105a047fdb926e8534832bf612e1e6afa9784ec8c39a42"
_V10_WITH_PRIORITY_SHA256 = "e38e6c1e7c3448149e6fd177f2592725ed5d03d41d1c613eeaf58f07956f17fb"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_section_system_prompt_report_is_byte_identical_to_v10() -> None:
    assert _sha(sb.SECTION_SYSTEM_PROMPT) == _V10_SHA256
    assert _sha(sb._section_system_prompt({})) == _V10_SHA256
    assert _sha(sb._section_system_prompt({"template": "report"})) == _V10_SHA256
    assert _sha(sb._section_system_prompt({"priority_block_active": True})) == (
        _V10_WITH_PRIORITY_SHA256
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
