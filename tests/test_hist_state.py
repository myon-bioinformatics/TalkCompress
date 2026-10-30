from __future__ import annotations

from shared.hist_state import build_state, summarize_old
from shared.keep_check import check


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
