"""Run: uv run --project backend pytest scripts/evals/theory_of_change/tests -q"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schema import Case  # noqa: E402

MINI = {
    "meta": {"id": "x", "title": "t", "organisation": "o", "year": 2024, "country": "UK",
             "topic": "health", "intervention_type": "policy", "timing": "retrospective",
             "doc_url": "u", "figure_pages": [3], "evidence_level": "A",
             "verdict_source": "ex_post_evaluation"},
    "brief": {"intended_change": "c", "population": "p", "place": "pl", "intervention": "i",
              "outcome_first": "o", "intervention_first": "i"},
    "boxes": [{"id": "B1", "label": "a", "layer": "input"},
              {"id": "B2", "label": "b", "layer": "output"}],
    "links": [{"id": "L1", "source": "B1", "target": "B2", "confidence": "high",
               "verdict": {"raw": "Strong", "scale": "supports"}}],
    "conclusions": {"weakest_links": ["L1"]},
    "key_claims": [{"id": "K1", "claim": "a leads to b", "refs": ["L1"]}],
    "transcription": {"method": "test"},
}


def test_valid_case():
    assert Case.model_validate(MINI).links[0].verdict.scale == "supports"


@pytest.mark.parametrize("path,value", [
    (("links", 0, "target"), "B9"),          # link to a missing box
    (("boxes", 1, "id"), "B1"),              # duplicate id
    (("conclusions", "weakest_links"), ["L9"]),  # conclusion names a missing link
    (("key_claims", 0, "refs"), ["L9"]),     # key claim covers a missing link
])
def test_bad_refs(path, value):
    import copy
    bad = copy.deepcopy(MINI)
    node = bad
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        Case.model_validate(bad)
