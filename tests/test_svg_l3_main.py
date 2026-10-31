"""CLI bookkeeping for SVG L3: failures are recorded per figure, never turned into a verdict."""
import io
import json
import socket
import subprocess
from pathlib import Path

import pytest

from shared import llama_cmd, svg_l3

FIGURE = Path(__file__).parents[1] / "examples/figures/flow_basic.svg"


def test_cut_off_answer_is_recorded_by_run_as_incomplete(monkeypatch, tmp_path):
    def boom(cmd, prompt, timeout=None):
        raise RuntimeError("model command failed (1): answer did not complete: 'length'")

    monkeypatch.setattr(svg_l3, "ask", boom)
    out = tmp_path / "report.json"
    code = svg_l3.main([str(FIGURE), "--cmd", "unused", "--model", "test", "-o", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))["reports"][0]
    assert report["status"] == "incomplete"
    assert "run_error" not in report
    assert report["score"] == 0.0 and report["dsl_ok"] is False
    assert code == 1


def test_timeout_escaping_run_is_recorded_as_run_error(monkeypatch, tmp_path):
    def timeout(source, ask_fn):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1860)

    monkeypatch.setattr(svg_l3, "run", timeout)
    out = tmp_path / "report.json"
    svg_l3.main([str(FIGURE), "--cmd", "unused", "--model", "test", "-o", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))["reports"][0]
    assert report["run_error"] == "timeout after 1860s"
    assert report["score"] is None


def test_finished_figures_are_kept_when_a_later_figure_times_out(monkeypatch, tmp_path):
    calls = iter([{"figure_ok": True}, subprocess.TimeoutExpired(cmd="x", timeout=5)])

    def fake_run(source, ask_fn):
        item = next(calls)
        if isinstance(item, Exception):
            raise item
        return {"dsl_ok": True, "score": 1.0, "hits": 1, "total": 1, "errors": []}

    monkeypatch.setattr(svg_l3, "run", fake_run)
    out = tmp_path / "report.json"
    svg_l3.main([str(FIGURE), str(FIGURE), "--cmd", "unused", "--model", "test", "-o", str(out)])
    reports = json.loads(out.read_text(encoding="utf-8"))["reports"]
    assert len(reports) == 2
    assert reports[0]["score"] == 1.0 and "run_error" not in reports[0]
    assert "run_error" in reports[1]


def test_unreachable_llama_server_is_a_named_measurement_failure(monkeypatch, capsys):
    with socket.socket() as probe:  # a port that is closed right now
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setenv("LLAMA_URL", f"http://127.0.0.1:{port}/v1/chat/completions")
    monkeypatch.setattr("sys.stdin", io.StringIO("prompt"))
    assert llama_cmd.main() == 2
    assert "llama-server unreachable" in capsys.readouterr().err
