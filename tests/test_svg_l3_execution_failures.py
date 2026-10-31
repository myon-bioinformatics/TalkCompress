"""Offline transport-vs-quality regressions; never starts a model or network call."""
import io
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from shared import llama_cmd, svg_l3

ROOT = Path(__file__).parents[1]
SOURCE = (ROOT / 'examples/figures/flow_basic.svg').read_text(encoding='utf-8')


def workflow_gate(tmp_path, monkeypatch, reports):
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'out').mkdir(exist_ok=True)
    (tmp_path / 'examples/figures').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'examples/figures/flow_basic.svg').write_text(SOURCE)
    (tmp_path / 'out/l3-report.json').write_text(json.dumps({'reports': reports}))
    workflow = (ROOT / '.github/workflows/svg-l3.yml').read_text()
    code = workflow.split("python - <<'PY'\n", 1)[1].split('\n          PY', 1)[0]
    exec(compile(textwrap.dedent(code), '<workflow-gate>', 'exec'), {})


@pytest.mark.parametrize('stage', ['describe', 'generate', 'probe'])
@pytest.mark.parametrize('error', [subprocess.TimeoutExpired('fake', 1860),
                                 svg_l3.ModelExecutionError('llama-server unreachable')])
def test_real_run_catches_and_gate_rejects_execution_failure(stage, error, tmp_path, monkeypatch):
    calls = 0
    def ask(_):
        nonlocal calls
        calls += 1
        if calls >= {'describe': 1, 'generate': 2, 'probe': 3}[stage]:
            raise error
        return 'description' if calls == 1 else SOURCE
    report = svg_l3.run(SOURCE, ask)
    report['figure'] = 'flow_basic.svg'
    assert report['status'] == 'incomplete'
    assert report['execution_errors']
    with pytest.raises(SystemExit, match='measurement did not complete'):
        workflow_gate(tmp_path, monkeypatch, [report])


@pytest.mark.parametrize('stage', ['describe', 'generate', 'probe'])
def test_quality_failure_is_recorded_but_not_execution_failure(stage, tmp_path, monkeypatch):
    calls = 0
    def ask(_):
        nonlocal calls
        calls += 1
        if calls >= {'describe': 1, 'generate': 2, 'probe': 3}[stage]:
            raise RuntimeError("model command failed (3): answer did not complete: 'length'")
        return 'description' if calls == 1 else SOURCE
    report = svg_l3.run(SOURCE, ask)
    report['figure'] = 'flow_basic.svg'
    assert report['status'] == 'incomplete'
    assert not report.get('execution_errors')
    workflow_gate(tmp_path, monkeypatch, [report])


@pytest.mark.parametrize('reports', [[], [{'figure': 'other.svg'}],
    [{'figure': 'flow_basic.svg'}, {'figure': 'flow_basic.svg'}]])
def test_partial_or_duplicate_reports_fail_gate(tmp_path, monkeypatch, reports):
    with pytest.raises(SystemExit, match='missing or duplicating'):
        workflow_gate(tmp_path, monkeypatch, reports)


def test_dsl_quality_failure_does_not_fail_gate(tmp_path, monkeypatch):
    workflow_gate(tmp_path, monkeypatch, [{'figure': 'flow_basic.svg', 'dsl_ok': False,
                                          'score': 0.0, 'errors': ['no svg in model output']}])


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


def test_early_failure_evidence_directory_is_created(tmp_path):
    workflow = (ROOT / '.github/workflows/svg-l3.yml').read_text()
    assert workflow.index('Prepare evidence directory') < workflow.index('Fetch or verify pinned weights')
    collect = workflow.split('      - name: Collect evidence\n', 1)[1].split('      - name:', 1)[0]
    assert 'if: always()' in collect
    body = textwrap.dedent(collect.split('        run: |\n', 1)[1])
    # Supply a fake docker executable, so no container or external process is used.
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    fake = bindir / 'docker'
    fake.write_text('#!/bin/sh\necho diagnostic\n')
    fake.chmod(0o755)
    import os
    env = {**os.environ, 'PATH': str(bindir) + os.pathsep + os.environ['PATH']}
    subprocess.run(['bash', '-ec', body], cwd=tmp_path, env=env, check=True)
    assert (tmp_path / 'out/llama-server.log').read_text().strip() == 'diagnostic'
    assert (tmp_path / 'out/container.json').read_text().strip() == 'diagnostic'

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
