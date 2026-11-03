"""古いハングル字母と異体字セレクタ(IVS)は o200k で結合されないので UTF-8 バイト数で数える。"""
import pytest

from TesseraTalk import tessera_talk as T
from TesseraTalk.tessera_talk import estimate_tokens


@pytest.mark.parametrize("text, expected", [
    ("\u1112\u119e\u11ab", 9),          # 回帰: main は 1(x 群で ceil(len/4))、o200k 9
    ("\ua960\ud7b0", 6),                 # 拡張 A / B(o200k 5)
    ("葛\U000E0100城", 7),               # IVS 1 つ = 4 バイト(o200k 6、main 4)
])
def test_jamo_ivs_bytes(text, expected):
    assert estimate_tokens(text) == expected


def test_modern_hangul_unchanged():
    assert estimate_tokens("한국어") == 2
    assert estimate_tokens("가") == 1
    # NFD の字母 "\u1100\u1161" の値は NFD ハングル補正(別 PR)で決まるのでここでは見ない


def test_jamo_group():
    assert [m.lastgroup for m in T._PRETOKEN.finditer("\u1112\u119e\u11ab")] == ["j"]
