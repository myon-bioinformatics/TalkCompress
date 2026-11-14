"""Offline plumbing for scripts/ai_readability.py: a fake OpenAI-style server stands in for llama-server."""
from __future__ import annotations

import json, math, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import scripts.ai_readability as ar


class Echo(BaseHTTPRequestHandler):
    """Restores by echoing the compressed paragraph back; the judge says YES unless A == B differs in length."""

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][0]["content"]
        if prompt.startswith("Two "):  # judge: only logprobs matter, never the generated text
            a, b = prompt.rsplit("\nA: ", 1)[1].split("\nB: ")
            p_yes = 0.9 if abs(len(a) - len(b)) < 3 else 0.2
            top = [{"token": "YES", "logprob": math.log(p_yes)}, {"token": " no", "logprob": math.log(1 - p_yes)}]
            choice = {"finish_reason": "length", "message": {"content": "X"}, "logprobs": {"content": [{"top_logprobs": top}]}}
        else:
            choice = {"finish_reason": "stop", "message": {"content": prompt.split("\n\n", 1)[1]}}
        data = json.dumps({"choices": [choice], "usage": {"completion_tokens": 1}}).encode()
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
    jm = json.loads(p["judge_matrix"])["include"]  # the NLI judge fixes its own shard count (1)
    assert [(x["restorer"], x["judge"], x["backend"], x["shard"], x["shards"]) for x in jm] == [
        ("qwen3-0.6b", "mdeberta-xnli-onnx", "nli-onnx", 0, 1)]
    llm = json.loads(ar.plan("pr-smoke", judges=["lfm2.5-1.2b-qad"])["judge_matrix"])["include"]
    assert [(x["backend"], x["shard"], x["shards"]) for x in llm] == [("llm-logprob", s, 4) for s in range(4)]
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
    assert set(ar.EVENT_PRESETS.values()) <= set(ar.PRESETS)


def test_ci_event_picks_preset(tmp_path, capsys):
    for event, preset in ar.EVENT_PRESETS.items():
        gh = tmp_path / f"{event}.txt"
        assert ar.main(["plan", "--event", event, "--github-output", str(gh)]) == 0
        lines = dict(line.split("=", 1) for line in gh.read_text(encoding="utf-8").splitlines())
        assert lines["preset"] == preset
    with pytest.raises(SystemExit):
        ar.main(["plan", "--event", "push", "--preset", "full"])


def test_restore_merge_judge_report_end_to_end(tmp_path, url):
    for s in range(2):
        assert ar.main(["restore", "--shard", str(s), "--shards", "2", "--per-lang", "1", "--url", url,
                        "--out", str(tmp_path / f"shard-{s}.json")]) == 0
    shard = json.loads((tmp_path / "shard-0.json").read_text(encoding="utf-8"))
    a0 = shard["answers"][0]  # traceable: inputs, raw response and pins are in the shard file
    assert {"id", "prompt", "prompt_sha256", "restore_prompt_sha256", "compressed_text", "response", "raw", "answer"} <= set(a0)
    assert shard["restore_prompt_version"] == ar.RESTORE_PROMPT_VERSION and a0["raw"].startswith("1. ")
    assert a0["restore_prompt_sha256"] == ar.pr.sha256(a0["prompt"]) != a0["prompt_sha256"]
    assert shard["restore"]["sha256"] and shard["restore"]["llama"] == "image" and shard["restore"]["inputs_sha256"]
    assert ar.main(["merge", str(tmp_path / "shard-*.json"), "--out", str(tmp_path / "m.json")]) == 0
    m = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert m["items_answered"] == m["items_expected"] == 39
    assert all(v["status"] == "ok" and v["format_followed"] for v in m["items"].values())
    assert m["summary"]["control"]["all"]["format_followed"] == m["summary"]["control"]["all"]["judgements"]
    ctl = m["summary"]["control"]["all"]
    assert ctl["notation_tolerant"] >= ctl["semantic_rule"] >= ctl["exact"]
    assert m["summary"]["control"]["size"]["o200k_delta_pct"] == 0
    assert m["failures"] and all(f["reasons"] for f in m["failures"])
    for s in range(2):
        assert ar.main(["judge", str(tmp_path / "m.json"), "--model", "lfm2.5-1.2b-qad", "--url", url,
                        "--shard", str(s), "--shards", "2", "--out", str(tmp_path / f"judge-{s}.json")]) == 0
    j0 = json.loads((tmp_path / "judge-0.json").read_text(encoding="utf-8"))
    assert j0["judge"]["backend"] == "llm-logprob" and all(0 <= v["score"] <= 1 for v in j0["scores"])
    assert ar.main(["report", str(tmp_path / "m.json"), str(tmp_path / "judge-*.json"),
                    "--out", str(tmp_path / "r.json"), "--markdown", str(tmp_path / "r.md")]) == 0
    r = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert r["ai_readability"] == {"status": "measured", "restorer": "qwen3-0.6b", "judges": ["rule", "lfm2.5-1.2b-qad"]}
    j = r["judges"]["lfm2.5-1.2b-qad"]
    assert j["shards"] == 2 and j["pins"]["sha256"] == ar.catalog()["lfm2.5-1.2b-qad"]["sha256"] and j["threshold"] == 0.5
    for meth, s in j["summary"].items():
        assert s["sentences"] == r["rule"][meth]["sentences"]
        assert s["rule_pass_judge_yes"] + s["rule_pass_judge_no"] == r["rule"][meth]["notation_tolerant"]
        assert 0 <= s["agreement_rate"] <= 1 and 0 <= s["mean_score"] <= 1
    assert sum(s["rule_fail_judge_yes"] for s in j["summary"].values()) > 0  # the judge can disagree with the rules
    md = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "agreement with notation_tolerant" in md and "one sentence per line" in md and ar.RESTORE_PROMPT_VERSION in md
    # YES/NO is derived from the scores afterwards: a threshold above every score turns all into NO.
    strict = ar.report(m, ar.expand([str(tmp_path / "judge-*.json")]), threshold=0.95)
    assert all(s["judge_yes"] == 0 for s in strict["judges"]["lfm2.5-1.2b-qad"]["summary"].values())


def test_nli_backend_is_pluggable(tmp_path, url, monkeypatch):
    """The NLI plug-in needs onnxruntime; here a stand-in with the same contract proves the wiring."""
    assert ar.main(["restore", "--per-lang", "1", "--url", url, "--out", str(tmp_path / "shard-0.json")]) == 0
    m = ar.merge([tmp_path / "shard-0.json"])
    seen = {}

    def fake(pairs, entry, model_dir, url_):
        seen["model_dir"] = model_dir
        return [{"score": 1.0 if p["notation_tolerant"] else 0.0, "p_entail_fwd": 1.0, "p_entail_bwd": 1.0} for p in pairs]

    monkeypatch.setitem(ar.JUDGE_BACKENDS, "nli-onnx", fake)
    res = ar.judge(m, "mdeberta-xnli-onnx", url, {}, model_dir=tmp_path)
    assert res["judge"]["backend"] == "nli-onnx" and "llama" not in res["judge"] and seen["model_dir"] == tmp_path
    ar.write(tmp_path / "judge-nli.json", res)
    rep = ar.report(m, [tmp_path / "judge-nli.json"])
    for s in rep["judges"]["mdeberta-xnli-onnx"]["summary"].values():
        assert s["rule_pass_judge_no"] == 0 and s["rule_fail_judge_yes"] == 0  # this stand-in mirrors the rules


def test_unreachable_server_is_recorded_not_raised(tmp_path):
    res = ar.restore(0, 60, "qwen3-0.6b", "http://127.0.0.1:9/v1/chat/completions", 1, ar.llama_pin(None))
    assert res["answers"] and all(a["status"] == "error" for a in res["answers"])
    ar.write(tmp_path / "s.json", res)
    m = ar.merge([tmp_path / "s.json"])
    assert all(f["reasons"][0].startswith("no_answer") or f["reasons"] for f in m["failures"])
    r = ar.report(m, [])
    assert r["judges"] == {} and r["rule"]["control"]["no_answer"] >= 1


def test_restore_prompt_numbers_the_input_sentences_not_the_gold():
    pack = {p["id"]: p for p in ar.pr.load_json(ar.pr.path("pack", 1))}
    gold = {p["id"]: p["sentences"] for p in ar.pr.load_json(ar.pr.SOURCES)["paragraphs"]}
    # Latin: the input splits on ";" into 7 pieces while the gold has 4 sentences; the B mosaic has 4 tiles.
    ctl = pack["la-caesar-01|control"]["compressed_text"]
    assert len(ar.input_sentences(ctl)) == 7 != len(gold["la-caesar-01"])
    assert len(ar.input_sentences(pack["la-caesar-01|BEF"]["compressed_text"])) == 4
    prompt = ar.restore_prompt("la", ctl)
    assert "Its 7 sentences are numbered" in prompt and "Write them in Latin; do not translate." in prompt
    body = prompt.split("\n\n", 1)[1].split("\n")
    assert [ln.split(". ", 1)[0] for ln in body] == [str(k) for k in range(1, 8)]
    assert ar.input_sentences("") == [""]


def test_unnumber():
    assert ar.unnumber("1. Uno.\r\n\n2) Due.\n 3、三。\nNo number.") == "Uno.\nDue.\n三。\nNo number."
    assert ar.pr.split_answer(ar.unnumber("1. A.\n2. B."), 2) == (["A.", "B."], True)


def test_merge_rejects_shards_from_another_restore_prompt(tmp_path, url):
    assert ar.main(["restore", "--per-lang", "1", "--shards", "60", "--url", url, "--out", str(tmp_path / "s.json")]) == 0
    s = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    s["restore_prompt_version"] = "paragraph-restore-v1"  # an old shard (pack prompt, unnumbered answers)
    ar.write(tmp_path / "s.json", s)
    with pytest.raises(SystemExit):
        ar.merge([tmp_path / "s.json"])
