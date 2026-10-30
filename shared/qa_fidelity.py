"""G4 qa-fidelity: can the compressed text still answer questions about the source?

Model-free probe builder and scorer. Probes come from the protected items that
keep_check (G3) extracts from the source. For each item, the question asks for
all items of that kind. Scores match complete values and normalize supported
calendar-date spellings, using only the final answer outside think blocks.

The only model call is the answer step. ``--cmd`` gets the prompt on stdin and
must print an answer on stdout; any local runner works, for example a wrapper
around a llama.cpp server. Without ``--cmd``, the script prints the probes so
they can be checked by hand.

Limitation: this measures whether protected items survive and can be retrieved.
It does not measure general comprehension. Compare methods with the same answer
command, and do not compare absolute scores across models.

Usage::

    uv run python shared/qa_fidelity.py --source src.txt --compressed out.txt \\
        --cmd 'my-local-llm --stdin' [--limit 20]
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

try:
    from shared.keep_check import extract_exact
except ImportError:
    from keep_check import extract_exact

KIND_QUESTION = {
    "url": "List all URLs mentioned. Copy each URL exactly.",
    "path": "List all filesystem paths mentioned. Copy each exactly.",
    "sha": "List all commit hashes (SHA) mentioned. Copy each exactly.",
    "date": "List all dates mentioned, using YYYY-MM-DD for each.",
    "issue": "List all issue or pull request numbers mentioned, including the # prefix.",
    "number": "List all numeric values mentioned, including counts. Use digits.",
}


@dataclass(frozen=True)
class Probe:
    kind: str
    question: str
    expected: str


def build_probes(source: str, ids: tuple[str, ...] = ()) -> list[Probe]:
    """One probe per exact item in the source, plus one per caller-given id."""
    probes: list[Probe] = []
    for kind, items in sorted(extract_exact(source).items()):
        question = KIND_QUESTION.get(kind)
        if question is None:
            continue
        for item in sorted(items):
            probes.append(Probe(kind=kind, question=question, expected=item))
    for item in ids:
        probes.append(Probe(kind="id", question="List all identifiers mentioned. Copy each exactly.", expected=item))
    return probes


def final_answer(answer: str) -> str:
    """Exclude think blocks; an unfinished block supplies no final answer.

    A closing tag without an opening tag occurs when the template supplied the
    opening tag. Treat everything before that closing tag as reasoning too.
    """
    answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.I | re.S)
    if re.search(r"<think>", answer, flags=re.I):
        return ""
    return re.split(r"</think>", answer, flags=re.I)[-1].strip()


def _dates(text: str) -> set[date]:
    """Recognize validated numeric and English full-month calendar dates."""
    values: set[date] = set()

    def add(year: str, month: str, day: str) -> None:
        try:
            values.add(date(int(year), int(month), int(day)))
        except ValueError:
            pass

    for year, month, day in re.findall(
        r"(?<!\w)(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})(?:日)?(?!\w)", text
    ):
        add(year, month, day)
    months = "January February March April May June July August September October November December".split()
    for number, month in enumerate(months, 1):
        for day, year in re.findall(
            rf"\b{month}\s+(\d{{1,2}})(?:st|nd|rd|th)?\s*,?\s+(\d{{4}})\b", text, re.I
        ):
            add(year, str(number), day)
        for day, year in re.findall(
            rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{month}\s+(\d{{4}})\b", text, re.I
        ):
            add(year, str(number), day)
    return values


def matches(probe: Probe, answer: str) -> bool:
    """Match complete protected values, with calendar normalization for dates."""
    if probe.kind == "date":
        expected = _dates(probe.expected)
        return bool(expected and expected.intersection(_dates(answer)))
    # Do not accept #400 for #40, a longer hash, or a child path/URL. Terminal
    # sentence punctuation is allowed. Keep URI/path suffix characters strict.
    if probe.kind in {"url", "path"}:
        end = r"(?![\w/\-?#=&%+~:@;]|\.[\w/])"
    elif probe.kind == "number":
        end = r"(?![\w]|[.,]\d)"
    else:
        end = r"(?!\w)"
    start = r"(?<![\w/#])"
    if probe.kind == "number":
        start = r"(?<![\w/#.,+\-])"
    flags = 0 if probe.kind in {"url", "path", "id"} else re.I
    return re.search(start + re.escape(probe.expected) + end, answer, flags) is not None


def make_prompt(compressed: str, question: str) -> str:
    return (
        "Use only the context to answer. If the answer is not there, say unknown.\n\n"
        f"Context:\n{compressed}\n\nQuestion: {question}\nAnswer briefly."
    )


def ask(cmd: str, prompt: str, timeout: int = 120) -> str:
    result = subprocess.run(
        shlex.split(cmd),
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"answer command failed ({result.returncode}): {result.stderr.strip()[:200]}")
    return result.stdout.strip()


def score(probes: list[Probe], compressed: str, answer_fn) -> dict[str, object]:
    """Run ``answer_fn(prompt) -> answer`` for each probe and count hits."""
    results = []
    hits = 0
    for probe in probes:
        raw_answer = answer_fn(make_prompt(compressed, probe.question))
        answer = final_answer(raw_answer)
        if not answer:
            raise ValueError("no completed final answer")
        ok = matches(probe, answer)
        hits += int(ok)
        results.append({"kind": probe.kind, "expected": probe.expected, "ok": ok,
                        "question": probe.question, "answer": answer, "raw_answer": raw_answer})
    total = len(probes)
    return {
        "status": "scored" if total else "not_applicable",
        "hits": hits,
        "total": total,
        "score": round(hits / total, 3) if total else None,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--compressed", required=True, type=Path)
    parser.add_argument("--id", action="append", default=[], dest="ids")
    parser.add_argument("--cmd", default="")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    source = args.source.read_text(encoding="utf-8")
    compressed = args.compressed.read_text(encoding="utf-8")
    probes = build_probes(source, tuple(args.ids))
    if args.limit:
        probes = probes[: args.limit]

    if not args.cmd:
        json.dump([p.__dict__ for p in probes], sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    report = score(probes, compressed, lambda prompt: ask(args.cmd, prompt))
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
