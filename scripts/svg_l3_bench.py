#!/usr/bin/env python3
"""SVG L3 matrix workflow helpers (#87). Stdlib only.

``matrix EVENT CHOICE``
    Print the GitHub Actions matrix. ``pull_request`` always measures one model
    (the default); ``workflow_dispatch`` accepts one key, a comma list, or ``all``.

``summarize REPORT REQUESTS --out-dir DIR``
    Turn ``svg_l3.py`` output and ``llama_cmd.py`` request evidence into raw,
    benchmark-like numbers per figure (complete/incomplete, DSL pass, probe
    hits/total, token counts). There is no quality threshold: DSL failures,
    unfinished answers and low scores are reported, never judged. The exit
    status is 1 only when the measurement itself did not complete (missing
    figures, transport/startup/inference errors, or missing tokenizer counts).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CATALOG = Path("shared/l3_models.json")
DEFAULT_MODEL = "qwen-0.5b"
FIGURES = Path("examples/figures")


def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def select_models(event: str, choice: str | None, models: dict | None = None) -> list[str]:
    models = catalog() if models is None else models
    if event != "workflow_dispatch":
        # PR / push events never fan out to every model.
        return [DEFAULT_MODEL]
    choice = (choice or DEFAULT_MODEL).strip()
    if choice == "all":
        return list(models)
    keys = [part.strip() for part in choice.split(",") if part.strip()]
    unknown = [k for k in keys if k not in models]
    if not keys or unknown:
        raise ValueError(f"unknown model(s) {unknown or [choice]!r}; choose all or from {', '.join(models)}")
    return list(dict.fromkeys(keys))


def _load_requests(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _probe(block: dict | None) -> dict | None:
    if not block:
        return None
    return {"hits": block.get("hits", 0), "total": block.get("total", 0),
            "status": block.get("status"), "unscorable": block.get("unscorable", 0)}


def summarize(report: dict | None, requests: list[dict], expected: list[str]) -> dict:
    problems: list[str] = []
    reports = (report or {}).get("reports", [])
    if report is None:
        problems.append("svg_l3 report missing")
    names = sorted(r.get("figure", "") for r in reports)
    if report is not None and names != sorted(expected):
        problems.append(f"figures measured {names} != expected {sorted(expected)}")
    if not requests:
        problems.append("no model requests were recorded")
    figures = []
    for r in reports:
        fig = r.get("figure", "")
        rows = [q for q in requests if q.get("figure") == fig]
        if not rows:
            problems.append(f"{fig}: no model requests were recorded")
        tokens = {"prompt": 0, "completion": 0, "requests": len(rows), "unfinished_answers": 0}
        for q in rows:
            if not q.get("answer_completed"):
                tokens["unfinished_answers"] += 1
            if "response" in q:  # the server answered; it must report token counts
                usage = q.get("usage") or {}
                if not isinstance(usage.get("prompt_tokens"), int) or not isinstance(usage.get("completion_tokens"), int):
                    problems.append(f"{fig}: tokenizer counts missing in a server response")
                    continue
                tokens["prompt"] += usage["prompt_tokens"]
                tokens["completion"] += usage["completion_tokens"]
        execution = dict(r.get("execution_errors") or {})
        execution.update({f"source_control.{k}": v for k, v in
                          ((r.get("source_control") or {}).get("execution_errors") or {}).items()})
        if "run_error" in r:
            execution["run"] = r["run_error"]
        if any("llama-server unreachable" in e for e in r.get("errors", [])):
            execution["server"] = "llama-server unreachable"
        if execution:
            problems.append(f"{fig}: measurement did not complete: {sorted(execution)}")
        # "incomplete" = an unfinished/unscorable model answer somewhere in the round trip.
        completed = bool(rows) and r.get("status") != "incomplete" and "run_error" not in r and not execution
        figures.append({
            "figure": fig,
            "completed": completed,
            "dsl_ok": bool(r.get("dsl_ok")),
            "roundtrip": _probe(r) if r.get("dsl_ok") else None,
            "source_control": _probe(r.get("source_control")),
            "tokens": tokens,
            "execution_errors": execution,
            "errors": r.get("errors", []),
        })
    meta = (report or {}).get("meta", {})
    return {"model": meta.get("model"), "max_tokens": meta.get("max_tokens_env"),
            "measurement_complete": not problems, "problems": problems, "figures": figures}


def to_markdown(summary: dict) -> str:
    def pr(block):
        return f"{block['hits']}/{block['total']}" if block else "-"
    lines = [f"### SVG L3: {summary['model']} (max_tokens={summary['max_tokens']}, -c 4096)", "",
             "合否判定なし。生の数字のみ。", "",
             "| figure | 完了 | DSL通過 | probe hits/total | source control hits/total | prompt tok | completion tok | requests |",
             "|---|---|---|---|---|---|---|---|"]
    for f in summary["figures"]:
        t = f["tokens"]
        lines.append(f"| {f['figure']} | {'yes' if f['completed'] else 'no'} | {'yes' if f['dsl_ok'] else 'no'} | "
                     f"{pr(f['roundtrip'])} | {pr(f['source_control'])} | {t['prompt']} | {t['completion']} | {t['requests']} |")
    if summary["problems"]:
        lines += ["", "計測が完了していません:"] + [f"- {p}" for p in summary["problems"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("matrix")
    m.add_argument("event")
    m.add_argument("choice", nargs="?", default="")
    m.add_argument("--github-output", type=Path)
    s = sub.add_parser("summarize")
    s.add_argument("report", type=Path)
    s.add_argument("requests", type=Path)
    s.add_argument("--out-dir", type=Path, required=True)
    s.add_argument("--figures", type=Path, default=FIGURES)
    args = parser.parse_args(argv)
    if args.cmd == "matrix":
        try:
            keys = select_models(args.event, args.choice)
        except ValueError as exc:
            parser.error(str(exc))
        matrix = json.dumps({"model": keys}, separators=(",", ":"))
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as stream:
                stream.write(f"matrix={matrix}\n")
        print(matrix)
        return 0
    report = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() and args.report.stat().st_size else None
    expected = [p.name for p in args.figures.glob("*.svg")]
    summary = summarize(report, _load_requests(args.requests), expected)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = to_markdown(summary)
    (args.out_dir / "summary.md").write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 0 if summary["measurement_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
