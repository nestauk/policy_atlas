"""The search guidance every theory-of-change item search carries (task 054, S3).

Lead-authored. The intent of an item search is the link's item text (the step,
both boxes, the conditions, the population and place); these sentences steer
the existing query writer toward evidence on the step and on each of its
conditions, for and against. Each entry is at most 200 characters (the
guidance channel's limit).
"""

ITEM_SEARCH_GUIDANCE: tuple[str, ...] = (
    "Write queries on the causal step itself: studies and evaluations of whether the "
    "first change leads to the second, including null and negative results.",
    "Write queries on each listed condition: evidence that it holds or fails, "
    "especially for this population and in this place.",
    "Prefer trials, quasi-experiments, systematic reviews and government evaluations, "
    "and include policy documents from this place.",
)
