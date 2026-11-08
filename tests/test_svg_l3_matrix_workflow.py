"""#87: SVG L3 matrix workflow and its helper (no quality threshold)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import svg_l3_bench as bench  # noqa: E402

WORKFLOW = ROOT / ".github/workflows/svg-l3-matrix.yml"
MODELS = json.loads((ROOT / "shared/l3_models.json").read_text(encoding="utf-8"))


def test_catalog_has_seven_pinned_models_about_6_86_gb():
    assert len(MODELS) == 7
    for model in MODELS.values():
        assert re.fullmatch(r"[0-9a-f]{40}", model["revision"])
        assert re.fullmatch(r"[0-9a-f]{64}", model["sha256"])
        assert model["revision"] in model["url"]
    assert MODELS["qwen-0.5b"]["sha256"] == "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"
    total = sum(m["bytes"] for m in MODELS.values())
    assert 6.8e9 < total < 10e9


def test_pull_request_never_fans_out():
    assert bench.select_models("pull_request", "all", MODELS) == ["qwen-0.5b"]
    assert bench.select_models("pull_request", "", MODELS) == ["qwen-0.5b"]


def test_dispatch_default_all_and_selection():
    assert bench.select_models("workflow_dispatch", "", MODELS) == ["qwen-0.5b"]
    assert bench.select_models("workflow_dispatch", "all", MODELS) == list(MODELS)
    assert bench.select_models("workflow_dispatch", "lfm3-1.7b, qwen-1.5b,lfm3-1.7b", MODELS) == ["lfm3-1.7b", "qwen-1.5b"]
    with pytest.raises(ValueError):
        bench.select_models("workflow_dispatch", "nope", MODELS)


def test_matrix_cli_writes_github_output(tmp_path):
    out = tmp_path / "o"
    subprocess.run([sys.executable, "scripts/svg_l3_bench.py", "matrix", "workflow_dispatch", "all",
                    "--github-output", str(out)], cwd=ROOT, check=True, capture_output=True)
    assert json.loads(out.read_text().split("=", 1)[1]) == {"model": list(MODELS)}


def _req(fig, completed=True, usage=(10, 5)):
    row = {"figure": fig, "answer_completed": completed, "phase": "roundtrip"}
    row["response"] = {}
    row["usage"] = None if usage is None else {"prompt_tokens": usage[0], "completion_tokens": usage[1]}
    return row


def test_quality_failures_are_raw_numbers_not_failures():
    report = {"meta": {"model": "m", "max_tokens_env": "2048"}, "reports": [
        {"figure": "a.svg", "dsl_ok": False, "errors": ["bad element"], "description": "d"},
        {"figure": "b.svg", "dsl_ok": True, "hits": 1, "total": 4, "status": "incomplete", "unscorable": 2,
         "description": "d", "source_control": {"hits": 4, "total": 4, "status": "scored"}},
    ]}
    s = bench.summarize(report, [_req("a.svg"), _req("b.svg", completed=False), _req("b.svg")], ["a.svg", "b.svg"])
    assert s["measurement_complete"] is True
    a, b = s["figures"]
    assert (a["dsl_ok"], a["roundtrip"], a["completed"]) == (False, None, True)
    assert b["roundtrip"]["hits"] == 1 and b["roundtrip"]["total"] == 4 and b["completed"] is False
    assert b["source_control"]["hits"] == 4
    assert b["tokens"] == {"prompt": 20, "completion": 10, "requests": 2, "unfinished_answers": 1}
    assert "| b.svg | no | yes | 1/4 | 4/4 | 20 | 10 | 2 |" in bench.to_markdown(s)


@pytest.mark.parametrize("report,requests,expected", [
    (None, [_req("a.svg")], "report missing"),
    ({"reports": []}, [_req("a.svg")], "figures measured"),
    ({"reports": [{"figure": "a.svg", "execution_errors": {"describe": "boom"}}]}, [_req("a.svg")], "did not complete"),
    ({"reports": [{"figure": "a.svg", "run_error": "timeout"}]}, [_req("a.svg")], "did not complete"),
    ({"reports": [{"figure": "a.svg", "source_control": {"execution_errors": {"color": "x"}}}]}, [_req("a.svg")], "did not complete"),
    ({"reports": [{"figure": "a.svg"}]}, [_req("a.svg", usage=None)], "tokenizer"),
    ({"reports": [{"figure": "a.svg"}]}, [], "no model requests"),
])
def test_incomplete_measurement_fails(report, requests, expected):
    s = bench.summarize(report, requests, ["a.svg"])
    assert s["measurement_complete"] is False
    assert any(expected in p for p in s["problems"])


def test_summarize_cli_exit_codes(tmp_path):
    figs = tmp_path / "figs"; figs.mkdir(); (figs / "a.svg").write_text("<svg/>")
    rep = tmp_path / "r.json"; req = tmp_path / "q.jsonl"
    rep.write_text(json.dumps({"reports": [{"figure": "a.svg", "dsl_ok": False}]}))
    req.write_text(json.dumps(_req("a.svg")) + "\n")
    cmd = [sys.executable, "scripts/svg_l3_bench.py", "summarize", str(rep), str(req), "--out-dir", str(tmp_path / "o"), "--figures", str(figs)]
    assert subprocess.run(cmd, cwd=ROOT, capture_output=True).returncode == 0
    assert json.loads((tmp_path / "o/summary.json").read_text())["figures"][0]["dsl_ok"] is False
    req.write_text("")
    assert subprocess.run(cmd, cwd=ROOT, capture_output=True).returncode == 1


def test_workflow_matches_issue_87_decisions():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'LLAMA_MAX_TOKENS: "2048"' in text and 'LLAMA_CONTEXT: "4096"' in text and '-c "$LLAMA_CONTEXT"' in text
    assert "pull_request:" in text and "workflow_dispatch:" in text
    assert "svg_l3_bench.py matrix" in text and "fromJSON(needs.plan.outputs.matrix)" in text
    assert "fail-fast: false" in text
    # svg_l3.py's DSL exit 1 is recorded, not a verdict.
    measure = text.split("Measure every figure", 1)[1].split("- name:", 1)[0]
    assert "set +e" in measure and "exit $status" not in measure
    assert "upload-artifact" in text and "if: always()" in text
    assert "playwright" not in text.lower() and "svg_render" not in text
    # Distinct from the manual-only svg-l3.yml that #152 removes.
    assert "svg-l3.yml" not in text.replace("svg-l3-matrix.yml", "")


def test_actions_pinned_to_full_sha():
    uses = re.findall(r"uses:\s*(\S+)", WORKFLOW.read_text(encoding="utf-8"))
    assert uses
    for ref in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), ref
