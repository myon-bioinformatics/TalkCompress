"""Calibrate the stdlib ``estimate_tokens`` toward o200k_base (dev-only; needs tiktoken).

Writes ``TesseraTalk/fixtures/o200k_calib.json``, the small data table that the
runtime estimator reads (the runtime itself never imports tiktoken):

* ``en_costs``: 2-bit packed o200k cost (1..4, capped) of every word in
  ``en_wordlist.txt`` in file order, scored as ``" " + word``.  Derived from the
  wordlist only, never from the tense matrix.
* ``contractions``: o200k cost of a fixed, documented list of English
  contractions (``we've`` = 1, ``hasn't`` = 2, ...).
* ``len_table``: fallback cost per (script class, word length) for words not in
  any table, the mode over *training* words only.
* ``exceptions``: training-split non-English words whose cost differs from the
  fallback.

Anti-overfitting: matrix cells are split deterministically by
``sha1(src) % 5 == 0`` -> held-out (20%).  Only training cells feed
``len_table``/``exceptions``; ``--report`` scores train vs held-out cells and
the independent natural sample ``token_natural_sample.json``.

Usage: ``uv run python scripts/calibrate_estimate.py [--write] [--report]``
"""
from __future__ import annotations

import argparse
import base64
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import tense_matrix as tm  # noqa: E402

FIX = ROOT / "TesseraTalk" / "fixtures"
CALIB = FIX / "o200k_calib.json"
WORDLIST = FIX / "en_wordlist.txt"
NATURAL = FIX / "token_natural_sample.json"

CONTRACTIONS = [
    f"{p}{s}" for p in ("i", "you", "we", "they", "he", "she", "it", "that", "there", "who", "what")
    for s in ("'m", "'re", "'ve", "'ll", "'d", "'s")
] + [f"{v}n't" for v in ("is", "are", "was", "were", "have", "has", "had", "do", "does", "did",
                         "will", "would", "can", "could", "should", "must", "might", "need")] + ["won't", "can't", "shan't", "ain't"]


# Hand-written, documented suffix deltas (linguistic prior, not fitted): Romance
# 1sg simple futures (-ré es, -rei pt, -rai fr, -rò it) split the ending off in o200k
# (tomaré = tom+aré, chamarei = cham+arei); the matrix has too few of them to learn.
# Stored as a minimum cost (``suffix_floor``) because the base length cost varies.
SUFFIX_FLOOR = {"ré": 2, "rei": 2, "rai": 2, "rò": 2}


_CJK_RUN = "\u3400-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF"


def cjk_space_vocab() -> list[str]:
    """CJK / kana / Hangul strings of 1-4 chars that o200k merges with a leading space."""
    import re

    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    pat = re.compile(f"^ [{_CJK_RUN}]{{1,4}}$")
    out = set()
    for i in range(enc.n_vocab):
        try:
            t = enc.decode_single_token_bytes(i).decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            continue
        if pat.match(t):
            out.add(t[1:])
    return sorted(out)


def symbol_vocab() -> str:
    """Non-ASCII, non-alphanumeric chars that are one o200k token with a leading space."""
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    out = set()
    for i in range(enc.n_vocab):
        try:
            t = enc.decode_single_token_bytes(i).decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            continue
        if len(t) == 2 and t[0] == " " and ord(t[1]) > 127 and not t[1].isalnum() and not t[1].isspace():
            out.add(t[1])
    return "".join(sorted(out))


def cjk_vocab() -> list[str]:
    """o200k vocabulary entries that are 2-4 CJK / kana / Hangul chars (one token each)."""
    import re

    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    pat = re.compile(f"^[{_CJK_RUN}]{{2,4}}$")
    out = set()
    for i in range(enc.n_vocab):
        try:
            t = enc.decode_single_token_bytes(i).decode("utf-8").lstrip(" ")
        except (KeyError, UnicodeDecodeError):
            continue
        if pat.match(t):
            out.add(t)
    return sorted(out)


def _vocab_strings():
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    for i in range(enc.n_vocab):
        try:
            yield enc.decode_single_token_bytes(i).decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            continue


def thai_vocab() -> tuple[list[str], list[str]]:
    """o200k tokens that are 2+ Thai chars, and Thai strings o200k merges with a leading space."""
    import re

    pat = re.compile("^( ?)([\u0E00-\u0E7F]+)$")
    plain, sp = set(), set()
    for t in _vocab_strings():
        m = pat.match(t)
        if m:
            if m.group(1):
                sp.add(m.group(2))
            elif len(m.group(2)) >= 2:
                plain.add(m.group(2))
    return sorted(plain), sorted(sp)


def vi_space_vocab() -> list[str]:
    """Non-ASCII words of Vietnamese letters only that are one " word" token in o200k (case-sensitive)."""
    mod = _est_mod()
    return sorted(t[1:] for t in _vocab_strings()
                  if t[:1] == " " and not t[1:].isascii() and mod._VI_WORD.fullmatch(t[1:]))


# Emoji code points costed one by one (measured: a ZWJ / skin-tone sequence costs the sum
# of its parts). Digits are o200k costs of each isolated code point, per range.
EMOJI_RANGES = ((0x2190, 0x2BFF), (0x200D, 0x200D), (0xFE0F, 0xFE0F), (0x1F000, 0x1FAFF), (0xE0020, 0xE007F))


def emoji_costs() -> dict:
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    ranges = [[a, "".join(str(min(len(enc.encode(chr(c))), 9)) for c in range(a, b + 1))] for a, b in EMOJI_RANGES]
    vs16 = "".join(chr(c) for a, b in EMOJI_RANGES for c in range(a, b + 1)
                   if c not in (0x200D, 0xFE0F) and len(enc.encode(chr(c) + "\ufe0f")) == 1)
    return {"ranges": ranges, "vs16": vs16}


def heldout(src: str) -> bool:
    return int(hashlib.sha1(src.encode("utf-8")).hexdigest(), 16) % 5 == 0


def _est_mod():
    from tests._helpers import load

    return load("tessera_talk", "TesseraTalk/tessera_talk.py")


def _words(wl: Path) -> list[str]:
    return [w.strip() for w in wl.read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")]


def cells_split():
    cells = json.loads(tm.REPORT_PATH.read_text(encoding="utf-8"))["cells"]
    tr = [c for c in cells if not heldout(c["src"])]
    ho = [c for c in cells if heldout(c["src"])]
    return tr, ho


# Hand-curated runtime banks (not the tense matrix): their sources and candidate
# forms are the estimator's real decision space, so they join the training side.
TRAIN_BANKS = ("zh_de_phrases", "pt_el_latin_phrases", "pt_el_latin_tense", "es_fr_tense", "translations")


def bank_strings() -> set[str]:
    out: set[str] = set()

    def walk(x, key=""):
        if isinstance(x, str):
            if key in ("from", "to", "form", "cand") and x.strip():
                out.add(x)
        elif isinstance(x, list):
            for y in x:
                walk(y, key)
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(v, "cand" if key == "candidates" else k)

    for b in TRAIN_BANKS:
        for e in json.loads((FIX / f"{b}.json").read_text(encoding="utf-8"))["entries"]:
            walk(e)
    return out


def cell_strings(cells) -> set[str]:
    out = set()
    for c in cells:
        out.add(c["src"])
        if "best" in c:
            out |= {c.get("en_best", c["src"]), c["best"]}
    return out


def build() -> dict:
    mod = _est_mod()
    o = tm.o200k_tokens
    words = _words(WORDLIST)
    costs = [min(o(w), 4) - 1 for w in words]
    packed = bytearray((len(costs) + 3) // 4)
    for i, c in enumerate(costs):
        packed[i >> 2] |= c << ((i & 3) * 2)
    en = set(words)
    tr, _ = cells_split()
    pieces = collections.Counter()
    cased: set[str] = set()
    for s in sorted(cell_strings(tr) | bank_strings()):
        for kind, p in mod._pretokens(s):
            if kind in ("w", "o"):
                pieces[p.lower()] += 1
                if p != p.lower():
                    cased.add(p)
    cost = {p: o(p) for p in pieces}
    buckets = collections.defaultdict(collections.Counter)
    for p, c in cost.items():
        if p not in en and "'" not in p:
            buckets[f"{mod._wclass(p)}{len(p)}"][c] += pieces[p] if p.isascii() else 1  # ASCII: frequency-weighted; accented: unique words
    len_table = {k: v.most_common(1)[0][0] for k, v in sorted(buckets.items())}
    contractions = {w: o(w) for w in CONTRACTIONS}
    # suffix rules: last-2/3-letter endings shared by >= 3 unique training words of >= 5
    # letters whose cost delta vs the length fallback is uniform (>= 75%) and non-zero.
    suf = collections.defaultdict(collections.Counter)
    for p, c in cost.items():
        if p not in en and "'" not in p and len(p) >= 5:
            for k in (p[-3:], p[-2:]):
                suf[k][(c, len_table.get(f"{mod._wclass(p)}{len(p)}"))] += 1
    suffixes = {}
    for k, v in sorted(suf.items()):
        n = sum(v.values())
        if n < 3:
            continue
        deltas = collections.Counter()
        for (c, base), m in v.items():
            if base is not None:
                deltas[c - base] += m
        if deltas:
            d, m = deltas.most_common(1)[0]
            if m / n >= 0.75:
                suffixes[k] = d
    # keep a zero delta only where it overrides a non-zero 2-letter parent
    suffixes = {k: d for k, d in suffixes.items() if d or (len(k) == 3 and suffixes.get(k[1:], 0))}
    calib = {"len_table": len_table, "contractions": contractions, "suffixes": suffixes,
             "suffix_floor": SUFFIX_FLOOR, "cjk_vocab": " ".join(cjk_vocab()),
             "cjk_space_vocab": " ".join(cjk_space_vocab()), "symbol_vocab": symbol_vocab(),
             "thai_vocab": " ".join(thai_vocab()[0]), "thai_space_vocab": " ".join(thai_vocab()[1]),
             "vi_space_vocab": " ".join(vi_space_vocab()), "emoji_costs": emoji_costs()}
    exc = {}
    for p, c in sorted(cost.items()):
        if p in en or p in contractions:
            continue
        if mod._fallback_cost(p, len_table, suffixes, SUFFIX_FLOOR) != c:
            exc[p] = c
    # capitalised training words whose o200k cost differs from the lowercase rule (" Bahnhof" = 1)
    cal = {**calib, "exceptions": exc, "contractions": contractions,
           "en": {w: c + 1 for w, c in zip(words, costs)}, "cased": {}}
    exc_cased = {p: o(p) for p in sorted(cased) if mod._word_cost(p, cal) != o(p)}
    return {
        "notes": ["Generated by scripts/calibrate_estimate.py --write; do not edit by hand. "
                  "o200k_base costs (leading space) for the stdlib estimate_tokens; see that script for provenance."],
        "wordlist_sha256": hashlib.sha256(WORDLIST.read_bytes()).hexdigest(),
        "en_costs": base64.b64encode(bytes(packed)).decode("ascii"),
        **calib,
        "exceptions": exc,
        "exceptions_cased": exc_cased,
    }


def report() -> dict:
    sys.path.insert(0, str(ROOT / "scripts"))
    import tokenizer_compat as tc

    mod = _est_mod()
    est_sp = lambda s: mod.estimate_tokens(" " + s)  # noqa: E731
    o = tm.o200k_tokens
    tr, ho = cells_split()
    trs = cell_strings(tr)
    hos = cell_strings(ho) - trs

    def flips(cells):
        n = f = 0
        ex = []
        for c in cells:
            if "best" not in c or c["status"] not in ("adopt", "reject"):
                continue
            if c.get("parity_verb") is not None and c["status"] == "reject":
                continue
            n += 1
            if tc._beats(c["best"], c["src"], o) != tc._beats(c["best"], c["src"], est_sp):
                f += 1
                ex.append(c["src"] + " -> " + c["best"])
        return n, f, ex[:8]

    nat = json.loads(NATURAL.read_text(encoding="utf-8"))["sample"]
    out = {}
    for name, xs in (("train", trs), ("heldout", hos), ("natural", nat)):
        xs = sorted(xs)
        out[name] = {"n": len(xs), "exact": sum(est_sp(s) == o(s) for s in xs),
                     "abs_err": sum(abs(est_sp(s) - o(s)) for s in xs)}
    for name, cs in (("train", tr), ("heldout", ho)):
        n, f, ex = flips(cs)
        out[name] |= {"cells": n, "flips": f, "flip_examples": ex}
    out["natural_misses"] = [(s, est_sp(s), o(s)) for s in nat if est_sp(s) != o(s)][:15]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.write:
        CALIB.write_text(json.dumps(build(), ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        print("wrote", CALIB.relative_to(ROOT))
    if a.report:
        print(json.dumps(report(), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
