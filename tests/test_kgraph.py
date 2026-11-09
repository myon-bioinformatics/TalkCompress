"""shared/kgraph.py: the self-written stdlib graph core (docs/ontology/)."""

from __future__ import annotations

import pytest

from shared.kgraph import CycleError, Graph, GraphError, aggregate, dependency_order


def _g() -> Graph:
    g = Graph()
    for n, t in (("a", "Form"), ("b", "Form"), ("c", "Candidate"), ("en", "EnglishSource")):
        g.add(n, t)
    g.link("c", "proposesForm", "a")
    g.link("c", "forSource", "en")
    g.link("a", "follows", "b")
    g.link("a", "follows", "b")  # duplicate triple is ignored
    return g


def test_typed_nodes_and_collision():
    g = _g()
    assert [n["id"] for n in g.of_type("Form")] == ["a", "b"]
    g.add("a", "Form", status="pass")
    g.add("a", "Form", status="fail")  # never overwritten
    assert g.nodes["a"]["status"] == "pass"
    with pytest.raises(GraphError):
        g.add("a", "Candidate")


def test_adjacency_both_directions_and_order():
    g = _g()
    assert len(g.edges) == 3
    assert g.out("c") == ["a", "en"] and g.out("c", "forSource") == ["en"]
    assert g.inc("a") == ["c"] and g.in_edges("b") == [("follows", "a")]


def test_reverse_index():
    assert _g().reverse_index("forSource") == {"en": ["c"]}


def test_filtered_traversal():
    g = _g()
    assert g.traverse("c", ["proposesForm", "follows"]) == ["a", "b"]
    assert g.traverse("c", ["forSource"]) == ["en"]
    assert g.traverse("b", ["follows", "proposesForm"], direction="in") == ["a", "c"]
    assert g.traverse("c", None, max_depth=1) == ["a", "en"]
    with pytest.raises(ValueError):
        g.traverse("c", direction="up")


def test_dangling_edge_detected():
    g = _g()
    g.link("c", "rejectedBy", "missing")
    with pytest.raises(GraphError, match="dangling"):
        g.validate()


def test_aggregate():
    rows = [{"lang": "pt", "status": "pass"}, {"lang": "de", "status": "untested"}, {"lang": "pt", "status": "pass"}]
    res = aggregate(rows, "lang", "status")
    assert list(res) == ["de", "pt"] and res["pt"]["pass"] == 2


def test_dependency_order_and_cycle():
    order = dependency_order({"follow": {"base"}, "derived": {"follow"}})
    assert order.index("base") < order.index("follow") < order.index("derived")
    with pytest.raises(CycleError):
        dependency_order({"x": {"y"}, "y": {"x"}})
