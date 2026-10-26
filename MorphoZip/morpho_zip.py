#!/usr/bin/env python3
"""MorphoZip (E): intra-sentence multilingual / grammar-minimal compression (layer 4).

Prefer short low-ambiguity tokens that shrink prediction candidates
(e.g. ``I`` over 私は/僕は/俺は). Keep useful counters (匹/個). Avoid heavy
gendered morphology and Chinese-only bias.

Shared lexeme policy (``shared.lex_policy``) usage:
- UNIQUE_READINGS long form only (``compact=False``) — anti-ambiguity
- ETYMON_ALIGN (information / info / 情報 → ℹ️)
- EN quantity phrases → short JA counters (experimental)
- spelled EN number words → digits (before counters)
- strip unquoted articles ``the`` / ``a`` / ``an`` (quoted forms keep the word)
- light contractions (``I will`` → ``I'll``, …)
- optional integer → hex rewrite (``hex_nums``)
- protected spans ``[[keep:...]]`` / `` `keep:...` `` (wrappers stripped)

Fillers and UNIQUE_COMPACT are **C (ShorthandEdge)** by default. Optional
``strip=True`` / ``--strip`` / ``--aggressive-fillers`` remain for opt-in.
``--keep-articles`` disables article stripping.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.lex_policy import (  # noqa: E402
    apply_etymon_align,
    apply_unique_readings,
    strip_fillers,
)

# (pattern, replacement) — applied in order; more specific first.
_SUBS: list[tuple[re.Pattern[str], str]] = [
    # JA first-person before EN "I will"/"I'm" so 私は will → I'll
    (re.compile(r"私は|僕は|俺は|拙者は|わたしは|あたしは"), "I"),
    (re.compile(r"私の|僕の|俺の|わたしの"), "my"),
    (re.compile(r"私を|僕を|俺を|わたしを"), "me"),
    # EN multi-word → compact
    (re.compile(r"\bwithout\b", re.I), "w/o"),
    (re.compile(r"\bwith\b", re.I), "w/"),
    (re.compile(r"\bI will\b", re.I), "I'll"),
    (re.compile(r"\bI would\b", re.I), "I'd"),
    (re.compile(r"\bI have\b", re.I), "I've"),
    (re.compile(r"\bI am\b", re.I), "I'm"),
    (re.compile(r"\byou are\b", re.I), "u r"),
    (re.compile(r"\bwe are\b", re.I), "we're"),
    (re.compile(r"\bthey are\b", re.I), "they're"),
    (re.compile(r"\bit is\b", re.I), "it's"),
    (re.compile(r"\bthat is\b", re.I), "that's"),
    (re.compile(r"\bthere is\b", re.I), "there's"),
    (re.compile(r"\bthere are\b", re.I), "there're"),
    (re.compile(r"\bdo not\b", re.I), "don't"),
    (re.compile(r"\bdoes not\b", re.I), "doesn't"),
    (re.compile(r"\bcannot\b", re.I), "can't"),
    (re.compile(r"\bwill not\b", re.I), "won't"),
    (re.compile(r"\bshould not\b", re.I), "shouldn't"),
    (re.compile(r"\bwould not\b", re.I), "wouldn't"),
    # Gender-light EN (before and/or collapse)
    (re.compile(r"\bhe or she\b", re.I), "they"),
    (re.compile(r"\bhim or her\b", re.I), "them"),
    (re.compile(r"\bhis or her\b", re.I), "their"),
    (re.compile(r"\band\b", re.I), "&"),
    (re.compile(r"\bor\b", re.I), "/"),
    (re.compile(r"\bbecause\b", re.I), "bc"),
    (re.compile(r"\btherefore\b", re.I), "∴"),
    (re.compile(r"\bhowever\b", re.I), "tho"),
    (re.compile(r"\bapproximately\b", re.I), "~"),
    (re.compile(r"\bequal to\b", re.I), "="),
    (re.compile(r"\bgreater than\b", re.I), ">"),
    (re.compile(r"\bless than\b", re.I), "<"),
    # whatever-compounds → compact signals
    (re.compile(r"\bwhatever\b", re.I), "∀"),
    (re.compile(r"\bwhoever\b", re.I), "∀who"),
    (re.compile(r"\bwhichever\b", re.I), "∀which"),
    (re.compile(r"\bwherever\b", re.I), "∀loc"),
    (re.compile(r"\bwhenever\b", re.I), "∀when"),
    (re.compile(r"\bnonetheless\b", re.I), "tho∴"),
    (re.compile(r"\bhereinafter referred to as\b", re.I), "∴="),
    (re.compile(r"\bhereinafter\b", re.I), "∴↓"),
    (re.compile(r"\bhereafter\b", re.I), "∴→"),
    (re.compile(r"\bherein\b", re.I), "∈"),
    (re.compile(r"\bthereof\b", re.I), "∴of"),
    (re.compile(r"\btherein\b", re.I), "∈there"),
    (re.compile(r"\bwhereas\b", re.I), "∵"),
    # JA polite endings → low-ambiguity
    (re.compile(r"です。|ます。|でした。|ました。"), "。"),
    (re.compile(r"ですね|ますね"), "ね"),
    (re.compile(r"でしょうか"), "?"),
    (re.compile(r"および|並びに|かつ"), "&"),
    (re.compile(r"または|若しくは|もしくは"), "/"),
    (re.compile(r"について"), "re:"),
    (re.compile(r"という"), "="),
    # Gender-light collapses
    (re.compile(r"彼は|彼女は"), "they"),
    (re.compile(r"彼の|彼女の"), "their"),
    (re.compile(r"彼を|彼女を"), "them"),
]

# EN quantity phrases → JA counters (unambiguous layer-4 experiments).
# Order: more specific animal/people phrases before generic pieces.
_COUNTER_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(\d+)\s+(?:animals?|cats?|dogs?|birds?|fish|pets?)\b", re.I), r"\1匹"),
    (re.compile(r"\b(\d+)\s+(?:people|persons?|humans?|users?|members?)\b", re.I), r"\1人"),
    (re.compile(r"\b(\d+)\s+(?:times|occasions?)\b", re.I), r"\1回"),
    (re.compile(r"\b(\d+)\s+(?:pieces?|items?|things?|objects?)\b", re.I), r"\1個"),
    (re.compile(r"\b(\d+)\s+(?:days?)\b", re.I), r"\1日"),
    (re.compile(r"\b(\d+)\s+(?:hours?)\b", re.I), r"\1時間"),
    (re.compile(r"\b(\d+)\s+(?:minutes?|mins?)\b", re.I), r"\1分"),
    (re.compile(r"\b(\d+)\s+(?:seconds?|secs?)\b", re.I), r"\1秒"),
    (re.compile(r"\b(\d+)\s+(?:books?|volumes?)\b", re.I), r"\1冊"),
    (re.compile(r"\b(\d+)\s+(?:sheets?|pages?|papers?)\b", re.I), r"\1枚"),
]

_DIGIT_FW = re.compile(r"[０-９]")
_INT_RE = re.compile(r"\b(\d+)\b")


# Spelled EN number words → digits (applied before counters).
_ONES: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_TENS_ALT = {"fourty": 40}  # common misspelling
_ALL_NUM_WORDS: dict[str, int] = {**_ONES, **_TENS, **_TENS_ALT}

_COMPOUND_NUM = re.compile(
    r"\b("
    + "|".join(sorted({**_TENS, **_TENS_ALT}, key=len, reverse=True))
    + r")[\s-]+("
    + "|".join(sorted(_ONES.keys() - {"zero", "ten", "eleven", "twelve", "thirteen",
                                       "fourteen", "fifteen", "sixteen", "seventeen",
                                       "eighteen", "nineteen"}, key=len, reverse=True))
    + r")\b",
    re.I,
)
_A_ONE_HUNDRED = re.compile(r"\b(?:a|one)\s+hundred\b", re.I)
_A_ONE_THOUSAND = re.compile(r"\b(?:a|one)\s+thousand\b", re.I)
_BARE_HUNDRED = re.compile(r"\bhundred\b", re.I)
_BARE_THOUSAND = re.compile(r"\bthousand\b", re.I)


def apply_spelled_numbers(text: str) -> str:
    """Best-effort EN number words → digits (zero–twenty, tens, hundred/thousand).

    Handles ``three``→``3``, ``twenty-one`` / ``twenty one``→``21``,
    ``a hundred`` / ``one hundred``→``100``.
    """
    out = text
    out = _A_ONE_HUNDRED.sub("100", out)
    out = _A_ONE_THOUSAND.sub("1000", out)
    out = _BARE_HUNDRED.sub("100", out)
    out = _BARE_THOUSAND.sub("1000", out)

    def _comp(m: re.Match[str]) -> str:
        tens = _ALL_NUM_WORDS[m.group(1).lower()]
        ones = _ONES[m.group(2).lower()]
        return str(tens + ones)

    out = _COMPOUND_NUM.sub(_comp, out)
    for word, num in sorted(_ALL_NUM_WORDS.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = re.sub(rf"(?i)\b{re.escape(word)}\b", str(num), out)
    return out


# Unquoted EN articles. Quoted ``"the"`` / ``'the'`` keep the inner word (quotes dropped).
_QUOTED_ARTICLE = re.compile(r"""(['"])(the|a|an)\1""", re.I)
_ARTICLE_WORD = re.compile(r"\b(?:the|a|an)\b", re.I)
_ART_PLACEHOLDER = "⟦ART{0}⟧"


def strip_articles(text: str) -> str:
    """Drop unquoted ``the`` / ``a`` / ``an``; quoted forms keep the inner word only."""
    restores: list[str] = []

    def _mask(m: re.Match[str]) -> str:
        restores.append(m.group(2))
        return _ART_PLACEHOLDER.format(len(restores) - 1)

    out = _QUOTED_ARTICLE.sub(_mask, text)
    out = _ARTICLE_WORD.sub("", out)
    for i, inner in enumerate(restores):
        out = out.replace(_ART_PLACEHOLDER.format(i), inner)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    return out


def apply_counters(text: str) -> str:
    """Map verbose EN quantity phrases toward short JA counters where unambiguous."""
    out = text
    for pat, repl in _COUNTER_SUBS:
        out = pat.sub(repl, out)
    return out


def apply_hex_nums(text: str, *, prefix: bool = True) -> str:
    """Rewrite decimal integers to lowercase hex.

    With ``prefix=True`` (default when enabled): ``42`` → ``0x2a``.
    With ``prefix=False``: bare hex digits style ``2a`` (documented; easy to
    confuse with words — prefer prefix).
    """
    def _repl(m: re.Match[str]) -> str:
        n = int(m.group(1))
        h = format(n, "x")
        return f"0x{h}" if prefix else h

    return _INT_RE.sub(_repl, text)



# Protected spans: [[keep:...]] wrappers are stripped; inner text is preserved
# verbatim through compress. Optional --protect-regex patterns similarly mask
# matched text (full match restored unchanged).
_KEEP_SPAN = re.compile(r"\[\[keep:(.*?)\]\]", re.DOTALL)
_KEEP_BT = re.compile(r"`keep:(.+?)`", re.DOTALL)
_PROTECT_PLACEHOLDER = "⟦KEEP{0}⟧"


def extract_protected(
    text: str,
    protect_regexes: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Mask protected spans; return (masked_text, list_of_inner_strings).

    Recognized forms (in order):
    - ``[[keep:...]]`` — wrappers stripped, inner preserved
    - `` `keep:...` `` — backtick form, wrappers stripped
    - each ``protect_regex`` — full match preserved as-is
    """
    restores: list[str] = []

    def _mask_keep(m: re.Match[str]) -> str:
        restores.append(m.group(1))
        return _PROTECT_PLACEHOLDER.format(len(restores) - 1)

    out = _KEEP_SPAN.sub(_mask_keep, text)
    out = _KEEP_BT.sub(_mask_keep, out)
    for pat in protect_regexes or []:
        cre = re.compile(pat)

        def _mask_full(m: re.Match[str], _cre=cre) -> str:
            restores.append(m.group(0))
            return _PROTECT_PLACEHOLDER.format(len(restores) - 1)

        out = cre.sub(_mask_full, out)
    return out, restores


def restore_protected(text: str, restores: list[str]) -> str:
    """Put protected inners back (placeholders → original text)."""
    out = text
    for i, inner in enumerate(restores):
        out = out.replace(_PROTECT_PLACEHOLDER.format(i), inner)
    return out


def compress(
    text: str,
    *,
    strip: bool = False,
    unique: bool = True,
    etymon: bool = True,
    aggressive_fillers: bool = False,
    counters: bool = True,
    spelled_nums: bool = True,
    keep_articles: bool = False,
    hex_nums: bool = False,
    hex_prefix: bool = True,
    protect_regexes: list[str] | None = None,
) -> str:
    """Compress text. ``[[keep:...]]`` / `` `keep:...` `` spans and optional
    ``protect_regexes`` are left unchanged (wrappers stripped for keep-forms).

    Default: no filler strip, no UNIQUE_COMPACT (those belong to C).
    ``strip=True`` or ``aggressive_fillers=True`` opt into filler removal.
    Unquoted articles ``the``/``a``/``an`` are stripped unless ``keep_articles``.
    Quoted articles keep the inner word (quotes dropped). Spelled number words
    become digits before counter mapping when ``spelled_nums`` is on.
    """
    out, restores = extract_protected(text, protect_regexes)
    # aggressive_fillers implies strip
    do_strip = strip or aggressive_fillers
    if do_strip:
        out = strip_fillers(out, aggressive=aggressive_fillers)
    if unique:
        out = apply_unique_readings(out, compact=False)
    if etymon:
        out = apply_etymon_align(out)
    if spelled_nums:
        out = apply_spelled_numbers(out)
    if counters:
        out = apply_counters(out)
    if not keep_articles:
        out = strip_articles(out)
    for pat, repl in _SUBS:
        out = pat.sub(repl, out)
    out = _DIGIT_FW.sub(lambda m: chr(ord(m.group(0)) - 0xFEE0), out)
    if hex_nums:
        out = apply_hex_nums(out, prefix=hex_prefix)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" *\n *", "\n", out)
    out = out.strip()
    return restore_protected(out, restores)



# Best-effort inverse maps (lossy / unambiguous subset only).
_EXPAND_COUNTERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(\d+)匹"), r"\1 animals"),
    (re.compile(r"(\d+)人"), r"\1 people"),
    (re.compile(r"(\d+)回"), r"\1 times"),
    (re.compile(r"(\d+)個"), r"\1 pieces"),
    (re.compile(r"(\d+)日"), r"\1 days"),
    (re.compile(r"(\d+)時間"), r"\1 hours"),
    (re.compile(r"(\d+)分"), r"\1 minutes"),
    (re.compile(r"(\d+)秒"), r"\1 seconds"),
    (re.compile(r"(\d+)冊"), r"\1 books"),
    (re.compile(r"(\d+)枚"), r"\1 sheets"),
]

# Unambiguous short → longer (subset of _SUBS / UNIQUE_COMPACT). Documented lossy.
_EXPAND_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bw/o\b", re.I), "without"),
    (re.compile(r"\bw/\b", re.I), "with"),
    (re.compile(r"\bu r\b", re.I), "you are"),
    (re.compile(r"\bbc\b", re.I), "because"),
    (re.compile(r"\btho∴\b"), "nonetheless"),
    (re.compile(r"\btho\b", re.I), "however"),
    (re.compile(r"∴↓"), "hereinafter"),
    (re.compile(r"∴→"), "hereafter"),
    (re.compile(r"∴="), "hereinafter referred to as"),
    (re.compile(r"∴of"), "thereof"),
    (re.compile(r"∈there"), "therein"),
    (re.compile(r"\b∀who\b"), "whoever"),
    (re.compile(r"\b∀which\b"), "whichever"),
    (re.compile(r"\b∀loc\b"), "wherever"),
    (re.compile(r"\b∀when\b"), "whenever"),
    (re.compile(r"\b∀\b"), "whatever"),
    (re.compile(r"∵"), "whereas"),
    (re.compile(r"∈"), "herein"),
    (re.compile(r"∴"), "therefore"),
    (re.compile(r"\bre:\b"), "について"),
]


def expand(text: str, *, counters: bool = True, compact: bool = True) -> str:
    """Best-effort inverse of compress for counters / a subset of short forms.

    Lossy: gender collapses, optional filler drops, unique-readings, and many _SUBS have no
    unique inverse. Only unambiguous counter and short-token mappings are reversed.
    """
    from shared.lex_policy import UNIQUE_COMPACT

    out = text
    if counters:
        for pat, repl in _EXPAND_COUNTERS:
            out = pat.sub(repl, out)
    # UNIQUE_COMPACT inverse (short → long) when unambiguous
    if compact:
        inv: dict[str, str] = {}
        for long, short in UNIQUE_COMPACT.items():
            if long == short:
                continue
            # skip collisions
            if short in inv and inv[short] != long:
                continue
            if short not in inv:
                inv[short] = long
        for short, long in sorted(inv.items(), key=lambda kv: len(kv[0]), reverse=True):
            out = re.sub(rf"(?i)\b{re.escape(short)}\b", long, out)
    for pat, repl in _EXPAND_SUBS:
        out = pat.sub(repl, out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


_PACK_SPLIT = re.compile(
    r"(\s+|[^\w\s\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]+)",
    re.UNICODE,
)


def pack_tokens(text: str) -> str:
    """Split on whitespace/punct and rejoin with minimal separators.

    CJK / Hangul runs stay glued (no space inserted between CJK-adjacent tokens).
    Latin/digit tokens get a single space between them. Punctuation stays attached
    lightly for layer-4 packing experiments.
    """
    if not text:
        return ""
    parts = [p for p in _PACK_SPLIT.split(text) if p is not None and p != ""]
    # Drop pure whitespace tokens; keep punct as their own tokens
    tokens: list[str] = []
    for p in parts:
        if p.isspace():
            continue
        tokens.append(p)

    def _is_cjkish(s: str) -> bool:
        return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", s))

    def _is_wordish(s: str) -> bool:
        return bool(re.match(r"^[\w]+$", s, re.UNICODE))

    out: list[str] = []
    for tok in tokens:
        if not out:
            out.append(tok)
            continue
        prev = out[-1]
        # No space between CJK runs or when either side is CJK-adjacent wordish
        if _is_cjkish(prev) or _is_cjkish(tok):
            out.append(tok)
        elif _is_wordish(prev) and _is_wordish(tok):
            out.append(" ")
            out.append(tok)
        elif _is_wordish(prev) and tok and tok[0] in "([{":
            out.append(" ")
            out.append(tok)
        else:
            # punctuation: attach without leading space for ,.;:!?)]}
            if tok and tok[0] in ",.;:!?)]}":
                out.append(tok)
            elif prev and prev[-1] in "([{":
                out.append(tok)
            elif _is_wordish(tok):
                out.append(" ")
                out.append(tok)
            else:
                out.append(tok)
    return "".join(out)


def density(before: str, after: str) -> dict[str, float | int]:
    b, a = len(before), len(after)
    ratio = (a / b) if b else 0.0
    return {
        "chars_before": b,
        "chars_after": a,
        "saved": b - a,
        "ratio": round(ratio, 4),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MorphoZip: layer-4 grammar-minimal compress")
    p.add_argument(
        "--mode",
        choices=("compress", "expand", "pack"),
        default="compress",
        help="compress (default), expand (lossy inverse), or pack_tokens",
    )
    p.add_argument("--text", help="input; else stdin")
    p.add_argument("--stats", action="store_true", help="print density metrics to stderr")
    p.add_argument(
        "--strip",
        action="store_true",
        help="opt-in filler strip (default off; fillers are C/ShorthandEdge)",
    )
    p.add_argument(
        "--no-strip",
        action="store_true",
        help="compat: fillers already kept by default",
    )
    p.add_argument("--no-unique", action="store_true", help="skip unique-reading pass")
    p.add_argument("--no-etymon", action="store_true", help="skip etymon alignment")
    p.add_argument("--no-counters", action="store_true", help="skip EN→JA counter mapping")
    p.add_argument(
        "--aggressive-fillers",
        action="store_true",
        help="opt-in aggressive filler strip (implies --strip)",
    )
    p.add_argument(
        "--hex-nums",
        action="store_true",
        help="rewrite integers to lowercase hex (0x…); default off",
    )
    p.add_argument(
        "--hex-bare",
        action="store_true",
        help="with --hex-nums, omit 0x prefix (bare 0-F style)",
    )
    p.add_argument(
        "--protect-regex",
        action="append",
        default=None,
        dest="protect_regex",
        help="regex whose matches are left unchanged (repeatable)",
    )
    p.add_argument(
        "--keep-articles",
        action="store_true",
        help="keep English articles the/a/an (default: strip unquoted)",
    )
    p.add_argument(
        "--no-spelled-nums",
        action="store_true",
        help="skip spelled number words → digits",
    )
    args = p.parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()
    if args.mode == "expand":
        out = expand(text, counters=not args.no_counters)
    elif args.mode == "pack":
        out = pack_tokens(text)
    else:
        out = compress(
            text,
            strip=args.strip and not args.no_strip,
            unique=not args.no_unique,
            etymon=not args.no_etymon,
            aggressive_fillers=args.aggressive_fillers,
            counters=not args.no_counters,
            spelled_nums=not args.no_spelled_nums,
            keep_articles=args.keep_articles,
            hex_nums=args.hex_nums,
            hex_prefix=not args.hex_bare,
            protect_regexes=args.protect_regex,
        )
    if args.stats:
        import json

        print(json.dumps(density(text, out), ensure_ascii=False), file=sys.stderr)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
