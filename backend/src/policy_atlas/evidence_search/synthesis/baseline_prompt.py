"""The baseline template (``baseline_template_v2``) — synthesise's baseline mode.

Lead-authored and versioned (task 044, deliverable 7; contract § Baseline,
findings A7, A14, C7, C18). The baseline is a profile of "Do nothing": eight
required sections, supplied to synthesise rather than proposed, plus up to
two problem-specific sections the section proposer may add after "What is
contested". Every empirical premise is a cited chunk claim; the key
assumption and what is contested are reasoning claims labelled as such;
"not found" is a gap claim, a content state and never a hedge; Policy Atlas
does not forecast.

The section writer is template-keyed (owner ruling 2026-09-09: "For the
synthesise, let's go with option 2"): one shared core in
``synthesis_backend.py`` (tools, claim types, anchoring, honesty) plus one
short preamble per output kind. ``BASELINE_SECTION_PREAMBLE`` below is the
baseline's; the Evidence search report keeps today's text byte-identical.
Each section's instruction travels in its seed ``focus``. The Sources section
is rendered by code from the coverage record (counts are facts about the run,
not claims about the evidence) and never written by the model.

Compile constants that are execution-bearing but not plan fields (C8) live
here so nothing hides: the per-section turn cap, the proposed-section limit
and the section order. Depth does not change them.
"""

from __future__ import annotations

from dataclasses import dataclass

BASELINE_PROMPT_VERSION = "baseline_template_v2"

# Execution-bearing constants (contract § Plan object, C8).
BASELINE_PROPOSED_SECTIONS_MAX = 2
BASELINE_SECTION_TURN_CAP = 4
# Position (0-based, in the required order below) after which proposed
# sections are inserted: after "What is contested".
BASELINE_PROPOSED_INSERT_AFTER = "What is contested"

# The directive key synthesise reads to enter baseline mode (plan S2).
BASELINE_TEMPLATE_KEY = "baseline"

# Prose the writer must not use as a section title for a proposed section.
# Duplicates of the eight and the ES-only structural sections.
BASELINE_FORBIDDEN_PROPOSED_TITLES: frozenset[str] = frozenset(
    {
        "conclusions",
        "conclusion",
        "key findings",
        "summary",
        "recommendations",
        "options",
        "what could be done",
    }
)

# The baseline preamble of the template-keyed section writer. It replaces the
# Evidence search report's opening two paragraphs; the shared core follows it
# unchanged. Reviewed as prompt text: version bumps live in
# BASELINE_PROMPT_VERSION.
BASELINE_SECTION_PREAMBLE = """\
You are writing one section of a BASELINE for senior policy makers in
government and the civil service: a profile of the situation as it is and
where it is heading if nothing changes, written before any option is
considered. You first gather evidence with read-only tools, then author the
section as prose in which every evidential statement is a typed, citable
claim.

Where you sit and who you write for:
- Policy Atlas is an evidence tool. Upstream components have searched,
  screened, appraised and classified a small corpus of academic and grey
  policy documents about the status quo for the target group in the place
  the question names. No findings were extracted and the corpus was not
  characterised: your evidence is the documents' own text. The reader will
  use this baseline to decide which options to consider, so describe the
  status quo; never propose, compare or evaluate interventions.
- Every empirical statement is a cited claim from the documents. Where the
  documents do not answer the section's focus, say so as a gap claim in
  plain words ("No source found reports …") rather than hedging: "not found"
  is a result. Policy Atlas does not forecast: report trends and projections
  only as the sources state them, with their dates. The key assumption and
  the naming of contested points are your own reasoning, labelled as such.
- Your reader sees only the finished baseline, so pipeline vocabulary is
  context for you, never content for them: machinery words such as "chunk",
  "corpus", "substrate", "screening" or "tier" do not appear in your prose.
  Write about the people, places, programmes and figures the documents
  describe — not about the reading of the files.

"""


@dataclass(frozen=True)
class BaselineSection:
    """One required baseline section.

    Attributes:
        title: The section heading the reader sees.
        nav_label: The short contents-list label.
        focus: The instruction the writer answers (carried in the seed).
        turn_cap: The per-section tool-loop turn cap.
    """

    title: str
    nav_label: str
    focus: str
    turn_cap: int = BASELINE_SECTION_TURN_CAP


BASELINE_SECTIONS: tuple[BaselineSection, ...] = (
    BaselineSection(
        title="What is in place",
        nav_label="In place",
        focus="What is currently in place for this group in this place: the "
        "existing policies, programmes, entitlements and services the "
        "documents describe, who runs them and whom they reach. State what is "
        "absent when a source says so. Name programmes as the sources name "
        "them.",
    ),
    BaselineSection(
        title="Trend if nothing changes",
        nav_label="Trend",
        focus="The recent trend and the current level of the outcomes the plan "
        "names, as the sources report them, with their dates and measures. "
        "Report any projection a source makes as that source's projection. "
        "If no source projects forward, say so as a gap claim.",
    ),
    BaselineSection(
        title="Who is affected",
        nav_label="Who",
        focus="Who is affected and how the burden is distributed: the "
        "characteristics of the affected group the sources report (age, "
        "health, prior attainment, place, income or others the documents "
        "use), and how the group the plan names compares with the group the "
        "data describes — state plainly where the plan's target group is "
        "wider or narrower than what the sources measure.",
    ),
    BaselineSection(
        title="What is already changing",
        nav_label="Changing",
        focus="What is already changing without a new decision: announced "
        "reforms, pilots, funding changes, programmes ending or starting, "
        "and external shifts (labour market, demography, technology) the "
        "sources report as under way. Dates as given. Do not judge whether "
        "these changes will work.",
    ),
    BaselineSection(
        title="What is contested",
        nav_label="Contested",
        focus="Where the sources disagree about the problem: rival explanations "
        "of its causes, disputes about its size or measurement, different "
        "views of who the problem is, and disagreement about whether the "
        "current offer works. Report each side as its source states it and "
        "leave it as reported, not settled. Naming which disagreements are "
        "the contested points is your own reasoning: label that sentence as "
        "reasoning. Where the sources do not disagree, say so.",
    ),
    BaselineSection(
        title="Cost of inaction",
        nav_label="Cost of inaction",
        focus="The cost of inaction as the sources report it: fiscal, economic "
        "and human costs, each with its basis, unit, period and who bears "
        "it, quoted as reported and never converted or summed across "
        "sources. If no source costs the status quo, say so as a gap claim.",
    ),
    BaselineSection(
        title="Key assumption",
        nav_label="Key assumption",
        focus="The single assumption that most shapes how this problem should be "
        "read — the one a decision maker should check before choosing "
        "options (for example, that the current offer does not reach the "
        "group driving the trend). State it in one or two sentences as your "
        "own reasoning, labelled as reasoning and not as a finding, and say "
        "in one further sentence which reported facts it rests on, citing "
        "them. Do not propose options.",
    ),
)

# The rapid depth writes five sections (owner ruling 2026-09-17, task 044 phase
# 8: "Go with options 2 and 5"): the standard list with two pairs merged — what
# is in place with what is already changing, and the trend with the cost of
# inaction — and no writer-proposed sections. Each merged focus is the two
# standard foci said once; nothing is asked of the writer that the standard
# sections do not ask.
BASELINE_RAPID_SECTIONS: tuple[BaselineSection, ...] = (
    BaselineSection(
        title="What is in place and already changing",
        nav_label="In place",
        focus="What is currently in place for this group in this place — the "
        "existing policies, programmes, entitlements and services the "
        "documents describe, who runs them and whom they reach — and what is "
        "already changing without a new decision: announced reforms, pilots, "
        "funding changes, programmes ending or starting, and external shifts "
        "the sources report as under way. Dates as given. State what is "
        "absent when a source says so. Name programmes as the sources name "
        "them. Do not judge whether the changes will work.",
    ),
    BaselineSection(
        title="Trend and cost if nothing changes",
        nav_label="Trend and cost",
        focus="The recent trend and the current level of the outcomes the plan "
        "names, as the sources report them, with their dates and measures, "
        "and the cost of inaction as the sources report it: fiscal, economic "
        "and human costs, each with its basis, unit, period and who bears it, "
        "quoted as reported and never converted or summed across sources. "
        "Report any projection a source makes as that source's projection. If "
        "no source projects forward, or none costs the status quo, say so as "
        "a gap claim.",
    ),
    BASELINE_SECTIONS[2],  # Who is affected
    BASELINE_SECTIONS[4],  # What is contested
    BASELINE_SECTIONS[6],  # Key assumption
)

#: The model-written section list per depth. Standard keeps the ruled seven
#: and allows proposed sections; rapid writes five and allows none.
BASELINE_SECTIONS_BY_DEPTH: dict[str, tuple[BaselineSection, ...]] = {
    "standard": BASELINE_SECTIONS,
    "rapid": BASELINE_RAPID_SECTIONS,
}

# The last required section is rendered by code, not written by the model.
SOURCES_SECTION_TITLE = "Sources"
SOURCES_SECTION_NAV_LABEL = "Sources"

SOURCES_SEARCHED_TEMPLATE = (
    "{document_count} sources from Overton and OpenAlex, searched for the "
    "situation and trend this plan describes{restriction_clause}."
)
SOURCES_NOT_SEARCHED_LINE = (
    "Live official statistics and departmental pages were not searched; "
    "figures come from the documents above, as at their publication dates."
)
SOURCES_SKEW_TEMPLATE = (
    "Source mix: {grey_count} grey literature (policy reports, official and "
    "organisational publications) and {academic_count} academic articles"
    "{unknown_clause}. The profile leans on {skew_word} sources."
)
SOURCES_RESTRICTION_TEMPLATE = ", limited to {restriction_text}"
SOURCES_UNKNOWN_TEMPLATE = ", with {unknown_count} of undetermined type"
SOURCES_LANGUAGE_NOT_APPLIED_LINE = (
    "A language restriction is recorded in the plan and not yet applied at "
    "retrieval."
)

# The deterministic intent text compiled from the plan for the baseline's
# intent record (contract § Model route: never written by a model).
BASELINE_INTENT_TEMPLATE = (
    "What is the current situation, and the trend if nothing changes, for "
    "{target_unit} in {where}, with respect to {intended_change}? Outcomes of "
    "interest: {outcomes}."
)

# The artefact title (Baseline board), the Result band and the depth label
# every scoping profile carries (C18).
BASELINE_ARTEFACT_TITLE = "Do nothing: current policy and trajectory"
BASELINE_BAND = "the situation these options would change"
BASELINE_DEPTH_LABEL = "scoping pass"


def required_titles(depth: str = "standard") -> tuple[str, ...]:
    """Return the required section titles in order for a depth, Sources last.

    Args:
        depth: ``standard`` (eight titles) or ``rapid`` (six).
    """
    sections = BASELINE_SECTIONS_BY_DEPTH[depth]
    return tuple(section.title for section in sections) + (SOURCES_SECTION_TITLE,)


def is_forbidden_proposed_title(title: str) -> bool:
    """Return whether a proposed section title duplicates a required or ES-only one.

    Args:
        title: The proposed title.
    """
    key = " ".join(title.lower().split())
    if key in BASELINE_FORBIDDEN_PROPOSED_TITLES:
        return True
    return any(
        key == required.lower()
        for depth in BASELINE_SECTIONS_BY_DEPTH
        for required in required_titles(depth)
    )


def compile_intent(
    *, target_unit: str, where: str, intended_change: str, outcomes: list[str]
) -> str:
    """Compile the baseline intent record's text from the plan.

    Args:
        target_unit: Who or what should change.
        where: The jurisdiction.
        intended_change: What we are trying to change.
        outcomes: The outcomes evidence is read against.
    """
    return BASELINE_INTENT_TEMPLATE.format(
        target_unit=target_unit.strip(),
        where=where.strip(),
        intended_change=intended_change.strip().rstrip("."),
        outcomes="; ".join(o.strip() for o in outcomes) or "as stated in the question",
    )
