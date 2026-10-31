"""pack_tokens: 結合文字(NFD のアクセント・ベトナム語の声調)で単語が分割されないこと。

出力は NFC (#65)。NFD 入力は NFC 等価な出力になり、語は結合文字の位置で分割されない。
"""
import unicodedata

import pytest

from MorphoZip.morpho_zip import pack_tokens


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


@pytest.mark.parametrize("word", ["Tiếng Việt", "Hà Nội", "naïve", "café", "İstanbul"])
def test_nfd_word_not_split(word):
    s = unicodedata.normalize("NFD", f"The {word} team, ready.")
    out = pack_tokens(s)
    assert out == _nfc(s)
    assert out == pack_tokens(_nfc(s))
    for w in _nfc(word).split():
        assert f" {w}" in f" {out} ".replace(",", " ")


def test_mark_after_nonfoldable_base():
    # x + U+0301 は NFC でも合成されない: 結合文字は語に残り、分割されない
    assert pack_tokens("x\u0301y z") == "x\u0301y z"


def test_mark_word_before_bracket():
    out = pack_tokens("cafe\u0301 (ok)")
    assert out == "caf\u00e9 (ok)"
    assert out.split()[0] == "caf\u00e9"


def test_noncomposable_mark_word_before_bracket():
    # NFC 後も結合文字が残る語でも、括弧の前の空白は保たれる
    assert pack_tokens("x\u0301 (ok)") == "x\u0301 (ok)"
