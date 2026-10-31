"""Zipilogue RuleBook: 置換はリテラル、ASCII 文字の大小無視は ASCII のみ。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Zipilogue"))

from rulebook import RuleBook  # noqa: E402


@pytest.mark.parametrize("short", [r"C:\new\1x", r"\g<0>!", r"a\tb", "\\"])
def test_encode_decode_literal(short: str) -> None:
    book = RuleBook()
    book.declare("my path here", short)
    enc = book.encode_with_rules("see my path here now")
    assert enc == f"see {short} now"
    assert book.decode_with_rules(enc) == "see my path here now"


@pytest.mark.parametrize(
    "text",
    ["the opınıon panel", "the OPİNİON panel", "the ſkip list", "the \u212aind word"],
)
def test_unicode_fold_not_matched(text: str) -> None:
    book = RuleBook()
    for long in ("opinion panel", "skip list", "kind word"):
        book.declare(long)
    assert book.encode_with_rules(text) == text


def test_ascii_and_nonascii_case_still_fold() -> None:
    book = RuleBook()
    r1 = book.declare("opinion panel")
    r2 = book.declare("café crème")
    assert book.encode_with_rules("The OPINION Panel") == f"The {r1.short}"
    assert book.encode_with_rules("CAFÉ CRÈME ok") == f"{r2.short} ok"


def test_ascii_case_match_helper() -> None:
    from rulebook import _ascii_case_match

    assert _ascii_case_match("Kind", "kind")
    assert not _ascii_case_match("\u212aind", "kind")
    assert not _ascii_case_match("kind", "\u212aind")
    assert not _ascii_case_match("kin", "kind")


def test_decode_long_form_is_literal() -> None:
    book = RuleBook()
    rule = book.declare(r"dir C:\new\1x", "DP")
    assert book.decode_with_rules(f"open {rule.short} ok") == r"open dir C:\new\1x ok"
