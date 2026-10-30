"""SVG DSL v0 (L3): can meaning survive a round trip through a language model?

Pipeline for one drawing (canonical SVG text):

1. describe: the model reads the SVG text and writes a plain description.
2. generate: the model writes SVG from the description, under the DSL v0 rules.
3. validate: the generated SVG must pass svg_dsl (otherwise the run fails here).
4. probe: the model reads the generated SVG and answers questions whose
   expected answers come from the original drawing's own attributes.

The score is hits / probes. It measures retained facts, not pixels. Run it with
a fixed model, endpoint, and settings, and record them with the result.

The model is called through a command that reads a prompt on stdin and prints
an answer on stdout (the same contract as qa_fidelity). For a local llama.cpp
server, use ``shared/llama_cmd.py`` with ``LLAMA_URL`` and ``LLAMA_MAX_TOKENS``.

CLI::

    python shared/svg_l3.py examples/figures/*.svg --cmd "python shared/llama_cmd.py" \\
        --model "LFM3-1.7B Q4_K_M" -o l3-report.json

See docs/l3-run.md for the full procedure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from shared.qa_fidelity import Probe, score
    from shared.svg_dsl import analyze, canonicalize
except ImportError:
    from qa_fidelity import Probe, score
    from svg_dsl import analyze, canonicalize

DSL_VERSION = "0"
PROMPT_VERSION = "1"  # bump when describe/generate prompts change
UNFINISHED = "<<unfinished>>"  # never matches an expected value

DSL_RULES = """Write one SVG document using only these elements and attributes:
- <svg width="W" height="H" viewBox="0 0 W H" xmlns="http://www.w3.org/2000/svg"> with integer W and H
- <g>, <rect x y width height>, <circle cx cy r>, <line x1 y1 x2 y2>, <path d>, <text x y>
- fill and stroke: "none" or #rrggbb; stroke-width; font-size
- <text> may use font-family="Noto Sans CJK JP" and text-anchor (start, middle, end); its only child is the text
- No transform, no arcs (A), no style, no script, no images.
Output the SVG only, in one code block."""

_SVG_RE = re.compile(r"<svg\b[^>]*/>|<svg\b.*</svg>", re.S)


def ask(cmd: str, prompt: str, timeout: int = 300) -> str:
    result = subprocess.run(
        shlex.split(cmd), input=prompt, capture_output=True, text=True, timeout=timeout, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"model command failed ({result.returncode}): {result.stderr.strip()[:200]}")
    return result.stdout.strip()


def describe_prompt(svg: str) -> str:
    return (
        "Below is an SVG drawing. Describe it in plain Japanese so that a reader could redraw it. "
        "Mention each shape, its position and size, its colors, and any text, with exact numbers.\n\n"
        f"{svg}"
    )


def generate_prompt(description: str) -> str:
    return f"{DSL_RULES}\n\nDescription:\n{description}\n"


def extract_svg(text: str) -> str:
    """Return the first SVG document in a model answer, or an empty string."""
    m = _SVG_RE.search(text)
    return m.group(0).strip() if m else ""


def probes_from(svg: str) -> list[Probe]:
    """Questions whose expected answers are the original drawing's own values."""
    root = ET.fromstring(svg)
    probes: list[Probe] = []
    colors: set[str] = set()
    for el in root.iter():
        name = el.tag.rsplit("}", 1)[-1]
        a = el.attrib
        for key in ("fill", "stroke"):
            if a.get(key, "none") != "none":
                colors.add(a[key])
        if name == "circle":
            probes.append(Probe("number", f"What is the radius of the circle centered at x={a['cx']}, y={a['cy']}? Answer with a number.", a["r"]))
        elif name == "rect":
            probes.append(Probe("number", f"What is the width of the rectangle whose top-left corner is x={a['x']}, y={a['y']}? Answer with a number.", a["width"]))
        elif name == "line":
            probes.append(Probe("number", f"What is x2 of the line that starts at x1={a['x1']}, y1={a['y1']}? Answer with a number.", a["x2"]))
        elif name == "text" and (el.text or "").strip():
            probes.append(Probe("id", "What text is written in the drawing? Copy it exactly.", el.text.strip()))
    for color in sorted(colors):
        probes.append(Probe("id", "List every fill or stroke color (#rrggbb) used in the drawing.", color))
    return probes


def run(source_svg: str, ask_fn) -> dict:
    """Run describe, generate, validate and probe with ``ask_fn(prompt) -> str``."""
    original = canonicalize(source_svg)
    description = ask_fn(describe_prompt(original))
    raw = ask_fn(generate_prompt(description))
    generated_src = extract_svg(raw)
    report: dict = {"description": description, "generated": generated_src, "dsl_ok": False,
                    "score": 0.0, "hits": 0, "total": 0, "errors": []}
    if not generated_src:
        report["errors"].append("no svg in model output")
        return report
    check = analyze(generated_src)
    report["errors"] = check.errors
    report["warnings"] = check.warnings
    if not check.ok:
        return report
    generated = check.canonical or ""
    report["dsl_ok"] = True
    report["generated"] = generated

    probes = probes_from(original)

    def answer(prompt: str) -> str:
        try:
            return ask_fn(prompt)
        except RuntimeError:
            return UNFINISHED

    result = score(probes, generated, answer)
    report.update(hits=result["hits"], total=result["total"], score=result["score"], results=result["results"])
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--cmd", required=True, help="command that reads a prompt on stdin and prints the answer")
    parser.add_argument("--model", required=True, help="label of the model you ran, e.g. 'LFM3-1.7B Q4_K_M'")
    parser.add_argument("-o", "--output", type=Path, help="write the JSON report here instead of stdout")
    args = parser.parse_args(argv)
    reports = []
    for path in args.files:
        text = path.read_text(encoding="utf-8")
        report = run(text, lambda p: ask(args.cmd, p))
        report["figure"] = path.name
        report["source_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        reports.append(report)
    meta = {
        "stage": "L3",
        "model": args.model,
        "command": args.cmd,
        "llama_url": os.environ.get("LLAMA_URL", "http://127.0.0.1:8080/v1/chat/completions"),
        "max_tokens_env": os.environ.get("LLAMA_MAX_TOKENS", "128 (default)"),
        "dsl_version": DSL_VERSION,
        "prompt_version": PROMPT_VERSION,
        "python": sys.version.split()[0],
    }
    out = {"meta": meta, "reports": reports}
    text = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0 if all(r["dsl_ok"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
