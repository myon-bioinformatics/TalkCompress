"""Offline plumbing for scripts/ai_readability.py: a fake OpenAI-style server stands in for llama-server."""
from __future__ import annotations

import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import scripts.ai_readability as ar


class Echo(BaseHTTPRequestHandler):
    """Restores by echoing the compressed paragraph back; the judge says YES unless A == B differs in length."""

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][0]["content"]
        if prompt.startswith("Two "):
            a, b = prompt.rsplit("\nA: ", 1)[1].split("\nB: ")
            text = "YES" if abs(len(a) - len(b)) < 3 else "NO"
        else:
            text = prompt.split("\n\n", 1)[1]
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


def test_presets_are_catalog_driven_and_shards_cover_once():
    p = ar.plan("pr-smoke")
    assert p["restorers"] == ["qwen3-0.6b"] and p["items_per_restorer"] == 39 and p["llama"] == "build"
    jm = json.loads(p["judge_matrix"])["include"]
    assert [(x["restorer"], x["judge"], x["shard"]) for x in jm] == [("qwen3-0.6b", "lfm2.5-1.2b-qad", s) for s in range(4)]
    assert all(x["sha256"] == ar.catalog()[x["model"]]["sha256"] for x in json.loads(p["models"])["include"])
    pair = ar.plan("full-pair", shards=2, judges=["qwen-0.5b"])
    assert pair["items_per_restorer"] == 180 and len(json.loads(pair["restore_matrix"])["include"]) == 4
    assert json.loads(pair["restorer_matrix"]) == {"restorer": ["qwen3-0.6b", "qwen3-1.7b"]}
    for name, cfg in ar.PRESETS.items():  # every preset resolves against the catalog
        assert all(k in ar.catalog() for k in [*cfg["restorers"], *ar.DEFAULTS["judges"]]), name
    items = ar.select(ar.pr.load_json(ar.pr.path("pack", 1)), 1)
    ids = [x["id"] for s in range(4) for x in ar.shard_of(items, s, 4)]
    assert sorted(ids) == sorted(x["id"] for x in items) and len(set(ids)) == len(ids)
    for bad in ({"judges": ["no-such-judge"]}, {"restorers": ["nope"]}, {"llama": "gpu"}):
        with pytest.raises(SystemExit):
            ar.plan("pr-smoke", **bad)
    with pytest.raises(SystemExit):
        ar.plan("no-such-preset")


def test_restore_merge_judge_report_end_to_end(tmp_path, url):
    for s in range(2):
        assert ar.main(["restore", "--shard", str(s), "--shards", "2", "--per-lang", "1", "--url", url,
                        "--out", str(tmp_path / f"shard-{s}.json")]) == 0
    shard = json.loads((tmp_path / "shard-0.json").read_text(encoding="utf-8"))
    a0 = shard["answers"][0]  # traceable: inputs, raw response and pins are in the shard file
    assert {"id", "prompt", "prompt_sha256", "compressed_text", "response", "answer"} <= set(a0)
    assert shard["restore"]["sha256"] and shard["restore"]["llama"] == "image" and shard["restore"]["inputs_sha256"]
    assert ar.main(["merge", str(tmp_path / "shard-*.json"), "--out", str(tmp_path / "m.json")]) == 0
    m = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert m["items_answered"] == m["items_expected"] == 39
    ctl = m["summary"]["control"]["all"]
    assert ctl["notation_tolerant"] >= ctl["semantic_rule"] >= ctl["exact"]
    assert m["summary"]["control"]["size"]["o200k_delta_pct"] == 0
    assert m["failures"] and all(f["reasons"] for f in m["failures"])
    for s in range(2):
        assert ar.main(["judge", str(tmp_path / "m.json"), "--model", "lfm2.5-1.2b-qad", "--url", url,
                        "--shard", str(s), "--shards", "2", "--out", str(tmp_path / f"judge-{s}.json")]) == 0
    assert ar.main(["report", str(tmp_path / "m.json"), str(tmp_path / "judge-*.json"),
                    "--out", str(tmp_path / "r.json"), "--markdown", str(tmp_path / "r.md")]) == 0
    r = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert r["ai_readability"] == {"status": "measured", "restorer": "qwen3-0.6b", "judges": ["rule", "lfm2.5-1.2b-qad"]}
    j = r["judges"]["lfm2.5-1.2b-qad"]
    assert j["shards"] == 2 and j["pins"]["sha256"] == ar.catalog()["lfm2.5-1.2b-qad"]["sha256"]
    for meth, s in j["summary"].items():
        assert s["sentences"] == r["rule"][meth]["sentences"]
        assert s["rule_pass_judge_yes"] + s["rule_pass_judge_no"] == r["rule"][meth]["notation_tolerant"]
        assert 0 <= s["agreement_rate"] <= 1
    assert sum(s["rule_fail_judge_yes"] for s in j["summary"].values()) > 0  # the judge can disagree with the rules
    assert "agreement with notation_tolerant" in (tmp_path / "r.md").read_text(encoding="utf-8")


def test_unreachable_server_is_recorded_not_raised(tmp_path):
    res = ar.restore(0, 60, "qwen3-0.6b", "http://127.0.0.1:9/v1/chat/completions", 1, ar.llama_pin(None))
    assert res["answers"] and all(a["status"] == "error" for a in res["answers"])
    ar.write(tmp_path / "s.json", res)
    m = ar.merge([tmp_path / "s.json"])
    assert all(f["reasons"][0].startswith("no_answer") or f["reasons"] for f in m["failures"])
    r = ar.report(m, [])
    assert r["judges"] == {} and r["rule"]["control"]["no_answer"] >= 1
