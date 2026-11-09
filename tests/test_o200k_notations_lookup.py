"""Sanity checks for docs/o200k-lookup/notations reference tables."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "docs" / "o200k-lookup" / "notations"

EXPECTED = {
    "kaomoji-ja-o200k.jsonl": 37_515,
    "emoticons-ascii-o200k.jsonl": 485,
    "kaomoji-i18n-o200k.jsonl": 530,
    "legacy-notations-o200k.jsonl": 10_832,
}


def _count(path: Path, *, gz: bool = False) -> int:
    opener = gzip.open if gz else open
    n = 0
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            json.loads(line)
            n += 1
    return n


def test_plain_jsonl_counts() -> None:
    for name, expected in EXPECTED.items():
        assert _count(D / name) == expected, name


def test_gzip_jsonl_counts() -> None:
    assert _count(D / "self-kaomoji-notations-o200k.jsonl.gz", gz=True) == 64_564
    assert _count(D / "self-extra-notations-o200k.jsonl.gz", gz=True) == 21_681


def test_readme_and_sources_present() -> None:
    assert (D / "README.md").is_file()
    assert (D / "self-notations-sources").is_dir()
    assert (D / "self-extra-sources").is_dir()
    assert (D / "kaomoji-i18n-emoticon-MIT-LICENSE.txt").is_file()
