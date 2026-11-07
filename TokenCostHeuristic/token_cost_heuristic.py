"""TokenCostHeuristic: shared o200k-calibrated token-cost estimator.

Extracted from SentenceCalibratedMosaic (former SentenceCalibratedMosaic). Every unit imports
``estimate_tokens`` from here, so no subproject depends on the mosaic body for
token costs. Data: ``fixtures/o200k_calib.json`` and ``fixtures/en_wordlist.txt``.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

_INDIC_CHARS_PER_TOKEN = 3
# Code points per o200k token for a Brahmic / SE-Asian run, by Unicode block (coarse tiers
# measured on Tatoeba, seed 1104). Lao / Tibetan have almost no o200k merges (~1.3-2 tokens/char).
_BRAHMIC_RATES = (
    (0x0A00, 0x0A7F, 1.75),  # Gurmukhi
    (0x0A80, 0x0AFF, 2.5),   # Gujarati
    (0x0B00, 0x0B7F, 1.0),   # Oriya (Tatoeba ori, seed 1104 held-out)
    (0x0C00, 0x0CFF, 2.5),   # Telugu, Kannada
    (0x0D80, 0x0DFF, 1.75),  # Sinhala
    (0x0E80, 0x0EFF, 0.5),   # Lao
    (0x0F00, 0x0FFF, 0.75),  # Tibetan (tsheg U+0F0B included)
    (0x1000, 0x109F, 1.75),  # Myanmar
    (0x1780, 0x17FF, 1.5),   # Khmer
)


def _brahmic_rate(ch: str) -> float:
    o = ord(ch)
    for lo, hi, r in _BRAHMIC_RATES:
        if lo <= o <= hi:
            return r
    return _INDIC_CHARS_PER_TOKEN  # Bengali, Tamil, Malayalam, Devanagari
# Nonspacing marks o200k splits off one token each inside a word: Hebrew points and
# Arabic harakat (U+064B–065F, U+0670, Quranic U+06D6–06ED), Devanagari virama.
# (Other Devanagari Mn signs stay merged: counting them overestimated real text.)
# A virama followed by a consonant (a conjunct: क्ष ज्ञ त्र …) is not a split point;
# o200k merges conjuncts (क्ष ज्ञ त्र = 1 token each). Word-final / ZWJ / ZWNJ viramas still split.
_SCRIPT_MARKS_RE = re.compile(
    "(?:(?!\u094D[\u0915-\u0939\u0958-\u095F\u0978-\u097F])"
    "[\u0591-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7"
    "\u064B-\u065F\u0670\u06D6-\u06DC\u06DF-\u06E4\u06E7\u06E8\u06EA-\u06ED"
    "\u094D])+"
)

_CJK_CHAR = re.compile(r"[\u3400-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]")
_LATIN_WORD = re.compile(r"[A-Za-z0-9\u00C0-\u024F\u1E00-\u1EFF']+")
# Latin Extended Additional (Vietnamese stacked diacritics: ạ ế ộ …): BPE vocabularies
# rarely merge these, so each such char costs ≈ 1 extra token on top of the subword rule.
_LATIN_EXT_ADD = re.compile(r"[\u1E00-\u1EFF]")
# Thai (U+0E00–U+0E7F): unspaced script, ≈ 1 token per character in GPT-style BPE.
_THAI_CHAR = re.compile(r"[\u0E00-\u0E7F]")
# Cyrillic / Arabic / Greek letter-runs (Devanagari is i-class)
_OTHER_WORD = re.compile(
    r"[\u0400-\u04FF\u0600-\u06FF\u0370-\u03FF\u1F00-\u1FFF]+"  # Devanagari is i-class
)


DEFAULT_O200K_CALIB = _FIXTURES_DIR / "o200k_calib.json"
DEFAULT_EN_WORDLIST = _FIXTURES_DIR / "en_wordlist.txt"
# o200k-style pre-tokens: a Latin letter-run (+ optional English contraction
# suffix, which o200k keeps in the same pre-token: ``we've`` = 1), digit groups
# of <= 3, one CJK/kana/Hangul/Thai char, an other-script run, a punctuation run.
_PRETOKEN = re.compile(
    # Archaic Hangul jamo (U+1100–11FF, A960–A97F, D7B0–D7FF) and ideographic variation
    # selectors (U+E0100–E01EF): o200k has no merges for them, one token per UTF-8 byte.
    r"(?P<j>[\u1100-\u11FF\uA960-\uA97F\uD7B0-\uD7FF\U000E0100-\U000E01EF]+)|"
    # Combining marks that survive NFC (x + U+0301, i + U+0307) stay inside the word.
    r"(?P<w>[A-Za-z\u00C0-\u024F\u1E00-\u1EFF][A-Za-z\u00C0-\u024F\u1E00-\u1EFF\u0300-\u036F]*"
    r"(?:['\u2019](?:s|t|re|ve|m|ll|d)(?![A-Za-z]))?)"
    r"|(?P<d>\d{1,3})"
    r"|(?P<k>[\u3400-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]+)"
    r"|(?P<c>[\u0E00-\u0E7F]+)"
    # Non-BMP chars outside o200k's vocabulary (CJK Ext B–H, Supplementary PUA-A/B):
    # o200k falls back to raw UTF-8 bytes, so each costs ≈ its 4 bytes.
    r"|(?P<b>[\U00020000-\U000323AF\U000F0000-\U0010FFFF])"
    # Emoji runs (skin-tone modifiers, ZWJ sequences, VS16, keycap U+20E3): costed from a measured table.
    # A text-default symbol + VS16 ("☺️", "©️", "™️") is an emoji run too, so it is costed
    # from the measured table instead of as a punctuation run.
    # Fullwidth digits / letters (not punctuation, which CJK text uses) / halfwidth kana / math alphanumerics: per-code-point measured costs.
    r"|(?P<u>[\uFF10-\uFF19\uFF21-\uFF3A\uFF41-\uFF5A\uFF61-\uFF9F\U0001D400-\U0001D7FF]+)"
    # Ethiopic syllables: 2 o200k tokens each.
    r"|(?P<t>[\u1200-\u139F\u2D80-\u2DDF\uAB00-\uAB2F]+)"
    r"|(?P<e>\ufe0f?\u20e3"
    r"|(?:[\u00A9\u00AE\u203C\u2049\u2122\u2139\u2190-\u2BFF\u3030\u303D\u3297\u3299]\ufe0f)+"
    r"(?:[\u200d\U0001F000-\U0001FAFF][\u2190-\u2BFF\u200d\ufe0f\U0001F000-\U0001FAFF\U000E0020-\U000E007F]*)?"
    r"|[\u2190-\u2BFF\u200d\ufe0f\U0001F000-\U0001FAFF\U000E0020-\U000E007F]*"
    r"[\u200d\U0001F000-\U0001FAFF][\u2190-\u2BFF\u200d\ufe0f\U0001F000-\U0001FAFF\U000E0020-\U000E007F]*)"
    # Brahmic / SE-Asian scripts outside the calibrated tables (Devanagari … Sinhala,
    # Myanmar, Khmer). Consonants are letters but vowel signs / viramas are marks, so
    # neither ``x`` nor ``p`` covered a whole word and the consonants cost 0.
    # Devanagari used to be an ``o`` word (ceil(len/4)) and under-counted Tatoeba hi/mr;
    # folding it into ``i`` at the default rate 3 matches held-out o200k (seed 1104).
    r"|(?P<i>[\u0900-\u097F]+|[\u0980-\u0DFF]+|[\u0E80-\u0FFF]+|[\u1000-\u109F]+|[\u1780-\u17FF]+)"
    r"|(?P<o>[\u0400-\u04FF\u0600-\u06FF\u0370-\u03FF\u1F00-\u1FFF]+)"
    # Letters of any other script (Hebrew, Armenian, Georgian, …) must not cost 0.
    # Indic / SE-Asian blocks keep the main-branch path: ceil(len/4) split at every vowel
    # sign drifts further from o200k there. Fixed ranges, not unicodedata, so the result
    # does not depend on the Python version.
    # Hebrew points (niqqud / cantillation, Mn) stay inside the word like Latin marks.
    r"|(?P<x>(?:(?![\u0900-\u109F\u1780-\u17FF\u1200-\u139F\u2D80-\u2DDF\uAB00-\uAB2F\uFF10-\uFF19\uFF21-\uFF3A\uFF41-\uFF5A\uFF61-\uFF9F\U0001D400-\U0001D7FF\U00020000-\U000323AF])[^\W\d_])"
    r"(?:(?![\u0900-\u109F\u1780-\u17FF\u1200-\u139F\u2D80-\u2DDF\uAB00-\uAB2F\uFF10-\uFF19\uFF21-\uFF3A\uFF41-\uFF5A\uFF61-\uFF9F\U0001D400-\U0001D7FF\U00020000-\U000323AF])[^\W\d_]|[\u0591-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7])*)"
    # Costly whitespace: in Python ``\s`` so ``p`` would miss them, but o200k charges.
    r"|(?P<n>[\x85\xa0\u1680\u2028\u2029\u202f\u205f]+)"
    # a keycap tail (U+FE0F U+20E3) is not swallowed by the symbol run: "#️⃣" = "#" + "️⃣" = 2
    r"|(?P<p>(?:(?!\ufe0f?\u20e3)[^\w\s])+)",
    re.IGNORECASE,
)
_GREEK = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")
# Historical name: this range covers Latin Extended-A AND Extended-B, not a
# Polish/Czech language detector. Other languages and transliterations can match.
_LATIN_EXT_A = re.compile(r"[\u0100-\u024F]")
# Author-reported #108 exceptions (Turkish ı ğ ş İ, Vietnamese đ): no +1 in
# the class-s heuristic. These are not a general accuracy guarantee; see README.
_O200K_MERGED_EXT = "\u0131\u0130\u011f\u011e\u015f\u015e\u0111\u0110"
_LATIN_EXT_SPLIT = re.compile(r"[^\W\d_" + _O200K_MERGED_EXT + r"]")
# Vietnamese syllable: tone letters U+1EA0–U+1EF9 only (not transliteration ḥ ṣ ẓ / ā ī),
# plus ASCII and the Vietnamese-only Latin letters đ ă ơ ư ĩ ũ and Latin-1 accents.
_VI_SYLLABLE = re.compile(r"[a-z\u00C0-\u00FF\u0111\u0103\u01A1\u01B0\u0129\u0169]*[\u1EA0-\u1EF9][a-z\u00C0-\u00FF\u0111\u0103\u01A1\u01B0\u0129\u0169\u1EA0-\u1EF9]*", re.IGNORECASE)
_VI_LETTER = re.compile(r"[\u1EA0-\u1EF9]")
_VI_RARE = re.compile("[\u1EB4\u1EB5\u1EB2\u1EB3\u1EAA\u1EAB\u1EBC\u1EBD\u1EF8\u1EF9\u1EF6\u1EF7\u1EF4\u1EF5]")  # ẵ ẳ ẫ ẽ ỹ ỷ ỵ
_COMBINING_RE = re.compile(r"[\u0300-\u036F]")
# A word spelled only with Vietnamese letters (ASCII + Latin-1 accents + đ ă ơ ư ĩ ũ + tone letters).
_VI_WORD = re.compile(r"[a-z\u00C0-\u00FF\u0111\u0103\u01A1\u01B0\u0129\u0169\u1EA0-\u1EF9]+", re.IGNORECASE)
_CALIB: dict | None = None

# Per-code-point o200k costs (one digit each, measured with tiktoken; o200k cost of a run
# equals the sum of its code points here): fullwidth ASCII U+FF01–FF5E, halfwidth kana /
# Hangul U+FF61–FF9F, Mathematical Alphanumeric Symbols U+1D400–1D7FF. Regenerate with
# ``scripts/gen_unicode_range_costs.py``.
_FULLWIDTH_COSTS = (
    "12221121111111111111111111111111111111122212111121112222221111112222122222221222"
    "22222212222121"
)
_HALFWIDTH_COSTS = (
    "121112222222221121222222222222222222222212222222222222222221211"
)
_MATH_ALNUM_COSTS = (
    "22222222222222222222222222222222222222222222222222222222222222223333333333333333"
    "23333333333323333333333333323333333333332333333333333333333333333333333333333333"
    "33332333333333333333333333333333333333333333333333333333333332333333333323333333"
    "23332333233333333333333333333333333333333333333333333333333333333333333333333333"
    "33333233333323333333333333333333333333333333333333333333333333333333333333333333"
    "33333333333333333333333333333333333333333333333322222222222222222222222222222222"
    "22222222222222222222222222222222333333333333333322333333333333333333333333333333"
    "33333333333333333323333333333333333333333333333333333333333333333333333333333333"
    "33333333333323333333333333333333333333333333333333333333333333333333233323333333"
    "33333333333333333333333333333333233333333333333333333333333333333333333323333333"
    "33333333333333333333233333333333333333333333333333333333333333333333333333333333"
    "33333333333333333333333333323233333333333333333333333333333333333333333333333333"
    "3233333333333333333333333333333333333233333333333332333333333333"
)
_RANGE_COSTS = ((0xFF01, _FULLWIDTH_COSTS), (0xFF61, _HALFWIDTH_COSTS), (0x1D400, _MATH_ALNUM_COSTS))


def _range_cost(run: str) -> int:
    n = 0
    for ch in run:
        cp = ord(ch)
        for start, table in _RANGE_COSTS:
            if start <= cp < start + len(table):
                n += int(table[cp - start])
                break
        else:
            n += len(ch.encode("utf-8"))
    return n


# Word-length factor for scripts o200k merges poorly (measured mean cost of " word" by
# length on Tatoeba even-id rows): tokens ≈ a * len + b. Hebrew / Arabic (incl. Urdu) /
# Georgian / Greek letters only; marked words keep the split-at-marks path. Shorter words
# than ``min_len`` keep the legacy rules: frequent short Hebrew / Greek words are often one
# o200k token (" שלום" = 1), while 4-letter Arabic / Urdu / Georgian words average 1.5–1.8.
_SCRIPT_FACTOR = (
    (re.compile(r"[\u05D0-\u05EA\uFB1D-\uFB4F]+"), 0.50, 0.0, 5),  # held-out heb seed 1104
    (re.compile(r"[\u0620-\u064A\u066E-\u06D3\u06D5\u06EE-\u06FF]+"), 0.30, 0.3, 4),
    (re.compile(r"[\u10A0-\u10FF\u1C90-\u1CBF]+"), 0.32, 0.4, 4),
    (re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]+"), 0.38, 0.3, 5),
)


def _script_factor_cost(w: str) -> int | None:
    for rx, a, b, min_len in _SCRIPT_FACTOR:
        if len(w) >= min_len and rx.fullmatch(w):
            return max(1, int(a * len(w) + b + 0.5))
    return None


_STACKED_MARKS_RE = re.compile(r"[\u0300-\u036F]{2,}")


def _pretokens(s: str) -> list[tuple[str, str]]:
    return [(m.lastgroup, m.group()) for m in _PRETOKEN.finditer(s)]


def _wclass(w: str) -> str:
    """Character-range class, not language ID: ``v`` Latin Extended Additional
    (U+1E00–U+1EFF, takes priority), ``s`` Latin Extended-A/B (U+0100–U+024F),
    ``x`` other accents, ``a`` ASCII. The cost rules are approximate."""
    if _GREEK.search(w):
        return "g"
    if _OTHER_WORD.search(w):
        return "o"
    if _LATIN_EXT_ADD.search(w):
        return "v"
    if _LATIN_EXT_A.search(w):
        return "s"
    return "a" if w.isascii() else "x"


def _fallback_cost(w: str, len_table: dict, suffixes: dict | None = None, floor: dict | None = None) -> int:
    """Cost of a word in no table: calibrated per (class, length) plus a suffix delta
    (e.g. Romance futures ``-rei``/``-ré`` split off), else the legacy ceil(len/4) rule."""
    k = f"{_wclass(w)}{len(w)}"
    if k[0] == "v" and _VI_SYLLABLE.fullmatch(w):
        # Vietnamese syllables (tones in U+1E00–U+1EFF) are mostly a single o200k token
        # (" tiếng" " Việt" " người" = 1): the old per-char +1 overestimated them.
        # tone letters that are rare in o200k's training data split off (" Nẵng" = 3, " Huế" = 2)
        return max(1, (len(w) + 5) // 6) + (1 if _VI_RARE.search(w) else 0)
    if k in len_table:
        if len(w) < 5:
            return len_table[k]
        fl, sx = floor or {}, suffixes or {}
        f = fl.get(w[-3:], fl.get(w[-2:]))
        if f is not None:  # documented floor rule wins over learned deltas
            return max(f, len_table[k])
        return max(1, len_table[k] + sx.get(w[-3:], sx.get(w[-2:], 0)))
    if k[0] == "g":  # Greek: o200k merges it poorly, ≈ ceil(len/2) beyond 3 letters
        return 1 if len(w) <= 3 else (len(w) + 1) // 2
    if k[0] == "s":  # Broad Latin Extended-A/B heuristic, excluding the #108 exceptions.
        return max(1, (len(w) + 3) // 4) + sum(
            1 for c in _LATIN_EXT_A.findall(w) if _LATIN_EXT_SPLIT.match(c)
        )
    return max(1, (len(w) + 3) // 4) + len(_LATIN_EXT_ADD.findall(w))


def _load_calib() -> dict:
    """Lazy-load the committed o200k calibration table (missing file -> legacy heuristic)."""
    global _CALIB
    if _CALIB is None:
        c: dict = {"en": {}, "len_table": {}, "contractions": {}, "exceptions": {}, "suffixes": {}, "suffix_floor": {}, "cjk": frozenset()}
        if DEFAULT_O200K_CALIB.exists():
            import base64

            d = json.loads(DEFAULT_O200K_CALIB.read_text(encoding="utf-8"))
            words = sorted(load_en_wordlist())
            packed = base64.b64decode(d["en_costs"])
            if len(packed) == (len(words) + 3) // 4:
                c["en"] = {w: ((packed[i >> 2] >> ((i & 3) * 2)) & 3) + 1 for i, w in enumerate(words)}
            c["len_table"] = d.get("len_table", {})
            c["contractions"] = d.get("contractions", {})
            c["exceptions"] = d.get("exceptions", {})
            c["suffixes"] = d.get("suffixes", {})
            c["suffix_floor"] = d.get("suffix_floor", {})
            c["cased"] = d.get("exceptions_cased", {})
            c["cjk_sp"] = frozenset(d.get("cjk_space_vocab", "").split())
            c["sym"] = frozenset(d.get("symbol_vocab", ""))
            c["cjk"] = frozenset(d.get("cjk_vocab", "").split())
            c["th"] = frozenset(d.get("thai_vocab", "").split())
            c["th_sp"] = frozenset(d.get("thai_space_vocab", "").split())
            # longest-match windows follow the table, so adding a longer word just works
            c["th_max"] = max(map(len, c["th"]), default=1)
            c["th_sp_max"] = max(map(len, c["th_sp"]), default=1)
            c["vi_sp"] = frozenset(d.get("vi_space_vocab", "").split())
            c["emoji"] = _unpack_emoji(d.get("emoji_costs", {}))
        _CALIB = c
    return _CALIB


def _word_cost(w: str, cal: dict) -> int:
    if w in cal.get("cased", ()):
        return cal["cased"][w]
    lw = w.lower().replace("\u2019", "'")
    for t in ("exceptions", "contractions", "en"):
        if lw in cal[t]:
            return cal[t][lw]
    if "'" in lw:  # unknown contraction: stem + suffix
        stem, _, _ = lw.partition("'")
        return _word_cost(stem, cal) + 1
    cost = _fallback_cost(lw, cal["len_table"], cal["suffixes"], cal["suffix_floor"])
    # UTF-8 misread as Latin-1/cp1252 often yields Ã/Â (lead bytes C3/C2). o200k keeps
    # each code point separate, so floor at len(w). Real Western text rarely needs this.
    if "Ã" in w or "Â" in w:
        return max(cost, len(w))
    return cost


def _unpack_emoji(d: dict) -> dict:
    """``{"ranges": [[start, "digits"], ...], "vs16": "chars"}`` -> {str: o200k cost}."""
    out: dict = {}
    for start, digits in d.get("ranges", []):
        for i, ch in enumerate(digits):
            out[chr(start + i)] = int(ch)
    for ch in d.get("vs16", ""):
        out[ch + "\ufe0f"] = 1  # e.g. "❤️" (U+2764 U+FE0F) is a single o200k token
    # keycap: "\ufe0f\u20e3" and a bare U+20E3 are each one o200k token ("1️⃣2️⃣" = 4)
    out["\ufe0f\u20e3"] = out["\u20e3"] = 1
    return out


def _emoji_cost(run: str, table: dict) -> int:
    """Sum of per-codepoint o200k costs (measured: a ZWJ / skin-tone sequence costs the sum
    of its parts, 👨‍👩‍👧‍👦 = 2+1+2+1+2+1+2 = 11); a base + VS16 pair can merge to 1."""
    n = i = 0
    while i < len(run):
        if run[i:i + 2] in table:
            n += table[run[i:i + 2]]
            i += 2
            continue
        n += table.get(run[i], len(run[i].encode("utf-8")))
        i += 1
    return n


def _thai_cost(run: str, vocab: frozenset, space: bool, sp_vocab: frozenset,
               max_len: int | None = None, sp_max_len: int | None = None) -> int:
    """Greedy longest match against o200k's Thai tokens; else 1 per char. The match window is
    the longest table entry (``max_len`` / ``sp_max_len``, computed from the table if omitted).
    After a space, a leading word o200k merges with the space is one token; otherwise
    the bare space costs its own token."""
    n = 0
    i = 0
    if max_len is None:
        max_len = max(map(len, vocab), default=1)
    if sp_max_len is None:
        sp_max_len = max(map(len, sp_vocab), default=1)
    if space:
        for L in range(min(sp_max_len, len(run)), 0, -1):
            if run[:L] in sp_vocab:
                n, i = 1, L
                break
        else:
            n = 1
    while i < len(run):
        for L in range(min(max_len, len(run) - i), 1, -1):
            if run[i:i + L] in vocab:
                i += L
                break
        else:
            i += 1
        n += 1
    return n


def _cjk_cost(run: str, vocab: frozenset) -> int:
    """Greedy longest match (4..2 chars) against o200k's CJK multi-char tokens; else 1 per char."""
    n = i = 0
    while i < len(run):
        for L in (4, 3, 2):
            if run[i:i + L] in vocab:
                i += L
                break
        else:
            i += 1
        n += 1
    return n


def _same_block_fragments(s: str, start: int, end: int, block: int) -> bool:
    """Do not discount controls beside mixed Brahmic runs using a first-char rate."""
    for at, step in ((start - 1, -1), (end, 1)):
        while 0 <= at < len(s):
            o = ord(s[at])
            if not (0x0980 <= o <= 0x0DFF or 0x0E80 <= o <= 0x109F
                    or 0x1780 <= o <= 0x17FF):
                break
            if o >> 7 != block:
                return False
            at += step
    return True


_FREE_WS = frozenset(" \t\n\r\f\v")
# Whitespace that Python ``\s`` treats as free but o200k still encodes. Measured with
# tiktoken 0.14.0 / o200k_base. NEL (U+0085) is the C1 control that ``strip()`` erases.
_COSTLY_WS_COST = {
    "\x85": 2,  # NEL (C1); strip() erases it and old early-return counted 0
    "\xa0": 1,  # NBSP
    "\u1680": 3,  # Ogham space mark
    "\u2028": 1,  # line separator
    "\u2029": 2,  # paragraph separator
    "\u202f": 1,  # narrow NBSP
    "\u205f": 2,  # medium mathematical space
}
# U+2000–200A and U+3000 stay free: NFC collapses some of them, and charging
# ideographic space overestimates Japanese / fullwidth contexts.


def estimate_tokens(text: str) -> int:
    """Stdlib-only token estimate calibrated toward o200k_base (no tiktoken at runtime).

    Splits like o200k's pre-tokenizer, then costs each piece:
    - Latin word (+ English contraction suffix): committed o200k table lookup
      (``fixtures/o200k_calib.json``: English wordlist costs, contractions,
      training-split exceptions), else a calibrated per-(class, length) fallback,
      else ``max(1, ceil(len/4))`` plus the character-range heuristic: class-s
      Latin Extended-A/B letters excluding the #108 exceptions, or U+1E00–U+1EFF
      characters for the other Latin fallback. This is not an exact token count.
    - CJK / kana / Hangul runs: greedy longest match against the committed o200k
      multi-char token list (``cjk_vocab``), else 1 per character
    - Thai runs: greedy longest match against o200k's Thai tokens (``thai_vocab``)
    - Vietnamese words after a space: 1 if o200k has " word" (``vi_space_vocab``), else >= 2
    - emoji runs (skin tone, ZWJ, VS16): sum of measured per-code-point costs (``emoji_costs``)
    - CJK Ext B–H / Supplementary PUA chars (no vocab token): UTF-8 bytes (4 each)
    - other-script runs (Greek, Cyrillic, Arabic) go through the same
      tables (own classes in the fallback)
    - Brahmic / Myanmar / Khmer runs (U+0900–0DFF, U+1000–109F, U+1780–17FF), signs
      included: ``ceil(len/3)`` (Oriya ``ceil(len/1)``), Myanmar / Khmer ``ceil(2*len/3)``
    - archaic Hangul jamo / ideographic variation selectors: UTF-8 byte count
    - Hebrew points / Arabic harakat: the word is split at them,
      each letter piece costs as a word and each mark +1
    - fullwidth digits / letters, halfwidth kana, math alphanumerics: measured per-code-point costs
    - Ethiopic: 2 per syllable, 3 in the supplement / extended blocks (+1 for a preceding space)
    - unmarked Hebrew / Arabic / Urdu / Georgian / Greek words: ``round(a*len + b)`` per script
    - stacked combining marks (2+ in a row): 2 per mark; C0 control chars 1 each, C1 2 each
    - digit groups of <= 3 = 1; each punctuation run = 1
    - costly whitespace (NEL, NBSP, Ogham, line/para separators): measured per-code-point costs
    ASCII whitespace is free. Regenerate the table with ``scripts/calibrate_estimate.py --write``.
    """
    if not text or all(ch in _FREE_WS for ch in text):
        return 0
    s = unicodedata.normalize("NFC", text)
    cal = _load_calib()
    vi_text = _VI_LETTER.search(s) is not None
    n = 0
    for m in _PRETOKEN.finditer(s):
        kind, p = m.lastgroup, m.group()
        # Keep shared pretokenization unchanged. Measured Tatoeba fit data supports
        # removing the extra control charge for Khmer/Lao ZWSP and Sinhala ZWJ,
        # while retaining each fragment's rounding cost. Joining runs instead
        # underestimates Bengali conjuncts. Other blocks/controls are unmodified.
        # Only a single interior control within one Unicode block qualifies:
        # edge/repeated controls, mixed blocks and emoji ZWJ keep their costs.
        if p in ("\u200b", "\u200d") and 0 < m.start() and m.end() < len(s):
            block = ord(s[m.start() - 1]) >> 7
            same_block = block == ord(s[m.end()]) >> 7
            if same_block and _same_block_fragments(s, m.start(), m.end(), block) and (
                (p == "\u200b" and block in (0x0E80 >> 7, 0x1780 >> 7))
                or (p == "\u200d" and block == 0x0D80 >> 7)
            ):
                continue
        if kind in ("w", "o"):
            # a combining mark left after NFC is its own byte-level token in o200k
            spaced = m.start() > 0 and s[m.start() - 1] == " "
            if spaced and not p.isascii() and (vi_text or _VI_SYLLABLE.fullmatch(p)) and _VI_WORD.fullmatch(p):
                # Vietnamese: o200k has many syllables as one " syllable" token (case-sensitive,
                # " tiếng" = 1 but " Tiếng" = 2); one it lacks splits into >= 2 (" phê" " Huế" = 2).
                # Unspaced words keep the #120 rule below (word cost + 1).
                n += 1 if p in cal.get("vi_sp", ()) else max(2, _word_cost(p, cal))
            else:
                marks = _SCRIPT_MARKS_RE.findall(p) if kind == "o" else ()
                if marks:
                    # Arabic harakat: o200k splits the word at the marks, so cost each
                    # letter piece as a word plus one token per mark
                    n += sum(_word_cost(q, cal) for q in _SCRIPT_MARKS_RE.split(p) if q)
                    n += sum(len(r) for r in marks)
                else:
                    f = _script_factor_cost(p) if kind == "o" else None
                    if f is not None:
                        n += f
                    else:
                        # stacked marks (Zalgo-style) fall back to bytes: 2 tokens per mark
                        n += _word_cost(p, cal) + len(_COMBINING_RE.findall(p)) + sum(
                            len(r) for r in _STACKED_MARKS_RE.findall(p))
            if (m.start() == 0 or s[m.start() - 1] != " ") and (
                _VI_SYLLABLE.fullmatch(p) or (vi_text and not p.isascii())
            ):
                # without a leading space o200k splits a Vietnamese syllable ("biết" = 2,
                # " biết" = 1); in Vietnamese text this also holds for "Hà" / "Đà" (2 vs " Hà" = 1)
                n += 1
        elif kind == "k":
            if m.start() == 0 or s[m.start() - 1] == " ":
                # o200k merges the preceding space only into some CJK tokens
                # (" 开" yes, " 绿" no: the bare space then costs its own token)
                for L in (4, 3, 2, 1):
                    if p[:L] in cal["cjk_sp"]:
                        n += 1 + (_cjk_cost(p[L:], cal["cjk"]) if p[L:] else 0)
                        break
                else:
                    n += 1 + _cjk_cost(p, cal["cjk"])
            else:
                n += _cjk_cost(p, cal["cjk"])
        elif kind == "c":
            n += _thai_cost(p, cal.get("th", frozenset()), m.start() > 0 and s[m.start() - 1] == " ",
                            cal.get("th_sp", frozenset()), cal.get("th_max"), cal.get("th_sp_max"))
        elif kind == "b":  # no vocabulary token: raw UTF-8 bytes
            n += len(p.encode("utf-8"))
        elif kind == "u":
            n += _range_cost(p)
        elif kind == "t":
            # Ethiopic (U+1200–139F, U+2D80–2DDF, U+AB00–AB2F): o200k has almost no merges,
            # 2 tokens per syllable; a preceding space is its own token.
            # Ethiopic Extended / Supplement / Extended-A have no merges: 3 UTF-8 bytes each.
            n += sum(2 if ch < "\u1380" else 3 for ch in p) + (1 if m.start() > 0 and s[m.start() - 1] == " " else 0)
        elif kind == "e":
            n += _emoji_cost(p, cal.get("emoji", {}))
        elif kind == "i":
            # whole run incl. vowel signs / viramas: o200k merges common Brahmic words, so
            # ≈ 1 token per 3 code points on real text (corpus Bengali / Tamil rows).
            # Splitting at every sign (the old path) overestimated them ≈ 1.6–2x.
            # Myanmar / Khmer merge far less: ≈ 2 tokens per 3 code points.
            per = _brahmic_rate(p[0])
            n += max(1, -int(-len(p) // per))
        elif kind == "x":  # uncalibrated script: legacy ceil(len/4)
            # Hebrew points split the word: each letter piece ceil(len/4), +1 per point
            marks = _SCRIPT_MARKS_RE.findall(p)
            f = None if marks else _script_factor_cost(p)
            if f is not None:
                n += f
                continue
            n += sum((len(q) + 3) // 4 for q in _SCRIPT_MARKS_RE.split(p) if q)
            n += sum(len(r) for r in marks)
        elif kind == "j":
            n += len(p.encode("utf-8"))
        elif kind == "n":
            n += sum(_COSTLY_WS_COST.get(ch, max(1, len(ch.encode("utf-8")))) for ch in p)
        elif kind == "p":
            # a punctuation run is one token; non-ASCII symbols outside o200k's
            # single-token set (e.g. "∴") cost one extra byte-level token each
            # C0 controls / DEL are one byte-level token each, C1 controls (2 UTF-8 bytes) two
            ctrl = sum(1 for ch in p if ord(ch) < 32 or ord(ch) == 127)
            c1 = sum(1 for ch in p if 128 <= ord(ch) < 160)
            n += max(1, ctrl + 2 * c1 + (ctrl + c1 < len(p))) + sum(
                1 for ch in p if ord(ch) >= 160 and ch not in cal["sym"])
        else:
            n += 1
    if s != text:
        n += _nfd_extra(text, cal)
    return n


_HANGUL_JAMO_RUN = re.compile("[\u1100-\u11FF\uA960-\uA97F\uD7B0-\uD7FF]+")


def _nfd_extra(text: str, cal: dict) -> int:
    """o200k sees the raw (non-NFC) bytes: a decomposed accent is its own token and splits
    the word at the mark. For each raw Latin word that NFC would change, add the gap between
    the split cost (pieces + 1 per mark) and the NFC-word cost already counted."""
    extra = 0
    for m in _PRETOKEN.finditer(text):
        w = m.group()
        if m.lastgroup != "w" or not _COMBINING_RE.search(w):
            continue
        c = unicodedata.normalize("NFC", w)
        if c == w:
            continue
        split = sum(_word_cost(q, cal) for q in _COMBINING_RE.split(w) if q) + len(_COMBINING_RE.findall(w))
        extra += max(0, split - (_word_cost(c, cal) + len(_COMBINING_RE.findall(c))))
    # Decomposed Hangul (conjoining jamo, e.g. NFD "한국어"): o200k has no merges for them,
    # one token per UTF-8 byte (3 per jamo), while NFC syllables were counted.
    for m in _HANGUL_JAMO_RUN.finditer(text):
        w = m.group()
        c = unicodedata.normalize("NFC", w)
        if c != w:
            extra += max(0, len(w.encode("utf-8")) - estimate_tokens(c))
    return extra




@lru_cache(maxsize=4)
def load_en_wordlist(path: str | None = None) -> frozenset[str]:
    """Lowercase English words for the homograph guard (``#`` lines = header)."""
    p = Path(path) if path is not None else DEFAULT_EN_WORDLIST
    if not p.exists():
        return frozenset()
    return frozenset(
        w.strip()
        for w in p.read_text(encoding="utf-8").splitlines()
        if w.strip() and not w.startswith("#")
    )
