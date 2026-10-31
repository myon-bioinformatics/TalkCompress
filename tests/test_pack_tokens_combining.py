"""pack_tokens: 結合文字(NFD のアクセント・ベトナム語の声調)で単語が分割されないこと。"""
import unicodedata

import pytest

from MorphoZip.morpho_zip import pack_tokens


@pytest.mark.parametrize("word", ["Tiếng Việt", "Hà Nội", "naïve", "café", "İstanbul"])
def test_nfd_word_not_split(word):
    s = unicodedata.normalize("NFD", f"The {word} team, ready.")
    # #85 defines NFC output; verify exact spelling/spacing, not raw NFD bytes.
    assert pack_tokens(s) == unicodedata.normalize("NFC", s)


def test_mark_after_nonfoldable_base():
    # x + U+0301 は NFC でも合成されない
    assert pack_tokens("x\u0301y z") == "x\u0301y z"


@pytest.mark.parametrize("text, expected", [
    ("cafe\u0301 (ok)", "café (ok)"),
    ("x\u0301y (ok)", "x\u0301y (ok)"),  # remains decomposed after NFC
    ("x\u0301 (ok)", "x\u0301 (ok)"),  # terminal mark immediately before bracket
])
def test_mark_word_before_bracket(text, expected):
    assert pack_tokens(text) == expected
