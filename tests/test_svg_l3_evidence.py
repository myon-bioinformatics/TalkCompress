"""Offline evidence and source-control regressions; no model required."""
import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from shared import llama_cmd, svg_l3


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
