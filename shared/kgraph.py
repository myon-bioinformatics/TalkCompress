"""Small typed knowledge graph on the standard library only.

Self-written core for ``scripts/mapping_graph.py`` (docs/ontology/), also shipped
as the single-file bundle ``dist/kgraph_min.py`` (docs/distributions.md).

* typed nodes (``id`` + ``type`` + properties) and directed triples
  ``(subject, predicate, object)`` with per-predicate adjacency in both directions
* reverse index: object -> subjects for one predicate (e.g. English source -> candidates)
* relation-type filtered traversal (breadth-first, out / in / both)
* status aggregation (``group -> Counter(status)``)
* dependency order and cycle detection via ``graphlib.TopologicalSorter``

It knows nothing about TalkCompress data: no file I/O and no ``__file__``.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from graphlib import CycleError, TopologicalSorter
from typing import Callable, Iterable

__all__ = ["CycleError", "Graph", "GraphError", "aggregate", "dependency_order"]


class GraphError(ValueError):
    """The graph contradicts itself (one ID with two classes, a dangling edge)."""


class Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict] = {}
        self.edges: list[tuple[str, str, str]] = []
        self._edge_set: set[tuple[str, str, str]] = set()
        self._out: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._in: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._by_type: dict[str, list[str]] = defaultdict(list)

    # ---------------------------------------------------------------- build
    def add(self, nid: str, kind: str, **props) -> str:
        """Add (or extend) a typed node; existing properties are never overwritten."""
        node = self.nodes.get(nid)
        if node is None:
            node = self.nodes[nid] = {"id": nid, "type": kind}
            self._by_type[kind].append(nid)
        elif node["type"] != kind:
            raise GraphError(f"ID collision across classes: {nid} is {node['type']} and {kind}")
        for k, v in props.items():
            node.setdefault(k, v)
        return nid

    def link(self, s: str, p: str, o: str) -> None:
        """Add the triple once; insertion order is kept for stable output."""
        e = (s, p, o)
        if e in self._edge_set:
            return
        self._edge_set.add(e)
        self.edges.append(e)
        self._out[s].append((p, o))
        self._in[o].append((p, s))

    def dangling(self) -> list[tuple[str, str, str]]:
        return [e for e in self.edges if e[0] not in self.nodes or e[2] not in self.nodes]

    def validate(self) -> None:
        bad = self.dangling()
        if bad:
            s, p, o = bad[0]
            raise GraphError(f"dangling edge {s} -{p}-> {o}")

    # ---------------------------------------------------------------- read
    def out(self, nid: str, pred: str | None = None) -> list[str]:
        return [o for p, o in self._out.get(nid, ()) if pred is None or p == pred]

    def inc(self, nid: str, pred: str | None = None) -> list[str]:
        return [s for p, s in self._in.get(nid, ()) if pred is None or p == pred]

    def out_edges(self, nid: str) -> list[tuple[str, str]]:
        return list(self._out.get(nid, ()))

    def in_edges(self, nid: str) -> list[tuple[str, str]]:
        return list(self._in.get(nid, ()))

    def of_type(self, kind: str) -> list[dict]:
        return [self.nodes[n] for n in self._by_type.get(kind, ())]

    def reverse_index(self, pred: str) -> dict[str, list[str]]:
        """object -> subjects for one predicate (e.g. ``forSource``: source -> candidates)."""
        idx: dict[str, list[str]] = defaultdict(list)
        for s, p, o in self.edges:
            if p == pred:
                idx[o].append(s)
        return dict(idx)

    def traverse(self, start: str, preds: Iterable[str] | None = None, *,
                 direction: str = "out", max_depth: int | None = None) -> list[str]:
        """Breadth-first walk from ``start`` along the given predicates only.

        ``direction`` is ``out`` (subject -> object), ``in`` or ``both``. Returns the
        reached node IDs in visit order, ``start`` excluded.
        """
        if direction not in ("out", "in", "both"):
            raise ValueError("direction must be out, in or both")
        allowed = None if preds is None else frozenset(preds)
        seen, order = {start}, []
        queue = deque([(start, 0)])
        while queue:
            nid, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue
            steps: list[tuple[str, str]] = []
            if direction in ("out", "both"):
                steps += self._out.get(nid, [])
            if direction in ("in", "both"):
                steps += self._in.get(nid, [])
            for p, nxt in steps:
                if (allowed is None or p in allowed) and nxt not in seen:
                    seen.add(nxt)
                    order.append(nxt)
                    queue.append((nxt, depth + 1))
        return order


def aggregate(items: Iterable[dict], group: str | Callable[[dict], str],
              value: str | Callable[[dict], str]) -> dict[str, Counter]:
    """``group -> Counter(value)`` with groups sorted, e.g. language -> status counts."""
    g = group if callable(group) else (lambda d, k=group: d[k])
    v = value if callable(value) else (lambda d, k=value: d[k])
    per: dict[str, Counter] = defaultdict(Counter)
    for item in items:
        per[g(item)][v(item)] += 1
    return dict(sorted(per.items()))


def dependency_order(depends_on: dict[str, Iterable[str]]) -> list[str]:
    """Nodes with their prerequisites first (``graphlib``); raises ``CycleError``."""
    ts = TopologicalSorter()
    for node in sorted(depends_on):
        ts.add(node, *sorted(depends_on[node]))
    return list(ts.static_order())
