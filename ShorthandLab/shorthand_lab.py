#!/usr/bin/env python3
"""ShorthandLab (C): slang / abbreviation / emoji conventions (layer 3)."""

from __future__ import annotations

import argparse

# Starter lexicon; expand with real corpora later.
DEFAULT_MAP: dict[str, str] = {
    "as soon as possible": "ASAP",
    "for your information": "FYI",
    "by the way": "BTW",
    "in my opinion": "IMO",
    "laughing out loud": "lol",
    "thank you": "ty",
    "you are welcome": "yw",
    "hereafter": "∴",  # session-rule marker stub
}


def compress(text: str, mapping: dict[str, str] | None = None) -> str:
    m = mapping or DEFAULT_MAP
    out = text
    # Longer keys first to avoid partial clobber.
    for long, short in sorted(m.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = out.replace(long, short)
        out = out.replace(long.title(), short)
        out = out.replace(long.upper(), short.upper() if short.isalpha() else short)
    return out


def expand(text: str, mapping: dict[str, str] | None = None) -> str:
    m = mapping or DEFAULT_MAP
    inv = {v: k for k, v in m.items()}
    out = text
    for short, long in sorted(inv.items(), key=lambda kv: len(kv[0]), reverse=True):
        out = out.replace(short, long)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ShorthandLab: layer-3 human shorthand")
    p.add_argument("mode", choices=("compress", "expand"))
    p.add_argument("--text", required=True)
    args = p.parse_args(argv)
    print(compress(args.text) if args.mode == "compress" else expand(args.text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
