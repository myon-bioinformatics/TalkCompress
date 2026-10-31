"""Offline only: fake bytes, tokenizer modules and Llama; never real encodings/models."""
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("measure", "svoc2", "svoc3", "llm_roundtrip")
LLM = importlib.import_module("scripts.syntax_encoding.llm_roundtrip")


def test_all_modules_import_without_heavy_dependencies_or_side_effects(tmp_path):
    code = """
import builtins, importlib, sys
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'tiktoken', 'llama_cpp', 'ShorthandEdge'}:
        raise AssertionError('import side effect: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
for name in ('cases', 'measure', 'svoc2', 'svoc3', 'llm_roundtrip'):
    importlib.import_module('scripts.syntax_encoding.' + name)
"""
    result = subprocess.run([sys.executable, "-c", code, str(ROOT)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("args,expected", [([], 2), (["--help"], 0)])
def test_cli_help_and_missing_opt_in_never_import_workloads(name, args, expected, tmp_path):
    code = """
import builtins, runpy, sys
path = sys.argv[1]
sys.path.insert(0, __import__('os').path.dirname(path))
sys.argv = [path] + sys.argv[2:]
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'tiktoken', 'llama_cpp', 'ShorthandEdge'}:
        raise AssertionError('workload imported before opt-in: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
runpy.run_path(path, run_name='__main__')
"""
    result = subprocess.run([sys.executable, "-c", code, str(ROOT / "scripts/syntax_encoding" / (name + ".py")), *args],
                            cwd=tmp_path, capture_output=True, text=True, timeout=10)
    assert result.returncode == expected, result.stderr
    assert "AssertionError" not in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_case_store_is_inert_and_source_execution_is_gone():
    root = ROOT / "scripts/syntax_encoding"
    tree = ast.parse((root / "cases.py").read_text())
    assert all(isinstance(node, (ast.Assign, ast.Expr)) for node in tree.body)
    for node in tree.body:
        ast.literal_eval(node.value)
    for name in NAMES:
        tree = ast.parse((root / (name + ".py")).read_text())
        assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id in {"exec", "eval"} for node in ast.walk(tree))


@pytest.mark.parametrize("name", ["measure", "svoc2", "svoc3"])
def test_tokenizer_entrypoints_work_with_fake_encoding_only(name, monkeypatch, capsys):
    calls = []
    class FakeEncoding:
        def encode(self, text):
            return list(text.encode("utf-8"))
        def decode(self, tokens):
            return bytes(tokens).decode("utf-8", errors="replace")
    monkeypatch.setitem(sys.modules, "tiktoken", types.SimpleNamespace(
        get_encoding=lambda encoding: (calls.append(encoding) or FakeEncoding())))
    # No repository compressor is needed to prove safe CLI wiring.
    monkeypatch.setitem(sys.modules, "ShorthandEdge.shorthand_edge",
                        types.SimpleNamespace(compress=lambda text: text))
    module = importlib.import_module("scripts.syntax_encoding." + name)
    assert module.main(["--run"]) == 0
    assert calls == ["o200k_base"]
    assert capsys.readouterr().out


def model_args(tmp_path):
    model = tmp_path / "fake.gguf"
    model.write_bytes(b"FAKE MODEL BYTES, NOT WEIGHTS")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    out = tmp_path / "receipt.jsonl"
    return ["--run", "--model", str(model), "--model-sha256", digest,
            "--model-source", "fake fixture; not a model download", "--output", str(out)], out


@pytest.mark.parametrize("fault", ["missing_path", "missing_hash", "missing_source", "bad_hash", "mismatch", "existing_output"])
def test_model_preflight_rejects_before_import_or_load(tmp_path, monkeypatch, fault):
    args, output = model_args(tmp_path)
    if fault == "missing_path":
        args[args.index("--model") + 1] = str(tmp_path / "missing.gguf")
    elif fault == "missing_hash":
        at = args.index("--model-sha256")
        del args[at:at + 2]
    elif fault == "missing_source":
        at = args.index("--model-source")
        del args[at:at + 2]
    elif fault == "bad_hash":
        args[args.index("--model-sha256") + 1] = "bad"
    elif fault == "mismatch":
        args[args.index("--model-sha256") + 1] = "0" * 64
    else:
        output.write_text("historical evidence\n")
    def forbidden(*args, **kwargs):
        pytest.fail("model load must not occur on invalid preflight")
    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=forbidden))
    with pytest.raises(SystemExit) as error:
        LLM.main(args)
    assert error.value.code == 2
    if fault == "existing_output":
        assert output.read_text() == "historical evidence\n"
    else:
        assert not output.exists()


def fake_runtime(monkeypatch, behavior):
    class FakeLlama:
        metadata = {"source": "fixture"}
        chat_format = "fixture-format"
        def __init__(self, **kwargs):
            assert kwargs["n_ctx"] == 1024 and kwargs["n_gpu_layers"] == 0
            self.index = 0
        def create_chat_completion(self, messages, **kwargs):
            assert kwargs == {"temperature": 0, "max_tokens": 24}
            case = LLM.SVOC[self.index % len(LLM.SVOC)]
            self.index += 1
            gold = f"{case[0]} {case[1]} {case[2]} {case[3]}."
            return behavior(self.index, gold)
        def close(self):
            pass
    monkeypatch.setitem(sys.modules, "llama_cpp",
                        types.SimpleNamespace(Llama=FakeLlama, __version__="FAKE"))
    return FakeLlama


def completion(content, reason="stop"):
    return {"choices": [{"finish_reason": reason, "message": {"content": content}}]}


@pytest.mark.parametrize("choices", [None, [], [{}, {}], [None], [{"message": {}}]])
def test_malformed_or_multiple_choices_are_unscorable(choices):
    result = LLM.inspect_completion({"choices": choices}, "I feel happy.")
    assert result["status"] == "error"
    assert result["exact_match"] is None


def test_measure_direct_cli_uses_real_stdlib_compressor_with_fake_encoding(tmp_path):
    code = """
import builtins, pathlib, runpy, sys, types
root = pathlib.Path(sys.argv[1])
path = root / 'scripts/syntax_encoding/measure.py'
sys.path.insert(0, str(path.parent))
sys.argv = [str(path), '--run']
class FakeEncoding:
    def encode(self, text):
        return list(text.encode('utf-8'))
    def decode(self, tokens):
        return bytes(tokens).decode('utf-8', errors='replace')
sys.modules['tiktoken'] = types.SimpleNamespace(get_encoding=lambda name: FakeEncoding())
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'llama_cpp', 'requests', 'urllib', 'http', 'socket'}:
        raise AssertionError('unexpected model/network import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
try:
    runpy.run_path(str(path), run_name='__main__')
except SystemExit as error:
    assert error.code == 0
assert pathlib.Path(sys.modules['ShorthandEdge.shorthand_edge'].__file__) == root / 'ShorthandEdge/shorthand_edge.py'
assert 'shared.ledger' in sys.modules and 'shared.lex_policy' in sys.modules
"""
    result = subprocess.run([sys.executable, "-c", code, str(ROOT)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout and result.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_fake_success_records_every_full_response_and_provenance(tmp_path, monkeypatch):
    args, output = model_args(tmp_path)
    fake_runtime(monkeypatch, lambda index, gold: completion(gold))
    assert LLM.main(args) == 0
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    header = rows[0]
    trials = [row for row in rows if row["kind"] == "trial"]
    assert len(trials) == header["expected_trials"] == 60
    assert header["model"]["sha256"] == header["model"]["expected_sha256"]
    assert set(header["source_sha256"]) == {"llm_roundtrip.py", "cases.py"}
    assert header["system_prompt"] == LLM.SYSTEM
    assert header["generation_config"] == {"temperature": 0, "max_tokens": 24}
    assert all(row["response"]["choices"][0]["message"]["content"] == row["gold"] for row in trials)
    assert all(row["finish_reason"] == "stop" and row["exact_match"] for row in trials)
    assert rows[-1]["complete"] is True and rows[-1]["exact_matches"] == 60


def test_incomplete_malformed_and_error_receipts_never_score_as_hits(tmp_path, monkeypatch):
    args, output = model_args(tmp_path)
    def behavior(index, gold):
        if index == 1:
            return completion(gold, "length")
        if index == 2:
            return completion(gold + "\nEXTRA WRONG ANSWER")
        if index == 3:
            raise TimeoutError("fake timeout")
        if index == 4:
            return {}
        if index == 5:
            return completion(None)
        return completion(gold)
    fake_runtime(monkeypatch, behavior)
    assert LLM.main(args) == 2
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    trials = [row for row in rows if row["kind"] == "trial"]
    assert len(trials) == 60
    assert trials[0]["status"] == "incomplete" and trials[0]["exact_match"] is None
    assert "\nEXTRA WRONG ANSWER" in trials[1]["content"]
    assert trials[1]["exact_match"] is False
    assert trials[2]["error"]["type"] == "TimeoutError"
    assert trials[3]["response"] == {} and trials[3]["exact_match"] is None
    assert trials[4]["content"] is None and trials[4]["exact_match"] is None
    assert rows[-1]["complete"] is False
    assert rows[-1]["exact_matches"] == 55


def test_model_initialization_failure_still_writes_incomplete_receipt(tmp_path, monkeypatch):
    args, output = model_args(tmp_path)
    def fail(**kwargs):
        raise RuntimeError("fake initialization error")
    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=fail, __version__="FAKE"))
    assert LLM.main(args) == 2
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert any(row["kind"] == "run_error" for row in rows)
    assert rows[-1]["complete"] is False and rows[-1]["attempted"] == 0

