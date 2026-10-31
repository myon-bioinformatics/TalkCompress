import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

spec=importlib.util.spec_from_file_location('cohort_rt',Path(__file__).resolve().parents[1]/'scripts/roundtrip.py')
rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)
ENTRY=[{'lang':'nl','from':['I have eaten'],'to':'ik at'}]

def data():
    return {'templates':['{s}.'],'seeds':[1,2,3],'records':{},'min_trials':2,
            'thresholds':{'lt100m':.9,'ge100m':.9},'ge100m_langs':['en']}

def fake(monkeypatch,answers=None,returncode=0):
    def call(*a,**kw):
        answer=(answers or {}).get(int(kw['env']['ROUNDTRIP_SEED']),True)
        if answer is None:raise subprocess.TimeoutExpired('fake',1)
        return subprocess.CompletedProcess('fake',returncode,'I have eaten.' if answer else 'no','')
    monkeypatch.setattr(rt.subprocess,'run',call)

def test_old_success_cannot_fill_new_minimum(monkeypatch):
    d=data();d['records']['nl:ik at']={'trials':100,'restored':100,'failures':[]}
    d['seeds']=[1];fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['trials']==101 and rt.rate(rec)==1
    assert rt.status(d,'nl','ik at')=='unverified'
    assert not rt.gate_for(d,'all')('ik at','nl')

def test_old_success_cannot_mask_current_failure(monkeypatch):
    d=data();d['records']['nl:ik at']={'trials':100,'restored':100,'failures':[]}
    fake(monkeypatch,{1:False,2:False,3:False});rt.run(d,'fake',entries=ENTRY)
    assert rt.rate(d['records']['nl:ik at'])==0
    assert rt.status(d,'nl','ik at')=='never'

@pytest.mark.parametrize('empty',['seeds','templates'])
def test_selected_zero_work_invalidates_latest_not_history(monkeypatch,empty):
    d=data();fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    old=copy.deepcopy(d['records']['nl:ik at']['cohorts'][0])
    d[empty]=[];rt.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['cohorts'][0]==old
    assert rec['cohorts'][-1]['attempted']==0
    assert rt.rate(rec) is None and rt.status(d,'nl','ik at')=='unverified'
    assert not d['run_history'][-1]['complete']

def test_partial_selection_leaves_other_history_untouched(monkeypatch):
    d=data();fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    old=copy.deepcopy(d['records'])
    rt.run(d,'fake',entries=ENTRY,only_lang='de')
    assert d['records']==old
    assert d['run_history'][-1]['selected_forms']==[]
    assert not d['run_history'][-1]['complete']

def test_history_and_legacy_snapshot_survive_recovery(monkeypatch):
    d=data();old={'trials':9,'restored':7,'timeouts':4,'failures':['old'], 'accounting_version':2,'pending_timeouts':2}
    d['records']['nl:ik at']=copy.deepcopy(old)
    fake(monkeypatch,{1:None,2:None,3:None});rt.run(d,'first-secret-command',entries=ENTRY)
    rec=d['records']['nl:ik at'];first=copy.deepcopy(rec['cohorts'][0])
    assert rec['legacy_snapshot']==old and rt.rate(rec) is None
    d=json.loads(json.dumps(d));d['seeds']=[4,5]
    fake(monkeypatch);rt.run(d,'new-command',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['legacy_snapshot']==old and rec['cohorts'][0]==first
    assert rec['timeouts']==7 and rec['pending_timeouts']==2 and rec['failures']==['old']
    assert rec['cohorts'][-1]['completed']==2 and rt.rate(rec)==1
    assert rt.status(d,'nl','ik at')=='pass'
    assert rec['cohorts'][0]['timeouts']==3 and not rec['cohorts'][0]['complete']
    assert rec['cohorts'][0]['config']['command_sha256']!=rec['cohorts'][1]['config']['command_sha256']
    assert 'first-secret-command' not in json.dumps(d)
    assert {t['target_id'] for t in first['targets']}.isdisjoint(t['target_id'] for t in rec['cohorts'][-1]['targets'])

def test_duplicate_targets_do_not_fill_minimum(monkeypatch):
    d=data();d['seeds']=[1,1];d['templates']=['{s}.','{s}.'];fake(monkeypatch)
    rt.run(d,'fake',entries=ENTRY*2)
    rec=d['records']['nl:ik at']
    assert rec['cohorts'][-1]['attempted']==1
    assert d['run_history'][-1]['duplicate_targets']==7
    assert rt.status(d,'nl','ik at')=='unverified'

def test_seed_identity_matches_actual_environment(monkeypatch):
    d=data();d['seeds']=[1,'1'];fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['cohorts'][-1]['attempted']==1
    assert rt.status(d,'nl','ik at')=='unverified'

def test_changed_prompt_changes_target_identity(monkeypatch):
    d=data();fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    first=copy.deepcopy(d['records']['nl:ik at']['cohorts'][-1])
    monkeypatch.setattr(rt,'PROMPT','Different instruction: {c}')
    rt.run(d,'fake',entries=ENTRY)
    latest=d['records']['nl:ik at']['cohorts'][-1]
    assert {t['target_id'] for t in first['targets']}.isdisjoint(t['target_id'] for t in latest['targets'])

@pytest.mark.parametrize('field,value',[('min_trials',float('nan')),('min_trials',-1),('min_trials',True),
    ('thresholds',{'lt100m':float('nan'),'ge100m':.9}),('thresholds',{'lt100m':-1,'ge100m':.9}),
    ('seeds',[True]),('seeds',[{}]),('templates',[None])])
def test_invalid_configuration_cannot_mutate_or_execute(monkeypatch,field,value):
    d=data();d[field]=value;before=copy.deepcopy(d)
    monkeypatch.setattr(rt.subprocess,'run',lambda *a,**k:pytest.fail('must not execute'))
    with pytest.raises(ValueError):rt.run(d,'fake',entries=ENTRY)
    assert json.dumps(d,sort_keys=True)==json.dumps(before,sort_keys=True)

def test_policy_snapshot_does_not_alias_current_policy(monkeypatch):
    d=data();fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    policy=d['records']['nl:ik at']['cohorts'][-1]['config']['evaluation_policy']
    d['min_trials']=10;d['thresholds']['lt100m']=.1
    assert policy['min_trials']==2 and policy['thresholds']['lt100m']==.9
    assert rt.status(d,'nl','ik at')=='unverified'

@pytest.mark.parametrize('mutation',['zero_completed','duplicate_targets','wrong_count','wrong_scope','wrong_version','wrong_identity','missing_history','missing_config','wrong_form','null_policy','null_minimum','null_threshold','null_languages'])
def test_loaded_malformed_cohort_is_unverified(monkeypatch,mutation):
    d=data();fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    d=json.loads(json.dumps(d));rec=d['records']['nl:ik at'];current=rec['cohorts'][-1]
    if mutation=='zero_completed':current['completed']=0
    elif mutation=='duplicate_targets':current['targets'][1]=copy.deepcopy(current['targets'][0])
    elif mutation=='wrong_count':current['restored']=100
    elif mutation=='wrong_scope':current['evaluation_scope']='cumulative'
    elif mutation=='wrong_version':current['accounting_version']=3
    elif mutation=='wrong_identity':current['targets'][0]['seed']='unrecorded'
    elif mutation=='missing_config':current['config']={}
    elif mutation=='wrong_form':rec['form']='other'
    elif mutation=='null_policy':current['config']['evaluation_policy']={k:None for k in ('min_trials','thresholds','ge100m_langs')}
    elif mutation=='null_minimum':current['config']['evaluation_policy']['min_trials']=None
    elif mutation=='null_threshold':current['config']['evaluation_policy']['thresholds']=None
    elif mutation=='null_languages':current['config']['evaluation_policy']['ge100m_langs']=None
    else:rec.pop('cohorts')
    assert rt.rate(rec) is None
    assert rt.status(d,'nl','ik at')=='unverified'
    assert not rt.gate_for(d,'all')('ik at','nl')

@pytest.mark.parametrize('mutation',['missing_outcome','missing_expected','extra_expected','duplicate_expected','absent_expected'])
def test_loaded_receipt_requires_exact_scheduled_targets(monkeypatch,mutation):
    d=data();fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at'];current=rec['cohorts'][-1]
    if mutation=='missing_outcome':
        current['targets'].pop()
        for field in ('attempted','completed','restored'):current[field]=2
    elif mutation=='missing_expected':current['expected_target_ids'].pop()
    elif mutation=='extra_expected':current['expected_target_ids'].append('0'*64)
    elif mutation=='duplicate_expected':current['expected_target_ids'].append(current['expected_target_ids'][0])
    else:current.pop('expected_target_ids')
    assert rt.rate(rec) is None
    assert rt.status(d,'nl','ik at')=='unverified'

@pytest.mark.parametrize('returncode',[1,2,-9])
def test_execution_failure_cannot_score_correct_stdout(monkeypatch,returncode):
    d=data();fake(monkeypatch,returncode=returncode);rt.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['cohorts'][-1]['execution_errors']==3
    assert rec['trials']==0 and rec['restored']==0 and rec['attempted']==3
    assert rt.rate(rec) is None

def test_latest_mixed_timeout_not_pass(monkeypatch):
    d=data();fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    fake(monkeypatch,{2:None});rt.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['trials']==5 and rec['cohorts'][-1]['completed']==2
    assert rt.rate(rec) is None and not rt.gate_for(d,'all')('ik at','nl')

def test_legacy_reads_unchanged():
    rec={'trials':10,'restored':9,'timeouts':0}
    before=copy.deepcopy(rec);assert rt.rate(rec)==.9;assert rec==before
    for rec in [{'trials':10,'restored':9,'timeouts':3,'pending_timeouts':0,'accounting_version':2},
                {'trials':10,'restored':9,'timeouts':3,'pending_trials':[],'legacy_pending':False,'accounting_version':3}]:
        before=copy.deepcopy(rec);assert rt.rate(rec) is None;assert rec==before
        d=data();d['records']['nl:ik at']=rec
        assert not rt.gate_for(d,'all')('ik at','nl')
    assert rt.rate({'trials':10,'restored':9,'timeouts':3}) is None
    assert rt.rate({'trials':10,'restored':9,'timeouts':3,'accounting_version':3,'pending_trials':['x']}) is None
    assert rt.rate({'trials':10,'restored':9,'timeouts':3,'accounting_version':3}) is None

def test_retry_layout_v3_is_snapshotted_not_reinterpreted(monkeypatch):
    d=data();old={'accounting_version':3,'trials':10,'restored':9,'timeouts':3,'failures':['old'],
                 'pending_trials':['old-source/seed'],'legacy_pending':True}
    d['records']['nl:ik at']=copy.deepcopy(old)
    assert rt.rate(d['records']['nl:ik at']) is None
    fake(monkeypatch,{1:False,2:False,3:False});rt.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['legacy_snapshot']==old and rec['pending_trials']==old['pending_trials']
    assert rec['accounting_version']==4 and rt.rate(rec)==0

def test_latest_retries_do_not_rewrite_previous_outcomes(monkeypatch):
    d=data();fake(monkeypatch,{1:None,2:None,3:None});rt.run(d,'fake',entries=ENTRY)
    first=copy.deepcopy(d['records']['nl:ik at']['cohorts'][0])
    d['seeds']=[1,2];fake(monkeypatch,{2:False});rt.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rt.rate(rec)==.5 and rt.status(d,'nl','ik at')=='fail'
    assert rec['cohorts'][0]==first and rec['timeouts']==3
    d['seeds']=[3];fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    assert rt.rate(rec)==1 and rt.status(d,'nl','ik at')=='unverified'
    assert rec['cohorts'][1]['restored']==1 and rec['failures']==['Ik at.']

def test_changed_source_has_new_identity_and_no_old_minimum(monkeypatch):
    d=data();fake(monkeypatch);rt.run(d,'fake',entries=ENTRY)
    previous=copy.deepcopy(d['records']['nl:ik at']['cohorts'][0])
    d['seeds']=[1]
    monkeypatch.setattr(rt.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess('fake',0,'Other.',''))
    rt.run(d,'fake',entries=[{'lang':'nl','from':['Other'],'to':'ik at'}])
    rec=d['records']['nl:ik at']
    assert rt.status(d,'nl','ik at')=='unverified'
    assert previous['targets'][0]['target_id']!=rec['cohorts'][-1]['targets'][0]['target_id']

@pytest.mark.parametrize('seeds,answers,exitcode',[([],{},1),([1],{},1),([1,2,3],{2:None},1),([1,2,3],{},0)])
def test_cli_saves_exact_invocation(monkeypatch,tmp_path,seeds,answers,exitcode):
    d=data();d['seeds']=seeds
    d['records']['de:x']={'trials':0,'restored':0,'timeouts':3,'failures':[]}
    fake(monkeypatch,answers);monkeypatch.setattr(rt,'load',lambda:d)
    monkeypatch.setattr(rt,'DATA_PATH',tmp_path/'result.json')
    monkeypatch.setitem(sys.modules,'tense_matrix',types.SimpleNamespace(build=lambda:({'entries':ENTRY},)))
    assert rt.main(['--run','--cmd','fake'])==exitcode
    assert json.loads((tmp_path/'result.json').read_text())==d
    assert d['run_history'][-1]['verifiable']==(exitcode==0)
