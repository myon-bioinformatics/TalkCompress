#!/usr/bin/env python3
"""TesseraTalk (B): sentence-level language-switch mosaic (layer 2)."""

from __future__ import annotations

import argparse
import re

# Crude sentence splitter for LTR prose; refine later.
_SENT_SPLIT = re.compile(r"(?<=[.!?。？！])\s+")


def segment(text: str) -> list[str]:
    parts = _SENT_SPLIT.split(text.strip())
    return [p for p in parts if p]


def tag_sentences(text: str, langs: list[str]) -> list[tuple[str, str]]:
    """Round-robin language tags as a stand-in for real LID."""
    sents = segment(text)
    if not langs:
        langs = ["und"]
    return [(langs[i % len(langs)], s) for i, s in enumerate(sents)]


def render(tagged: list[tuple[str, str]]) -> str:
    return "\n".join(f"[{lang}] {sent}" for lang, sent in tagged)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="TesseraTalk: layer-2 sentence mosaic")
    p.add_argument("--text", required=True)
    p.add_argument(
        "--langs",
        default="en,ja,es",
        help="comma-separated language codes for round-robin tagging",
    )
    args = p.parse_args(argv)
    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    print(render(tag_sentences(args.text, langs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
