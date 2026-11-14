"""Offline plumbing for scripts/qwen_readability.py: a fake OpenAI-style server stands in for llama-server."""
from __future__ import annotations

import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import scripts.qwen_readability as qr

ROOT = Path(__file__).resolve().parents[1]


class Echo(BaseHTTPRequestHandler):
    """Restores by echoing the compressed paragraph back, one sentence per line; judges say YES."""

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][0]["content"]
        text = "YES" if prompt.startswith("Two ") else prompt.split("\n\n", 1)[1]
        data = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": text}}],
                           "usage": {"completion_tokens": 1}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture()
def url():
    srv = HTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1/chat/completions"
    srv.shutdown()


def test_plan_shards_cover_selection_once():
    p = qr.plan(4, ["rule", "qwen-0.5b"], per_lang=1)
    assert p["items"] == 39 and json.loads(p["judges"]) == {"judge": ["qwen-0.5b"]}
    items = qr.select(qr.pr.load_json(qr.pr.path("pack", 1)), 1)
    ids = [x["id"] for s in range(4) for x in qr.shard_of(items, s, 4)]
    assert sorted(ids) == sorted(x["id"] for x in items) and len(set(ids)) == len(ids)
    with pytest.raises(SystemExit):
        qr.plan(2, ["no-such-judge"], 0)


def test_restore_merge_judge_end_to_end(tmp_path, url):
    for s in range(2):
        assert qr.main(["restore", "--shard", str(s), "--shards", "2", "--per-lang", "1", "--url", url,
                        "--out", str(tmp_path / f"shard-{s}.json")]) == 0
    assert qr.main(["merge", str(tmp_path / "shard-*.json"), "--out", str(tmp_path / "m.json"),
                    "--markdown", str(tmp_path / "m.md")]) == 0
    m = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert m["items_answered"] == m["items_expected"] == 39
    assert m["ai_readability"] == {"status": "measured", "restorer": "qwen-1.5b", "judge": "rule"}
    ctl = m["summary"]["control"]["all"]
    assert ctl["notation_tolerant"] >= ctl["semantic_rule"] >= ctl["exact"]
    assert m["summary"]["control"]["size"]["o200k_delta_pct"] == 0
    # Echoing the compressed text back loses wherever the codec changed words: every failure has a reason.
    assert m["failures"] and all(f["reasons"] for f in m["failures"])
    assert "| CEF |" in (tmp_path / "m.md").read_text(encoding="utf-8")
    assert qr.main(["judge", str(tmp_path / "m.json"), "--model", "qwen-0.5b", "--url", url,
                    "--out", str(tmp_path / "j.json")]) == 0
    j = json.loads((tmp_path / "j.json").read_text(encoding="utf-8"))
    assert j["judge"]["type"] == "llm" and j["restorer"] == "qwen-1.5b"
    # The rule numbers are kept; the LLM column only adds sentences the judge accepted (fake judge: all YES).
    for meth, s in j["summary"].items():
        assert s["notation_tolerant"] == m["summary"][meth]["all"]["notation_tolerant"]
        assert s["notation_tolerant"] + s["llm_equivalent"] <= s["sentences"]
    assert sum(s["llm_equivalent"] for s in j["summary"].values()) > 0


def test_unreachable_server_is_recorded_not_raised(tmp_path):
    res = qr.restore(0, 60, "qwen-1.5b", "http://127.0.0.1:9/v1/chat/completions", per_lang=1)
    assert res["answers"] and all(a["status"] == "error" for a in res["answers"])
    write = tmp_path / "s.json"; qr.write(write, res)
    m = qr.merge([write])
    assert all(f["reasons"][0].startswith("no_answer") for f in m["failures"])
