"""pack_tokens: 結合文字(NFD のアクセント・ベトナム語の声調)で単語が分割されないこと。"""
import unicodedata

import pytest

from MorphoZip.morpho_zip import pack_tokens


@pytest.mark.parametrize("word", ["Tiếng Việt", "Hà Nội", "naïve", "café", "İstanbul"])
def test_nfd_word_not_split(word):
    s = unicodedata.normalize("NFD", f"The {word} team, ready.")
    assert pack_tokens(s) == s


def test_mark_after_nonfoldable_base():
    # x + U+0301 は NFC でも合成されない
    assert pack_tokens("x\u0301y z") == "x\u0301y z"


def test_mark_word_before_bracket():
    assert pack_tokens("cafe\u0301 (ok)") == "cafe\u0301 (ok)"
