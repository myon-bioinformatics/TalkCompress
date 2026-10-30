import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from shared.hist_state import main

class CheckedOutputTests(unittest.TestCase):
    def invoke(self, rows, keep, checked=True):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'chat.jsonl'
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            out, err = io.StringIO(), io.StringIO()
            args = ['--file', str(path), '--keep-recent', str(keep)]
            if checked:
                args.append('--check')
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = main(args)
            return status, out.getvalue(), err.getvalue()

    def test_secret_failure_emits_no_chat_or_secret_diagnostic(self):
        status, out, err = self.invoke([{'role': 'user', 'text': 'Do not disclose token=FAKE_CANARY_ONLY'}], 0)
        self.assertEqual(status, 1)
        self.assertEqual(out, '')
        self.assertNotIn('FAKE_CANARY_ONLY', err)
        self.assertFalse(json.loads(err)['ok'])

    def test_noop_boundaries_preserve_rows(self):
        rows = [{'role': 'system', 'text': 'system'}, *[{'role': 'user', 'text': text} for text in ['keep #40', 'second', 'third']]]
        for keep in (3, 4, 5, 50):
            with self.subTest(keep=keep):
                status, out, err = self.invoke(rows, keep)
                self.assertEqual(status, 0)
                self.assertEqual([json.loads(line) for line in out.splitlines()], rows)
                self.assertTrue(json.loads(err)['ok'])

    def test_empty_checked_input(self):
        status, out, err = self.invoke([], 0)
        self.assertEqual((status, out), (0, ''))
        self.assertTrue(json.loads(err)['ok'])

    def test_success_checked_output_matches_unchecked(self):
        rows = [{'role': 'user', 'text': 'We decided to keep #40.'}, {'role': 'assistant', 'text': 'recent'}]
        for keep in (0, 1):
            with self.subTest(keep=keep):
                status, out, err = self.invoke(rows, keep)
                plain_status, plain_out, plain_err = self.invoke(rows, keep, False)
                self.assertEqual((status, out), (plain_status, plain_out))
                self.assertEqual(status, 0)
                self.assertEqual(plain_err, '')
                self.assertTrue(json.loads(err)['ok'])

if __name__ == '__main__':
    unittest.main()
