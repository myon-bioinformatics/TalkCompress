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
    assert rec['accounting_version']==2
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
    # the legacy timeouts stay counted, but this run completed every attempt
    assert rec['pending_timeouts']==0
    assert rt.rate(rec)==11/13

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
