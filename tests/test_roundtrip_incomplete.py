import copy
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('roundtrip_under_test', Path(__file__).resolve().parents[1] / 'scripts/roundtrip.py')
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

def data():
    return {'templates':['{s}.'], 'seeds':[1,2,3], 'records':{}, 'min_trials':2,
            'thresholds':{'lt100m':0.9,'ge100m':0.9}, 'ge100m_langs':['en']}

@pytest.mark.parametrize('responses', [(True,None,True), (None,None,None), (False,None,False)])
@pytest.mark.parametrize('lang', ['nl','en'])
def test_incomplete_never_passes(monkeypatch, responses, lang):
    d=data()
    def fake(*args, **kwargs):
        answer=responses[int(kwargs['env']['ROUNDTRIP_SEED'])-1]
        if answer is None:
            raise subprocess.TimeoutExpired('fake',1)
        return subprocess.CompletedProcess('fake',0,'I have eaten.' if answer else 'no','')
    monkeypatch.setattr(rt.subprocess,'run',fake)
    rt.run(d,'fake',entries=[{'lang':lang,'from':['I have eaten'],'to':'ik at'}])
    rec=d['records'][f'{lang}:ik at']
    assert rec['attempted']==3
    assert rec['completed']==rec['trials']==sum(x is not None for x in responses)
    assert rec['timeouts']==sum(x is None for x in responses)
    assert rec['restored']==sum(x is True for x in responses)
    assert rec['failures']==['Ik at.']*sum(x is False for x in responses)
    assert rec['accounting_version']==3
    assert rt.rate(rec) is None
    assert rt.status(d,lang,'ik at')=='unverified'
    assert not rt.gate_for(d,'all')('ik at',lang)
    assert not rt.gate_for(d,'lt100m')('ik at',lang)

def test_existing_complete_record_unchanged():
    d=data(); rec={'trials':10,'restored':9,'failures':['past failure']}
    d['records']['nl:ik at']=rec; before=copy.deepcopy(d)
    assert rt.rate(rec)==0.9
    assert rt.status(d,'nl','ik at')=='pass'
    assert rt.gate_for(d,'all')('ik at','nl')
    assert d==before

def test_append_keeps_old_counts_and_failure(monkeypatch):
    d=data(); d['records']['nl:ik at']={'trials':10,'restored':8,'failures':['past failure'],'timeouts':2}
    monkeypatch.setattr(rt.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess('fake',0,'I have eaten.',''))
    rt.run(d,'fake',entries=[{'lang':'nl','from':['I have eaten'],'to':'ik at'}])
    rec=d['records']['nl:ik at']
    assert (rec['attempted'],rec['completed'],rec['restored'],rec['timeouts'])==(15,13,11,2)
    assert rec['failures']==['past failure']
    assert rt.rate(rec) is None
    rt.run(d, "fake", entries=[{"lang":"nl","from":["I have eaten"],"to":"ik at"}], revalidate_legacy=True)
    assert rt.rate(rec) == 14 / 16

@pytest.mark.parametrize('timeout',[0,-1,float('nan'),float('inf')])
def test_invalid_timeout_rejected_before_mutation(timeout):
    d=data(); before=copy.deepcopy(d)
    with pytest.raises(ValueError,match='finite and positive'):
        rt.run(d,'fake',entries=[],timeout=timeout)
    assert d==before

def test_cli_saves_incomplete_before_failure(monkeypatch,tmp_path,capsys):
    d=data(); target=tmp_path/'results.json'
    monkeypatch.setattr(rt,'load',lambda:d)
    monkeypatch.setattr(rt,'DATA_PATH',target)
    def fake_run(d,*a,**k):
        d['records']['nl:ik at']={'trials':2,'restored':2,'timeouts':1,'failures':[], 'attempted':3,'completed':2,'accounting_version':2}
        return d
    monkeypatch.setattr(rt,'run',fake_run)
    assert rt.main(['--run','--cmd','fake'])==1
    assert json.loads(target.read_text())==d
    assert 'unverified' in capsys.readouterr().err


def test_retry_slots_preserve_history_and_require_matching_identity(monkeypatch):
    d = data()
    entry = [{'lang': 'nl', 'from': ['I have eaten'], 'to': 'ik at'}]
    answers = {1: None, 2: None, 3: None}
    def fake(*args, **kwargs):
        answer = answers[int(kwargs['env']['ROUNDTRIP_SEED'])]
        if answer is None:
            raise subprocess.TimeoutExpired('fake', 1)
        return subprocess.CompletedProcess('fake', 0, 'I have eaten.' if answer else 'no', '')
    monkeypatch.setattr(rt.subprocess, 'run', fake)
    rt.run(d, 'fake', entries=entry)
    rec = d['records']['nl:ik at']
    assert len(rec['pending_trials']) == 3
    rt.run(d, 'fake', entries=entry)  # same timeouts are not extra pending slots
    assert len(rec['pending_trials']) == 3
    assert rec['timeouts'] == 6
    answers.update({1: True, 2: False})
    rt.run(d, 'fake', entries=entry)
    assert len(rec['pending_trials']) == 1
    assert rt.rate(rec) is None
    d['seeds'] = [1, 2]
    rt.run(d, 'fake', entries=entry)  # unrelated success cannot clear seed 3
    assert len(rec['pending_trials']) == 1
    d['seeds'] = [3]
    answers[3] = True
    rt.run(d, 'fake', entries=entry)
    assert rec['pending_trials'] == []
    assert rec['timeouts'] == 7
    assert rec['failures'] == ['Ik at.', 'Ik at.']
    assert rt.rate(rec) == 3 / 5
    assert rt.status(d, 'nl', 'ik at') == 'fail'
    # Full successes do not erase earlier completed failures.
    d['seeds'] = [1, 2, 3]
    answers.update({1: True, 2: True, 3: True})
    rt.run(d, 'fake', entries=entry)
    assert rt.rate(rec) == 6 / 8
    assert not rt.incomplete(rec)


def test_all_timeout_then_complete_success_resumes_gate_and_cli(monkeypatch, tmp_path):
    d = data()
    entry = [{'lang': 'nl', 'from': ['I have eaten'], 'to': 'ik at'}]
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired('fake', 1)
    monkeypatch.setattr(rt.subprocess, 'run', timeout)
    rt.run(d, 'fake', entries=entry)
    monkeypatch.setattr(rt.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess('fake', 0, 'I have eaten.', ''))
    rt.run(d, 'fake', entries=entry)
    rec = d['records']['nl:ik at']
    assert rec['timeouts'] == 3
    assert rt.rate(rec) == 1
    assert rt.gate_for(d, 'all')('ik at', 'nl')
    monkeypatch.setattr(rt, 'load', lambda: d)
    monkeypatch.setattr(rt, 'DATA_PATH', tmp_path / 'results.json')
    monkeypatch.setattr(rt, 'run', lambda *a, **k: d)
    assert rt.main(['--run', '--cmd', 'fake']) == 0


def test_changed_sentence_and_reload_do_not_clear_pending(monkeypatch):
    d = data()
    d['seeds'] = [1]
    entry = [{'lang': 'nl', 'from': ['I have eaten'], 'to': 'ik at'}]
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired('fake', 1)
    monkeypatch.setattr(rt.subprocess, 'run', timeout)
    rt.run(d, 'fake', entries=entry)
    d = json.loads(json.dumps(d))
    monkeypatch.setattr(rt.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess('fake', 0, 'Other.', ''))
    rt.run(d, 'fake', entries=[{'lang': 'nl', 'from': ['Other'], 'to': 'ik at'}])
    assert rt.incomplete(d['records']['nl:ik at'])


def test_legacy_partial_retry_requires_explicit_baseline(monkeypatch):
    d = data()
    d['seeds'] = [1]
    d['records']['nl:ik at'] = {'trials': 0, 'restored': 0, 'timeouts': 3, 'failures': []}
    monkeypatch.setattr(rt.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess('fake', 0, 'I have eaten.', ''))
    rt.run(d, 'fake', entries=[{'lang': 'nl', 'from': ['I have eaten'], 'to': 'ik at'}])
    assert rt.rate(d['records']['nl:ik at']) is None
