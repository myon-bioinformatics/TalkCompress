"""shared/hist_state.py: 状態ブロックの構築と CLI 回帰。

- hist_state
- hist_cli_regressions
"""

from __future__ import annotations

from pathlib import Path
from shared.hist_state import build_state
from shared.hist_state import main
from shared.hist_state import summarize_old
from shared.keep_check import check
import contextlib
import io
import json
import tempfile
import unittest


# ──── hist_state ──────────────────────────────────────────────────

ROWS = [
    {"role": "system", "text": "Never drop this system line."},
    {"role": "user", "text": "Which repo should hold the parser?"},
    {"role": "tool", "text": "grep output ...long..."},
    {"role": "assistant", "text": "We decided to use TalkCompress #40 for the parser."},
    {"role": "user", "text": "Please check https://example.com/spec v2 on 2026-10-30."},
    {"role": "assistant", "text": "Noted. Still pending: the SHA 3f9a2c1d review."},
    {"role": "user", "text": "Next: run keep-check on shared/keep_check.py."},
    {"role": "assistant", "text": "Running it now."},
]


def test_system_row_stays_first_and_recent_rows_stay_verbatim():
    new_rows, _, _ = summarize_old(ROWS, keep_recent=2)
    assert new_rows[0] == ROWS[0]
    assert new_rows[-2:] == ROWS[-2:]
    assert new_rows[1]["role"] == "system"
    assert new_rows[1]["text"].startswith("[state]")


def test_decision_and_open_rows_go_to_their_slots():
    state, _ = build_state(ROWS[1:6])
    decided_part = state.split("未決:")[0]
    open_part = state.split("未決:")[1].split("識別子・数値:")[0]
    assert "We decided to use TalkCompress #40" in decided_part
    assert "Which repo should hold the parser?" in open_part
    assert "Still pending" in open_part


def test_ids_are_kept_in_state():
    state, _ = build_state(ROWS[1:6])
    assert "https://example.com/spec" in state
    assert "2026-10-30" in state
    assert "3f9a2c1d" in state
    assert "#40" in state


def test_tool_rows_are_cleared_to_a_count():
    state, cleared = build_state(ROWS[1:6])
    assert cleared == 1
    assert "grep output" not in state
    assert "ツール結果: 1 件" in state


def test_next_step_is_last_old_user_row():
    state, _ = build_state(ROWS[1:6])
    assert "次の一手: Please check https://example.com/spec" in state


def test_nothing_to_summarize_returns_rows_unchanged():
    new_rows, state, cleared = summarize_old(ROWS, keep_recent=50)
    assert new_rows == ROWS
    assert state == "" and cleared == 0


def test_keep_check_passes_for_ids_between_old_text_and_state():
    old = "\n".join(r["text"] for r in ROWS[1:6] if r["role"] != "tool")
    state, _ = build_state(ROWS[1:6])
    report = check(old, state)
    kinds = {m["kind"] for m in report.missing}
    assert "url" not in kinds and "sha" not in kinds and "issue" not in kinds
    assert not report.secrets


def test_state_preserves_number_independent_of_issue_overlap():
    from shared.hist_state import build_state
    source = 'Budget 42; issue #142; https://example.com/a on 2026-10-30 commit abc1234'
    state, _ = build_state([{'role': 'assistant', 'text': source}])
    assert '42' in state.split('識別子・数値: ')[1].split('次の一手:')[0].splitlines()
    assert check(source, state).ok


# ──── hist_cli_regressions ────────────────────────────────────────

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
