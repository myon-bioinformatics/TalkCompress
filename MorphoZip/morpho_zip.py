#!/usr/bin/env python3
"""MorphoZip (E): intra-sentence multilingual / grammar-minimal compression (layer 4)."""

from __future__ import annotations

import argparse
import re

# Tiny starter substitutions favoring short, low-ambiguity tokens.
# Prefer forms with few competing first-person / gender variants.
_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bI am\b", re.I), "I'm"),
    (re.compile(r"\byou are\b", re.I), "u r"),
    (re.compile(r"\band\b", re.I), "&"),
    (re.compile(r"\bwith\b", re.I), "w/"),
    (re.compile(r"\bwithout\b", re.I), "w/o"),
    (re.compile(r"\bwhatever\b", re.I), "∀"),  # "any/whatever" signal stub
    (re.compile(r"\bwherever\b", re.I), "∀loc"),
    (re.compile(r"私は|僕は|俺は|拙者は"), "I"),
    (re.compile(r"です。|ます。"), "。"),
    (re.compile(r"および|並びに"), "&"),
]


def compress(text: str) -> str:
    out = text
    for pat, repl in _SUBS:
        out = pat.sub(repl, out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MorphoZip: layer-4 grammar-minimal compress")
    p.add_argument("--text", required=True)
    args = p.parse_args(argv)
    print(compress(args.text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
