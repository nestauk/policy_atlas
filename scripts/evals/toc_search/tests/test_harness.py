"""Self-checks for the agentic search harness: the stop rule and the System client's
parsing. No network, no database, no model calls.

Run: uv run --project backend pytest scripts/evals/toc_search/tests -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import harness as h  # noqa: E402
from policy_atlas.theory_of_change.evidence.grade import DocAppraisal, Judgement  # noqa: E402


def _j(
    elsewhere: str, here: str = "not_about", robust: bool | None = None
) -> Judgement:
    return Judgement("d", elsewhere, here, robust)


def test_is_decisive() -> None:
    trial = DocAppraisal(score=4)
    assert h.is_decisive(_j("supports"), trial, "elsewhere")
    assert h.is_decisive(_j("challenges"), DocAppraisal(score=5), "elsewhere")
    assert not h.is_decisive(_j("supports"), trial, "here")  # other question
    assert not h.is_decisive(_j("supports"), DocAppraisal(score=3), "elsewhere")
    assert not h.is_decisive(
        _j("supports"), DocAppraisal(score=4, web=True), "elsewhere"
    )  # capped web
    model = DocAppraisal(score=2, modelling=True)
    assert h.is_decisive(_j("supports", robust=True), model, "elsewhere")
    assert not h.is_decisive(_j("supports", robust=False), model, "elsewhere")
    assert not h.is_decisive(_j("supports"), None, "elsewhere")


def test_stop_reason() -> None:
    assert h.stop_reason(True, 1, 5) == "decisive"
    assert h.stop_reason(False, 1, 0) == "saturated"
    assert h.stop_reason(False, 1, 3) is None
    assert h.stop_reason(False, 2, 3) == "budget"
    assert h.stop_reason(True, 2, 0) == "decisive"


def test_system_parsing() -> None:
    assert h.split_cause_effect("energy intake -> obesity") == (
        "energy intake",
        "obesity",
    )
    assert h.split_cause_effect('"sugary drinks" → body weight') == (
        "sugary drinks",
        "body weight",
    )
    assert h.split_cause_effect("no arrow here") is None
    concepts = [
        {"system_id": "a", "wikidata_label": "Metabolically healthy obesity"},
        {"system_id": "b", "wikidata_label": "obesity management"},
        {"system_id": "c", "wikidata_label": "obesity"},
    ]
    assert h.best_concept("Obesity", concepts)["system_id"] == "c"
    assert h.best_concept("childhood obesity", concepts)["system_id"] == "c"
    assert (
        h.best_concept(
            "BMI",
            [
                {
                    "system_id": "x",
                    "wikidata_label": "body mass index",
                    "wikidata_aliases": ["BMI"],
                }
            ],
        )["system_id"]
        == "x"
    )
    assert h.best_concept("teeth", concepts) is None
    payload = {
        "data": [
            {"doi": "10.1186/1471-2458-14-1291"},
            {"doi": None},
            {"doi": "https://doi.org/10.1186/1471-2458-14-1291"},
            {"doi": "10.3390/NU13093167"},
        ]
    }
    assert h.study_dois(payload) == ["10.1186/1471-2458-14-1291", "10.3390/nu13093167"]


def test_trusted_and_gold() -> None:
    assert (
        h.trusted("www.gov.uk")
        and h.trusted("england.nhs.uk")
        and h.trusted("www.ucl.ac.uk")
    )
    assert not h.trusted("notgov.uk") and not h.trusted("example.com")
    doc = h.Doc(
        key="k",
        title="Preventing childhood obesity by reducing consumption of carbonated drinks",
        abstract="",
        year=2004,
        source="openalex",
        doi="10.1136/bmj.38077.458438.ee",
    )
    assert h.gold_match({"doi": "10.1136/BMJ.38077.458438.EE"}, doc)
    assert h.gold_match(
        {
            "title": "Preventing childhood obesity by reducing consumption of carbonated drinks: cluster randomised controlled trial"
        },
        doc,
    )
    assert not h.gold_match({"doi": "10.1/x"}, doc)


def test_cache_keeps_every_entry_across_threads(tmp_path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    cache = h.Cache(tmp_path / "c.pkl", budget=100.0)
    meter = h.Meter()

    def work(t: int) -> None:
        for i in range(50):
            cache.call(meter, ("k", t, i), lambda: (i, [h.Cost("x", usd=0.001)]))

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(work, range(8)))
    cache.save()
    assert len([k for k in cache.data if k != "__total_spent__"]) == 400
    assert meter.calls["x"] == 400 and abs(cache.total - 0.4) < 1e-9
    assert len(h.Cache(tmp_path / "c.pkl", budget=1.0).data) == 401


def test_round_robin_and_s2_dois() -> None:
    def doc(key: str, doi: str | None, title: str = "t") -> h.Doc:
        return h.Doc(key=key, title=title, abstract="", year=None, source="x", doi=doi)

    q1 = [doc("a", "1"), doc("b", "2"), doc("c", "3")]
    q2 = [doc("d", "1"), doc("e", "4")]  # d duplicates a by DOI
    ov = [doc("f", None, title=" "), doc("g", "5")]  # f has no title
    assert [d.key for d in h.round_robin([q1, q2, ov], 10)] == ["a", "b", "e", "g", "c"]
    assert [d.key for d in h.round_robin([q1, q2, ov], 2)] == ["a", "b"]
    papers = [
        {"externalIds": {"DOI": "10.1234/A"}},
        None,
        {"externalIds": {}},
        {"externalIds": {"DOI": "10.1234/a"}},
    ]
    assert h.s2_dois(papers) == ["10.1234/a"]
