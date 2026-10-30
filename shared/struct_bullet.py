"""G1 struct-bullet: turn prose into one-fact-per-line bullets, then verify.

Rule-based and stdlib only. Each sentence becomes one ``- `` line. Leading
filler words are removed and a trailing full stop is dropped. The result is
checked with keep_check (G3) against the source, and token counts from the
stdlib estimator in TesseraTalk are printed for comparison.

Whether bullets are cheaper than prose depends on the text, so the counts are
the decision input, not the bullet form itself.

Usage::

    uv run python shared/struct_bullet.py --file notes.txt [--tokens] [--no-dash]

On the six repo samples (estimate_tokens), plain lines without the dash marker
came to 0.95 of prose in total; with the dash marker the total was 1.01.

Exit status is 0 when keep_check passes, otherwise 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:  # package import (pytest, DensityZip)
    from shared.keep_check import check
except ImportError:  # run as a script from shared/
    from keep_check import check

SENTENCE_SPLIT = re.compile(r"(?<=[。！？])|(?<=[.!?])\s+|\n+")
FILLER_PREFIX = re.compile(
    r"^(?:(?:um|uh|well|so|also|basically|actually|just|you know)[,]?\s+)+",
    re.IGNORECASE,
)


def strip_fillers(sentence: str) -> str:
    return FILLER_PREFIX.sub("", sentence, count=1).strip()


def to_bullets(text: str, marker: str = "- ") -> str:
    """One sentence per line with ``marker`` (default ``- ``), fillers removed,
    trailing full stop dropped. ``marker=""`` gives plain lines with no dash."""
    lines: list[str] = []
    for part in SENTENCE_SPLIT.split(text):
        sentence = strip_fillers(part.strip())
        if not sentence:
            continue
        sentence = sentence.rstrip(".。")
        if sentence and sentence[0].isascii() and sentence[0].islower():
            sentence = sentence[0].upper() + sentence[1:]
        if sentence:
            lines.append(f"{marker}{sentence}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--tokens", action="store_true", help="print estimated tokens (stdlib estimator)")
    parser.add_argument("--no-dash", action="store_true", help="plain lines without the \"- \" marker")
    args = parser.parse_args(argv)

    source = args.file.read_text(encoding="utf-8")
    bullets = to_bullets(source, marker="" if args.no_dash else "- ")
    print(bullets)

    report = check(source, bullets)
    summary: dict[str, object] = {
        "ok": report.ok,
        "missing": report.missing,
        "count_drops": report.count_drops,
    }
    if args.tokens:
        sys.path.insert(0, str(ROOT / "TesseraTalk"))
        from tessera_talk import estimate_tokens

        summary["tokens"] = {
            "prose": estimate_tokens(source),
            "bullets": estimate_tokens(bullets),
        }
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
