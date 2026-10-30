from __future__ import annotations

import json
import pytest
from Zipilogue.dialogue_lab import (Client, corpus, encode, experiment, negotiate,
                                    receiver_prompt, valid_task, validate_mapping)


def test_heldout_is_disjoint_and_task_data_is_not_trivial():
    training, heldout = corpus()
    assert len(training) == 8 and len(heldout) == 20
    assert not {x['text'] for x in training} & {x['text'] for x in heldout}
    assert len({json.dumps(x['expected'], sort_keys=True) for x in heldout}) == 20
    assert {x['expected']['keep_backup'] for x in heldout} == {True, False}
    assert {x['expected']['action'] for x in heldout} == {'deploy', 'rollback', 'hold'}


@pytest.mark.parametrize('mapping', [
    [{'long': 'deploy', 'short': 'alpha'}],
    [{'long': 'unseen phrase', 'short': 'q1'}],
    [{'long': 'deploy', 'short': 'q1'}, {'long': 'rollback', 'short': 'Q1'}],
    [{'long': 'deploy', 'short': 'q1'}, {'long': 'DEPLOY', 'short': 'q2'}],
    [{'long': 'deploy', 'short': 'x; rm'}],
])
def test_model_proposals_must_not_collide_or_invent_long_forms(mapping):
    with pytest.raises(ValueError):
        validate_mapping({'mapping': mapping}, corpus()[0])


def test_one_pass_codec_preserves_boundaries_and_negation():
    mapping = [{'long': 'delete the backup', 'short': 'q7'},
               {'long': 'do not delete the backup', 'short': 'q8'}]
    assert encode('do not delete the backup; delete the backup', mapping) == 'q8; q7'
    assert encode('deploy deployment', [{'long': 'deploy', 'short': 'q1'}]) == 'q1 deployment'


def test_receiver_never_sees_expected_task_or_original_message():
    source = corpus()[1][0]
    prompt = receiver_prompt('q1 alpha q2', [{'long': 'deploy', 'short': 'q1'}])
    assert source['text'] not in prompt
    assert 'expected' not in prompt and 'case-' not in prompt
    assert 'q1 alpha q2' in prompt


def test_task_validation_rejects_bool_as_integer():
    expected = corpus()[1][0]['expected']
    assert valid_task(expected)
    assert not valid_task(dict(expected, retries=True))
    assert not valid_task(dict(expected, keep_backup=1))
    assert not valid_task({'unknown': True})


class ScriptedClient:
    """Protocol test fixture only: never evidence of model invention."""
    def __init__(self, reject=False):
        self.calls = []
        self.reject = reject
        self.receiver_prompts = []
    def tokens(self, text):
        return len(text.encode())
    def ask(self, role, prompt, max_tokens=256):
        self.calls.append({'role': role, 'request': {'messages': [{'content': prompt}]},
                           'response': {'choices': [{'message': {'content': '{}'}}]}})
        if role == 'sender-proposal':
            return {'mapping': [{'long': 'For service', 'short': 'q1'}]}
        if 'critique' in role:
            return {'accept': not self.reject, 'reason': 'fixture vote'}
        self.receiver_prompts.append(prompt)
        return {'unknown': True}


def test_unanimous_peer_approval_required_and_rounds_are_bounded():
    client = ScriptedClient(reject=True)
    result = negotiate(client, corpus()[0], peers=2, rounds=2)
    assert result['agreed'] is False
    assert len(client.calls) == 6
    assert len(result['transcripts']) == 2
    peer_prompts = [x['request']['messages'][0]['content'] for x in client.calls if 'critique' in x['role']]
    assert peer_prompts[0] != peer_prompts[1]
    assert 'negation and condition' in peer_prompts[0]
    assert 'collisions' in peer_prompts[1]


def test_control_arms_frozen_rulebook_and_cost_accounting():
    client = ScriptedClient()
    result = experiment(client, groups=1, peers=2, rounds=1)
    group = result['groups'][0]
    assert group['status'] == 'completed'
    assert len(group['cases']) == 60 and len(client.calls) == 63
    assert group['rulebook']['rules'][0]['short'] == 'q1'
    assert all(x['status'] == 'unknown_or_invalid' for x in group['cases'])
    assert {x['arm'] for x in group['cases']} == {'raw', 'shared', 'unshared'}
    assert group['wire_tokens_with_book_and_negotiation'] > group['summary']['shared']['message_tokens']
    assert group['negotiation_and_dictionary_net_saving'] < 0
    assert group['positive_evidence'] is False
    assert result['emergent_language_claim'] is False
    for case, prompt in zip(group['cases'], client.receiver_prompts):
        if case['arm'] == 'unshared':
            assert 'CODEBOOK:\n[]' in prompt and '"long"' not in prompt


def test_negotiation_errors_are_not_reported_as_success():
    class Broken(ScriptedClient):
        def ask(self, *args, **kwargs):
            raise ValueError('incomplete model output')
    result = experiment(Broken(), groups=1)
    assert result['groups'][0]['status'] == 'negotiation_error'
    assert result['calls'] == []


def test_invalid_limits_fail_before_model_call():
    with pytest.raises(ValueError):
        experiment(ScriptedClient(), peers=0)


def test_client_requires_completed_json_and_keeps_error_log(monkeypatch):
    client = Client('http://127.0.0.1:8080')
    monkeypatch.setattr(client, 'post', lambda *args: {'choices': [
        {'finish_reason': 'length', 'message': {'content': '{"mapping":[]}'}}]})
    with pytest.raises(ValueError, match='incomplete'):
        client.ask('sender-proposal', 'fixture')
    assert len(client.calls) == 1 and 'error' in client.calls[0]
    assert client.calls[0]['request']['response_format'] == {'type': 'json_object'}


def test_client_does_not_accept_non_object_json(monkeypatch):
    client = Client('http://127.0.0.1:8080')
    monkeypatch.setattr(client, 'post', lambda *args: {'choices': [
        {'finish_reason': 'stop', 'message': {'content': '[]'}}]})
    with pytest.raises(ValueError, match='JSON object'):
        client.ask('receiver', 'fixture')


def test_tokenizer_unavailable_is_not_silently_an_estimate(monkeypatch):
    client = Client('http://127.0.0.1:8080')
    monkeypatch.setattr(client, 'post', lambda *args: {'tokens': 42})
    with pytest.raises(ValueError, match='tokenizer'):
        client.tokens('text')
