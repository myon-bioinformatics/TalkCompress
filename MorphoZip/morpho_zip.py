#!/usr/bin/env python3
"""MorphoZip (E): intra-sentence multilingual / grammar-minimal compression (layer 4).

Prefer short low-ambiguity tokens that shrink prediction candidates
(e.g. ``I`` over 私は/僕は/俺は). Keep useful counters (匹/個). Avoid heavy
gendered morphology and Chinese-only bias.

Also applies shared lexeme policy (``shared.lex_policy``):
- strip fillers / light interjections
- unique-reading (rank-1) verb/phrase choice
- light etymon alignment across related LTR languages
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Allow running as a script without installed package.
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
    # EN multi-word → compact
    (re.compile(r"\bwithout\b", re.I), "w/o"),
    (re.compile(r"\bwith\b", re.I), "w/"),
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
    (re.compile(r"\bhereafter\b", re.I), "∴→"),
    (re.compile(r"\bherein\b", re.I), "∈"),
    # JA first-person / polite endings → low-ambiguity
    (re.compile(r"私は|僕は|俺は|拙者は|わたしは|あたしは"), "I"),
    (re.compile(r"私の|僕の|俺の|わたしの"), "my"),
    (re.compile(r"私を|僕を|俺を|わたしを"), "me"),
    (re.compile(r"です。|ます。|でした。|ました。"), "。"),
    (re.compile(r"ですね|ますね"), "ね"),
    (re.compile(r"でしょうか"), "?"),
    (re.compile(r"および|並びに|かつ"), "&"),
    (re.compile(r"または|若しくは|もしくは"), "/"),
    (re.compile(r"について"), "re:"),
    (re.compile(r"という"), "="),
    # Gender-light: collapse 彼は/彼女は → they (neutral)
    (re.compile(r"彼は|彼女は"), "they"),
    (re.compile(r"彼の|彼女の"), "their"),
]

_DIGIT_FW = re.compile(r"[０-９]")


def compress(
    text: str,
    *,
    strip: bool = True,
    unique: bool = True,
    etymon: bool = True,
    aggressive_fillers: bool = False,
) -> str:
    out = text
    if strip:
        out = strip_fillers(out, aggressive=aggressive_fillers)
    if unique:
        out = apply_unique_readings(out, compact=True)
    if etymon:
        out = apply_etymon_align(out)
    for pat, repl in _SUBS:
        out = pat.sub(repl, out)
    out = _DIGIT_FW.sub(lambda m: chr(ord(m.group(0)) - 0xFEE0), out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r" *\n *", "\n", out)
    return out.strip()


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
    p.add_argument("--text", help="input; else stdin")
    p.add_argument("--stats", action="store_true", help="print density metrics to stderr")
    p.add_argument("--no-strip", action="store_true", help="keep fillers")
    p.add_argument("--no-unique", action="store_true", help="skip unique-reading pass")
    p.add_argument("--no-etymon", action="store_true", help="skip etymon alignment")
    p.add_argument("--aggressive-fillers", action="store_true")
    args = p.parse_args(argv)
    text = args.text if args.text is not None else sys.stdin.read()
    out = compress(
        text,
        strip=not args.no_strip,
        unique=not args.no_unique,
        etymon=not args.no_etymon,
        aggressive_fillers=args.aggressive_fillers,
    )
    if args.stats:
        import json

        print(json.dumps(density(text, out), ensure_ascii=False), file=sys.stderr)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
