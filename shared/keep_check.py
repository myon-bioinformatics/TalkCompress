"""G3 keep-check: does a compressed text still carry what the source must keep?

Stdlib only, no network, no model calls. Given a source text and its compressed
form, report:

- exact items (URL, path, SHA, date, issue ref #N, number, and caller-given
  ids such as "#40 keep-check") that are missing from the compressed text;
- counted items (negation, condition) whose occurrence count dropped;
- secret-like strings that appear in the compressed text (always a failure).

Counted items can drop legitimately when a summary merges duplicates, so a
count drop is reported for review rather than treated as proof of loss.

Usage::

    uv run python shared/keep_check.py --source src.txt --compressed out.txt \\
        --id "#40 keep-check"

Exit status is 0 when nothing is missing and no secret leaked, otherwise 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

URL_RE = re.compile(r"(?<![\w])https?://[^\s)>\]\"']+")
PATH_RE = re.compile(r"(?<![\w:/.])(?:\.{1,2}/)?[\w.-]+(?:/[\w.-]+)+")
SHA_RE = re.compile(r"\b(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")
DATE_RE = re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b")
ISSUE_RE = re.compile(r"(?<![\w&#])#\d+\b")
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?!\w|\.\d)")

NEGATION_RE = re.compile(
    r"\b(?:not|no|never|cannot|without)\b|\b\w*n['\u2019\u02bc\uff07]t\b|ない|ません|なし|禁止|不要",
    re.IGNORECASE,
)
CONDITION_RE = re.compile(
    r"\b(?:if|unless|only if|except|whenever|when|provided)\b|場合|ならば|限り|もし|ただし",
    re.IGNORECASE,
)

SECRET_RES = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
]


def _find_all(pattern: re.Pattern[str], text: str) -> list[str]:
    return [m.group(0) for m in pattern.finditer(text)]


def extract_exact(text: str) -> dict[str, set[str]]:
    """Return the exact-match items found in ``text``, grouped by kind."""
    patterns = {
        "url": URL_RE, "path": PATH_RE, "sha": SHA_RE,
        "date": DATE_RE, "issue": ISSUE_RE,
    }
    matches = {kind: list(pattern.finditer(text)) for kind, pattern in patterns.items()}
    # Suppress only occurrences actually inside a URL, not equal text elsewhere.
    matches["path"] = [
        m for m in matches["path"]
        if not all(part in {"ES", "DE", "FR", "EN", "JA", "PT", "IT", "ZH", "KO"}
                   for part in m.group().split("/"))
        and not any(u.start() <= m.start() and m.end() <= u.end()
                   for u in matches["url"])
    ]
    found = {kind: {m.group() for m in ms} for kind, ms in matches.items()}
    spans = [m.span() for ms in matches.values() for m in ms]
    found["number"] = {
        m.group() for m in NUMBER_RE.finditer(text)
        if not any(start <= m.start() and m.end() <= end for start, end in spans)
    }
    return found


def contains_exact(text: str, item: str, kind: str = "id") -> bool:
    """Match complete extracted tokens, or a caller-defined identifier boundary.

    Numbers embedded in another protected token cannot satisfy a standalone
    number. Custom identifiers must not be part of a longer word/identifier.
    """
    if kind != "id":
        return item in extract_exact(text).get(kind, set())
    return re.search(r"(?<![\w#])" + re.escape(item) + r"(?![\w])", text) is not None


def count_items(text: str) -> dict[str, int]:
    """Count negation and condition occurrences in ``text``."""
    # NFD の結合文字は \w ではないため、no\u0301 が "no" と数えられないよう NFC にそろえる
    text = unicodedata.normalize("NFC", text)
    return {
        "negation": len(NEGATION_RE.findall(text)),
        "condition": len(CONDITION_RE.findall(text)),
    }


def find_secrets(text: str) -> list[str]:
    found: list[str] = []
    for pattern in SECRET_RES:
        found.extend(m.group(0) for m in pattern.finditer(text))
    return found


@dataclass
class Report:
    missing: list[dict[str, str]] = field(default_factory=list)
    count_drops: list[dict[str, object]] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.secrets


def check(source: str, compressed: str, ids: tuple[str, ...] = ()) -> Report:
    """Compare ``compressed`` against ``source`` and report what was lost."""
    report = Report()

    destination = extract_exact(compressed)
    for kind, items in extract_exact(source).items():
        for item in sorted(items):
            if item not in destination[kind]:
                report.missing.append({"kind": kind, "item": item})

    for item in ids:
        if not contains_exact(compressed, item):
            report.missing.append({"kind": "id", "item": item})

    src_counts = count_items(source)
    dst_counts = count_items(compressed)
    for kind, src_n in src_counts.items():
        dst_n = dst_counts[kind]
        if dst_n < src_n:
            report.count_drops.append({"kind": kind, "source": src_n, "compressed": dst_n})

    report.secrets = find_secrets(compressed)
    return report


def _report_dict(report: Report) -> dict[str, object]:
    return {
        "ok": report.ok,
        "missing": report.missing,
        "count_drops": report.count_drops,
        "secrets": ["<redacted>" for _ in report.secrets],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--compressed", required=True, type=Path)
    parser.add_argument("--id", action="append", default=[], dest="ids")
    args = parser.parse_args(argv)

    report = check(
        args.source.read_text(encoding="utf-8"),
        args.compressed.read_text(encoding="utf-8"),
        tuple(args.ids),
    )
    json.dump(_report_dict(report), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
