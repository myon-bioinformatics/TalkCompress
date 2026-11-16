"""scripts/roundtrip.py: コホート、未完了、NFC 正規化、来歴、タイムアウト。

- roundtrip_cohorts
- roundtrip_incomplete
- roundtrip_norm_nfc: roundtrip.norm: NFD の応答でアクセントが落ちて NFC の原文と不一致にならないこと。
- roundtrip_provenance: Round-trip run provenance: origin/main SHA and timestamp on every new run (no backfill).
- roundtrip_sticky_timeout: A recorded timeout must not exclude a form forever (2bot #97 Should 1).
- roundtrip_timeout: scripts/roundtrip.run: 1 試行のタイムアウトで他の結果を失わない。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from roundtrip import norm
import copy
import importlib.util
import json
import mapping_graph as mg
import roundtrip
import roundtrip as rt
import shlex
import subprocess
import sys
import types
import unicodedata

import pytest


# ──── roundtrip_cohorts ───────────────────────────────────────────

spec=importlib.util.spec_from_file_location('cohort_rt',Path(__file__).resolve().parents[1]/'scripts/roundtrip.py')


rt_roundtrip_cohorts=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt_roundtrip_cohorts)


ENTRY=[{'lang':'nl','from':['I have eaten'],'to':'ik at'}]


def data():
    return {'templates':['{s}.'],'seeds':[1,2,3],'records':{},'min_trials':2,
            'thresholds':{'lt100m':.9,'ge100m':.9},'ge100m_langs':['en']}


def fake(monkeypatch,answers=None,returncode=0):
    def call(*a,**kw):
        answer=(answers or {}).get(int(kw['env']['ROUNDTRIP_SEED']),True)
        if answer is None:raise subprocess.TimeoutExpired('fake',1)
        return subprocess.CompletedProcess('fake',returncode,'I have eaten.' if answer else 'no','')
    monkeypatch.setattr(rt_roundtrip_cohorts.subprocess,'run',call)


def test_old_success_cannot_fill_new_minimum(monkeypatch):
    d=data();d['records']['nl:ik at']={'trials':100,'restored':100,'failures':[]}
    d['seeds']=[1];fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['trials']==101 and rt_roundtrip_cohorts.rate(rec)==1
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'
    assert not rt_roundtrip_cohorts.gate_for(d,'all')('ik at','nl')


def test_old_success_cannot_mask_current_failure(monkeypatch):
    d=data();d['records']['nl:ik at']={'trials':100,'restored':100,'failures':[]}
    fake(monkeypatch,{1:False,2:False,3:False});rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    assert rt_roundtrip_cohorts.rate(d['records']['nl:ik at'])==0
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='never'


@pytest.mark.parametrize('empty',['seeds','templates'])
def test_selected_zero_work_invalidates_latest_not_history(monkeypatch,empty):
    d=data();fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    old=copy.deepcopy(d['records']['nl:ik at']['cohorts'][0])
    d[empty]=[];rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['cohorts'][0]==old
    assert rec['cohorts'][-1]['attempted']==0
    assert rt_roundtrip_cohorts.rate(rec) is None and rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'
    assert not d['run_history'][-1]['complete']


def test_partial_selection_leaves_other_history_untouched(monkeypatch):
    d=data();fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    old=copy.deepcopy(d['records'])
    rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY,only_lang='de')
    assert d['records']==old
    assert d['run_history'][-1]['selected_forms']==[]
    assert not d['run_history'][-1]['complete']


def test_history_and_legacy_snapshot_survive_recovery(monkeypatch):
    d=data();old={'trials':9,'restored':7,'timeouts':4,'failures':['old'], 'accounting_version':2,'pending_timeouts':2}
    d['records']['nl:ik at']=copy.deepcopy(old)
    fake(monkeypatch,{1:None,2:None,3:None});rt_roundtrip_cohorts.run(d,'first-secret-command',entries=ENTRY)
    rec=d['records']['nl:ik at'];first=copy.deepcopy(rec['cohorts'][0])
    assert rec['legacy_snapshot']==old and rt_roundtrip_cohorts.rate(rec) is None
    d=json.loads(json.dumps(d));d['seeds']=[4,5]
    fake(monkeypatch);rt_roundtrip_cohorts.run(d,'new-command',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['legacy_snapshot']==old and rec['cohorts'][0]==first
    assert rec['timeouts']==7 and rec['pending_timeouts']==2 and rec['failures']==['old']
    assert rec['cohorts'][-1]['completed']==2 and rt_roundtrip_cohorts.rate(rec)==1
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='pass'
    assert rec['cohorts'][0]['timeouts']==3 and not rec['cohorts'][0]['complete']
    assert rec['cohorts'][0]['config']['command_sha256']!=rec['cohorts'][1]['config']['command_sha256']
    assert 'first-secret-command' not in json.dumps(d)
    assert {t['target_id'] for t in first['targets']}.isdisjoint(t['target_id'] for t in rec['cohorts'][-1]['targets'])


def test_duplicate_targets_do_not_fill_minimum(monkeypatch):
    d=data();d['seeds']=[1,1];d['templates']=['{s}.','{s}.'];fake(monkeypatch)
    rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY*2)
    rec=d['records']['nl:ik at']
    assert rec['cohorts'][-1]['attempted']==1
    assert d['run_history'][-1]['duplicate_targets']==7
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'


def test_seed_identity_matches_actual_environment(monkeypatch):
    d=data();d['seeds']=[1,'1'];fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['cohorts'][-1]['attempted']==1
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'


def test_changed_prompt_changes_target_identity(monkeypatch):
    d=data();fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    first=copy.deepcopy(d['records']['nl:ik at']['cohorts'][-1])
    monkeypatch.setattr(rt_roundtrip_cohorts,'PROMPT','Different instruction: {c}')
    rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    latest=d['records']['nl:ik at']['cohorts'][-1]
    assert {t['target_id'] for t in first['targets']}.isdisjoint(t['target_id'] for t in latest['targets'])


@pytest.mark.parametrize('field,value',[('min_trials',float('nan')),('min_trials',-1),('min_trials',True),
    ('thresholds',{'lt100m':float('nan'),'ge100m':.9}),('thresholds',{'lt100m':-1,'ge100m':.9}),
    ('seeds',[True]),('seeds',[{}]),('templates',[None])])
def test_invalid_configuration_cannot_mutate_or_execute(monkeypatch,field,value):
    d=data();d[field]=value;before=copy.deepcopy(d)
    monkeypatch.setattr(rt_roundtrip_cohorts.subprocess,'run',lambda *a,**k:pytest.fail('must not execute'))
    with pytest.raises(ValueError):rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    assert json.dumps(d,sort_keys=True)==json.dumps(before,sort_keys=True)


def test_policy_snapshot_does_not_alias_current_policy(monkeypatch):
    d=data();fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    policy=d['records']['nl:ik at']['cohorts'][-1]['config']['evaluation_policy']
    d['min_trials']=10;d['thresholds']['lt100m']=.1
    assert policy['min_trials']==2 and policy['thresholds']['lt100m']==.9
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'


@pytest.mark.parametrize('mutation',['zero_completed','duplicate_targets','wrong_count','wrong_scope','wrong_version','wrong_identity','missing_history','missing_config','wrong_form','null_policy','null_minimum','null_threshold','null_languages'])
def test_loaded_malformed_cohort_is_unverified(monkeypatch,mutation):
    d=data();fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
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
    assert rt_roundtrip_cohorts.rate(rec) is None
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'
    assert not rt_roundtrip_cohorts.gate_for(d,'all')('ik at','nl')


@pytest.mark.parametrize('mutation',['missing_outcome','missing_expected','extra_expected','duplicate_expected','absent_expected'])
def test_loaded_receipt_requires_exact_scheduled_targets(monkeypatch,mutation):
    d=data();fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at'];current=rec['cohorts'][-1]
    if mutation=='missing_outcome':
        current['targets'].pop()
        for field in ('attempted','completed','restored'):current[field]=2
    elif mutation=='missing_expected':current['expected_target_ids'].pop()
    elif mutation=='extra_expected':current['expected_target_ids'].append('0'*64)
    elif mutation=='duplicate_expected':current['expected_target_ids'].append(current['expected_target_ids'][0])
    else:current.pop('expected_target_ids')
    assert rt_roundtrip_cohorts.rate(rec) is None
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'


@pytest.mark.parametrize('returncode',[1,2,-9])
def test_execution_failure_cannot_score_correct_stdout(monkeypatch,returncode):
    d=data();fake(monkeypatch,returncode=returncode);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['cohorts'][-1]['execution_errors']==3
    assert rec['trials']==0 and rec['restored']==0 and rec['attempted']==3
    assert rt_roundtrip_cohorts.rate(rec) is None


def test_latest_mixed_timeout_not_pass(monkeypatch):
    d=data();fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    fake(monkeypatch,{2:None});rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['trials']==5 and rec['cohorts'][-1]['completed']==2
    assert rt_roundtrip_cohorts.rate(rec) is None and not rt_roundtrip_cohorts.gate_for(d,'all')('ik at','nl')


def test_legacy_reads_unchanged():
    rec={'trials':10,'restored':9,'timeouts':0}
    before=copy.deepcopy(rec);assert rt_roundtrip_cohorts.rate(rec)==.9;assert rec==before
    for rec in [{'trials':10,'restored':9,'timeouts':3,'pending_timeouts':0,'accounting_version':2},
                {'trials':10,'restored':9,'timeouts':3,'pending_trials':[],'legacy_pending':False,'accounting_version':3}]:
        before=copy.deepcopy(rec);assert rt_roundtrip_cohorts.rate(rec) is None;assert rec==before
        d=data();d['records']['nl:ik at']=rec
        assert not rt_roundtrip_cohorts.gate_for(d,'all')('ik at','nl')
    assert rt_roundtrip_cohorts.rate({'trials':10,'restored':9,'timeouts':3}) is None
    assert rt_roundtrip_cohorts.rate({'trials':10,'restored':9,'timeouts':3,'accounting_version':3,'pending_trials':['x']}) is None
    assert rt_roundtrip_cohorts.rate({'trials':10,'restored':9,'timeouts':3,'accounting_version':3}) is None


def test_retry_layout_v3_is_snapshotted_not_reinterpreted(monkeypatch):
    d=data();old={'accounting_version':3,'trials':10,'restored':9,'timeouts':3,'failures':['old'],
                 'pending_trials':['old-source/seed'],'legacy_pending':True}
    d['records']['nl:ik at']=copy.deepcopy(old)
    assert rt_roundtrip_cohorts.rate(d['records']['nl:ik at']) is None
    fake(monkeypatch,{1:False,2:False,3:False});rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rec['legacy_snapshot']==old and rec['pending_trials']==old['pending_trials']
    assert rec['accounting_version']==4 and rt_roundtrip_cohorts.rate(rec)==0


def test_latest_retries_do_not_rewrite_previous_outcomes(monkeypatch):
    d=data();fake(monkeypatch,{1:None,2:None,3:None});rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    first=copy.deepcopy(d['records']['nl:ik at']['cohorts'][0])
    d['seeds']=[1,2];fake(monkeypatch,{2:False});rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    rec=d['records']['nl:ik at']
    assert rt_roundtrip_cohorts.rate(rec)==.5 and rt_roundtrip_cohorts.status(d,'nl','ik at')=='fail'
    assert rec['cohorts'][0]==first and rec['timeouts']==3
    d['seeds']=[3];fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    assert rt_roundtrip_cohorts.rate(rec)==1 and rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'
    assert rec['cohorts'][1]['restored']==1 and rec['failures']==['Ik at.']


def test_changed_source_has_new_identity_and_no_old_minimum(monkeypatch):
    d=data();fake(monkeypatch);rt_roundtrip_cohorts.run(d,'fake',entries=ENTRY)
    previous=copy.deepcopy(d['records']['nl:ik at']['cohorts'][0])
    d['seeds']=[1]
    monkeypatch.setattr(rt_roundtrip_cohorts.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess('fake',0,'Other.',''))
    rt_roundtrip_cohorts.run(d,'fake',entries=[{'lang':'nl','from':['Other'],'to':'ik at'}])
    rec=d['records']['nl:ik at']
    assert rt_roundtrip_cohorts.status(d,'nl','ik at')=='unverified'
    assert previous['targets'][0]['target_id']!=rec['cohorts'][-1]['targets'][0]['target_id']


@pytest.mark.parametrize('seeds,answers,exitcode',[([],{},1),([1],{},1),([1,2,3],{2:None},1),([1,2,3],{},0)])
def test_cli_saves_exact_invocation(monkeypatch,tmp_path,seeds,answers,exitcode):
    d=data();d['seeds']=seeds
    d['records']['de:x']={'trials':0,'restored':0,'timeouts':3,'failures':[]}
    fake(monkeypatch,answers);monkeypatch.setattr(rt_roundtrip_cohorts,'load',lambda:d)
    monkeypatch.setattr(rt_roundtrip_cohorts,'DATA_PATH',tmp_path/'result.json')
    monkeypatch.setitem(sys.modules,'tense_matrix',types.SimpleNamespace(build=lambda:({'entries':ENTRY},)))
    assert rt_roundtrip_cohorts.main(['--run','--cmd','fake'])==exitcode
    assert json.loads((tmp_path/'result.json').read_text())==d
    assert d['run_history'][-1]['verifiable']==(exitcode==0)


# ──── roundtrip_incomplete ────────────────────────────────────────

spec_roundtrip_incomplete = importlib.util.spec_from_file_location('roundtrip_under_test', Path(__file__).resolve().parents[1] / 'scripts/roundtrip.py')


rt_roundtrip_incomplete = importlib.util.module_from_spec(spec_roundtrip_incomplete)


spec_roundtrip_incomplete.loader.exec_module(rt_roundtrip_incomplete)


@pytest.mark.parametrize('responses', [(True,None,True), (None,None,None), (False,None,False)])
@pytest.mark.parametrize('lang', ['nl','en'])
def test_incomplete_never_passes(monkeypatch, responses, lang):
    d=data()
    def fake(*args, **kwargs):
        answer=responses[int(kwargs['env']['ROUNDTRIP_SEED'])-1]
        if answer is None:
            raise subprocess.TimeoutExpired('fake',1)
        return subprocess.CompletedProcess('fake',0,'I have eaten.' if answer else 'no','')
    monkeypatch.setattr(rt_roundtrip_incomplete.subprocess,'run',fake)
    rt_roundtrip_incomplete.run(d,'fake',entries=[{'lang':lang,'from':['I have eaten'],'to':'ik at'}])
    rec=d['records'][f'{lang}:ik at']
    assert rec['attempted']==3
    assert rec['completed']==rec['trials']==sum(x is not None for x in responses)
    assert rec['timeouts']==sum(x is None for x in responses)
    assert rec['restored']==sum(x is True for x in responses)
    assert rec['failures']==['Ik at.']*sum(x is False for x in responses)
    assert rec['accounting_version']==4
    assert rt_roundtrip_incomplete.rate(rec) is None
    assert rt_roundtrip_incomplete.status(d,lang,'ik at')=='unverified'
    assert not rt_roundtrip_incomplete.gate_for(d,'all')('ik at',lang)
    assert not rt_roundtrip_incomplete.gate_for(d,'lt100m')('ik at',lang)


def test_existing_complete_record_unchanged():
    d=data(); rec={'trials':10,'restored':9,'failures':['past failure']}
    d['records']['nl:ik at']=rec; before=copy.deepcopy(d)
    assert rt_roundtrip_incomplete.rate(rec)==0.9
    assert rt_roundtrip_incomplete.status(d,'nl','ik at')=='pass'
    assert rt_roundtrip_incomplete.gate_for(d,'all')('ik at','nl')
    assert d==before


def test_append_keeps_old_counts_and_failure(monkeypatch):
    d=data(); d['records']['nl:ik at']={'trials':10,'restored':8,'failures':['past failure'],'timeouts':2}
    monkeypatch.setattr(rt_roundtrip_incomplete.subprocess,'run',lambda *a,**k:subprocess.CompletedProcess('fake',0,'I have eaten.',''))
    rt_roundtrip_incomplete.run(d,'fake',entries=[{'lang':'nl','from':['I have eaten'],'to':'ik at'}])
    rec=d['records']['nl:ik at']
    assert (rec['attempted'],rec['completed'],rec['restored'],rec['timeouts'])==(15,13,11,2)
    assert rec['failures']==['past failure']
    # the legacy timeouts stay counted, but this run completed every attempt
    assert rec['legacy_snapshot']['timeouts']==2
    assert rec['cohorts'][-1]['timeouts']==0
    assert rec['cohorts'][-1]['restored']==3
    assert rt_roundtrip_incomplete.rate(rec)==1.0  # latest 3/3, not cumulative 11/13


@pytest.mark.parametrize('timeout',[0,-1,float('nan'),float('inf')])
def test_invalid_timeout_rejected_before_mutation(timeout):
    d=data(); before=copy.deepcopy(d)
    with pytest.raises(ValueError,match='finite and positive'):
        rt_roundtrip_incomplete.run(d,'fake',entries=[],timeout=timeout)
    assert d==before


def test_cli_saves_incomplete_before_failure(monkeypatch,tmp_path,capsys):
    d=data(); target=tmp_path/'results.json'
    monkeypatch.setattr(rt_roundtrip_incomplete,'load',lambda:d)
    monkeypatch.setattr(rt_roundtrip_incomplete,'DATA_PATH',target)
    def fake_run(d,*a,**k):
        d['records']['nl:ik at']={'trials':2,'restored':2,'timeouts':1,'failures':[], 'attempted':3,'completed':2,'accounting_version':2}
        return d
    monkeypatch.setattr(rt_roundtrip_incomplete,'run',fake_run)
    assert rt_roundtrip_incomplete.main(['--run','--cmd','fake'])==1
    assert json.loads(target.read_text())==d
    assert 'unverified' in capsys.readouterr().err


# ──── roundtrip_norm_nfc ──────────────────────────────────────────

"""roundtrip.norm: NFD の応答でアクセントが落ちて NFC の原文と不一致にならないこと。"""


def test_nfd_reply_matches_nfc_source():
    src = "The café in Hà Nội is naïve."
    assert norm(unicodedata.normalize("NFD", src)) == norm(src) == "the café in hà nội is naïve"


# ──── roundtrip_provenance ────────────────────────────────────────

"""Round-trip run provenance: origin/main SHA and timestamp on every new run (no backfill)."""


ROOT = Path(__file__).resolve().parents[1]


SHA = "0123456789abcdef0123456789abcdef01234567"


TS = "2026-11-10T09:55:00+00:00"


PROV = {"origin_main_sha": SHA, "timestamp": TS}


DOC = ROOT / "docs/ontology/tense-merge-collisions.md"


def data_roundtrip_provenance() -> dict:
    return {"templates": ["{s}.", "Maybe {s} today."], "seeds": [1, 2], "records": {}, "min_trials": 2,
            "thresholds": {"lt100m": .9, "ge100m": .9}, "ge100m_langs": ["en"]}


@pytest.fixture
def restorer(monkeypatch):
    def call(cmd, **kw):
        source = kw["input"].rsplit("\n", 1)[-1].replace("Ik at", "I have eaten").replace("ik at", "I have eaten")
        return subprocess.CompletedProcess(cmd, 0, source, "")
    monkeypatch.setattr(rt.subprocess, "run", call)


def test_injected_provenance_on_invocation_and_every_cohort(restorer):
    d = data_roundtrip_provenance()
    prov = copy.deepcopy(PROV)
    rt.run(d, "fake", entries=ENTRY + [{"lang": "nl", "from": ["I have seen"], "to": "ik zag"}], provenance=prov)
    assert d["run_history"][-1]["provenance"] == PROV
    for k in ("nl:ik at", "nl:ik zag"):
        assert d["records"][k]["cohorts"][-1]["provenance"] == PROV
    assert prov == PROV  # caller's dict is copied, not shared
    d["run_history"][-1]["provenance"]["timestamp"] = "x"
    assert d["records"]["nl:ik at"]["cohorts"][-1]["provenance"] == PROV


def test_default_provenance_uses_git_and_clock(restorer, monkeypatch):
    monkeypatch.setattr(rt, "origin_main_sha", lambda root=rt.ROOT: SHA)
    monkeypatch.setattr(rt, "utc_now", lambda: TS)
    d = data_roundtrip_provenance()
    rt.run(d, "fake", entries=ENTRY)
    assert d["run_history"][-1]["provenance"] == PROV
    assert d["records"]["nl:ik at"]["cohorts"][-1]["provenance"] == PROV


def test_missing_git_is_recorded_as_none(restorer, monkeypatch):
    monkeypatch.setattr(rt, "origin_main_sha", lambda root=rt.ROOT: None)
    monkeypatch.setattr(rt, "utc_now", lambda: TS)
    d = data_roundtrip_provenance()
    rt.run(d, "fake", entries=ENTRY)
    assert d["run_history"][-1]["provenance"] == {"origin_main_sha": None, "timestamp": TS}


def test_existing_records_are_not_backfilled(restorer):
    d = data_roundtrip_provenance()
    rt.run(d, "fake", entries=ENTRY, provenance=PROV)
    old = d["records"]["nl:ik at"]["cohorts"][0]
    old_history = d["run_history"][0]
    del old["provenance"], old_history["provenance"]  # simulate a pre-provenance run
    later = {"origin_main_sha": SHA[::-1], "timestamp": "2026-11-11T00:00:00+09:00"}
    rt.run(d, "fake", entries=ENTRY, provenance=later)
    assert "provenance" not in d["records"]["nl:ik at"]["cohorts"][0]
    assert "provenance" not in d["run_history"][0]
    assert d["records"]["nl:ik at"]["cohorts"][1]["provenance"] == later


def test_provenance_does_not_change_scoring(restorer):
    a, b = data_roundtrip_provenance(), data_roundtrip_provenance()
    rt.run(a, "fake", entries=ENTRY, provenance=PROV)
    rt.run(b, "fake", entries=ENTRY, provenance={"origin_main_sha": None, "timestamp": "2020-01-01T00:00:00-05:00"})
    assert rt.status(a, "nl", "ik at") == rt.status(b, "nl", "ik at") == "pass"
    assert rt.rate(a["records"]["nl:ik at"]) == rt.rate(b["records"]["nl:ik at"]) == 1
    # an older cohort without provenance still validates
    del a["records"]["nl:ik at"]["cohorts"][-1]["provenance"]
    assert rt.status(a, "nl", "ik at") == "pass"


@pytest.mark.parametrize("bad", [
    {"origin_main_sha": SHA, "timestamp": "2026-11-10T09:55:00"},          # naive
    {"origin_main_sha": SHA, "timestamp": "yesterday"},
    {"origin_main_sha": SHA, "timestamp": None},
    {"origin_main_sha": SHA.upper(), "timestamp": TS},
    {"origin_main_sha": SHA[:12], "timestamp": TS},
    {"origin_main_sha": SHA, "timestamp": TS, "extra": 1},
    {"timestamp": TS},
    [SHA, TS],
])
def test_invalid_provenance_is_rejected_before_execution(monkeypatch, bad):
    d = data_roundtrip_provenance()
    before = copy.deepcopy(d)
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **k: pytest.fail("must not execute"))
    with pytest.raises(ValueError):
        rt.run(d, "fake", entries=ENTRY, provenance=bad)
    assert json.dumps(d, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_malformed_default_clock_is_rejected(restorer, monkeypatch):
    monkeypatch.setattr(rt, "utc_now", lambda: "2026-11-10 09:55")
    with pytest.raises(ValueError):
        rt.run(data_roundtrip_provenance(), "fake", entries=ENTRY)


def test_utc_now_is_timezone_aware_iso8601():
    parsed = datetime.fromisoformat(rt.utc_now())
    assert parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0
    assert rt.valid_provenance({"origin_main_sha": None, "timestamp": rt.utc_now()})


def test_origin_main_sha_matches_git_and_ignores_run_fakes(monkeypatch, tmp_path):
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **k: pytest.fail("restore-command fake must not be used"))
    sha = rt.origin_main_sha()
    p = subprocess.Popen(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", "origin/main^{commit}"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    expected = p.communicate()[0].strip() or None
    assert sha == (expected if p.returncode == 0 else None)
    assert rt.origin_main_sha(tmp_path) is None  # not a git checkout


# ---------------------------------------------------------------- mapping_graph reads it
def _cohort(run_id: str, **extra) -> dict:
    return {"run_id": run_id, "config": {"command_sha256": "a" * 64, "templates": ["{s}.", "Maybe {s} today."]},
            "targets": [{"status": "completed", "restored": True, "source": "I came."},
                        {"status": "completed", "restored": False, "source": "Maybe I came today."}], **extra}


def _graph(rtd: dict) -> mg.Graph:
    g = mg.Graph()
    g.add("form:de:kam", "Form")
    mg._record_nodes(g, rtd, "de", "kam", "form:de:kam")
    return g


def test_graph_reads_cohort_then_history_provenance():
    other = {"origin_main_sha": SHA[::-1], "timestamp": "2026-11-09T00:00:00+09:00"}
    rtd = {"records": {"de:kam": {"lang": "de", "form": "kam", "cohorts": [
        _cohort("r1", provenance=PROV), _cohort("r2"), _cohort("r3", provenance={"timestamp": "bad"})]}},
           "run_history": [{"run_id": "r1", "provenance": other}, {"run_id": "r2", "provenance": other}]}
    g = _graph(rtd)
    r1, r2, r3 = (g.nodes[f"rt:de:kam:{r}"] for r in ("r1", "r2", "r3"))
    assert (r1["measured_at_main"], r1["timestamp"]) == (SHA, TS)  # cohort wins over run_history
    assert (r2["measured_at_main"], r2["timestamp"]) == (SHA[::-1], "2026-11-09T00:00:00+09:00")
    assert (r3["measured_at_main"], r3["timestamp"]) == (None, None)  # malformed is ignored
    assert r1["measured_sources"] == ["i came"] and r3["latest"] is True


def test_judge_snapshot_sha_keeps_priority_for_measured_at_main():
    judge = {"kind": "independent_blind_judge", "origin_main_sha": "c" * 40}
    rtd = {"records": {"de:kam": {"lang": "de", "form": "kam", "cohorts": [_cohort("r1", provenance=PROV)]}},
           "run_history": [{"run_id": "r1", "judge_provenance": judge}]}
    n = _graph(rtd).nodes["rt:de:kam:r1"]
    assert n["measured_at_main"] == "c" * 40 and n["run_origin_main_sha"] == SHA and n["timestamp"] == TS
    assert n["evaluator"] == "independent_blind_judge"


def test_new_run_is_counted_by_check(restorer):
    d = data_roundtrip_provenance()
    rt.run(d, "fake", entries=ENTRY, provenance=PROV)
    n = _graph({**d, "records": {"de:kam": {**d["records"]["nl:ik at"], "lang": "de", "form": "kam"}}}).nodes
    rec = n[f"rt:de:kam:{d['run_history'][-1]['run_id']}"]
    assert rec["measured_at_main"] == SHA and rec["timestamp"] == TS
    assert rec["measured_sources"] == ["i have eaten"]


def test_measured_sources_prefers_the_most_specific_template():
    c = {"config": {"templates": ["{s}.", "Maybe {s} today.", "She told me that {s}."]},
         "targets": [{"source": s} for s in ("He came.", "Maybe he came today.", "She told me that he came.")]}
    assert mg.measured_sources(c) == ["he came"]
    assert mg.measured_sources({"targets": [{"source": "x"}]}) == []


# ---------------------------------------------------------------- tense_merge report
@pytest.fixture(scope="module")
def g():
    return mg.build()


def test_tense_merge_doc_is_generated_from_the_graph(g):
    assert DOC.read_text(encoding="utf-8") == mg.tense_merge_doc(g), (
        "regenerate: uv run python scripts/mapping_graph.py --collisions --markdown > docs/ontology/tense-merge-collisions.md")


def test_tense_merge_rows_match_collisions(g):
    rows = mg.tense_merge_rows(g)
    col = mg.collisions(g)["tense_merge"]
    assert [r["id"] for r in rows] == [c["id"] for c in col]
    assert sum(Counter(r["lang"] for r in rows).values()) == len(col)
    for r in rows:
        assert len(r["tenses"]) >= 2
        assert {s["meaning"] for s in r["sources"]} == set(r["meanings"])
        assert {s["source"] for s in r["sources"] if s["measured"]} <= set(r["measured_sources"])


def test_cli_markdown_needs_collisions():
    out = subprocess.run([sys.executable, str(ROOT / "scripts/mapping_graph.py"), "--check", "--markdown"],
                         capture_output=True, text=True)
    assert out.returncode == 2 and "--markdown needs --collisions" in out.stderr
    out = subprocess.run([sys.executable, str(ROOT / "scripts/mapping_graph.py"), "--collisions", "--markdown"],
                         capture_output=True, text=True, check=True)
    assert out.stdout == DOC.read_text(encoding="utf-8")


# ──── roundtrip_sticky_timeout ────────────────────────────────────

"""A recorded timeout must not exclude a form forever (2bot #97 Should 1)."""


spec_roundtrip_sticky_timeout = importlib.util.spec_from_file_location("roundtrip_sticky", Path(__file__).resolve().parents[1] / "scripts/roundtrip.py")


rt_roundtrip_sticky_timeout = importlib.util.module_from_spec(spec_roundtrip_sticky_timeout)


spec_roundtrip_sticky_timeout.loader.exec_module(rt_roundtrip_sticky_timeout)


def _hang(*a, **k):
    raise subprocess.TimeoutExpired("fake", 1)


def _ok(*a, **k):
    return subprocess.CompletedProcess("fake", 0, "I have eaten.", "")


def test_timeout_then_success_is_verifiable(monkeypatch):
    d = data()
    monkeypatch.setattr(rt_roundtrip_sticky_timeout.subprocess, "run", _hang)
    rt_roundtrip_sticky_timeout.run(d, "fake", entries=ENTRY)
    rec = d["records"]["nl:ik at"]
    assert rt_roundtrip_sticky_timeout.unresolved_timeouts(rec) == 3 and rt_roundtrip_sticky_timeout.rate(rec) is None
    monkeypatch.setattr(rt_roundtrip_sticky_timeout.subprocess, "run", _ok)
    rt_roundtrip_sticky_timeout.run(d, "fake", entries=ENTRY)
    rec = d["records"]["nl:ik at"]
    assert (rec["trials"], rec["timeouts"], rec["completed"], rec["attempted"]) == (3, 3, 3, 6)
    assert rec["cohorts"][-1]["timeouts"] == 0
    assert rt_roundtrip_sticky_timeout.rate(rec) == 1.0
    assert rt_roundtrip_sticky_timeout.status(d, "nl", "ik at") == "pass"
    assert rt_roundtrip_sticky_timeout.gate_for(d, "all")("ik at", "nl")


def test_partial_timeout_in_latest_run_stays_unverified(monkeypatch):
    d = data()
    monkeypatch.setattr(rt_roundtrip_sticky_timeout.subprocess, "run", _ok)
    rt_roundtrip_sticky_timeout.run(d, "fake", entries=ENTRY)
    monkeypatch.setattr(rt_roundtrip_sticky_timeout.subprocess, "run", lambda *a, **k: _hang() if k["env"]["ROUNDTRIP_SEED"] == "2" else _ok())
    rt_roundtrip_sticky_timeout.run(d, "fake", entries=ENTRY)
    rec = d["records"]["nl:ik at"]
    assert rec["cohorts"][-1]["timeouts"] == 1 and rec["timeouts"] == 1
    assert rt_roundtrip_sticky_timeout.rate(rec) is None
    assert not rt_roundtrip_sticky_timeout.gate_for(d, "lt100m")("ik at", "nl")


def test_legacy_record_without_pending_uses_timeouts():
    assert rt_roundtrip_sticky_timeout.unresolved_timeouts({"trials": 3, "restored": 3, "timeouts": 2}) == 2
    assert rt_roundtrip_sticky_timeout.unresolved_timeouts(None) == 0


def _cli(monkeypatch, tmp_path, d, fake):
    monkeypatch.setattr(rt_roundtrip_sticky_timeout, "load", lambda: d)
    monkeypatch.setattr(rt_roundtrip_sticky_timeout, "DATA_PATH", tmp_path / "r.json")
    monkeypatch.setattr(rt_roundtrip_sticky_timeout.subprocess, "run", fake)
    monkeypatch.setitem(sys.modules, "tense_matrix", types.SimpleNamespace(build=lambda: ({"entries": ENTRY},)))
    return rt_roundtrip_sticky_timeout.main(["--run", "--cmd", "fake"])


def test_cli_exit_recovers_after_successful_rerun(monkeypatch, tmp_path):
    d = data()
    assert _cli(monkeypatch, tmp_path, d, _hang) == 1
    assert _cli(monkeypatch, tmp_path, d, _ok) == 0
    assert json.loads((tmp_path / "r.json").read_text())["records"]["nl:ik at"]["cohorts"][-1]["timeouts"] == 0


def test_cli_exit_ignores_untouched_stale_record(monkeypatch, tmp_path):
    d = data()
    d["records"]["de:x"] = {"lang": "de", "form": "x", "trials": 0, "restored": 0, "failures": [], "timeouts": 3}
    assert _cli(monkeypatch, tmp_path, d, _ok) == 0


# ──── roundtrip_timeout ───────────────────────────────────────────

"""scripts/roundtrip.run: 1 試行のタイムアウトで他の結果を失わない。"""


_SCRIPT = (
    "import os,sys,time\n"
    "sys.stdin.read()\n"
    "if os.environ['ROUNDTRIP_SEED']=='2': time.sleep(30)\n"
    "print('I have eaten.' if os.environ['ROUNDTRIP_SEED']=='1' else 'no')\n"
)


def test_timeout_keeps_other_results() -> None:
    data = {"templates": ["{s}."], "seeds": [1, 2, 3], "records": {}}
    cmd = f"{shlex.quote(sys.executable)} -c {shlex.quote(_SCRIPT)}"
    entries = [{"lang": "nl", "from": ["I have eaten"], "to": "ik at"}]
    out = roundtrip.run(data, cmd, entries=entries, timeout=2)
    rec = out["records"]["nl:ik at"]
    assert rec["trials"] == 2
    assert rec["restored"] == 1
    assert rec["timeouts"] == 1
    assert rec["failures"] == ["Ik at."]
