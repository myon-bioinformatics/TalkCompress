#!/usr/bin/env python3
# minpy-bundle/1
# tool: minpy/0.1.0
# python: 3.14
# repository: myon-bioinformatics/TalkCompress
# commit: 8ca026f3018fa765eb74aad0df237ea813243f83
# entry: shared/kgraph.py
# entry-module: kgraph
# search-paths: shared
# allow: 
# allow-cycles: no
# cycles: 
# modules: kgraph
# prefix: _minpy_4601c6a3e5ab1173
# content-sha256: f64c9a5d1ffe4f64665fc61caff86574cfe7a2a3ac6bb9656df4d18277b24cce
# content-sha256-rule: sha256-utf8-with-content-sha256-hex-replaced-by-64-zeros

import importlib.machinery
import sys

_MINPY_PREFIX = "_minpy_4601c6a3e5ab1173"
_MINPY_ENTRY = "kgraph"
_MINPY_PACKAGES = ()
_MINPY_SOURCES = {
    "kgraph": "\"\"\"Small typed knowledge graph on the standard library only.\n\nSelf-written core for ``scripts/mapping_graph.py`` (docs/ontology/), also shipped\nas the single-file bundle ``dist/kgraph_min.py`` (docs/distributions.md).\n\n* typed nodes (``id`` + ``type`` + properties) and directed triples\n  ``(subject, predicate, object)`` with per-predicate adjacency in both directions\n* reverse index: object -> subjects for one predicate (e.g. English source -> candidates)\n* relation-type filtered traversal (breadth-first, out / in / both)\n* status aggregation (``group -> Counter(status)``)\n* dependency order and cycle detection via ``graphlib.TopologicalSorter``\n\nIt knows nothing about TalkCompress data: no file I/O and no ``__file__``.\n\"\"\"\n\nfrom __future__ import annotations\n\nfrom collections import Counter, defaultdict, deque\nfrom graphlib import CycleError, TopologicalSorter\nfrom typing import Callable, Iterable\n\n__all__ = [\"CycleError\", \"Graph\", \"GraphError\", \"aggregate\", \"dependency_order\"]\n\n\nclass GraphError(ValueError):\n    \"\"\"The graph contradicts itself (one ID with two classes, a dangling edge).\"\"\"\n\n\nclass Graph:\n    def __init__(self) -> None:\n        self.nodes: dict[str, dict] = {}\n        self.edges: list[tuple[str, str, str]] = []\n        self._edge_set: set[tuple[str, str, str]] = set()\n        self._out: dict[str, list[tuple[str, str]]] = defaultdict(list)\n        self._in: dict[str, list[tuple[str, str]]] = defaultdict(list)\n        self._by_type: dict[str, list[str]] = defaultdict(list)\n\n    # ---------------------------------------------------------------- build\n    def add(self, nid: str, kind: str, **props) -> str:\n        \"\"\"Add (or extend) a typed node; existing properties are never overwritten.\"\"\"\n        node = self.nodes.get(nid)\n        if node is None:\n            node = self.nodes[nid] = {\"id\": nid, \"type\": kind}\n            self._by_type[kind].append(nid)\n        elif node[\"type\"] != kind:\n            raise GraphError(f\"ID collision across classes: {nid} is {node['type']} and {kind}\")\n        for k, v in props.items():\n            node.setdefault(k, v)\n        return nid\n\n    def link(self, s: str, p: str, o: str) -> None:\n        \"\"\"Add the triple once; insertion order is kept for stable output.\"\"\"\n        e = (s, p, o)\n        if e in self._edge_set:\n            return\n        self._edge_set.add(e)\n        self.edges.append(e)\n        self._out[s].append((p, o))\n        self._in[o].append((p, s))\n\n    def dangling(self) -> list[tuple[str, str, str]]:\n        return [e for e in self.edges if e[0] not in self.nodes or e[2] not in self.nodes]\n\n    def validate(self) -> None:\n        bad = self.dangling()\n        if bad:\n            s, p, o = bad[0]\n            raise GraphError(f\"dangling edge {s} -{p}-> {o}\")\n\n    # ---------------------------------------------------------------- read\n    def out(self, nid: str, pred: str | None = None) -> list[str]:\n        return [o for p, o in self._out.get(nid, ()) if pred is None or p == pred]\n\n    def inc(self, nid: str, pred: str | None = None) -> list[str]:\n        return [s for p, s in self._in.get(nid, ()) if pred is None or p == pred]\n\n    def out_edges(self, nid: str) -> list[tuple[str, str]]:\n        return list(self._out.get(nid, ()))\n\n    def in_edges(self, nid: str) -> list[tuple[str, str]]:\n        return list(self._in.get(nid, ()))\n\n    def of_type(self, kind: str) -> list[dict]:\n        return [self.nodes[n] for n in self._by_type.get(kind, ())]\n\n    def reverse_index(self, pred: str) -> dict[str, list[str]]:\n        \"\"\"object -> subjects for one predicate (e.g. ``forSource``: source -> candidates).\"\"\"\n        idx: dict[str, list[str]] = defaultdict(list)\n        for s, p, o in self.edges:\n            if p == pred:\n                idx[o].append(s)\n        return dict(idx)\n\n    def traverse(self, start: str, preds: Iterable[str] | None = None, *,\n                 direction: str = \"out\", max_depth: int | None = None) -> list[str]:\n        \"\"\"Breadth-first walk from ``start`` along the given predicates only.\n\n        ``direction`` is ``out`` (subject -> object), ``in`` or ``both``. Returns the\n        reached node IDs in visit order, ``start`` excluded.\n        \"\"\"\n        if direction not in (\"out\", \"in\", \"both\"):\n            raise ValueError(\"direction must be out, in or both\")\n        allowed = None if preds is None else frozenset(preds)\n        seen, order = {start}, []\n        queue = deque([(start, 0)])\n        while queue:\n            nid, depth = queue.popleft()\n            if max_depth is not None and depth >= max_depth:\n                continue\n            steps: list[tuple[str, str]] = []\n            if direction in (\"out\", \"both\"):\n                steps += self._out.get(nid, [])\n            if direction in (\"in\", \"both\"):\n                steps += self._in.get(nid, [])\n            for p, nxt in steps:\n                if (allowed is None or p in allowed) and nxt not in seen:\n                    seen.add(nxt)\n                    order.append(nxt)\n                    queue.append((nxt, depth + 1))\n        return order\n\n\ndef aggregate(items: Iterable[dict], group: str | Callable[[dict], str],\n              value: str | Callable[[dict], str]) -> dict[str, Counter]:\n    \"\"\"``group -> Counter(value)`` with groups sorted, e.g. language -> status counts.\"\"\"\n    g = group if callable(group) else (lambda d, k=group: d[k])\n    v = value if callable(value) else (lambda d, k=value: d[k])\n    per: dict[str, Counter] = defaultdict(Counter)\n    for item in items:\n        per[g(item)][v(item)] += 1\n    return dict(sorted(per.items()))\n\n\ndef dependency_order(depends_on: dict[str, Iterable[str]]) -> list[str]:\n    \"\"\"Nodes with their prerequisites first (``graphlib``); raises ``CycleError``.\"\"\"\n    ts = TopologicalSorter()\n    for node in sorted(depends_on):\n        ts.add(node, *sorted(depends_on[node]))\n    return list(ts.static_order())\n",
}
_MINPY_SKIP = (
    "__builtins__",
    "__cached__",
    "__file__",
    "__loader__",
    "__name__",
    "__package__",
    "__path__",
    "__spec__",
)


def _minpy_original(fullname):
    if fullname == _MINPY_PREFIX:
        return ""
    prefix = _MINPY_PREFIX + "."
    if fullname.startswith(prefix):
        return fullname[len(prefix):]
    return None


class _MinpyLoader:
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        original = _minpy_original(module.__name__)
        if original is None:
            raise ImportError(module.__name__)
        if original == "":
            module.__path__ = []
            return
        source = _MINPY_SOURCES[original]
        filename = "minpy://" + original + ".py"
        module.__file__ = filename
        exec(compile(source, filename, "exec"), module.__dict__)


class _MinpyFinder:
    def __init__(self):
        self._minpy_sources = _MINPY_SOURCES

    def find_spec(self, fullname, path, target=None):
        original = _minpy_original(fullname)
        if original is None:
            return None
        if original == "":
            is_package = True
        elif original not in _MINPY_SOURCES:
            return None
        else:
            is_package = original in _MINPY_PACKAGES
        return importlib.machinery.ModuleSpec(
            fullname,
            _MinpyLoader(),
            origin="minpy://" + (original or _MINPY_PREFIX),
            is_package=is_package,
        )


def _minpy_install():
    for finder in sys.meta_path:
        if getattr(finder, "_minpy_sources", None) is _MINPY_SOURCES:
            return
    sys.meta_path.insert(0, _MinpyFinder())


def _minpy_run_entry_as_main():
    import types

    original = _MINPY_ENTRY
    full = _MINPY_PREFIX + "." + original
    module = types.ModuleType("__main__")
    origin = "minpy://" + original + ".py"
    module.__file__ = globals().get("__file__") or origin
    if original in _MINPY_PACKAGES:
        module.__package__ = full
        module.__path__ = []
    elif "." in original:
        module.__package__ = full.rpartition(".")[0]
    else:
        module.__package__ = _MINPY_PREFIX
    sys.modules["__main__"] = module
    sys.modules[full] = module
    exec(compile(_MINPY_SOURCES[original], origin, "exec"), module.__dict__)


def _minpy_export_entry(namespace):
    import importlib

    module = importlib.import_module(_MINPY_PREFIX + "." + _MINPY_ENTRY)
    for key, value in module.__dict__.items():
        if key not in _MINPY_SKIP:
            namespace[key] = value


_minpy_install()
if __name__ == "__main__":
    _minpy_run_entry_as_main()
else:
    _minpy_export_entry(globals())
