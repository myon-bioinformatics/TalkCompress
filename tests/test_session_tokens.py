"""Mocked protocol tests, not measured model evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from Zipilogue.rulebook import RuleBook
from Zipilogue.session_tokens import LlamaTokenizer, comparison, main


class SessionTokenTests(unittest.TestCase):
    def response(self, payload):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        return response

    def test_protocol_unicode_cache_and_zero(self):
        with patch('urllib.request.urlopen', return_value=self.response({'tokens': [5, 9]})) as post:
            counter = LlamaTokenizer('http://localhost:8080/tokenize')
            self.assertEqual(counter('日本語<|im_start|>'), 2)
            self.assertEqual(counter('日本語<|im_start|>'), 2)
            post.assert_called_once()
            self.assertEqual(json.loads(post.call_args.args[0].data), {
                'content': '日本語<|im_start|>', 'add_special': False,
                'parse_special': False, 'with_pieces': False})
        with patch('urllib.request.urlopen', return_value=self.response({'tokens': []})):
            self.assertEqual(counter(''), 0)

    def test_invalid_and_failed_requests_never_become_zero(self):
        for payload in ({}, {'tokens': 'x'}, {'tokens': [True]}, {'tokens': [-1]}, {'tokens': [1.5]}):
            with patch('urllib.request.urlopen', return_value=self.response(payload)):
                with self.assertRaises(ValueError):
                    LlamaTokenizer('http://localhost/tokenize')('x')
        with patch('urllib.request.urlopen', return_value=self.response({'tokens': [1]})):
            with self.assertRaises(ValueError):
                LlamaTokenizer('http://localhost/tokenize')('')
        with patch('urllib.request.urlopen', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                LlamaTokenizer('http://localhost/tokenize')('x')

    def test_accounting_uses_counter_for_setup_messages_retries(self):
        book = RuleBook(auto_adopt=False)
        phrase = 'please run the regression tests before merging'
        book.declare(phrase, 'r1')
        # Deliberately synthetic word counts; not tokenizer measurements.
        count = lambda text: len(text.split())
        results = comparison(book, [phrase] * 32, count)
        costs = results['tokens']
        wire = json.dumps(book.export_rules(), ensure_ascii=False, separators=(',', ':'))
        self.assertEqual(costs['repeated']['setup'], count(wire))
        self.assertEqual(costs['repeated']['original_total'], 7 * 32)
        self.assertEqual(costs['repeated']['encoded_total'], 32)
        self.assertEqual(costs['full_resend']['recovery_total'], 7 * 32)
        self.assertLess(costs['full_resend']['net_saved'], 0)
        self.assertTrue(costs['repeated']['exact_roundtrip'])
        cumulative = costs['repeated']['setup']
        expected = None
        for i in range(1, 33):
            cumulative += 1
            if expected is None and cumulative < i * 7:
                expected = i
        self.assertEqual(costs['repeated']['first_saving_turn'], expected)
        collision = comparison(book, ['r1'] * 32, count)
        self.assertFalse(collision['tokens']['repeated']['exact_roundtrip'])
        self.assertFalse(collision['tokens']['repeated']['beneficial'])

    def test_failure_evidence_and_exit_status(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            with patch('Zipilogue.session_tokens.prepare', side_effect=OSError('offline')):
                status = main(['--model-path', 'missing.gguf', '--runtime-id', 'test-only',
                               '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(status, 1)
            self.assertEqual(report['status'], 'unmeasured')
            self.assertIsNone(report['costs'])
            self.assertIsNone(report['task_success']['success_rate'])
            self.assertEqual(report['tokenizations'], [])

    def test_tokenizer_failure_preserves_unmeasured_status(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            with patch('Zipilogue.session_tokens.prepare', return_value={'sha256_verified': True}), \
                 patch('urllib.request.urlopen', side_effect=TimeoutError('server down')):
                status = main(['--model-path', 'test.gguf', '--runtime-id', 'test-only',
                               '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(status, 1)
            self.assertEqual(report['status'], 'unmeasured')
            self.assertIsNone(report['costs'])
            self.assertIn('TimeoutError', report['error'])

    def test_successful_cli_keeps_quality_unmeasured(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.json'
            # HTTP responses here are synthetic, for CLI contract testing only.
            def reply(req, **kwargs):
                text = json.loads(req.data)['content']
                return self.response({'tokens': [7] * len(text.split())})
            with patch('Zipilogue.session_tokens.prepare', return_value={'sha256_verified': True}), \
                 patch('urllib.request.urlopen', side_effect=reply):
                status = main(['--model-path', 'test.gguf', '--runtime-id', 'test-only',
                               '--output', str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(status, 0)
            self.assertEqual(report['status'], 'measured')
            self.assertEqual(report['semantic_understanding']['status'], 'unmeasured')
            self.assertIsNone(report['task_success']['success_rate'])
            self.assertTrue(report['costs']['tokens']['repeated']['exact_roundtrip'])
