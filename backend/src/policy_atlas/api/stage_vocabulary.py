"""The one source of run-progress copy: stage labels, blurbs, card rows, verbs, counts.

Task 058 (N17, D4): every word a run page shows about a stage comes from this
module. The client has no stage copy of its own; it renders the labels the
frames and the plan steps carry, the activity line a ``tick`` carries, and the
counts this table names. The voice is a short label, then one plain sentence
(owner, 2026-11-04).

Internal names must never leave the API: ``StageKey`` is the pinned contract
vocabulary (spec § SSE); labels and blurbs are presentation and may change.

This module is a leaf: it imports only the contract vocabulary, so the
runtime, the stage loops and the model-call wrapper may all import it.
"""

from __future__ import annotations

from typing import Any

from policy_atlas.api.contract import StageKey

#: ``(label, blurb)`` per public stage. Stages that share a card row (see
#: :data:`STAGE_ROW`) share the label: the row is what the user sees.
STAGE_PRESENTATION: dict[StageKey, tuple[str, str]] = {
    "acquire": ("Searching", "Querying the databases and collecting candidates."),
    "screen": ("Screening", "Reading each abstract against the question."),
    "classify": ("Classifying", "Labelling each source by its evidence type."),
    "appraise": ("Classifying", "Scoring how much weight each source can bear."),
    "ingest": (
        "Collecting the full texts",
        "Fetching each full text and making it searchable.",
    ),
    "characterise": ("Mapping", "What the evidence covers, and where it is thin."),
    "select": ("Shortlisting", "The strongest, most varied set for close reading."),
    "extract": ("Extracting findings", "Each finding is pulled out with its exact quote."),
    "group": ("Grouping findings", "Findings that answer the same question, together."),
    "synthesise": ("Writing", "A cited report, checked claim by claim."),
    "inherit": ("Reading the linked search", "Its documents and report join this task."),
    "suggest": ("Suggesting options", "From your plan, the baseline and any linked report."),
    "option_searches": ("Searching for each option", "One search per option."),
    "extract_interventions": ("Reading the abstracts", "Which interventions each source covers."),
    "longlist": (
        "Clustering into options",
        "Sources grouped into options. Options may be folded together or added.",
    ),
    "option_profile": (
        "Writing what each option would take",
        "Cost, time, workforce and who decides, for each option.",
    ),
    "constrain": ("Applying your constraints", "Each option checked against the plan's limits."),
    "theme": ("Grouping into themes", "Included options grouped into themes."),
    # Task 055 (PG3): its own key, so the Evidence search's "select" blurb (a
    # ranking claim) never describes the shortlist proposal.
    "shortlist": ("Shortlisting", "Proposing options for close reading."),
}

#: The card row each stage belongs to (D5, direction C). Stages with the same
#: row key render as one row: classify and appraise as "Classifying". Search
#: and screen are two rows again, "Searching" and "Screening" (owner round 8,
#: 2026-11-05). The client groups by this key and decides nothing about rows
#: itself.
STAGE_ROW: dict[StageKey, str] = {
    "acquire": "search",
    "screen": "screen",
    "classify": "categorise",
    "appraise": "categorise",
    "ingest": "ingest",
    "characterise": "characterise",
    "select": "select",
    "extract": "extract",
    "group": "group",
    "synthesise": "synthesise",
    "inherit": "inherit",
    "suggest": "suggest",
    "option_searches": "option_searches",
    "extract_interventions": "extract_interventions",
    "longlist": "longlist",
    "option_profile": "option_profile",
    "constrain": "constrain",
    "theme": "theme",
    "shortlist": "shortlist",
}

#: The ``stage.completed.summary`` keys a done row shows, in order, each with
#: its noun: ``312 found · 118 relevant``. Chosen per stage, not an allow-list
#: (N17); the loops guarantee each named key is a top-level integer.
STAGE_COUNTS: dict[StageKey, tuple[tuple[str, str], ...]] = {
    "acquire": (("acquired", "found"),),
    "screen": (("relevant", "relevant"),),
    "classify": (("classified", "classified"),),
    "appraise": (),
    "ingest": (("ingested", "collected"),),
    "characterise": (("theme_count", "themes"),),
    "select": (("selected_count", "selected"),),
    "extract": (("finding_count", "findings"),),
    "group": (("group_count", "groups"),),
    "synthesise": (("section_count", "sections"),),
    "inherit": (("documents", "documents"),),
    "suggest": (("suggested", "suggested"),),
    "option_searches": (("total", "searches"), ("sources", "sources")),
    "extract_interventions": (("documents", "abstracts"),),
    "longlist": (("options", "options"),),
    "option_profile": (("profiled", "profiled"),),
    "constrain": (("excluded", "excluded"),),
    "theme": (("themes", "themes"),),
    "shortlist": (("shortlisted", "shortlisted"),),
}

#: The plain verb shown while a model call of this route step is in flight and
#: the stage's loop has published no line of its own (N1). Keyed by the step
#: ids in ``model_routes.toml [steps]``; a test pins the coverage. Steps that
#: run outside a harness (chat, the agents) publish nothing; their verb is
#: here so the table is complete.
STEP_VERBS: dict[str, str] = {
    "classify_document": "Classifying",
    "screen_abstract": "Screening abstracts",
    "screen_full": "Reading full texts for relevance",
    "select_rerank": "Ranking sources",
    "characterise_discover": "Finding themes",
    "characterise_assign": "Assigning themes",
    "group_discover": "Finding groups",
    "group_assign": "Assigning findings to groups",
    "extract_iof_findings": "Extracting findings",
    "extract_icf_findings": "Extracting findings",
    "extract_interventions": "Reading abstracts for interventions",
    "extract_vet_iof_findings": "Checking findings",
    "extract_vet_icf_findings": "Checking findings",
    "extract_annotate_relevance": "Marking relevance",
    "search_generate_queries": "Writing search queries",
    "search_reformulate": "Rewriting search queries",
    "search_suggest": "Suggesting search queries",
    "search_queries_v2_openalex": "Writing search queries",
    "search_queries_v2_overton": "Writing search queries",
    "search_reformulate_v2_openalex": "Rewriting search queries",
    "search_reformulate_v2_overton": "Rewriting search queries",
    "synthesise_propose_sections": "Planning the sections",
    "synthesise_write_block_summary": "Summarising a section",
    "synthesise_write_artefact_summary": "Summarising the report",
    "synthesise_judge_summary": "Checking a summary",
    "synthesise_section_turn": "Writing",
    "synthesise_section_emit": "Writing",
    "synthesise_write_key_findings": "Writing the key findings",
    "synthesise_write_case_studies": "Writing the case studies",
    "synthesise_write_source_note": "Writing a source note",
    "synthesise_write_intro": "Writing the introduction",
    "judge_grounding": "Checking claims",
    "chat": "Answering",
    "agent_route": "Reading your reply",
    "agent_triage": "Deciding the next step",
    "agent_decide": "Deciding the next step",
    "agent_gate_sort": "Reading your answer",
    "agent_longlist_sort": "Reading your answer",
    "agent_option_design": "Designing the option",
    "agent_suggest": "Suggesting options",
    "task_agent_turn": "Drafting the plan",
    "task_agent_scoping_turn": "Drafting the plan",
    "longlist_discover": "Finding the options",
    "longlist_assign": "Assigning sources to options",
    "longlist_themes": "Finding themes",
    "longlist_assign_themes": "Assigning options to themes",
    "longlist_type": "Typing each option",
    "longlist_constrain": "Checking constraints",
    "longlist_distinct": "Checking the options are distinct",
    "longlist_authority": "Checking who can act",
    "longlist_shortlist": "Choosing the shortlist",
    "option_profile_line": "Writing profile lines",
    "option_profile_potential_impact": "Judging potential impact",
    "option_profile_ambition": "Judging ambition",
    "option_profile_setting": "Judging the setting",
    "option_profile_fold": "Folding duplicate options",
    "option_profile_place_sentences": "Writing place sentences",
}

#: Activity-line templates (N2, N3, N21). The loops format these with their
#: own counts and publish the result as the tick's ``activity``; the client
#: renders the string as it is. Field names are the ``str.format`` keys.
ACTIVITY: dict[str, str] = {
    # acquire and screen stage 1: no honest total, so a running count (N2;
    # "new" and "so far" dropped, owner round 9)
    "search.writing_queries": "Writing search queries",
    "acquire.searching": "searching · {found:,} found",
    "acquire.searching_again": "Search {pass_number} · {found:,} found",
    # round 9: the topic or semantic query out last, cut on a word
    "acquire.searching_query": "searching · {found:,} found · {query}",
    "acquire.searching_again_query": "Search {pass_number} · {found:,} found · {query}",
    # round 9: the passes that look works up by id
    "acquire.following": "following citations · {found:,} found",
    # round 9 (lead ruling): while the ranked pool is kept, counted against
    # the search's candidates, so the count never reads as a drop
    "acquire.keeping": "keeping {kept:,} of {found:,} candidates",
    "screen.abstracts": "screening {remaining:,} abstracts · {relevant:,} relevant",
    # round 9: how a citations or lookup pass is named in the search's query
    # list (``search.query``), never by its ids
    "search.citations_from": "Following citations from {count:,} sources",
    "search.citations_from_one": "Following citations from 1 source",
    "search.lookup_works": "Looking up {count:,} cited works",
    "search.lookup_works_one": "Looking up 1 cited work",
    "search.lookup_documents": "Looking up {count:,} cited documents",
    "search.lookup_documents_one": "Looking up 1 cited document",
    # round 11: the same passes once the search has ended, as the saved
    # coverage names them
    "search.citations_followed": "Followed citations from {count:,} sources",
    "search.citations_followed_one": "Followed citations from 1 source",
    "search.works_looked_up": "Looked up {count:,} cited works",
    "search.works_looked_up_one": "Looked up 1 cited work",
    "search.documents_looked_up": "Looked up {count:,} cited documents",
    "search.documents_looked_up_one": "Looked up 1 cited document",
    # loops with a known total: "n of M <unit>"
    "screen.full_texts": "reading {done} of {total} full texts for relevance",
    "classify.progress": "{done:,} of {total:,} classified",
    # owner round 9: the stage fetches and indexes; it does not read
    "ingest.progress": "collecting {done} of {total}",
    "extract.progress": "{done} of {total} read for findings",
    "extract_interventions.progress": "{done:,} of {total:,} abstracts read",
    # batch stages: "batch n of M" (N2)
    "select.batches": "Ranking sources · batch {done} of {total}",
    "characterise.batches": "Assigning themes · batch {done} of {total}",
    "group.batches": "Assigning findings · batch {done} of {total}",
    "longlist.clustering": "options may be folded together or added",
    "longlist.batches": "Assigning sources to options · batch {done} of {total}",
    "theme.batches": "Assigning options to themes · batch {done} of {total}",
    "constrain.batches": "Checking constraints · batch {done} of {total}",
    "option_profile.typing": "Typing options · batch {done} of {total}",
    "option_profile.places": "Writing place sentences · {done} of {total} options",
    # the option-search join loop (N21)
    "option_searches.progress": "{done} of {total} searches done · {sources:,} sources so far",
    # the writer (N3): the section line rides on ``tick.section``
    "synthesise.section": "Section {number} of {total} · {title}",
    "synthesise.looking_for": "Looking for: {query}",
    "synthesise.reading_findings": "Reading findings",
    "synthesise.looking_up": "Looking up sources",
    "synthesise.writing": "Writing",
    "synthesise.checking": "Checking claims",
    "synthesise.revising": "Revising {count} claim",
    "synthesise.revising_many": "Revising {count} claims",
    "synthesise.key_findings": "Writing the key findings",
    "synthesise.sources": "Listing the sources",
    "synthesise.case_studies": "Writing the case studies",
    "synthesise.source_note": "Writing a source note",
    # round 8: the note's source, by its short name ("Smith 2023")
    "synthesise.source_note_named": "Writing a source note · {name}",
    "synthesise.intro": "Writing the introduction",
    "synthesise.summaries": "Summarising the sections",
}


def activity(key: str, **fields: Any) -> str:
    """Return the formatted activity line for ``key``.

    Args:
        key: A :data:`ACTIVITY` key.
        **fields: The template's fields.

    Returns:
        The line the client shows, in the plain voice.
    """
    return ACTIVITY[key].format(**fields)


STAGE_BY_REGISTRY: dict[str, StageKey] = {
    "acquire": "acquire",
    "screen": "screen",
    "screen_full": "screen",
    "classify": "classify",
    "appraise": "appraise",
    "ingest_full_text": "ingest",
    "characterise": "characterise",
    "select": "select",
    "extract": "extract",
    "group": "group",
    "synthesise": "synthesise",
    "inherit": "inherit",
    "suggest": "suggest",
    "option_searches": "option_searches",
    "extract_interventions": "extract_interventions",
    "longlist": "longlist",
    "option_profile": "option_profile",
    "constrain": "constrain",
    "theme": "theme",
    "shortlist": "shortlist",
}


def stage_for_payload(payload: dict[str, Any]) -> StageKey | None:
    """Map a composed or registry component name onto a public stage key.

    The full-text screen (composed component ``screen_full``) emits no live
    stage frame: its progress shows as a line on the "Screening" row (task
    058, N2; its own row since owner round 8). The guard tests the composed ``component``,
    because the full-text screen's ``run.started`` payload carries
    ``registry_component = "screen"`` (the duplicate Screening row seen on
    staging and production, owner 2026-11-04).
    """
    from policy_atlas.runtime.steering import BASELINE_CONFIRM
    from policy_atlas.runtime.task_plan import canonical_steer_point, registry_component_for

    # The baseline gate's card is about the baseline, so its stage word is
    # stated here rather than inherited from the component name (task 044, P11).
    if canonical_steer_point(payload.get("steer_point")) == BASELINE_CONFIRM:
        return "synthesise"
    component = payload.get("component")
    if not isinstance(component, str):
        return None
    if component == "screen_full":
        return None
    registry_component = payload.get("registry_component")
    if not isinstance(registry_component, str):
        registry_component = registry_component_for(component)
    if registry_component == "screen_full":
        return None
    return STAGE_BY_REGISTRY.get(registry_component)


def presentation(stage: StageKey) -> tuple[str, str]:
    """Return the server-owned label and blurb for a public stage."""
    return STAGE_PRESENTATION[stage]
