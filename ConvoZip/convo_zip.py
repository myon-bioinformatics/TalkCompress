#!/usr/bin/env python3
"""ConvoZip (D): cross-layer router / shared CLI entry."""

from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(mod_name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ConvoZip: route to TalkCompress subprojects")
    p.add_argument(
        "--layer",
        required=True,
        choices=("1", "2", "3", "4", "A", "B", "C", "E", "zipilogue", "tessera", "shorthand", "morpho"),
        help="target layer / subproject",
    )
    p.add_argument("--text", required=True)
    p.add_argument("--key", help="layer-1 shared secret")
    args = p.parse_args(argv)

    layer = args.layer
    if layer in ("1", "A", "zipilogue"):
        z = _load("zipilogue", "Zipilogue/zipilogue.py")
        if not args.key:
            p.error("--key is required for layer 1 / Zipilogue")
        sys.stdout.write(z.encode(args.text.encode("utf-8"), key=args.key.encode("utf-8")).hex() + "\n")
        return 0
    if layer in ("2", "B", "tessera"):
        t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
        print(t.render(t.tag_sentences(args.text, ["en", "ja", "es"])))
        return 0
    if layer in ("3", "C", "shorthand"):
        s = _load("shorthand_lab", "ShorthandLab/shorthand_lab.py")
        print(s.compress(args.text))
        return 0
    if layer in ("4", "E", "morpho"):
        m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
        print(m.compress(args.text))
        return 0
    p.error(f"unhandled layer: {layer}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
