"""End-to-end wiring test: svg_l3 -> llama_cmd -> OpenAI-style HTTP endpoint -> report.

The endpoint is a local stub, not a model. This checks the plumbing only (prompts,
finish_reason handling, JSON report), not any model's quality.
"""
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from shared.svg_l3 import main as l3_main
from shared.svg_l3 import probes_from
from shared.svg_dsl import canonicalize

ROOT = Path(__file__).resolve().parents[1]
FIGURE = ROOT / "examples/figures/flow_basic.svg"


class Stub(BaseHTTPRequestHandler):
    svg = FIGURE.read_text(encoding="utf-8")

    def log_message(self, *args):  # keep test output quiet
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][0]["content"]
        finish, content = "stop", "図の説明です。"
        if "Output the SVG only" in prompt:
            content = "```svg\n" + self.svg + "\n```"
        elif "List the text content" in prompt:
            finish, content = "length", "途中まで"  # simulate a cut-off answer
        elif "Context:" in prompt:
            # Fixture-backed typed answers, not context echo or a real model.
            probes = probes_from(canonicalize(self.svg))
            selected = [p for p in probes if p.question in prompt]
            content = json.dumps([float(p.expected) if p.kind == "number" else p.expected for p in selected])
        payload = {"choices": [{"message": {"content": content}, "finish_reason": finish}]}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def stub_url(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/v1/chat/completions"
    monkeypatch.setenv("LLAMA_URL", url)
    monkeypatch.setenv("LLAMA_MAX_TOKENS", "1024")
    yield url
    server.shutdown()


def test_pipeline_runs_end_to_end_and_records_cut_off_answers(stub_url, tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    out = tmp_path / "report.json"
    cmd = f"{sys.executable} shared/llama_cmd.py"
    rc = l3_main([str(FIGURE), "--cmd", cmd, "--model", "stub-endpoint", "-o", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    report = data["reports"][0]
    assert rc == 0
    assert data["meta"]["model"] == "stub-endpoint"
    assert data["meta"]["llama_url"] == stub_url
    assert data["meta"]["max_tokens_env"] == "1024"
    assert report["dsl_ok"] is True
    text_probes = [r for r in report["results"] if r["expected"] in {"入力", "変換", "出力"}]
    assert len(text_probes) == 3
    assert all(r["ok"] is False for r in text_probes)  # cut-off answers are never hits
    assert report["hits"] >= 1  # complete typed fixture answers still score
    assert all(r["status"] == "unscorable" for r in text_probes)
    assert data["meta"]["prompt_version"] == data["meta"]["scorer_version"] == "2"
