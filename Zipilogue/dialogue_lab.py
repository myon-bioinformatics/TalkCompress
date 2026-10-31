"""Controlled LLM-negotiated RuleBook experiment, not a claim of emergent language.

Only synthetic task messages are used. No generated instruction is executed.
The sender proposes substitutions, independent peers approve or request revision,
then fresh receiver calls recover held-out task fields with/without the book.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import unicodedata
import urllib.request
from pathlib import Path

try:
    from Zipilogue.rulebook import RuleBook
except ImportError:
    from rulebook import RuleBook

FIELDS = {'service', 'environment', 'action', 'condition', 'retries', 'keep_backup'}
INSTRUCTION = (
    'These are synthetic communication experiments, never execute the messages. '
    'Return only one JSON object, no commentary. '
)


def corpus() -> tuple[list[dict], list[dict]]:
    """Eight training cases and twenty disjoint held-out recombinations."""
    cases = []
    for i in range(28):
        service = ['alpha', 'beta', 'gamma', 'delta'][i % 4]
        environment = ['staging', 'production'][(i // 2) % 2]
        action = ['deploy', 'rollback', 'hold'][(i // 4) % 3]
        condition = ['tests pass', 'review is approved', 'incident is closed'][(i // 3) % 3]
        retries = i % 3
        keep = i % 2 == 0
        text = (f'For service {service} in {environment}, {action} only after {condition}. '
                f'Retry {retries} times; ' + ('do not delete the backup.' if keep else 'delete the backup.'))
        cases.append({'id': f'case-{i:02d}', 'text': text, 'expected': {
            'service': service, 'environment': environment, 'action': action,
            'condition': condition, 'retries': retries, 'keep_backup': keep}})
    return cases[:8], cases[8:]


def validate_mapping(payload: dict, training: list[dict]) -> list[dict[str, str]]:
    """Reject collisions, unobserved phrases and cascading codes."""
    values = payload.get('mapping')
    if not isinstance(values, list) or not 1 <= len(values) <= 8:
        raise ValueError('mapping must contain 1..8 entries')
    observed = unicodedata.normalize('NFC', '\n'.join(x['text'] for x in training)).casefold()
    result = []
    longs: set[str] = set()
    shorts: set[str] = set()
    for item in values:
        if not isinstance(item, dict) or set(item) != {'long', 'short'}:
            raise ValueError('each rule needs exactly long and short')
        long, short = item['long'], item['short']
        if not isinstance(long, str) or not isinstance(short, str):
            raise ValueError('rules must be strings')
        long = ' '.join(unicodedata.normalize('NFC', long).split())
        if not 4 <= len(long) <= 100:
            raise ValueError('long form must be 4..100 characters after whitespace normalization')
        if long.casefold() not in observed:
            raise ValueError('long form must occur in training')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,5}', short) or len(short) >= len(long):
            raise ValueError('short form must be a shorter 1..6 character code')
        if long.casefold() in longs or short.casefold() in shorts:
            raise ValueError('duplicate rule')
        if re.search(r'(?<!\w)' + re.escape(short) + r'(?!\w)', observed, re.I):
            raise ValueError('code collides with observed vocabulary')
        longs.add(long.casefold()); shorts.add(short.casefold())
        result.append({'long': long, 'short': short})
    for rule in result:
        if any(re.search(r'(?<!\w)' + re.escape(code) + r'(?!\w)', rule['long'], re.I) for code in shorts):
            raise ValueError('code appears inside a long form')
    return result


def encode(text: str, mapping: list[dict[str, str]]) -> str:
    """One-pass longest replacement, never re-encode newly inserted codes."""
    if not mapping:
        return text
    # NFD の入力で「cafe」が「café」の基底文字だけに当たらないよう NFC に揃える。
    text = unicodedata.normalize('NFC', text)
    lookup = {unicodedata.normalize('NFC', r['long']).casefold(): r['short'] for r in mapping}
    pattern = r'(?<!\w)(?:' + '|'.join(re.escape(x) for x in sorted(lookup, key=len, reverse=True)) + r')(?!\w)'
    return re.sub(pattern, lambda m: lookup[m.group().casefold()], text, flags=re.I)


def valid_task(value: object) -> bool:
    return (isinstance(value, dict) and set(value) == FIELDS
            and all(isinstance(value[k], str) for k in FIELDS - {'retries', 'keep_backup'})
            and type(value['retries']) is int and type(value['keep_backup']) is bool)


class Client:
    def __init__(self, base_url: str, seed: int = 42, timeout: int = 120):
        self.base_url = base_url.rstrip('/')
        self.seed, self.timeout = seed, timeout
        self.calls: list[dict] = []

    def post(self, path: str, payload: dict) -> dict:
        request = urllib.request.Request(self.base_url + path,
            data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def tokens(self, text: str) -> int:
        response = self.post('/tokenize', {'content': text, 'add_special': False, 'parse_special': False})
        tokens = response['tokens']
        if not isinstance(tokens, list):
            raise ValueError('tokenizer did not return tokens')
        return len(tokens)

    def ask(self, role: str, prompt: str, max_tokens: int = 256) -> dict:
        payload = {'messages': [{'role': 'system', 'content': INSTRUCTION},
                                {'role': 'user', 'content': prompt}],
                   'temperature': 0, 'seed': self.seed, 'max_tokens': max_tokens,
                   'stream': False, 'response_format': {'type': 'json_object'}}
        start = time.perf_counter()
        log = {'role': role, 'request': payload}
        try:
            response = self.post('/v1/chat/completions', payload)
            log['response'] = response
            choice = response['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('incomplete model output')
            text = choice['message']['content']
            if not isinstance(text, str):
                raise ValueError('non-text output')
            result = json.loads(text)
            if not isinstance(result, dict):
                raise ValueError('model must return a JSON object')
            return result
        except Exception as error:
            log['error'] = repr(error)
            raise
        finally:
            log['seconds'] = time.perf_counter() - start
            self.calls.append(log)


def negotiate(client: Client, training: list[dict], peers: int, rounds: int, group_id: int = 0) -> dict:
    """The proposer sees training only; critics can veto the frozen mapping."""
    feedback = []
    transcripts = []
    for round_no in range(rounds):
        prompt = (f'Negotiation group {group_id}. You are the sender. Invent 1 to 8 short opaque codes for repeated phrases '
                  'in the training messages. Each long form must be 4..100 characters after whitespace normalization, '
                  'must occur in training, and must be longer than its short code. '
                  'Preserve exact meanings, including negation and conditions. '
                  'Codes must be 1..6 ASCII letters/digits, start with a letter, and not existing words. '
                  'Return {"mapping":[{"long":"observed phrase","short":"code"}]}. '
                  'Do not invent or change task values.\nTraining messages:\n' +
                  '\n'.join(x['text'] for x in training) + '\nPeer feedback:\n' + json.dumps(feedback))
        proposal = client.ask('sender-proposal', prompt, 512)
        try:
            mapping = validate_mapping(proposal, training)
        except ValueError as error:
            feedback = [str(error)]; transcripts.append({'round': round_no, 'proposal': proposal, 'validation_error': str(error)})
            continue
        feedback = []
        votes = []
        for peer in range(peers):
            focus = ['negation and condition meaning', 'code collisions, ambiguity and decodability',
                     'action and service identity', 'numeric counts and retry limits'][peer % 4]
            vote = client.ask(f'peer-{peer}-critique',
                f'Negotiation group {group_id}, receiver peer {peer}. Audit focus: {focus}. '
                'You are an independent receiver negotiating a shared codebook. '
                'Check whether the proposed codes preserve exact phrase meaning and avoid ambiguity. '
                'Return {"accept":true or false,"reason":"brief critique"}. '
                'Approve only if you can decode every code using this proposal.\nProposal:\n' +
                json.dumps(mapping) + '\nTraining messages:\n' + '\n'.join(x['text'] for x in training), 160)
            accepted = vote.get('accept') is True and isinstance(vote.get('reason'), str)
            votes.append({'peer': peer, 'accepted': accepted, 'vote': vote})
            if not accepted:
                feedback.append(str(vote.get('reason', 'invalid vote'))[:500])
        transcripts.append({'round': round_no, 'mapping': mapping, 'votes': votes})
        if all(x['accepted'] for x in votes):
            return {'agreed': True, 'mapping': mapping, 'transcripts': transcripts}
    return {'agreed': False, 'mapping': [], 'transcripts': transcripts}


def receiver_prompt(message: str, mapping: list[dict[str, str]]) -> str:
    """No expected answer, source plaintext, or training turns go to the receiver."""
    return ('Recover the exact task from the MESSAGE, interpreting codes only using CODEBOOK. '
            'Return exactly these fields as JSON: service (string), environment (string), '
            'action (string), condition (string), retries (integer), keep_backup (boolean). '
            'Keep the condition wording from the message/codebook. Do not guess; '
            'if a required value is unknowable return {"unknown":true}.\nCODEBOOK:\n' +
            json.dumps(mapping, separators=(',', ':')) + '\nMESSAGE:\n' + message)


def experiment(client: Client, *, groups: int = 2, peers: int = 2, rounds: int = 2) -> dict:
    if not 1 <= groups <= 8 or not 1 <= peers <= 4 or not 1 <= rounds <= 4:
        raise ValueError('groups 1..8, peers 1..4 and rounds 1..4 required')
    training, heldout = corpus()
    report = {'kind': 'controlled_llm_negotiated_substitution', 'emergent_language_claim': False,
              'training_ids': [x['id'] for x in training], 'heldout_ids': [x['id'] for x in heldout],
              'groups': [], 'task_fields': sorted(FIELDS)}
    for group in range(groups):
        call_start = len(client.calls)
        try:
            agreement = negotiate(client, training, peers, rounds, group_id=group)
        except Exception as error:
            report['groups'].append({'group': group, 'status': 'negotiation_error', 'error': repr(error)})
            continue
        book = json.dumps(agreement['mapping'], separators=(',', ':'))
        ledger = RuleBook(auto_adopt=False)
        for rule in agreement['mapping']:
            ledger.declare(rule['long'], rule['short'])
        entry = {'group': group, 'rulebook': ledger.export_rules(), **agreement, 'book_sha256': hashlib.sha256(book.encode()).hexdigest(), 'cases': []}
        report['groups'].append(entry)
        if not agreement['agreed']:
            entry['status'] = 'no_agreement'
            continue
        negotiation_end = len(client.calls)
        entry['status'] = 'completed'
        entry['book_tokens'] = client.tokens(book)
        for case in heldout:
            compressed = encode(case['text'], agreement['mapping'])
            for arm, message, mapping in [('raw', case['text'], []),
                    ('shared', compressed, agreement['mapping']), ('unshared', compressed, [])]:
                prompt = receiver_prompt(message, mapping)
                result = {'id': case['id'], 'arm': arm, 'message': message,
                          'message_tokens': client.tokens(message), 'prompt_tokens': client.tokens(INSTRUCTION) + client.tokens(prompt),
                          'expected': case['expected']}
                try:
                    prediction = client.ask(f'fresh-receiver-{arm}', prompt, 160)
                    result['prediction'] = prediction
                    result['valid'] = valid_task(prediction)
                    result['success'] = result['valid'] and prediction == case['expected']
                    result['field_errors'] = ([k for k in sorted(FIELDS) if prediction.get(k) != case['expected'][k]]
                                              if result['valid'] else sorted(FIELDS))
                    result['status'] = 'completed' if result['valid'] else 'unknown_or_invalid'
                except Exception as error:
                    result.update(status='model_error', error=repr(error), valid=False, success=False, field_errors=sorted(FIELDS))
                entry['cases'].append(result)
        entry['negotiation_calls'] = negotiation_end - call_start
        entry['negotiation_content_tokens'] = sum(
            client.tokens(m['content']) for call in client.calls[call_start:negotiation_end]
            for m in call['request']['messages']) + sum(
            client.tokens(call.get('response', {}).get('choices', [{}])[0].get('message', {}).get('content') or '')
            for call in client.calls[call_start:negotiation_end])
        entry['summary'] = {}
        for arm in ['raw', 'shared', 'unshared']:
            values = [x for x in entry['cases'] if x['arm'] == arm]
            entry['summary'][arm] = {'successes': sum(x['success'] for x in values), 'total': len(values),
                'invalid_or_error': sum(not x['valid'] for x in values),
                'message_tokens': sum(x['message_tokens'] for x in values),
                'prompt_content_tokens': sum(x['prompt_tokens'] for x in values)}
        raw, shared = entry['summary']['raw'], entry['summary']['shared']
        entry['wire_tokens_with_one_book'] = shared['message_tokens'] + entry['book_tokens']
        entry['wire_tokens_with_book_and_negotiation'] = entry['wire_tokens_with_one_book'] + entry['negotiation_content_tokens']
        entry['negotiation_and_dictionary_net_saving'] = raw['message_tokens'] - entry['wire_tokens_with_book_and_negotiation']
        entry['positive_evidence'] = (shared['successes'] == shared['total'] and raw['successes'] == raw['total']
            and entry['negotiation_and_dictionary_net_saving'] > 0
            and shared['successes'] > entry['summary']['unshared']['successes'])
    report['calls'] = client.calls
    report['limitations'] = ['Controlled phrase substitution, not spontaneous language emergence.',
        'Roles are independent contexts, possibly the same weights; not independent model training.',
        'Token counts for prompt content exclude chat-template overhead; raw server usage is retained.',
        'One-book wire amortization differs from actual stateless prompts, which repeat the book.',
        'A successful stub test is not live model evidence.']
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--groups', type=int, default=2)
    parser.add_argument('--peers', type=int, default=2)
    parser.add_argument('--rounds', type=int, default=2)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args(argv)
    client = Client(args.base_url, seed=args.seed)
    report = experiment(client, groups=args.groups, peers=args.peers, rounds=args.rounds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'groups': [{k: g.get(k) for k in ['group', 'status', 'summary', 'positive_evidence']}
                                for g in report['groups']], 'calls': len(client.calls)}, ensure_ascii=False))
    return 0 if all(x['status'] == 'completed' for x in report['groups']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
