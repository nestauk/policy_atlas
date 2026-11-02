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

# The modes are filled in by the lead from the measurement in
# experiments/cache-modes-per-site-2026-11-02 (task 056, N3). Until then every
# step stays "auto", the provider's default, so this table changes nothing.
# Keys are the route STEP names in model_routes.toml [steps]; the table must hold
# every step and nothing else. A step missing from the table is an error
# (cache_mode_for raises), never a silent default.
CACHE_MODES: dict[str, PromptCache] = {
    "classify_document": "auto",
    "screen_abstract": "auto",
    "screen_full": "auto",
    "select_rerank": "auto",
    "characterise_discover": "auto",
    "characterise_assign": "auto",
    "group_discover": "auto",
    "group_assign": "auto",
    "extract_iof_findings": "auto",
    "extract_icf_findings": "auto",
    "extract_interventions": "auto",
    "extract_vet_iof_findings": "auto",
    "extract_vet_icf_findings": "auto",
    "extract_annotate_relevance": "auto",
    "search_generate_queries": "auto",
    "search_reformulate": "auto",
    "search_suggest": "auto",
    "search_queries_v2_openalex": "auto",
    "search_queries_v2_overton": "auto",
    "search_reformulate_v2_openalex": "auto",
    "search_reformulate_v2_overton": "auto",
    "synthesise_propose_sections": "auto",
    "synthesise_write_block_summary": "auto",
    "synthesise_write_artefact_summary": "auto",
    "synthesise_judge_summary": "auto",
    "synthesise_section_turn": "auto",
    "synthesise_write_key_findings": "auto",
    "synthesise_write_case_studies": "auto",
    "synthesise_write_source_note": "auto",
    "synthesise_write_intro": "auto",
    "judge_grounding": "auto",
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
    "longlist_discover": "auto",
    "longlist_assign": "auto",
    "longlist_themes": "auto",
    "longlist_assign_themes": "auto",
    "longlist_type": "auto",
    "longlist_constrain": "auto",
    "longlist_distinct": "auto",
    "longlist_authority": "auto",
    "longlist_shortlist": "auto",
    "option_profile_line": "auto",
    "option_profile_potential_impact": "auto",
    "option_profile_ambition": "auto",
    "option_profile_setting": "auto",
    "option_profile_fold": "auto",
    "option_profile_place_sentences": "auto",
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
