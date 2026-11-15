"""shared/svg_l3.py: 説明→SVG→質問回答の L3 検証、証跡、実行失敗の扱い、CLI、配線。

- svg_l3
- svg_l3_evidence: Offline evidence and source-control regressions; no model required.
- svg_l3_execution_failures: Offline transport-vs-quality regressions; never starts a model or network call.
- svg_l3_main: CLI bookkeeping for SVG L3: failures are recorded per figure, never turned into a verdict.
- svg_l3_plumbing: End-to-end wiring test: svg_l3 -> llama_cmd -> OpenAI-style HTTP endpoint -> report.
"""

from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from shared import llama_cmd
from shared import svg_l3
from shared.svg_dsl import canonicalize
from shared.svg_l3 import extract_svg
from shared.svg_l3 import main as l3_main
from shared.svg_l3 import probes_from
from shared.svg_l3 import run
from unittest.mock import patch
import io
import json
import socket
import subprocess
import sys
import threading

import pytest


# ──── svg_l3 ──────────────────────────────────────────────────────

SRC = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <circle cx="32" cy="32" r="20" fill="#f00" stroke="#000" stroke-width="2"/>
  <rect x="8" y="8" width="16" height="12" fill="none" stroke="#0a0"/>
  <line x1="0" y1="60" x2="64" y2="60" stroke="#000"/>
  <text x="32" y="36" text-anchor="middle" font-family="Noto Sans CJK JP" font-size="8">図</text>
</svg>"""


def test_extract_svg_from_fenced_answer():
    text = "Here:\n```svg\n<svg width=\"8\" height=\"8\" viewBox=\"0 0 8 8\"/>\n```"
    assert extract_svg(text).startswith("<svg") and extract_svg(text).endswith("/>")


def test_extract_svg_returns_empty_when_absent():
    assert extract_svg("no drawing here") == ""


def test_extract_svg_excludes_reasoning_only_generation():
    assert extract_svg("<think>" + SRC + "</think>No final drawing.") == ""
    assert extract_svg("<think>" + SRC) == ""
    assert extract_svg("<think>reasoning</think>```svg\n" + SRC + "\n```") == SRC
    assert extract_svg("Some thoughts: <think>" + SRC) == ""
    assert extract_svg("```text\n<think>" + SRC + "\n```") == ""
    assert extract_svg(SRC + "</think>No final drawing") == ""
    assert extract_svg("prefix<think>" + SRC + "</think>" + SRC) == SRC


def test_extract_svg_preserves_literal_reasoning_tags_inside_cdata():
    source = '<svg width="64" height="64" viewBox="0 0 64 64"><text><![CDATA[<think>literal</think>]]></text></svg>'
    assert extract_svg(source) == source
    assert extract_svg("Here:\n```svg\n" + source + "\n```") == source


@pytest.mark.parametrize("stage", ["describe", "generate"])
def test_unfinished_generation_stages_are_recorded_without_scoring(stage):
    calls = []
    def ask(prompt):
        calls.append(prompt)
        if stage == "describe" or "Output the SVG only" in prompt:
            raise RuntimeError("unfinished output")
        return "description"
    report = run(SRC, ask)
    assert report["status"] == "incomplete" and not report["dsl_ok"]
    assert report["hits"] == 0 and report["errors"][0].startswith(stage + ":")
    assert len(calls) == (1 if stage == "describe" else 2)


def test_probes_take_expected_values_from_original():
    probes = probes_from(canonicalize(SRC))
    expected = {p.expected for p in probes}
    assert {"20", "16", "64", "図", "#ff0000", "#000000", "#00aa00"} <= expected


def test_perfect_generation_with_typed_answers_scores_full():
    def ask(prompt):
        if prompt.startswith("Below is an SVG drawing"):
            return "a circle, a rectangle, a line and a text"
        if "Output the SVG only" in prompt:
            return "```svg\n" + SRC + "\n```"
        if "radius of every circle" in prompt:
            return "[20]"
        if "width of every rect" in prompt:
            return "[16]"
        if "x2 coordinate of every line" in prompt:
            return "[64]"
        if "text content of every" in prompt:
            return '["図"]'
        return '["#ff0000", "#000000", "#00aa00"]'
    report = run(SRC, ask)
    assert report["dsl_ok"]
    assert report["score"] == 1.0


def wrap(body):
    return '<svg width="64" height="64" viewBox="0 0 64 64">' + body + '</svg>'


def answerer(svg, answer):
    def ask(prompt):
        if prompt.startswith("Below is an SVG drawing"):
            return "description"
        if "Output the SVG only" in prompt:
            return svg
        return answer(prompt) if callable(answer) else answer
    return ask


def test_original_coordinates_cannot_leak_expected_radius_in_question():
    source = wrap('<circle cx="20" cy="30" r="20"/>')
    wrong = wrap('<circle cx="20" cy="30" r="1"/>')
    probe = probes_from(canonicalize(source))[0]
    assert "20" not in probe.question and "30" not in probe.question
    report = run(source, answerer(wrong, lambda prompt: prompt.split("Question: ")[1]))
    assert report["score"] == 0
    assert report["results"][0]["status"] == "unscorable"
    assert run(source, answerer(wrong, "[1]"))["score"] == 0


def test_context_echo_is_not_a_completed_typed_answer():
    report = run(SRC, answerer(SRC, lambda prompt: prompt))
    assert report["score"] == 0
    assert report["unscorable"] == report["total"]


@pytest.mark.parametrize("body, expected", [
    ('<circle r="20"/>', "20"), ('<circle/>', "0"),
    ('<rect width="12" height="8"/>', "12"), ('<rect/>', "0"),
    ('<line x2="12"/>', "12"), ('<line/>', "0"),
])
def test_svg_default_attributes_do_not_crash_probes_or_pipeline(body, expected):
    source = wrap(body)
    probe = probes_from(canonicalize(source))[0]
    assert probe.expected == expected
    report = run(source, answerer(source, f"[{expected}]"))
    assert report["dsl_ok"] and report["score"] == 1


@pytest.mark.parametrize("answer", [
    "20", '"20"', '["20"]', "[true]", "[null]", "[NaN]", "[Infinity]",
    "[-Infinity]", "[[20]]", '{"value":20}', "[20,20]", "[]", "[20] [20]",
    "[20] trailing text", "The answer is [20]", "```json\n[20]\n```", "[20",
    "<think>[20]</think>", "<think>[20]", "",
    "[1e9999999999999999999999999999999999999999]",
])
def test_malformed_partial_or_non_numeric_answers_do_not_score(answer):
    source = wrap('<circle r="20"/>')
    report = run(source, answerer(source, answer))
    assert report["score"] == 0
    assert report["unscorable"] == 1
    assert report["status"] == "incomplete"


def test_only_completed_final_json_is_scored():
    source = wrap('<circle r="20"/>')
    assert run(source, answerer(source, '<think>[20]</think>[1]'))["score"] == 0
    assert run(source, answerer(source, '<think>[1]</think>[20]'))["score"] == 1
    assert run(source, answerer(source, '<think>nested<think>[1]</think></think>[20]'))["score"] == 1
    assert run(source, answerer(source, 'template reasoning</think>[20]'))["score"] == 1


def test_reasoning_tags_inside_json_strings_are_literal_svg_text():
    source = wrap('<text>correct</text>')
    answer = '["<think>wrong</think>correct"]'
    report = run(source, answerer(source, answer))
    assert report["score"] == 0
    assert report["results"][0]["answer"] == answer
    literal = wrap('<text>&lt;think&gt;literal&lt;/think&gt;</text>')
    assert run(literal, answerer(literal, '["<think>literal</think>"]'))["score"] == 1
    assert run(literal, answerer(literal, '<think>reasoning</think>["<think>literal</think>"]'))["score"] == 1


def test_duplicates_are_scored_by_position_with_one_answer_per_attribute():
    source = wrap('<circle r="20"/><circle r="20"/><circle r="7"/>')
    calls = []
    def reply(prompt):
        calls.append(prompt)
        return "[20,7,20]"
    report = run(source, answerer(source, reply))
    assert report["hits"] == 1 and report["total"] == 3
    assert len(calls) == 1
    assert run(source, answerer(source, "[20,20,7]"))["score"] == 1


def test_numeric_json_values_compare_without_rounding_answers():
    source = wrap('<circle r="0.1"/>')
    assert run(source, answerer(source, "[1e-1]"))["score"] == 1
    assert run(source, answerer(source, "[0.10001]"))["score"] == 0


def test_text_values_are_complete_ordered_strings_not_substrings():
    source = wrap('<text>item</text><text>item</text><text>last</text>')
    assert run(source, answerer(source, '["item", "item", "last"]'))["score"] == 1
    assert run(source, answerer(source, '["item plus", "last", "item"]'))["score"] == 0


def test_unfinished_marker_is_not_a_magic_correct_text_answer():
    source = wrap('<text>&lt;&lt;unfinished&gt;&gt;</text>')
    def fail(prompt):
        raise RuntimeError("unfinished output")
    report = run(source, answerer(source, fail))
    assert report["score"] == 0 and report["unscorable"] == 1


def test_explicit_colors_are_unordered_but_must_be_unique_and_typed():
    source = wrap('<g fill="#f00"><circle r="2" stroke="#abc"/></g>')
    def reply(prompt):
        return "[2]" if "radius of every" in prompt else '["#aabbcc", "#ff0000"]'
    assert run(source, answerer(source, reply))["score"] == 1
    for colors in ['["#ff0000","#ff0000"]', '["#ff0000",123]', '["#f00","#abc"]']:
        def wrong(prompt):
            return "[2]" if "radius of every" in prompt else colors
        report = run(source, answerer(source, wrong))
        assert report["hits"] == 1 and report["unscorable"] == 2


def test_empty_drawing_has_no_applicable_probes():
    source = wrap("")
    report = run(source, answerer(source, lambda prompt: pytest.fail("no probe call expected")))
    assert report["dsl_ok"] and report["score"] is None
    assert report["total"] == 0 and report["status"] == "not_applicable"
    assert report["prompt_version"] == report["scorer_version"] == "2"


def test_invalid_generation_fails_at_validation():
    def ask(prompt):
        if "Output the SVG only" in prompt:
            return '<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 8 8"><script/></svg>'
        return "x"
    report = run(SRC, ask)
    assert not report["dsl_ok"]
    assert report["errors"]


def test_unanswered_probes_score_zero():
    def ask(prompt):
        if "Output the SVG only" in prompt:
            return SRC
        if "Context:" in prompt:
            raise RuntimeError("model command failed (1)")
        return "some description"
    report = run(SRC, ask)
    assert report["dsl_ok"]
    assert report["score"] == 0.0


def test_cli_writes_meta_and_reports(tmp_path):
    import json
    from shared.svg_l3 import main

    fig = tmp_path / "f.svg"
    fig.write_text(SRC, encoding="utf-8")
    out = tmp_path / "report.json"
    # A model that never writes an SVG: the run must finish, record the failure, and exit 1.
    rc = main([str(fig), "--cmd", "python3 -c \"import sys; sys.stdin.read(); print('no svg')\"",
               "--model", "test-model", "-o", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 1
    assert data["meta"]["model"] == "test-model"
    assert data["meta"]["stage"] == "L3"
    assert data["reports"][0]["figure"] == "f.svg"
    assert len(data["reports"][0]["source_sha256"]) == 64
    assert data["reports"][0]["dsl_ok"] is False


# ──── svg_l3_evidence ─────────────────────────────────────────────

"""Offline evidence and source-control regressions; no model required."""


def response(payload):
    return io.BytesIO(json.dumps(payload).encode())


@pytest.mark.parametrize('reason', ['stop', 'length'])
def test_response_evidence_survives_answer_rejection(tmp_path, monkeypatch, reason):
    out = tmp_path / 'requests.jsonl'
    monkeypatch.setenv('LLAMA_EVIDENCE_JSONL', str(out))
    monkeypatch.setenv('LLAMA_EVIDENCE_FIGURE', 'figure.svg')
    payload = {'choices': [{'finish_reason': reason, 'message': {'content': 'answer'}}],
               'usage': {'prompt_tokens': 10, 'completion_tokens': 2048}}
    with patch.object(llama_cmd.urllib.request, 'urlopen', return_value=response(payload)):
        if reason == 'stop':
            assert llama_cmd.ask_llama('prompt') == 'answer'
        else:
            with pytest.raises(llama_cmd.AnswerValidationError):
                llama_cmd.ask_llama('prompt')
    item = json.loads(out.read_text())
    assert item['response'] == payload
    assert item['usage']['completion_tokens'] == 2048
    assert item['answer_completed'] == (reason == 'stop')
    assert item['figure'] == 'figure.svg'
    if reason == 'length':
        assert "answer did not complete: 'length'" in item['error']


def test_transport_error_has_full_evidence(tmp_path, monkeypatch):
    out = tmp_path / 'requests.jsonl'
    monkeypatch.setenv('LLAMA_EVIDENCE_JSONL', str(out))
    with patch.object(llama_cmd.urllib.request, 'urlopen', side_effect=TimeoutError('socket timed out')):
        with pytest.raises(TimeoutError):
            llama_cmd.ask_llama('prompt')
    item = json.loads(out.read_text())
    assert not item['answer_completed']
    assert 'TimeoutError: socket timed out' in item['error']
    assert 'usage' not in item  # no fabricated token count


def test_source_control_runs_even_when_roundtrip_is_unfinished(tmp_path, monkeypatch):
    source = tmp_path / 'figure.svg'
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10"><rect x="0" y="0" width="10" height="10"/></svg>')
    calls = []
    def ask(cmd, prompt):
        import os
        calls.append((os.environ['LLAMA_EVIDENCE_FIGURE'], os.environ['LLAMA_EVIDENCE_PHASE']))
        if len(calls) == 1:
            raise RuntimeError('unfinished')
        return '[10]'
    monkeypatch.setattr(svg_l3, 'ask', ask)
    monkeypatch.setenv('LLAMA_EVIDENCE_PHASE', 'previous')
    out = tmp_path / 'report.json'
    svg_l3.main([str(source), '--cmd', 'fake', '--model', 'fake', '--source-control', '-o', str(out)])
    report = json.loads(out.read_text())['reports'][0]
    assert report['status'] == 'incomplete' and report['hits'] == 0
    assert report['source_control']['hits'] == report['source_control']['total'] == 1
    assert calls == [('figure.svg', 'roundtrip'), ('figure.svg', 'source_control')]
    import os
    assert os.environ['LLAMA_EVIDENCE_PHASE'] == 'previous'


# ──── svg_l3_execution_failures ───────────────────────────────────

"""Offline transport-vs-quality regressions; never starts a model or network call."""


ROOT = Path(__file__).resolve().parents[1]


SOURCE = (ROOT / 'examples/figures/flow_basic.svg').read_text(encoding='utf-8')


def test_exit_two_is_typed_transport_failure(monkeypatch):
    monkeypatch.setattr(svg_l3.subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess('fake', 2, '', 'llama-server unreachable'))
    with pytest.raises(svg_l3.ModelExecutionError):
        svg_l3.ask('fake', 'prompt')


def test_http_socket_timeout_returns_execution_exit_two(monkeypatch, capsys):
    def fail(*a, **k):
        raise TimeoutError('socket timed out')
    monkeypatch.setattr(llama_cmd, 'ask_llama', fail)
    monkeypatch.setattr('sys.stdin', io.StringIO('prompt'))
    assert llama_cmd.main() == 2
    assert 'socket timed out' in capsys.readouterr().err


@pytest.mark.parametrize('code', [1, 2, -9, 64, 127])
def test_all_unclassified_nonzero_exits_are_execution_failures(code, monkeypatch):
    monkeypatch.setattr(svg_l3.subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess('fake', code, '', 'failure'))
    with pytest.raises(svg_l3.ModelExecutionError):
        svg_l3.ask('fake', 'prompt')


def test_only_explicit_quality_exit_is_non_execution(monkeypatch):
    monkeypatch.setattr(svg_l3.subprocess, 'run', lambda *a, **k:
        subprocess.CompletedProcess('fake', 3, '', 'answer validation failed: length'))
    with pytest.raises(RuntimeError) as caught:
        svg_l3.ask('fake', 'prompt')
    assert not isinstance(caught.value, svg_l3.ModelExecutionError)


@pytest.mark.parametrize('reason,content', [('length', ''), ('content_filter', None),
    ('stop', None), ('stop', ''), ('stop', '<think>unfinished')])
def test_known_invalid_answers_return_dedicated_quality_exit(reason, content, monkeypatch, capsys):
    payload = {'choices': [{'finish_reason': reason, 'message': {'content': content}}]}
    monkeypatch.setattr(llama_cmd, 'ask_llama', lambda *a, **k: llama_cmd.extract_answer(payload))
    monkeypatch.setattr('sys.stdin', io.StringIO('prompt'))
    assert llama_cmd.main() == 3
    assert 'answer validation failed' in capsys.readouterr().err


@pytest.mark.parametrize('payload', [{}, {'choices': []},
    {'choices': [{'message': {'content': 'x'}}]},
    {'choices': [{'finish_reason': 'unknown', 'message': {'content': 'x'}}]},
    {'choices': [{'finish_reason': 'stop', 'message': {'content': 123}}]}])
def test_unexpected_schema_is_not_answer_validation(payload, monkeypatch):
    monkeypatch.setattr(llama_cmd, 'ask_llama', lambda *a, **k: llama_cmd.extract_answer(payload))
    monkeypatch.setattr('sys.stdin', io.StringIO('prompt'))
    with pytest.raises((KeyError, IndexError, ValueError, TypeError)) as caught:
        llama_cmd.main()
    assert not isinstance(caught.value, llama_cmd.AnswerValidationError)


def test_malformed_json_is_not_quality_exit(monkeypatch):
    def broken(*a, **k):
        return json.loads('{broken')
    monkeypatch.setattr(llama_cmd, 'ask_llama', broken)
    monkeypatch.setattr('sys.stdin', io.StringIO('prompt'))
    with pytest.raises(json.JSONDecodeError):
        llama_cmd.main()


# ──── svg_l3_main ─────────────────────────────────────────────────

"""CLI bookkeeping for SVG L3: failures are recorded per figure, never turned into a verdict."""


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


# ──── svg_l3_plumbing ─────────────────────────────────────────────

"""End-to-end wiring test: svg_l3 -> llama_cmd -> OpenAI-style HTTP endpoint -> report.

The endpoint is a local stub, not a model. This checks the plumbing only (prompts,
finish_reason handling, JSON report), not any model's quality.
"""


FIGURE_svg_l3_plumbing = ROOT / "examples/figures/flow_basic.svg"


class Stub(BaseHTTPRequestHandler):
    svg = FIGURE_svg_l3_plumbing.read_text(encoding="utf-8")

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
    rc = l3_main([str(FIGURE_svg_l3_plumbing), "--cmd", cmd, "--model", "stub-endpoint", "-o", str(out)])
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
