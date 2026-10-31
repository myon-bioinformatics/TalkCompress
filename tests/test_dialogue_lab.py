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
            return {'accept': not self.reject, 'reason': 'fixture vote', 'issues': ([{'rule_index': 0, 'category': 'ambiguity', 'reason': 'fixture specific misreading'}] if self.reject else [])}
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
    for summary in group['summary'].values():
        assert summary['total_content_tokens_with_negotiation'] == (
            summary['prompt_content_tokens'] + summary['completion_content_tokens'] + group['negotiation_content_tokens'])
        assert summary['success_rate'] == 0
    assert result['emergent_language_claim'] is False
    for case, prompt in zip(group['cases'], client.receiver_prompts):
        if case['arm'] == 'unshared':
            assert 'CODEBOOK:\n[]' in prompt and '"long"' not in prompt


def test_negotiation_errors_are_not_reported_as_success():
    class Broken(ScriptedClient):
        def ask(self, *args, **kwargs):
            raise ValueError('incomplete model output')
    result = experiment(Broken(), groups=1)
    assert result['groups'][0]['status'] == 'no_agreement'
    assert result['groups'][0]['failure_counts'] == {'proposal_output': 2}
    assert result['groups'][0]['receiver_evaluation_status'] == 'not_run_no_agreement'
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


def test_proposer_gets_same_length_limit_as_validator_and_precise_feedback():
    client = ScriptedClient()
    negotiate(client, corpus()[0], peers=1, rounds=1)
    prompt = client.calls[0]['request']['messages'][0]['content']
    assert '4..100 characters after whitespace normalization' in prompt
    with pytest.raises(ValueError, match=r'4\.\.100 characters'):
        validate_mapping({'mapping': [{'long': 'x' * 101, 'short': 'q1'}]}, corpus()[0])
    with pytest.raises(ValueError, match='must occur in training'):
        validate_mapping({'mapping': [{'long': 'unseen phrase', 'short': 'q1'}]}, corpus()[0])


def test_candidates_are_repeated_training_only_spans():
    from Zipilogue.dialogue_lab import phrase_candidates
    training, _ = corpus()
    candidates = phrase_candidates(training)
    assert candidates == phrase_candidates(training)
    assert candidates and len(candidates) <= 40
    for phrase in candidates:
        assert sum(phrase.casefold() in c['text'].casefold() for c in training) >= 2
        validate_mapping({'mapping': [{'long': phrase, 'short': 'z99'}]}, training)


@pytest.mark.parametrize('vote', [
    {'accept': False, 'reason': 'ambiguous', 'issues': []},
    {'accept': True, 'reason': 'yes'},
    {'accept': 'true', 'reason': 'yes', 'issues': []},
    {'accept': False, 'reason': 'bad', 'issues': [{'rule_index': True, 'category': 'meaning', 'reason': 'x'}]},
    {'accept': False, 'reason': 'bad', 'issues': [{'rule_index': 1, 'category': 'meaning', 'reason': 'x'}]},
    {'accept': True, 'reason': 'yes', 'issues': [{'rule_index': 0, 'category': 'meaning', 'reason': 'x'}]},
])
def test_vote_contract_rejects_unlocalized_or_contradictory_feedback(vote):
    from Zipilogue.dialogue_lab import validate_vote
    with pytest.raises(ValueError):
        validate_vote(vote, [{'long': 'For service', 'short': 'q1'}])


def test_formal_failure_does_not_call_peers_and_correction_gets_context():
    class Repair(ScriptedClient):
        def ask(self, role, prompt, max_tokens=256):
            result = super().ask(role, prompt, max_tokens)
            if len(self.calls) == 1:
                return {'mapping': [{'long': 'invented phrase', 'short': 'q1'}]}
            return result
    client = Repair()
    result = negotiate(client, corpus()[0], peers=2, rounds=2)
    assert result['agreed']
    assert [c['role'] for c in client.calls] == ['sender-proposal', 'sender-proposal', 'peer-0-critique', 'peer-1-critique']
    prompt = client.calls[1]['request']['messages'][0]['content']
    assert 'proposal_validation' in prompt and 'invented phrase' in prompt


def test_vague_veto_stays_rejected_and_retains_book_in_feedback():
    class Vague(ScriptedClient):
        def ask(self, role, prompt, max_tokens=256):
            result = super().ask(role, prompt, max_tokens)
            if 'critique' in role:
                return {'accept': False, 'reason': 'Some codes ambiguous'}
            return result
    client = Vague()
    report = experiment(client, groups=1, peers=2, rounds=2)
    group = report['groups'][0]
    assert group['failure_counts'] == {'peer_vote_contract': 4}
    assert group['cases'] == [] and 'summary' not in group
    assert group['negotiation_calls'] == 6 and group['negotiation_content_tokens'] > 0
    assert group['receiver_evaluation_status'] == 'not_run_no_agreement'
    prompt = client.calls[3]['request']['messages'][0]['content']
    assert 'peer_vote_contract' in prompt and 'For service' in prompt


def test_specific_veto_feedback_identifies_rule_and_can_be_revised():
    client = ScriptedClient(reject=True)
    result = negotiate(client, corpus()[0], peers=1, rounds=2)
    assert not result['agreed']
    assert result['failure_counts'] == {'peer_semantic_rejection': 2}
    prompt = client.calls[2]['request']['messages'][0]['content']
    assert 'rule_index' in prompt and 'fixture specific misreading' in prompt


def test_failed_negotiation_is_preserved_when_tokenizer_unavailable():
    class Offline(ScriptedClient):
        def ask(self, *args, **kwargs):
            self.calls.append({'request': {'messages': [{'content': 'request'}]}})
            raise OSError('offline')
        def tokens(self, text):
            raise OSError('tokenizer offline')
    group = experiment(Offline(), groups=1)['groups'][0]
    assert group['status'] == 'no_agreement'
    assert group['failure_counts'] == {'proposal_output': 2}
    assert group['negotiation_content_tokens'] is None
    assert 'token_accounting_error' in group
    assert group['cases'] == []


@pytest.mark.parametrize('category', [[], {}, None, True, 42])
def test_invalid_category_is_a_bounded_contract_veto(category):
    class InvalidCategory(ScriptedClient):
        def ask(self, role, prompt, max_tokens=256):
            response = super().ask(role, prompt, max_tokens)
            if 'critique' in role:
                return {'accept': False, 'reason': 'bad', 'issues': [
                    {'rule_index': 0, 'category': category, 'reason': 'specific'}]}
            return response
    report = experiment(InvalidCategory(), groups=1, rounds=2)
    group = report['groups'][0]
    assert group['status'] == 'no_agreement'
    assert group['failure_counts'] == {'peer_vote_contract': 4}
    assert len(group['transcripts']) == 2
    assert group['negotiation_calls'] == 6
    assert group['negotiation_content_tokens'] > 0
    assert group['receiver_evaluation_status'] == 'not_run_no_agreement'


class OfflineResponseClient(Client):
    """Exercise real ask/log/error handling, with no HTTP or model calls."""
    def __init__(self, response):
        super().__init__('http://unused.invalid')
        self.receiver_response = response

    def tokens(self, text):
        return len(text)

    def post(self, path, payload):
        assert path == '/v1/chat/completions'
        if len(self.calls) == 0:
            value = {'mapping': [{'long': 'For service', 'short': 'q1'}]}
        elif len(self.calls) < 3:
            value = {'accept': True, 'reason': 'fixture', 'issues': []}
        else:
            return self.receiver_response
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]}


@pytest.mark.parametrize('response', [
    {'choices': []}, {'choices': None}, {'choices': [None]},
    {'choices': [{'message': None}]}, {'choices': [{'message': {'content': None}}]},
    {}, None,
])
def test_malformed_receiver_response_retains_report_and_unknown_cost(response):
    client = OfflineResponseClient(response)
    report = experiment(client, groups=1)
    group = report['groups'][0]
    assert group['status'] == 'incomplete_token_accounting'
    assert group['receiver_evaluation_status'] == 'completed'
    assert len(group['cases']) == 60 and len(report['calls']) == 63
    assert all(c['status'] == 'model_error' for c in group['cases'])
    assert all(c['completion_content_tokens'] is None for c in group['cases'])
    assert all(s['total_content_tokens_with_negotiation'] is None for s in group['summary'].values())
    assert group['positive_evidence'] is False


@pytest.mark.parametrize('fail_at', ['negotiation', 'book', 'message', 'prompt', 'completion'])
def test_successful_agreement_survives_tokenizer_failure(fail_at):
    class TokenFailure(ScriptedClient):
        def tokens(self, text):
            book = '[{"long":"For service","short":"q1"}]'
            is_target = {
                'negotiation': len(self.calls) == 3 and text != book,
                'book': text == book,
                'message': text.startswith('For service alpha in staging, hold'),
                'prompt': text.startswith('Recover the exact task'),
                'completion': len(self.calls) > 3 and text == '{}',
            }[fail_at]
            if is_target:
                raise OSError('tokenizer unavailable')
            return super().tokens(text)
    report = experiment(TokenFailure(), groups=1)
    group = report['groups'][0]
    assert group['status'] == 'incomplete_token_accounting'
    assert group['token_accounting_status'] == 'incomplete'
    assert group['receiver_evaluation_status'] == 'completed'
    assert len(group['cases']) == 60 and len(report['calls']) == 63
    assert group['positive_evidence'] is False
    if fail_at == 'completion':
        assert all(c['completion_content_tokens'] is None for c in group['cases'])
        assert all(s['total_content_tokens_with_negotiation'] is None for s in group['summary'].values())


def test_missing_receiver_log_cannot_reuse_previous_peer_completion():
    class MissingLog(ScriptedClient):
        def ask(self, role, prompt, max_tokens=256):
            if role.startswith('fresh-receiver'):
                raise OSError('failed before call log')
            return super().ask(role, prompt, max_tokens)
    group = experiment(MissingLog(), groups=1)['groups'][0]
    assert all(c['completion_content_tokens'] is None for c in group['cases'])
    assert all('receiver call log unavailable' in c['token_accounting_errors']['completion_content_tokens']
               for c in group['cases'])


def test_cli_writes_failed_receiver_evidence_and_returns_nonzero(monkeypatch, tmp_path):
    from Zipilogue import dialogue_lab
    client = OfflineResponseClient({'choices': []})
    monkeypatch.setattr(dialogue_lab, 'Client', lambda *args, **kwargs: client)
    output = tmp_path / 'report.json'
    assert dialogue_lab.main(['--groups', '1', '--output', str(output)]) == 1
    report = json.loads(output.read_text())
    assert len(report['calls']) == 63
    assert len(report['groups'][0]['cases']) == 60
    assert report['groups'][0]['summary']['raw']['completion_content_tokens'] is None
