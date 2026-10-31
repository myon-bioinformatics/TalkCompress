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
from dataclasses import dataclass
from decimal import Decimal, DecimalException
from pathlib import Path

try:
    from shared.qa_fidelity import Probe, make_prompt
    from shared.svg_dsl import analyze, canonicalize
except ImportError:
    from qa_fidelity import Probe, make_prompt
    from svg_dsl import analyze, canonicalize

DSL_VERSION = "0"
PROMPT_VERSION = "2"  # includes the probe answer contract
SCORER_VERSION = "2"  # do not compare or reinterpret version-1 scores

DSL_RULES = """Write one SVG document using only these elements and attributes:
- <svg width="W" height="H" viewBox="0 0 W H" xmlns="http://www.w3.org/2000/svg"> with integer W and H
- <g>, <rect x y width height>, <circle cx cy r>, <line x1 y1 x2 y2>, <path d>, <text x y>
- fill and stroke: "none" or #rrggbb; stroke-width; font-size
- <text> may use font-family="Noto Sans CJK JP" and text-anchor (start, middle, end); its only child is the text
- No transform, no arcs (A), no style, no script, no images.
Output the SVG only, in one code block."""

_SVG_RE = re.compile(r"<svg\b[^>]*/>|<svg\b.*?</svg>", re.S)


def ask(cmd: str, prompt: str, timeout: int | None = None) -> str:
    # The command's own HTTP timeout (LLAMA_TIMEOUT) is the limit; this outer one is a margin above it.
    if timeout is None:
        timeout = int(os.environ.get("LLAMA_TIMEOUT", "300")) + 60
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
    """Return a final SVG, ignoring reasoning outside the SVG document.

    Do not run prose substitutions inside SVG: CDATA may legitimately contain
    strings such as '<think>'. A closing tag outside the candidate means a
    template supplied the opening reasoning tag, so that candidate is discarded.
    """
    while True:
        m = _SVG_RE.search(text)
        if not m:
            return ""
        depth = 0
        for tag in re.finditer(r"</?think>", text[:m.start()], re.I):
            depth = max(0, depth - 1) if tag.group(0).startswith("</") else depth + 1
        if depth:
            for tag in re.finditer(r"</?think>", text[m.start():], re.I):
                depth += -1 if tag.group(0).startswith("</") else 1
                if depth == 0:
                    text = text[m.start() + tag.end():]
                    break
            else:
                return ""
            continue
        closing = re.search(r"</think>", text[m.end():], re.I)
        if closing:
            text = text[m.end() + closing.end():]
            continue
        return m.group(0).strip()


@dataclass(frozen=True)
class SvgProbe(Probe):
    field: str
    index: int | None


_QUESTIONS = {
    "circle.r": "List the radius of every circle element in document order. Return only a JSON array of numbers; include SVG default values for omitted attributes.",
    "rect.width": "List the width of every rect element in document order. Return only a JSON array of numbers; include SVG default values for omitted attributes.",
    "line.x2": "List the x2 coordinate of every line element in document order. Return only a JSON array of numbers; include SVG default values for omitted attributes.",
    "text": "List the text content of every nonempty text element in document order. Return only a JSON array of strings.",
    "color": "List every distinct explicitly specified fill or stroke color used in the drawing, excluding none. Return only a JSON array of #rrggbb strings, without duplicates.",
}


def probes_from(svg: str) -> list[SvgProbe]:
    """Attribute-list probes: no source value or coordinate enters a question.

    Geometry/text correspondence uses document order, not shape recognition.
    Omitted circle radius, rect width and line x2 have SVG's zero default.
    Colors describe explicit attributes, not computed inherited appearance.
    """
    root = ET.fromstring(svg)
    probes: list[SvgProbe] = []
    indices: dict[str, int] = {}
    colors: set[str] = set()
    for el in root.iter():
        name = el.tag.rsplit("}", 1)[-1]
        a = el.attrib
        for key in ("fill", "stroke"):
            if a.get(key, "none") != "none":
                colors.add(a[key])
        field = {"circle": "circle.r", "rect": "rect.width", "line": "line.x2"}.get(name)
        if field is not None:
            index = indices.get(field, 0)
            indices[field] = index + 1
            probes.append(SvgProbe("number", _QUESTIONS[field], a.get(field.split(".")[1], "0"), field, index))
        elif name == "text" and (el.text or "").strip():
            index = indices.get("text", 0)
            indices["text"] = index + 1
            probes.append(SvgProbe("id", _QUESTIONS["text"], el.text.strip(), "text", index))
    for color in sorted(colors):
        probes.append(SvgProbe("id", _QUESTIONS["color"], color, "color", None))
    return probes


def _final_payload(raw: str) -> str:
    """Remove leading reasoning, never rewrite literal strings inside JSON.

    qa_fidelity's prose filtering is deliberately not used for structured data:
    a legitimate SVG text may itself contain the characters '<think>'.
    """
    text = raw.strip()
    while text.lower().startswith("<think>"):
        depth = 0
        end = None
        for match in re.finditer(r"</?think>", text, re.I):
            depth += -1 if match.group(0).startswith("</") else 1
            if depth == 0:
                end = match.end()
                break
        if end is None:
            return ""
        text = text[end:].strip()
    # Templates may supply the opening tag. A complete JSON candidate takes
    # precedence, so a closing tag inside a JSON string remains literal data.
    if not text.startswith(("[", "<svg", "```")) and re.search(r"</think>", text, re.I):
        text = re.split(r"</think>", text, flags=re.I)[-1].strip()
    return text


def _answer_values(raw: str, field: str, count: int) -> tuple[str, list]:
    """Require one complete typed JSON array, never extract a matching substring."""
    answer = _final_payload(raw)
    def reject_constant(value):
        raise ValueError(f"non-finite JSON number: {value}")
    values = json.loads(answer, parse_float=Decimal, parse_int=Decimal, parse_constant=reject_constant)
    if not isinstance(values, list) or len(values) != count:
        raise ValueError("answer must be one JSON array with one value per requested item")
    if field in {"circle.r", "rect.width", "line.x2"}:
        if any(not isinstance(value, Decimal) or not value.is_finite() for value in values):
            raise ValueError("numeric answers must contain only finite JSON numbers")
    elif any(not isinstance(value, str) for value in values):
        raise ValueError("text/color answers must contain only JSON strings")
    if field == "color":
        if len(set(values)) != len(values) or any(not re.fullmatch(r"#[0-9a-f]{6}", value) for value in values):
            raise ValueError("colors must be unique lowercase #rrggbb strings")
    return answer, values


def score_probes(probes: list[SvgProbe], generated: str, ask_fn) -> dict:
    """Score each source item; request each attribute list only once.

    A missing, malformed, unfinished or wrong-length list is explicitly
    unscorable and earns no hits. It is not replaced with a magic answer string.
    """
    counts: dict[str, int] = {}
    for probe in probes:
        counts[probe.field] = counts.get(probe.field, 0) + 1
    answers: dict[str, tuple[str, str, list | None, str | None]] = {}
    results = []
    for probe in probes:
        if probe.field not in answers:
            raw = ""
            try:
                raw = ask_fn(make_prompt(generated, probe.question))
                answer, values = _answer_values(raw, probe.field, counts[probe.field])
                answers[probe.field] = (raw, answer, values, None)
            except (RuntimeError, subprocess.TimeoutExpired, ValueError, TypeError, DecimalException) as exc:
                answers[probe.field] = (raw, _final_payload(raw) if isinstance(raw, str) else "", None, str(exc))
        raw, answer, values, error = answers[probe.field]
        ok = False
        if values is not None:
            expected = Decimal(probe.expected) if probe.kind == "number" else probe.expected
            ok = expected in values if probe.index is None else values[probe.index] == expected
        results.append({"kind": probe.kind, "field": probe.field, "index": probe.index,
                        "expected": probe.expected, "ok": ok, "question": probe.question,
                        "answer": answer, "raw_answer": raw, "error": error,
                        "status": "unscorable" if error is not None else "scored"})
    hits = sum(result["ok"] for result in results)
    unscorable = sum(result["status"] == "unscorable" for result in results)
    return {"hits": hits, "total": len(probes), "score": round(hits / len(probes), 3) if probes else None,
            "status": ("incomplete" if unscorable else "scored") if probes else "not_applicable",
            "results": results, "unscorable": unscorable}


def run(source_svg: str, ask_fn) -> dict:
    """Run describe, generate, validate and probe with ``ask_fn(prompt) -> str``."""
    original = canonicalize(source_svg)
    report: dict = {"description": "", "generated": "", "dsl_ok": False,
                    "score": 0.0, "hits": 0, "total": 0, "errors": [],
                    "prompt_version": PROMPT_VERSION, "scorer_version": SCORER_VERSION}
    stage = "describe"
    try:
        description = _final_payload(ask_fn(describe_prompt(original)))
        if not description:
            raise ValueError("no completed description")
        report["description"] = description
        stage = "generate"
        raw = ask_fn(generate_prompt(description))
        generated_src = extract_svg(raw)
    except (RuntimeError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
        report["status"] = "incomplete"
        report["errors"].append(f"{stage}: {exc}")
        return report
    report["generated"] = generated_src
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

    report.update(score_probes(probes, generated, ask_fn))
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
        try:
            report = run(text, lambda p: ask(args.cmd, p))
        except subprocess.TimeoutExpired as exc:  # probe answers only catch RuntimeError, so this can escape run()
            report = {"dsl_ok": False, "score": None, "hits": 0, "total": 0, "errors": [],
                      "run_error": f"timeout after {exc.timeout}s"}
        report["figure"] = path.name
        report["source_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        reports.append(report)
        if args.output:  # keep finished figures if a later one fails
            _write(args, reports)
    if not args.output:
        _write(args, reports)
    return 0 if all(r["dsl_ok"] for r in reports) else 1


def _write(args: argparse.Namespace, reports: list[dict]) -> None:
    meta = {
        "stage": "L3",
        "model": args.model,
        "command": args.cmd,
        "llama_url": os.environ.get("LLAMA_URL", "http://127.0.0.1:8080/v1/chat/completions"),
        "max_tokens_env": os.environ.get("LLAMA_MAX_TOKENS", "128 (default)"),
        "dsl_version": DSL_VERSION,
        "prompt_version": PROMPT_VERSION,
        "scorer_version": SCORER_VERSION,
        "python": sys.version.split()[0],
    }
    out = {"meta": meta, "reports": reports}
    text = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    raise SystemExit(main())
