"""NFD(字母分解)のハングルは o200k で字母 1 つ = 3 バイト = 3 トークン(o200k_base 実測)。"""
import unicodedata

import pytest

from TesseraTalk.tessera_talk import estimate_tokens


@pytest.mark.parametrize("text, expected", [
    ("한국어", 24),            # 回帰: main は 2、o200k 24
    ("안녕하세요 세계", 48),   # o200k 49
    ("x 한국어 y", 26),        # o200k 27
])
def test_nfd_hangul(text, expected):
    assert estimate_tokens(unicodedata.normalize("NFD", text)) == expected


def test_nfd_jamo_pair():
    assert estimate_tokens("\u1100\u1161") == 6  # NFD の 가、o200k 6


def test_nfc_hangul_unchanged():
    assert estimate_tokens("한국어") == 2


def test_vietnamese_nfd_unchanged():
    assert estimate_tokens(unicodedata.normalize("NFD", "Tiếng Việt")) == 9  # o200k 8
