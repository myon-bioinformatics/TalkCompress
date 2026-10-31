"""ShorthandEdge.compress: 短縮形はリテラル置換、改行は入力どおり保持する。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ShorthandEdge"))

from shorthand_edge import Session, compress  # noqa: E402


@pytest.mark.parametrize(
    "short",
    [r"C:\new\1x", r"\g<0>!", r"a\tb", "\\"],
)
def test_short_form_is_literal(short: str) -> None:
    sess = Session()
    sess.declare("my path", short)
    assert compress("see my path now", session=sess, ledger=False) == f"see {short} now"


@pytest.mark.parametrize(
    "text",
    ["hello\n", "a\r\nb", "a\u2028b", "x\n\ny\n", "a\rb\r\n", "ok\x0bthen\x85"],
)
def test_line_endings_preserved(text: str) -> None:
    assert compress(text, ledger=False) == text


def test_declaration_line_consumed_with_its_newline() -> None:
    out = compress("hereafter big thing = BT\r\nthe big thing\n", ledger=False)
    assert out == "the BT\n"


def test_single_declaration_and_empty() -> None:
    assert compress("hereafter a b = X", ledger=False) == ""
    assert compress("", ledger=False) == ""


def test_cli_does_not_double_trailing_newline() -> None:
    script = ROOT / "ShorthandEdge" / "shorthand_edge.py"
    r = subprocess.run(
        [sys.executable, str(script), "compress", "--no-ledger"],
        input="hello\n", capture_output=True, text=True, check=True,
    )
    assert r.stdout == "hello\n"
    r = subprocess.run(
        [sys.executable, str(script), "compress", "--no-ledger", "--text", "hello"],
        capture_output=True, text=True, check=True,
    )
    assert r.stdout == "hello\n"


def test_main_in_process_keeps_single_newline(monkeypatch, capsys) -> None:
    import io

    from shorthand_edge import main

    monkeypatch.setattr(sys, "stdin", io.StringIO("hello\n"))
    assert main(["compress", "--no-ledger"]) == 0
    assert capsys.readouterr().out == "hello\n"
    assert main(["compress", "--no-ledger", "--text", "hello"]) == 0
    assert capsys.readouterr().out == "hello\n"
