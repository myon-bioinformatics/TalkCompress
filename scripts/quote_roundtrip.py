"""Measure curly→straight quote normalisation and check it can be restored.

Tokens/bytes: ``compress`` output with vs. without ``normalize_quotes`` on the
PD corpus.  Round-trip: ``restore_quotes(normalize_quotes(src)) == src`` for
every corpus file that uses curly quotes; mismatches are listed.

Usage::

    uv run python scripts/quote_roundtrip.py [--json]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/pd_corpus"


def restore_quotes(text: str) -> str:
    """Straight quotes → curly by context: a quote opens after space/start/bracket/dash
    when a non-space follows, otherwise it closes (``”`` / ``’``)."""
    out: list[str] = []
    for i, ch in enumerate(text):
        prev = text[i - 1] if i else "\n"
        nxt = text[i + 1] if i + 1 < len(text) else " "
        opening = (prev.isspace() or prev in "([{—–-") and not nxt.isspace()
        if ch == '"':
            out.append("\u201c" if opening else "\u201d")
        elif ch == "'":
            out.append("\u2018" if opening else "\u2019")
        else:
            out.append(ch)
    return "".join(out)


def load_mz():
    spec = importlib.util.spec_from_file_location("morpho_zip", ROOT / "MorphoZip/morpho_zip.py")
    mz = importlib.util.module_from_spec(spec)
    sys.modules["morpho_zip"] = mz
    spec.loader.exec_module(mz)  # type: ignore[union-attr]
    return mz


def to_corner(text: str) -> str:
    """Q「」 variant: double quote pairs (curly) → 「」; single quotes untouched."""
    return text.replace("\u201c", "\u300c").replace("\u201d", "\u300d")


def from_corner(text: str) -> str:
    return text.replace("\u300c", "\u201c").replace("\u300d", "\u201d")


VARIANTS = ("curly", 'Q""', "Q「」")


def check(texts: dict[str, str], mz, count: Callable[[str], int]) -> dict[str, object]:
    """Totals per variant, round-trip per variant, quoted spans and the heaviest file."""
    rows = {k: {"tokens": 0, "bytes": 0} for k in VARIANTS}
    rt = {k: {"checked": 0, "mismatches": []} for k in VARIANTS[1:]}
    per_file: dict[str, dict[str, int]] = {}
    spans = 0
    real = mz.normalize_quotes
    fns = {"curly": lambda t: t, 'Q""': real, "Q「」": lambda t: real(to_corner(t))}
    for name in sorted(texts):
        src = texts[name]
        n = src.count("\u201c")
        spans += n
        per_file[name] = {"spans": n}
        for key, fn in fns.items():
            mz.normalize_quotes = fn
            try:
                out = mz.compress(src)
            finally:
                mz.normalize_quotes = real
            tok = count(out)
            per_file[name][key] = tok
            rows[key]["tokens"] += tok
            rows[key]["bytes"] += len(out.encode("utf-8"))
        if any(c in src for c in "\u201c\u201d\u2018") and '"' not in src and "'" not in src:
            for key, back in (('Q""', restore_quotes(real(src))), ("Q「」", from_corner(to_corner(src)))):
                rt[key]["checked"] += 1
                if back != src:
                    rt[key]["mismatches"].append(name)
    heavy = max(per_file, key=lambda k: per_file[k]["spans"], default=None)
    per_span = {k: (rows[k]["tokens"] - rows["curly"]["tokens"]) / spans if spans else 0.0 for k in VARIANTS[1:]}
    return {"rows": rows, "roundtrip": rt, "spans": spans, "per_span": per_span, "heavy": {heavy: per_file[heavy]} if heavy else {}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(CORPUS.rglob("*.txt"))}
    res = check(texts, load_mz(), lambda t: len(enc.encode(t)))
    if args.json:
        print(json.dumps(res, indent=1))
        return 0
    for k, v in res["rows"].items():
        print(f"{k}: tokens={v['tokens']} bytes={v['bytes']}")
    for k, v in res["roundtrip"].items():
        print(f"roundtrip {k}: {v['checked'] - len(v['mismatches'])}/{v['checked']} ok {v['mismatches']}")
    print(f"quoted spans: {res['spans']} per-span tokens: {res['per_span']}")
    print(f"heaviest: {res['heavy']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
