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


def _fold_alt(phrase: str) -> str:
    """Escape *phrase*; ASCII phrases get ASCII-only IGNORECASE.

    Unicode re.I folds Turkish İ/ı, long s ſ and the Kelvin sign K onto
    i/s/k, so ``kiss`` would match ``KİSS`` / ``kıss`` (and the casefold
    lookup then misses).  Non-ASCII phrases keep Unicode case folding.
    """
    esc = re.escape(phrase)
    return f'(?a:{esc})' if phrase.isascii() else esc


def _code_pattern(code: str) -> str:
    """Word-bounded (Unicode \\w edges) ASCII-only case-insensitive code match."""
    return r'(?<!\w)' + _fold_alt(code) + r'(?!\w)'


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
        if re.search(_code_pattern(short), observed, re.I):
            raise ValueError('code collides with observed vocabulary')
        longs.add(long.casefold()); shorts.add(short.casefold())
        result.append({'long': long, 'short': short})
    for rule in result:
        if any(re.search(_code_pattern(code), rule['long'], re.I) for code in shorts):
            raise ValueError('code appears inside a long form')
    return result


def encode(text: str, mapping: list[dict[str, str]]) -> str:
    """One-pass longest replacement, never re-encode newly inserted codes.

    The result is always NFC-normalized, even when ``mapping`` is empty or no
    rule matches, so NFD input never leaks out undecomposed.
    """
    # NFD の入力で「cafe」が「café」の基底文字だけに当たらないよう NFC に揃える。
    text = unicodedata.normalize('NFC', text)
    if not mapping:
        return text
    lookup = {unicodedata.normalize('NFC', r['long']).casefold(): r['short'] for r in mapping}
    pattern = r'(?<!\w)(?:' + '|'.join(_fold_alt(x) for x in sorted(lookup, key=len, reverse=True)) + r')(?!\w)'
    # İ/ı/ſ/K never fold onto an ASCII long form (see _fold_alt); the .get
    # fallback keeps any other re.I-vs-casefold mismatch from raising KeyError.
    return re.sub(pattern, lambda m: lookup.get(m.group().casefold(), m.group()), text, flags=re.I)


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


def phrase_candidates(training: list[dict]) -> list[str]:
    """Training-only repeated word spans; no held-out values or automatic adoption."""
    counts: dict[str, int] = {}
    for case in training:
        words = case['text'].split()
        seen = set()
        for start in range(len(words)):
            for size in range(1, 6):
                phrase = ' '.join(words[start:start + size]).strip('.,;')
                if 4 <= len(phrase) <= 100 and phrase.casefold() in case['text'].casefold():
                    seen.add(phrase)
        for phrase in seen:
            counts[phrase] = counts.get(phrase, 0) + 1
    return sorted((p for p, n in counts.items() if n >= 2),
                  key=lambda p: (-counts[p], -len(p), p))[:40]


def validate_vote(vote: dict, mapping: list[dict]) -> list[dict]:
    """A malformed or vague veto never becomes approval. Rule indices are zero-based."""
    if type(vote.get('accept')) is not bool or not isinstance(vote.get('reason'), str) or not vote['reason'].strip():
        raise ValueError('vote needs boolean accept and nonempty reason')
    issues = vote.get('issues')
    if not isinstance(issues, list):
        raise ValueError('vote needs issues array')
    if vote['accept'] and issues:
        raise ValueError('approval must have no issues')
    if not vote['accept'] and not issues:
        raise ValueError('rejection must identify a rule and concrete reason')
    for issue in issues:
        if (not isinstance(issue, dict) or type(issue.get('rule_index')) is not int
                or not 0 <= issue['rule_index'] < len(mapping)
                or not isinstance(issue.get('category'), str)
                or issue.get('category') not in {'meaning', 'ambiguity', 'collision', 'decodability'}
                or not isinstance(issue.get('reason'), str) or not issue['reason'].strip()):
            raise ValueError('issue needs valid rule_index, category and concrete reason')
    return issues


def negotiate(client: Client, training: list[dict], peers: int, rounds: int, group_id: int = 0) -> dict:
    """The proposer sees training only; critics can veto the frozen mapping."""
    feedback = []
    transcripts = []
    candidates = phrase_candidates(training)
    for round_no in range(rounds):
        prompt = (f'Negotiation group {group_id}. You are the sender. Invent 1 to 8 short opaque codes for repeated phrases '
                  'in the training messages. Each long form must be 4..100 characters after whitespace normalization, '
                  'must occur in training, and must be longer than its short code. '
                  'Preserve exact meanings, including negation and conditions. '
                  'Codes must be 1..6 ASCII letters/digits, start with a letter, and not existing words. '
                  'Return {"mapping":[{"long":"observed phrase","short":"code"}]}. '
                  'Do not invent or change task values. You may select exact long forms from these training-only candidates; '
                  'you still choose the codes and peers may reject any proposal.\nCandidates:\n' +
                  json.dumps(candidates) + '\nTraining messages:\n' +
                  '\n'.join(x['text'] for x in training) + '\nPeer feedback:\n' + json.dumps(feedback))
        try:
            proposal = client.ask('sender-proposal', prompt, 512)
        except Exception as error:
            feedback = [{'stage': 'proposal_output', 'reason': str(error)}]
            transcripts.append({'round': round_no, 'failure_stage': 'proposal_output', 'error': repr(error)})
            continue
        try:
            mapping = validate_mapping(proposal, training)
        except ValueError as error:
            feedback = [{'stage': 'proposal_validation', 'proposal': proposal, 'reason': str(error)}]
            transcripts.append({'round': round_no, 'failure_stage': 'proposal_validation', 'proposal': proposal, 'validation_error': str(error)})
            continue
        feedback = []
        votes = []
        for peer in range(peers):
            focus = ['negation and condition meaning', 'code collisions, ambiguity and decodability',
                     'action and service identity', 'numeric counts and retry limits'][peer % 4]
            try:
                vote = client.ask(f'peer-{peer}-critique',
                f'Negotiation group {group_id}, receiver peer {peer}. Audit focus: {focus}. '
                'You are an independent receiver negotiating a shared codebook. '
                'Check whether the proposed codes preserve exact phrase meaning and avoid ambiguity. '
                'Codes are opaque labels: their spelling need not resemble the phrase. '
                'Decode by exact lookup in the shared book, preserving surrounding words. '
                'Return {"accept":true or false,"reason":"overall explanation","issues":[]}. '
                'For rejection, issues must be nonempty, each with zero-based rule_index, '
                'category (meaning, ambiguity, collision, decodability), and reason describing '
                'the specific misreading or collision for that rule. Approval requires issues=[]. '
                'Approve only if you can decode every code using this proposal.\nProposal:\n' +
                json.dumps(mapping) + '\nTraining messages:\n' + '\n'.join(x['text'] for x in training), 384)
            except Exception as error:
                votes.append({'peer': peer, 'accepted': False, 'failure_stage': 'peer_output', 'error': repr(error)})
                feedback.append({'stage': 'peer_output', 'peer': peer, 'mapping': mapping, 'reason': str(error)})
                continue
            try:
                issues = validate_vote(vote, mapping)
                accepted = vote['accept']
                stage = None if accepted else 'peer_semantic_rejection'
            except ValueError as error:
                accepted, issues, stage = False, [], 'peer_vote_contract'
                feedback.append({'stage': stage, 'peer': peer, 'mapping': mapping,
                                 'vote': vote, 'reason': str(error)})
            votes.append({'peer': peer, 'accepted': accepted, 'vote': vote, 'failure_stage': stage})
            if stage == 'peer_semantic_rejection':
                feedback.append({'stage': stage, 'peer': peer, 'mapping': mapping, 'issues': issues})
        transcripts.append({'round': round_no, 'mapping': mapping, 'votes': votes})
        if all(x['accepted'] for x in votes):
            return {'agreed': True, 'mapping': mapping, 'transcripts': transcripts}
    return {'agreed': False, 'mapping': [], 'transcripts': transcripts,
            'failure_counts': failure_counts(transcripts)}


def failure_counts(transcripts: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for turn in transcripts:
        for item in [turn, *turn.get('votes', [])]:
            stage = item.get('failure_stage')
            if stage:
                counts[stage] = counts.get(stage, 0) + 1
    return counts


def negotiation_cost(client: Client, start: int, end: int) -> dict:
    calls = client.calls[start:end]
    return {'negotiation_calls': len(calls), 'negotiation_content_tokens': sum(
        client.tokens(m['content']) for call in calls for m in call['request']['messages']) + sum(
        client.tokens(completion_content(call))
        for call in calls)}


def completion_content(call: dict) -> str:
    """Missing/malformed response content is unknown cost, not an empty answer."""
    response = call.get('response')
    choices = response.get('choices') if isinstance(response, dict) else None
    choice = choices[0] if isinstance(choices, list) and choices else None
    message = choice.get('message') if isinstance(choice, dict) else None
    content = message.get('content') if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ValueError('completion content unavailable for token accounting')
    return content


def account_tokens(client: Client, record: dict, key: str, *texts: str) -> None:
    """Keep evaluation evidence even if the independent tokenizer is unavailable."""
    try:
        record[key] = sum(client.tokens(text) for text in texts)
    except Exception as error:
        record[key] = None
        record.setdefault('token_accounting_errors', {})[key] = repr(error)


def known_sum(values) -> int | None:
    values = list(values)
    return None if any(value is None for value in values) else sum(values)


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
        entry['receiver_evaluation_status'] = 'not_run_no_agreement'
        try:
            entry.update(negotiation_cost(client, call_start, len(client.calls)))
        except Exception as error:
            entry.update(negotiation_calls=len(client.calls) - call_start,
                         negotiation_content_tokens=None, token_accounting_error=repr(error))
        if not agreement['agreed']:
            entry['status'] = 'no_agreement'
            continue
        entry['status'] = 'completed'
        entry['receiver_evaluation_status'] = 'completed'
        account_tokens(client, entry, 'book_tokens', book)
        for case in heldout:
            compressed = encode(case['text'], agreement['mapping'])
            for arm, message, mapping in [('raw', case['text'], []),
                    ('shared', compressed, agreement['mapping']), ('unshared', compressed, [])]:
                prompt = receiver_prompt(message, mapping)
                result = {'id': case['id'], 'arm': arm, 'message': message,
                          'expected': case['expected']}
                account_tokens(client, result, 'message_tokens', message)
                account_tokens(client, result, 'prompt_tokens', INSTRUCTION, prompt)
                receiver_call_start = len(client.calls)
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
                try:
                    if len(client.calls) != receiver_call_start + 1:
                        raise ValueError('receiver call log unavailable for token accounting')
                    completion = completion_content(client.calls[-1])
                    account_tokens(client, result, 'completion_content_tokens', completion)
                except Exception as error:
                    result['completion_content_tokens'] = None
                    result.setdefault('token_accounting_errors', {})['completion_content_tokens'] = repr(error)
                entry['cases'].append(result)
        entry['summary'] = {}
        for arm in ['raw', 'shared', 'unshared']:
            values = [x for x in entry['cases'] if x['arm'] == arm]
            entry['summary'][arm] = {'successes': sum(x['success'] for x in values), 'total': len(values),
                'invalid_or_error': sum(not x['valid'] for x in values),
                'message_tokens': known_sum(x['message_tokens'] for x in values),
                'prompt_content_tokens': known_sum(x['prompt_tokens'] for x in values),
                'completion_content_tokens': known_sum(x['completion_content_tokens'] for x in values)}
            summary = entry['summary'][arm]
            summary['success_rate'] = summary['successes'] / summary['total']
            summary['total_content_tokens_with_negotiation'] = known_sum([
                summary['prompt_content_tokens'], summary['completion_content_tokens'], entry['negotiation_content_tokens']])
        raw, shared = entry['summary']['raw'], entry['summary']['shared']
        entry['wire_tokens_with_one_book'] = known_sum([shared['message_tokens'], entry['book_tokens']])
        entry['wire_tokens_with_book_and_negotiation'] = known_sum([
            entry['wire_tokens_with_one_book'], entry['negotiation_content_tokens']])
        entry['negotiation_and_dictionary_net_saving'] = (raw['message_tokens'] - entry['wire_tokens_with_book_and_negotiation']
            if entry['wire_tokens_with_book_and_negotiation'] is not None and raw['message_tokens'] is not None else None)
        entry['token_accounting_status'] = ('incomplete' if entry.get('token_accounting_error')
            or entry.get('token_accounting_errors')
            or any(case.get('token_accounting_errors') for case in entry['cases']) else 'completed')
        if entry['token_accounting_status'] == 'incomplete':
            entry['status'] = 'incomplete_token_accounting'
        entry['positive_evidence'] = (shared['successes'] == shared['total'] and raw['successes'] == raw['total']
            and entry['token_accounting_status'] == 'completed'
            and entry['negotiation_and_dictionary_net_saving'] is not None
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
