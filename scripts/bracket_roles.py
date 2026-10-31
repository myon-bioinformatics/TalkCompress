"""Opt-in experiment: role-differentiated brackets modelled on code syntax.

Builds on ``bracket_chunk.chunks`` (NFC-normalised).  Applied to compressed
MorphoZip output; baseline is the unchanged output (lowercase variant A).

* ``P1``   — call form ``prep(obj)``: ``in(Zürich)``
* ``P1m``  — ``P1`` only for multi-word objects, single words untouched
* ``P2``   — ``prep(obj)``, multi-word noun phrase as variable ``prep({a b})``
* ``P3«»`` / ``P3‹›`` — object as variable ``prep«obj»``; ``m`` = multi-word only
* ``Q「」`` / ``Q""`` — quoted literals ``“…”`` / ``"…"`` rewritten as ``「…」`` / ``"…"``

Usage::

    uv run python scripts/bracket_roles.py [--json]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("bracket_chunk", ROOT / "scripts/bracket_chunk.py")
bc = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("bracket_chunk", bc)
_spec.loader.exec_module(bc)  # type: ignore[union-attr]

_QUOTE_RE = re.compile(r"[\"“]([^\"“”\n]*)[\"”]")


def _fmt(variant: str, inner: str) -> str | None:
    if variant not in VARIANTS[:7]:
        raise ValueError(f"unknown variant {variant!r}")
    multi = " " in inner
    if variant.endswith("m") and not multi:
        return None
    if variant.startswith("P1"):
        return f"({inner})"
    if variant == "P2":
        return f"({{{inner}}})" if multi else f"({inner})"
    return variant[2] + inner + variant[3]


def apply(text: str, variant: str) -> str:
    """Rewrite ``text`` (NFC) per ``variant``; unknown variants raise."""
    text = unicodedata.normalize("NFC", text)
    if variant.startswith("Q"):
        if variant not in ('Q「」', 'Q""'):
            raise ValueError(f"unknown variant {variant!r}")
        left, right = variant[1], variant[2]
        return _QUOTE_RE.sub(lambda m: left + m.group(1) + right, text)
    parts: list[str] = []
    last = 0
    for prep_end, _s, end, inner in bc.chunks(text):
        rep = _fmt(variant, inner)
        if rep is None:
            continue
        parts.append(text[last:prep_end] + rep)
        last = end
    parts.append(text[last:])
    return "".join(parts)


VARIANTS = ("P1", "P1m", "P2", "P3«»", "P3‹›", "P3«»m", "P3‹›m", "Q「」", 'Q""')


def measure(texts: dict[str, str], compress: Callable[[str], str], count: Callable[[str], int]) -> dict[str, dict[str, int]]:
    rows: dict[str, dict[str, int]] = {}
    for name in sorted(texts):
        comp = unicodedata.normalize("NFC", compress(texts[name]))
        for key, s in [("A", comp)] + [(v, apply(comp, v)) for v in VARIANTS]:
            r = rows.setdefault(key, {"tokens": 0, "bytes": 0})
            r["tokens"] += count(s)
            r["bytes"] += len(s.encode("utf-8"))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    import tiktoken

    spec = importlib.util.spec_from_file_location("morpho_zip", ROOT / "MorphoZip/morpho_zip.py")
    mz = importlib.util.module_from_spec(spec)
    sys.modules["morpho_zip"] = mz
    spec.loader.exec_module(mz)  # type: ignore[union-attr]
    enc = tiktoken.get_encoding("o200k_base")
    rows = measure(bc.load_corpus(), mz.compress, lambda t: len(enc.encode(t)))
    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        return 0
    base = rows["A"]
    for k, v in rows.items():
        dt, db = v["tokens"] - base["tokens"], v["bytes"] - base["bytes"]
        print(f"{k}: tokens={v['tokens']} ({dt:+d}, {dt / base['tokens']:+.1%}) bytes={v['bytes']} ({db:+d})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
