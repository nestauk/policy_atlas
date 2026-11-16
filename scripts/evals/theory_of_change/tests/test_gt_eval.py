"""Self-checks for the ground-truth eval: the dataset parser and the metric functions.
No network, no database, no model calls.

Run: uv run --project backend pytest scripts/evals/theory_of_change/tests -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gt_eval as g  # noqa: E402


def test_parse_dataset() -> None:
    gt = g.load_case("epps")
    assert len(gt["nodes"]) == 26 and len(gt["edges"]) == 27 and len(gt["groups"]) == 4
    assert gt["brief"].startswith("Environment Act 2021 s.19") and gt["brief"].endswith(
        "long-term environmental impact."
    )
    assert (
        "## Machine-readable" not in gt["notes"]
        and "Intervention-first brief" not in gt["notes"]
    )
    assert "## Assumptions and risks" in gt["notes"]
    # EPPS weak set: edge 18 (A9-A11) and edges 22-24 (A13), 0-based.
    assert g.gt_weak_edges(gt) == [17, 21, 22, 23]
    cf = g.load_case("cf_individual")
    assert {cf["edges"][i]["status"] for i in g.gt_weak_edges(cf)} <= {
        "insufficient",
        "not_leading",
    }


GT = {
    "nodes": [
        {"id": "a", "layer": "activity", "group": None, "label": ""},
        {"id": "m1", "layer": "outcome_short", "group": "G", "label": ""},
        {"id": "m2", "layer": "outcome_short", "group": "G", "label": ""},
        {"id": "z", "layer": "impact", "group": None, "label": ""},
    ],
    "groups": [{"id": "G", "layer": "outcome_short", "label": ""}],
    "edges": [
        {"source": "a", "target": "G", "confidence": "high", "status": "progressing"},
        {
            "source": "G",
            "target": "z",
            "confidence": "medium",
            "status": "insufficient",
        },
    ],
    "shape": {
        "n_nodes": 4,
        "n_groups": 1,
        "longest_path_len": 3,
        "nodes_by_layer": {"activity": 1, "outcome_short": 2, "impact": 1},
    },
}


def _pa(edges: list[tuple[str, str, str]]) -> dict:
    return {
        "nodes": [
            {"id": "A", "layer": "input/activity"},
            {"id": "O", "layer": "outcome"},
            {"id": "X", "layer": "output"},
            {"id": "I", "layer": "impact"},
        ],
        "edges": [
            {
                "source": s,
                "target": t,
                "evidence": {
                    "lower_grade": gr,
                    "weak": gr in ("weak", "none"),
                    "strength": g.STRENGTH[gr],
                },
            }
            for s, t, gr in edges
        ],
        "failure_nodes": [],
        "failure_edges": [],
    }


def _m(pairs: dict) -> dict:
    return {
        k: {"match_id": v, "match_type": "exact" if v else "none"}
        for k, v in pairs.items()
    }


def test_edge_recall_expands_containers() -> None:
    # Only m2 (a container member) is matched; the a→G and G→z links still count through it.
    matches = _m({"a": "A", "m1": None, "m2": "O", "z": "I"})
    ms = g.match_sets(GT, matches)
    assert ms["G"] == {"O"}
    pa = _pa([("A", "O", "strong"), ("O", "X", "weak"), ("X", "I", "none")])
    assert (
        g.edge_recall(GT, pa, ms, soft=False, weighted=False) == 0.5
    )  # a→G direct; G→z missing
    assert (
        g.edge_recall(GT, pa, ms, soft=True, weighted=False) == 0.75
    )  # G→z via two steps, half
    assert g.edge_recall(GT, pa, ms, soft=True, weighted=True) == (1 + 0.5 * 0.7) / 1.7
    w = g.weak_recall(GT, pa, ms)
    assert (w["n_gt_weak"], w["n_drawn"], w["n_flagged"]) == (1, 1, 1)


def test_node_metrics_and_layers() -> None:
    pa = _pa([])
    matches = {
        "a": {"match_id": "A", "match_type": "exact"},
        "m1": {"match_id": "O", "match_type": "narrower"},
        "m2": {"match_id": None, "match_type": "none"},
        "z": {"match_id": "O", "match_type": "broader"},
    }
    m = g.node_metrics(GT, pa, matches)
    assert m["recall"] == (1 + 0.5 + 0 + 0.7) / 4
    assert m["layer_agreement"] == 2 / 3  # z (impact) matched an outcome box
    assert m["novel_rate"] == 0.5  # X and I unmatched


def test_shape_score() -> None:
    pa = _pa(
        [("A", "O", "strong"), ("O", "I", "weak")]
    )  # 4 boxes, chain of 3, 1 impact
    s = g.shape(GT, pa)
    assert s["checks"] == {
        "boxes": 1.0,
        "containers": 0.0,
        "longest_chain": 1.0,
        "impacts": 1.0,
        "per_layer": 1.0,
    }
    assert s["score"] == 0.8
    assert g.gradient(pa) == -1.0  # the deeper link is the weaker one
    assert (
        g.longest_chain(["a", "b"], [("a", "b"), ("b", "a")]) == 2
    )  # a cycle is not followed twice


def test_route_recall_moves_forwards_only() -> None:
    matches = _m({"a": "A", "m1": None, "m2": "O", "z": "I"})
    ms = g.match_sets(GT, matches)
    # a→G reached in three links A→X→O... and G→z via O→I; a backwards link is not taken.
    pa = _pa([("A", "X", "strong"), ("X", "O", "weak"), ("O", "I", "none")])
    assert g.route_recall(GT, pa, ms, weighted=False) == 1.0
    back = _pa(
        [("O", "A", "strong"), ("A", "I", "strong")]
    )  # O reaches I only backwards
    assert g.route_recall(GT, back, ms, weighted=True) == 0.0


def test_container_recall() -> None:
    gt = {
        **GT,
        "nodes": GT["nodes"]
        + [{"id": "m3", "layer": "outcome_short", "group": "G", "label": ""}],
    }
    two_narrower = {
        "a": {"match_type": "exact"},
        "m1": {"match_type": "narrower"},
        "m2": {"match_type": "narrower"},
        "m3": {"match_type": "none"},
        "z": {"match_type": "none"},
    }
    c = g.container_recall(gt, two_narrower)
    assert c["recall"] == 1.0 and c["mean_share"] == 2 / 3
    one_narrower = {**two_narrower, "m2": {"match_type": "none"}}
    assert g.container_recall(gt, one_narrower)["recall"] == 0.0
    assert g.container_recall({**gt, "groups": []}, one_narrower) is None


def _toc(link: dict, layers: tuple[str, str], codes: tuple) -> dict:
    boxes = [
        {"box_id": f"b{i}", "layer": la, "text": la, "code": c}
        for i, (la, c) in enumerate(zip(layers, codes))
    ]
    base = {
        "link_id": "l1",
        "source_box_id": "b0",
        "target_box_id": "b1",
        "sentence": "",
        "critical": True,
        "code": codes[0] and "#1",
    }
    return {"boxes": boxes, "links": [{**base, **link}], "pathways": []}


def test_convert_reads_both_builds() -> None:
    new = g.convert(
        _toc({"verdict": "not_sure_mixed"}, ("input", "outcome_long"), ("A1", "L1"))
    )
    assert [n["id"] for n in new["nodes"]] == ["A1", "L1"] and new["edges"][0][
        "id"
    ] == "#1"
    assert new["nodes"][1]["layer"] == "outcome_long"
    assert new["edges"][0]["evidence"] == {
        "verdict": "not_sure_mixed",
        "weak": True,
        "strength": 2,
    }
    old = g.convert(
        _toc(
            {
                "lower_grade": "medium",
                "elsewhere": {"grade": "strong"},
                "here": {"grade": "medium"},
            },
            ("input", "outcome"),
            (None, None),
        )
    )
    assert [n["id"] for n in old["nodes"]] == ["B1", "B2"] and old["edges"][0][
        "id"
    ] == "L1"
    assert (
        old["edges"][0]["evidence"]["weak"] is False
        and old["edges"][0]["evidence"]["strength"] == 2
    )
    assert g.layers_agree("outcome_long", "outcome") and not g.layers_agree(
        "outcome_long", "outcome_short"
    )
