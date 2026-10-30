"""Opt-in experiment: noun-marking case schemes on MorphoZip output (A/B/C).

Schemes (applied to the *compressed* text only; default behaviour unchanged):

* ``A`` — as is (lowercase stays lowercase)
* ``B`` — noun first letter capitalised (``book`` → ``Book``)
* ``C`` — noun ALL CAPS (``book`` → ``BOOK``)

Noun detection is mechanical and reuses existing MorphoZip tables only:

1. lexicon = nouns listed in ``_COUNTER_SUBS`` (digit+noun counters) and in
   the #37 ``that/those + NOUN`` determiner rule (alternations parsed from the
   compiled patterns, ``s?``/``(?:s)?`` expanded);
2. position = an ASCII word right after a determiner from the closed
   inventories (articles + possessive pronouns + these/those) that is itself
   not a closed-class surface (any ``CLOSED_INVENTORIES`` slot / alias).

Usage::

    uv run python scripts/noun_case.py [--top 15] [--json]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/fixtures/pd_corpus"
SCHEMES = ("A", "B", "C")
DETERMINERS = frozenset(
    {"the", "a", "an", "my", "your", "his", "her", "its", "our", "their", "these", "those"}
)
_WORD_RE = re.compile(r"[A-Za-z]+")
_ALT_RE = re.compile(r"\(\?:([a-z|?()]+)\)|\(([a-z|]+)\)")


def load_morpho() -> ModuleType:
    """Import MorphoZip by path (same module the repo tests use)."""
    name = "morpho_zip"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / "MorphoZip/morpho_zip.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def expand_alternation(body: str) -> set[str]:
    """``cats?|fish|bus(?:es)?`` style → concrete words."""
    out: set[str] = set()
    for alt in body.split("|"):
        alt = alt.replace("(?:", "(")
        m = re.fullmatch(r"([a-z]+)(?:\(([a-z]+)\)\?|([a-z])\?)?", alt)
        if m is None:
            continue
        stem, grp, ch = m.group(1), m.group(2), m.group(3)
        out.add(stem)
        if grp or ch:
            out.add(stem + (grp or ch))
    return out


def noun_lexicon(mz: ModuleType) -> frozenset[str]:
    """Nouns already enumerated in MorphoZip rule tables."""
    words: set[str] = set()
    for pat, _ in mz._COUNTER_SUBS:
        for m in _ALT_RE.finditer(pat.pattern):
            words |= expand_alternation(m.group(1) or m.group(2))
    for pat, _ in determiner_rules(mz):
        for m in _ALT_RE.finditer(pat.pattern):
            body = m.group(1) or m.group(2)
            if body != "that|those":
                words |= expand_alternation(body)
    return frozenset(words)


def determiner_rules(mz: ModuleType) -> list[tuple[re.Pattern[str], object]]:
    """The #37 ``that/those + NOUN`` rule(s), located by pattern prefix."""
    found = []
    for value in vars(mz).values():
        if isinstance(value, list):
            for item in value:
                if (
                    isinstance(item, tuple)
                    and len(item) == 2
                    and isinstance(item[0], re.Pattern)
                    and item[0].pattern.startswith(r"\b(?:that|those)\s+(")
                ):
                    found.append(item)
    return found


def closed_surfaces(mz: ModuleType) -> frozenset[str]:
    """Every closed-class slot/alias (lowercased) — never tagged as noun."""
    out: set[str] = set()
    for inv in mz.CLOSED_INVENTORIES.values():
        out.update((*inv.canonical, *inv.extended, *inv.aliases, *inv.aliases.values()))
    return frozenset(s.lower() for s in out)


def noun_spans(text: str, lexicon: frozenset[str], closed: frozenset[str]) -> list[tuple[int, int]]:
    """(start, end) of words tagged as nouns in ``text``."""
    spans: list[tuple[int, int]] = []
    prev = ""
    prev_end = 0
    for m in _WORD_RE.finditer(text):
        w = m.group(0).lower()
        after_det = prev in DETERMINERS and text[prev_end : m.start()] == " "
        if w not in closed and (w in lexicon or after_det):
            spans.append((m.start(), m.end()))
        prev = w
        prev_end = m.end()
    return spans


def mark(text: str, scheme: str, spans: list[tuple[int, int]]) -> str:
    """Apply scheme A/B/C to the given noun spans."""
    if scheme not in SCHEMES:
        raise ValueError(f"unknown scheme {scheme!r}")
    if scheme == "A":
        return text
    parts: list[str] = []
    last = 0
    for s, e in spans:
        word = text[s:e]
        parts.append(text[last:s])
        parts.append(word[:1].upper() + word[1:] if scheme == "B" else word.upper())
        last = e
    parts.append(text[last:])
    return "".join(parts)


def measure(
    texts: dict[str, str],
    compress: Callable[[str], str],
    count: Callable[[str], int],
    lexicon: frozenset[str],
    closed: frozenset[str],
) -> dict[str, object]:
    """Per-scheme token/byte totals + per-word worst cases."""
    totals = {s: {"tokens": 0, "bytes": 0} for s in SCHEMES}
    words: dict[str, dict[str, object]] = {}
    for name in sorted(texts):
        src = texts[name]
        comp = compress(src)
        spans = noun_spans(comp, lexicon, closed)
        src_words = {w.lower() for w in _WORD_RE.findall(src)}
        for s in SCHEMES:
            out = mark(comp, s, spans)
            totals[s]["tokens"] += count(out)
            totals[s]["bytes"] += len(out.encode("utf-8"))
        for a, b in spans:
            w = comp[a:b].lower()
            if w in words:
                words[w]["n"] += 1
                continue
            costs = {s: count(" " + mark(w, s, [(0, len(w))])) for s in SCHEMES}
            words[w] = {
                "n": 1,
                "A": costs["A"],
                "B": costs["B"],
                "C": costs["C"],
                "short_form": w not in src_words,
                "rare": costs["A"] >= 2,
            }
    return {
        "totals": totals,
        "words": words,
        "noun_tokens": sum(int(v["n"]) for v in words.values()),
        "short_forms": short_form_costs(texts, compress, count),
    }


def short_form_costs(
    texts: dict[str, str], compress: Callable[[str], str], count: Callable[[str], int]
) -> dict[str, dict[str, int]]:
    """Stress view: every ASCII word the compressor introduced (absent from the
    source), costed as if marked B/C — regardless of noun tagging."""
    out: dict[str, dict[str, int]] = {}
    for name in sorted(texts):
        src_words = {w.lower() for w in _WORD_RE.findall(texts[name])}
        for w in _WORD_RE.findall(compress(texts[name])):
            lw = w.lower()
            if lw in src_words:
                continue
            if lw in out:
                out[lw]["n"] += 1
                continue
            out[lw] = {"n": 1, **{s: count(" " + mark(lw, s, [(0, len(lw))])) for s in SCHEMES}}
    return out


def worst(words: dict[str, dict[str, object]], scheme: str, top: int) -> list[tuple[str, dict[str, object]]]:
    """Words with the largest per-occurrence token increase vs A."""
    rows = [(w, v) for w, v in words.items() if int(v[scheme]) > int(v["A"])]
    rows.sort(key=lambda r: (-(int(r[1][scheme]) - int(r[1]["A"])) * int(r[1]["n"]), r[0]))
    return rows[:top]


def rank_short_forms(sf: dict[str, dict[str, int]], top: int) -> list[tuple[str, dict[str, int]]]:
    """Short forms by total C-vs-A token increase (then name)."""
    return sorted(sf.items(), key=lambda r: (-(r[1]["C"] - r[1]["A"]) * r[1]["n"], r[0]))[:top]


def load_corpus(root: Path = CORPUS) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(root.rglob("*.txt"))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    mz = load_morpho()
    res = measure(
        load_corpus(), mz.compress, lambda t: len(enc.encode(t)), noun_lexicon(mz), closed_surfaces(mz)
    )
    if args.json:
        print(json.dumps(res, indent=1))
        return 0
    print(f"noun occurrences: {res['noun_tokens']}  distinct: {len(res['words'])}")
    for s in SCHEMES:
        t = res["totals"][s]
        print(f"{s}: tokens={t['tokens']} bytes={t['bytes']}")
    for s in ("B", "C"):
        for label, key in (("short_form", "short_form"), ("rare", "rare"), ("all", None)):
            sub = {w: v for w, v in res["words"].items() if key is None or v[key]}
            print(f"-- worst {s} ({label})")
            for w, v in worst(sub, s, args.top):
                print(f"  {w}: A={v['A']} {s}={v[s]} n={v['n']}")
    print("-- compressor-introduced short forms (stress, B/C vs A)")
    for w, v in rank_short_forms(res["short_forms"], args.top):
        print(f"  {w}: A={v['A']} B={v['B']} C={v['C']} n={v['n']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
