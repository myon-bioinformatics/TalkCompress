"""G4 qa-fidelity: can the compressed text still answer questions about the source?

Model-free probe builder and scorer. Probes come from the protected items that
keep_check (G3) extracts from the source. For each item, the question asks for
that item, and the answer is correct when it contains the expected string.

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
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from keep_check import extract_exact

KIND_QUESTION = {
    "url": "Which URL is mentioned?",
    "path": "Which file or path is mentioned?",
    "sha": "Which commit hash (SHA) is mentioned?",
    "date": "Which date is mentioned?",
    "issue": "Which issue or pull request number is mentioned?",
    "number": "Which number is mentioned?",
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
        probes.append(Probe(kind="id", question=f"Which identifier mentions '{item}'?", expected=item))
    return probes


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
        answer = answer_fn(make_prompt(compressed, probe.question))
        ok = probe.expected.lower() in answer.lower()
        hits += int(ok)
        results.append({"kind": probe.kind, "expected": probe.expected, "ok": ok})
    total = len(probes)
    return {
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
