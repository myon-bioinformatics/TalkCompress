"""Offline transport-vs-quality regressions; never starts a model or network call."""
import io, json, subprocess
from pathlib import Path

import pytest

from shared import llama_cmd, svg_l3

ROOT = Path(__file__).parents[1]
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
