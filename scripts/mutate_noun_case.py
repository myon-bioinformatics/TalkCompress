"""Mutation check for scripts/noun_case.py (stdlib only; restores source).

Applies one textual mutant at a time to the real source and runs
``tests/test_noun_case.py``; a mutant is killed when pytest fails.

    uv run python scripts/mutate_noun_case.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/noun_case.py"
OPS = [
    (r" == ", " != "), (r" != ", " == "), (r" >= ", " > "), (r" <= ", " < "),
    (r" > ", " >= "), (r" < ", " <= "), (r" in ", " not in "), (r" not in ", " in "),
    (r" and ", " or "), (r" or ", " and "), (r"\+= 1", "+= 2"), (r"\+ 1", "- 1"),
    (r"- 1", "+ 1"), (r"\[1:\]", "[2:]"), (r"\[:1\]", "[:2]"), (r"\.upper\(\)", ".lower()"),
    (r"\.lower\(\)", ".upper()"), (r"\bTrue\b", "False"), (r"\bFalse\b", "True"),
    (r"return 0", "return 1"), (r"-\(", "("), (r"\[:", "[1:"), (r'"B"', '"C"'), (r'"C"', '"B"'),
    (r'== " "', '== ""'), (r"\.add\(", ".discard("),
    (r"rglob", "glob"), (r"\bcontinue\b", "pass"), (r"\bnot \b", ""),
]


def mutants(lines: list[str]):
    in_doc = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.count('"""') == 1:
            in_doc = not in_doc
            continue
        if in_doc or not s or s.startswith(("#", '"""', "import", "from", "def ", "class ")) or "pragma" in s:
            continue
        for pat, rep in OPS:
            for m in re.finditer(pat, line):
                new = line[: m.start()] + re.sub(pat, rep, m.group(0)) + line[m.end() :]
                if new != line:
                    yield i, new


def main() -> int:
    orig = SRC.read_text(encoding="utf-8")
    lines = orig.splitlines(keepends=True)
    killed, survived = 0, []
    try:
        for i, new in mutants(lines):
            SRC.write_text("".join(lines[:i] + [new] + lines[i + 1 :]), encoding="utf-8")
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests/test_noun_case.py"],
                cwd=ROOT, capture_output=True,
            )
            if r.returncode:
                killed += 1
            else:
                survived.append(f"L{i + 1}: {new.strip()}")
    finally:
        SRC.write_text(orig, encoding="utf-8")
    print(f"killed {killed}/{killed + len(survived)}")
    for s in survived:
        print("SURVIVED", s)
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
