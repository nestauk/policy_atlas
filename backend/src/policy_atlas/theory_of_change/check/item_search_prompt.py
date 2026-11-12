"""The search guidance every theory-of-change item search carries (task 054, S3).

Lead-authored. The intent of an item search is the link's item text (the step,
both boxes, the conditions, the population and place); these sentences steer
the existing query writer toward evidence on the step and on each of its
conditions, for and against. Each entry is at most 200 characters (the
guidance channel's limit).
"""

#: The second search for a step the first left thin (C44, owner 2026-11-06):
#: the same five calls, in the words of the research that would test the step.
REFORMULATE_GUIDANCE: tuple[str, ...] = (
    "Earlier searches used the step's own words and found no study that tests it. "
    "Do not repeat them; write queries a researcher of this question would use.",
    "Name the constructs, outcomes and mechanisms the literature measures (for example "
    "self-efficacy, skill acquisition, adherence), not the step's phrasing.",
    "Make the paraphrase one research-style sentence stating the hypothesis the step "
    "makes, for a search by meaning.",
)

#: Characters of the earlier queries shown to the query writer (the guidance limit).
PREVIOUS_QUERIES_CHARS = 200


def reformulate_guidance(previous: list[str]) -> list[str]:
    """The guidance a reformulated item search carries (C44).

    Args:
        previous: The queries the link's earlier searches ran, newest first.

    Returns:
        :data:`REFORMULATE_GUIDANCE`, plus one line listing the earlier queries
        when there are any, cut to the guidance channel's limit.
    """
    lines = list(REFORMULATE_GUIDANCE)
    if previous:
        shown = "Earlier queries: " + "; ".join(q for q in previous if q)
        lines.append(shown[:PREVIOUS_QUERIES_CHARS])
    return lines


ITEM_SEARCH_GUIDANCE: tuple[str, ...] = (
    "Write queries on the causal step itself: studies and evaluations of whether the "
    "first change leads to the second, including null and negative results.",
    "Write queries on each listed condition: evidence that it holds or fails, "
    "especially for this population and in this place.",
    "Prefer trials, quasi-experiments, systematic reviews and government evaluations, "
    "and include policy documents from this place.",
)
