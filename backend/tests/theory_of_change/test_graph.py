"""Graph structure checks (E1), item hash and link state (task 054, S8, C19)."""

from policy_atlas.theory_of_change.graph import (
    Box,
    Graph,
    Link,
    Pathway,
    assumption_type,
    check_graph,
    item_hash,
    item_text,
    link_state,
)


def _graph() -> Graph:
    boxes = {
        "b1": Box("b1", "input", "Ban adverts before 9pm"),
        "b2": Box("b2", "output", "Fewer adverts seen"),
        "b3": Box("b3", "outcome", "Fewer requests for snacks"),
        "b4": Box("b4", "impact", "Fewer children with obesity"),
        "b5": Box("b5", "failure_outcome", "Spend moves online"),
    }
    links = {
        "l1": Link("l1", "b1", "b2", conditions=["Rules are enforced"]),
        "l2": Link("l2", "b2", "b3", conditions=["Adverts drive requests"]),
        "l3": Link("l3", "b3", "b4", conditions=["Parents act on fewer requests"]),
        "l4": Link("l4", "b1", "b5", conditions=["Online is not covered"]),
    }
    pathways = [Pathway("p1", "success", ["l1", "l2", "l3"]), Pathway("p2", "failure", ["l4"])]
    return Graph(boxes, links, pathways)


def test_a_good_graph_passes() -> None:
    assert check_graph(_graph()) == []


def test_structure_problems_are_named() -> None:
    graph = _graph()
    graph.links["l2"].conditions = []
    graph.boxes["b6"] = Box("b6", "outcome", "Orphan")
    graph.links["l5"] = Link("l5", "b1", "b4", conditions=["x"])
    graph.pathways[0].links = ["l1", "l3"]
    graph.pathways[1].status = "set_aside"
    problems = check_graph(graph)
    assert "step l2 has no conditions" in problems
    assert "box b6 is on no step" in problems
    assert "step l5: an input cannot lead straight to an impact" in problems
    assert "pathway p1 is broken between l1 and l3" in problems
    assert "there is no failure pathway" in problems


def test_backwards_and_same_layer_steps() -> None:
    graph = _graph()
    graph.links["l9"] = Link("l9", "b3", "b2", conditions=["x"])
    graph.links["l8"] = Link("l8", "b2", "b2", conditions=["x"])
    problems = check_graph(graph)
    assert any("goes backwards" in p for p in problems)
    assert any("inside the output layer" in p for p in problems)


def test_assumption_types() -> None:
    assert assumption_type("input", "output") == "delivery"
    assert assumption_type("output", "outcome") == "take-up"
    assert assumption_type("outcome", "outcome") == "behaviour change"
    assert assumption_type("outcome", "impact") == "benefits and side effects"
    assert assumption_type("output", "failure_outcome") == "if it goes wrong"


def test_item_hash_covers_link_boxes_conditions_not_plan() -> None:
    link = _graph().links["l2"]
    base = item_hash(link, "Fewer adverts seen", "Fewer requests")
    assert item_hash(link, "fewer  adverts seen ", "Fewer requests") == base  # case and spacing
    assert item_hash(link, "Fewer adverts shown", "Fewer requests") != base  # a box edit
    link.conditions.append("Children watch live TV")
    assert item_hash(link, "Fewer adverts seen", "Fewer requests") != base
    text_a = item_text(
        link, source_text="a", target_text="b", population="children", place="England"
    )
    text_b = item_text(link, source_text="a", target_text="b", population="adults", place="Wales")
    assert text_a != text_b  # plan scope is in the text, not the hash
    assert "Children watch live TV" in text_a


def test_link_state_follows_the_c19_table() -> None:
    def state(
        current: str,
        counted: str | None,
        kept: str | None = None,
        by: str | None = None,
        checking: bool = False,
    ) -> str:
        return link_state(
            current_hash=current,
            counted_hash=counted,
            kept_hash=kept,
            kept_by=by,
            checking=checking,
        )

    assert state("h1", None) == "unchecked"
    assert state("h1", None, checking=True) == "checking"
    assert state("h1", "h1") == "checked"
    assert state("h2", "h1") == "pending"
    assert state("h2", "h1", "h2", "user") == "kept"
    assert state("h2", "h1", "h2", "check") == "no_change"
    assert state("h2", "h1", "h2", "choose") == "checked"
    assert state("h3", "h1", "h2", "user") == "pending"
