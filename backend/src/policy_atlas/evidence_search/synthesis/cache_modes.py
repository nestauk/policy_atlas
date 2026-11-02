"""Prompt-cache mode per model call site (task 056, contract D3).

What this is, in plain terms: the model provider can keep a copy of the start
(the "prefix") of a prompt it has just seen, so a later call that starts with the
same text is billed far more cheaply for that part. Storing the prefix costs extra
(25% on top of the normal input price), so it only pays off when the prefix really
does come back. Each call site (each route step in ``model_routes.toml``) gets one
of three modes, described on :data:`PromptCache`.

The type lives in ``core.openai_client`` (``core`` must not import
``evidence_search`` when it loads) and is re-exported here so callers have one
place to look.
"""

from __future__ import annotations

from policy_atlas.core.openai_client import PromptCache

__all__ = ["CACHE_MODES", "PromptCache", "cache_mode_for"]

# Picked by the lead on 2026-11-02 from the measurement in
# experiments/cache-modes-per-site-2026-11-02-tables.txt (task 056). The rule:
# one-shot sites (one request, no growing conversation) use "breakpoint", which
# stores and reuses only the system message, so it is never worse than "off" or
# "auto". Conversation sites (chat and the agent turns, where each request starts
# with the whole previous request) keep "auto".
# Keys are the route STEP names in model_routes.toml [steps]; the table must hold
# every step and nothing else. A step missing from the table is an error
# (cache_mode_for raises), never a silent default.
CACHE_MODES: dict[str, PromptCache] = {
    "classify_document": "breakpoint",
    "screen_abstract": "breakpoint",
    "screen_full": "breakpoint",
    "select_rerank": "breakpoint",
    "characterise_discover": "breakpoint",
    "characterise_assign": "breakpoint",
    "group_discover": "breakpoint",
    "group_assign": "breakpoint",
    "extract_iof_findings": "breakpoint",
    "extract_icf_findings": "breakpoint",
    "extract_interventions": "breakpoint",
    "extract_vet_iof_findings": "breakpoint",
    "extract_vet_icf_findings": "breakpoint",
    "extract_annotate_relevance": "breakpoint",
    "search_generate_queries": "breakpoint",
    "search_reformulate": "breakpoint",
    "search_suggest": "breakpoint",
    "search_queries_v2_openalex": "breakpoint",
    "search_queries_v2_overton": "breakpoint",
    "search_reformulate_v2_openalex": "breakpoint",
    "search_reformulate_v2_overton": "breakpoint",
    "synthesise_propose_sections": "breakpoint",
    "synthesise_write_block_summary": "breakpoint",
    "synthesise_write_artefact_summary": "breakpoint",
    "synthesise_judge_summary": "breakpoint",
    "synthesise_section_turn": "auto",
    "synthesise_write_key_findings": "breakpoint",
    "synthesise_write_case_studies": "breakpoint",
    "synthesise_write_source_note": "breakpoint",
    "synthesise_write_intro": "breakpoint",
    "judge_grounding": "breakpoint",
    "chat": "auto",
    "agent_route": "auto",
    "agent_triage": "auto",
    "agent_decide": "auto",
    "agent_gate_sort": "auto",
    "agent_longlist_sort": "auto",
    "agent_option_design": "auto",
    "agent_suggest": "auto",
    "task_agent_turn": "auto",
    "task_agent_scoping_turn": "auto",
    "longlist_discover": "breakpoint",
    "longlist_assign": "breakpoint",
    "longlist_themes": "breakpoint",
    "longlist_assign_themes": "breakpoint",
    "longlist_type": "breakpoint",
    "longlist_constrain": "breakpoint",
    "longlist_distinct": "breakpoint",
    "longlist_authority": "breakpoint",
    "longlist_shortlist": "breakpoint",
    "option_profile_line": "breakpoint",
    "option_profile_potential_impact": "breakpoint",
    "option_profile_ambition": "breakpoint",
    "option_profile_setting": "breakpoint",
    "option_profile_fold": "breakpoint",
    "option_profile_place_sentences": "breakpoint",
}


def cache_mode_for(step: str) -> PromptCache:
    """Return the prompt-cache mode for one route step.

    Args:
        step: A step name from the route file's ``[steps]`` table.

    Returns:
        The step's mode from :data:`CACHE_MODES`.

    Raises:
        RuntimeError: If the step has no entry in :data:`CACHE_MODES`.
    """
    if step not in CACHE_MODES:
        raise RuntimeError(f"cache_modes.CACHE_MODES has no entry for step {step!r}")
    return CACHE_MODES[step]
