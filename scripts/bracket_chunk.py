"""Opt-in experiment: wrap prepositional chunks in brackets (default unchanged).

Chunk = preposition + following words (max ``MAX_WORDS``) up to punctuation,
another preposition, a closed-class word or a non-ASCII symbol.  Applied to
the *compressed* MorphoZip output (articles there are already dropped) and,
as a reference, to the raw source (where the bracket form drops articles).

Forms per bracket pair ``LR``:

* ``keep``  — ``in good fortune``  → ``in(good fortune)``
* ``space`` — ``in good fortune``  → ``in (good fortune)``
* ``raw``   — source ``to the store`` → ``to(store)`` (articles dropped
  inside); baseline is the untouched source, ``noart`` is articles dropped
  without brackets (isolates the bracket cost).

Usage::

    uv run python scripts/bracket_chunk.py [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/pd_corpus"
BRACKETS = ("()", "[]", "{}", "「」", '""')
MAX_WORDS = 3
PREPOSITIONS = frozenset(
    "in on at to of for with from by into onto upon about over under after before "
    "through between among against during without within near behind across".split()
)
ARTICLES = frozenset({"the", "a", "an"})
STOP = PREPOSITIONS | frozenset(
    "and or but that which who whom whose if as than so when while because is are was were "
    "be been am has have had do does did not it he she they we i me him her us them u".split()
)
_TOKEN_RE = re.compile(r"[^\W\d_]+|\s+|.", re.S)


def _is_word(t: str) -> bool:
    return t.isascii() and t.isalpha()


def chunks(text: str, drop_articles: bool = False) -> list[tuple[int, int, int, str]]:
    """(prep_end, start, end, inner) for each chunk; ``inner`` may drop articles.

    Offsets refer to ``unicodedata.normalize("NFC", text)`` so NFD accents stay
    attached to their base letter (``Zu\u0308rich`` is one non-ASCII word).
    """
    text = unicodedata.normalize("NFC", text)
    toks = [(m.start(), m.group(0)) for m in _TOKEN_RE.finditer(text)]
    out: list[tuple[int, int, int, str]] = []
    i = 0
    while i < len(toks):
        pos, t = toks[i]
        if not (_is_word(t) and t.lower() in PREPOSITIONS):
            i += 1
            continue
        prep_end = pos + len(t)
        j = i + 1
        words: list[str] = []
        start = end = None
        while j + 1 < len(toks) and toks[j][1] == " " and _is_word(toks[j + 1][1]):
            w = toks[j + 1][1]
            if drop_articles and w.lower() in ARTICLES and not words:
                j += 2
                continue
            if w.lower() in STOP or len(words) == MAX_WORDS:
                break
            if start is None:
                start = toks[j + 1][0]
            words.append(w)
            end = toks[j + 1][0] + len(w)
            j += 2
        nxt = toks[j + 1][1] if j + 1 < len(toks) and toks[j][1] == " " else (toks[j][1] if j < len(toks) else "")
        abbrev = words and end < len(text) and text[end] == "." and words[-1][:1].isupper() and len(words[-1]) <= 3
        if words and not abbrev and not (nxt and _is_word(nxt) and nxt.lower() not in STOP and len(words) == MAX_WORDS):
            out.append((prep_end, start, end, " ".join(words)))
        i = j if words else i + 1
    return out


def wrap(text: str, pair: str, form: str = "keep", drop_articles: bool = False) -> str:
    """Bracket every chunk; ``form`` is ``keep`` (glued), ``space`` or ``none``."""
    if form not in ("keep", "space", "none"):
        raise ValueError(f"unknown form {form!r}")
    text = unicodedata.normalize("NFC", text)
    left, right = (pair[0], pair[1]) if form != "none" else ("", "")
    parts: list[str] = []
    last = 0
    for prep_end, _s, end, inner in chunks(text, drop_articles):
        sep = " " if form != "keep" else ""
        parts.append(text[last:prep_end] + sep + left + inner + right)
        last = end
    parts.append(text[last:])
    return "".join(parts)


def measure(
    texts: dict[str, str], compress: Callable[[str], str], count: Callable[[str], int]
) -> dict[str, object]:
    """Token/byte totals per variant, plus adjacent-merge stats per bracket."""
    rows: dict[str, dict[str, int]] = {}

    def add(key: str, s: str) -> None:
        r = rows.setdefault(key, {"tokens": 0, "bytes": 0})
        r["tokens"] += count(s)
        r["bytes"] += len(s.encode("utf-8"))

    n_comp = n_raw = 0
    for name in sorted(texts):
        src = texts[name]
        comp = compress(src)
        n_comp += len(chunks(comp))
        n_raw += len(chunks(src, True))
        add("comp:base", comp)
        add("raw:base", src)
        add("raw:noart", wrap(src, "()", "none", True))
        for p in BRACKETS:
            add(f"comp:keep{p}", wrap(comp, p, "keep"))
            add(f"comp:space{p}", wrap(comp, p, "space"))
            add(f"raw:keep{p}", wrap(src, p, "keep", True))
    merge = {p: merges(p, count) for p in BRACKETS}
    return {"rows": rows, "chunks_comp": n_comp, "chunks_raw": n_raw, "merge": merge}


def merges(pair: str, count: Callable[[str], int], sample: tuple[str, ...] = ("to store", "in good fortune", "of wife")) -> dict[str, int]:
    """Extra tokens vs plain for glued ``prep(L)inner(R)`` on a small sample."""
    extra = 0
    for s in sample:
        prep, inner = s.split(" ", 1)
        extra += count(" " + prep + pair[0] + inner + pair[1]) - count(" " + s)
    return {"extra_tokens": extra, "samples": len(sample)}


def load_corpus(root: Path = CORPUS) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(root.rglob("*.txt"))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    import importlib.util
    import sys

    import tiktoken

    spec = importlib.util.spec_from_file_location("morpho_zip", ROOT / "MorphoZip/morpho_zip.py")
    mz = importlib.util.module_from_spec(spec)
    sys.modules["morpho_zip"] = mz
    spec.loader.exec_module(mz)  # type: ignore[union-attr]
    enc = tiktoken.get_encoding("o200k_base")
    res = measure(load_corpus(), mz.compress, lambda t: len(enc.encode(t)))
    if args.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0
    print(f"chunks: compressed={res['chunks_comp']} raw={res['chunks_raw']}")
    for k, v in res["rows"].items():
        print(f"{k}: tokens={v['tokens']} bytes={v['bytes']}")
    for p, v in res["merge"].items():
        print(f"merge {p}: +{v['extra_tokens']} tokens over {v['samples']} samples")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
