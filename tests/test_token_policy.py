"""オーナー方針の回帰テスト: 英語よりトークンが増えるマッピングを禁止する。

o200k_base で先頭スペース込み (' word') を数える。出力が英語の入力（または
記号の英語正規形）より多トークンなら NG。同トークンは UTF-8 バイトが真に
少ない場合のみ許可。対象: MorphoZip の _SUBS / _PHRASE_GRAMMAR /
_COUNTER_SUBS（リテラル入力のみ）、*_CANONICAL / *_EXTENDED 在庫、
C ledger (conventions.json) の from→to。
"""

from __future__ import annotations

import json
import re

import pytest

from tests._helpers import ROOT, load

tiktoken = pytest.importorskip("tiktoken")
_ENC = tiktoken.get_encoding("o200k_base")

# 外国語（非英語）ASCII 入力。英語入力ではないので、入力ではなく出力記号の
# 英語グロスと比較する（グロス不明なら入力と比較）。
FOREIGN_INPUTS = frozenset(
    """ils il elle ella él tu tú du usted ustedes aus con avec mit vor nach
    para pour für fur sin desde depuis bei y et und oder ou esa cela
    estos estas esos esas hacia vers""".split()
)

# 記号 → 英語正規形（expand で戻らない記号用）。
GLOSS = {
    "4": "for", "w/": "with", "!can": "cannot", "∈": "in", "〜": "until",
    "→": "to", "re:": "about", "=": "called", "!": "not", "+": "also",
    "&": "and", "/": "or", "≥": "at least", "≤": "at most", "ça": "this",
    "eso": "that", "U": "you", "←": "from", "e.g.": "for example",
    "i.e.": "that is", "esp.": "especially", "˅": "extremely",
    "∴": "therefore", "∵": "because", "君": "you", "彼": "he",
}

_ASCII_WORDS = re.compile(r"^[A-Za-z][A-Za-z' ]*$")
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def tok(s: str) -> int:
    return len(_ENC.encode(" " + s))


def loses(en: str, out: str) -> bool:
    t_en, t_out = tok(en), tok(out)
    if t_out != t_en:
        return t_out > t_en
    return len(out.encode()) >= len(en.encode())


def _literal(pattern: str) -> str | None:
    s = re.sub(r"^\(\?[a-z]+\)", "", pattern).replace(r"\b", "")
    s = s.replace(r"\s+", " ").replace(r"\ ", " ")
    return s if re.fullmatch(r"[^\\()\[\]|?*+{}.^$]+", s) else None


def _gloss(m, out: str) -> str | None:
    g = GLOSS.get(out)
    if g is None:
        ex = m.expand(out)
        g = ex if ex != out and _ASCII_WORDS.match(ex) else None
    return g


def _refs(m, src: str, out: str) -> list[str]:
    """入力英語と、出力記号の英語正規形の両方に勝つ必要がある。"""
    refs = []
    r = _english_ref(m, src, out)
    if r:
        refs.append(r)
    g = _gloss(m, out)
    if g and g != out:
        refs.append(g)
    return refs


def _english_ref(m, src: str, out: str) -> str | None:
    """Reference English the output must beat (None = nothing to check)."""
    if src == out:
        return None
    gloss = GLOSS.get(out)
    if gloss is None:
        ex = m.expand(out)
        gloss = ex if ex != out and _ASCII_WORDS.match(ex) else None
    src_is_english = (
        _ASCII_WORDS.match(src) is not None and src.lower() not in FOREIGN_INPUTS
    )
    if src_is_english:
        return src
    if _ASCII_WORDS.match(out) and gloss is None:
        return None  # 出力自体が英語（例: 彼ら→they）
    return gloss or src


@pytest.fixture(scope="module")
def m():
    return load("morpho_zip", "MorphoZip/morpho_zip.py")


def _alternatives(pattern: str) -> list[str]:
    s = re.sub(r"^\(\?[a-z]+\)", "", pattern)
    if re.search(r"\(\?<?[=!]", s):
        s = re.sub(r"\(\?<?[=!][^)]*\)", "", s)
    out = []
    for alt in s.split("|"):
        w = _literal(alt)
        if w:
            out.append(w)
    return out


def collect_rule_losers(m) -> list[str]:
    bad = []
    for name in ("_SUBS", "_PHRASE_GRAMMAR", "_COUNTER_SUBS"):
        for pat, out in getattr(m, name):
            if not isinstance(out, str) or "\\" in out or not out.strip():
                continue
            out = out.strip()  # CJK 文脈では英単語を空白で区切って出力
            for src in _alternatives(pat.pattern):
                for ref in _refs(m, src, out):
                    if loses(ref, out):
                        bad.append(f"{name}: {src!r}->{out!r} (ref {ref!r})")
    return bad


def collect_canonical_losers(m) -> list[str]:
    bad = []
    for n in dir(m):
        if not (n.endswith("_CANONICAL") or n.endswith("_EXTENDED")):
            continue
        inv = getattr(m, n)
        if not isinstance(inv, tuple):
            continue  # alias dicts: keys are inputs; values must be in a tuple
        for s in inv:
            if not isinstance(s, str):
                continue
            ref = _english_ref(m, "\0", s)
            if ref and ref != "\0" and loses(ref, s):
                bad.append(f"{n}: {s!r} (ref {ref!r})")
    return bad


def collect_ledger_losers(m) -> list[str]:
    data = json.loads((ROOT / "ShorthandEdge/ledger/conventions.json").read_text(encoding="utf-8"))
    bad = []
    for c in data["conventions"]:
        to = c.get("to")
        if not isinstance(to, str) or not to:
            continue
        for f in c.get("from", []):
            if not isinstance(f, str):
                continue
            for ref in _refs(m, f, to):
                if loses(ref, to):
                    bad.append(f"{c['id']}: {f!r}->{to!r} (ref {ref!r})")
    return bad


def test_no_token_losing_rules(m):
    assert collect_rule_losers(m) == []


def test_no_token_losing_canonicals(m):
    assert collect_canonical_losers(m) == []


def test_no_token_losing_ledger(m):
    assert collect_ledger_losers(m) == []
