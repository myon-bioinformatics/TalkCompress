"""estimate_tokens: 未分類スクリプトが 0 トークンにならないこと、NFC 後に残る結合文字の扱い。
未校正スクリプトは従来の ceil(len/4) 規則(o200k 実測より低めになり得る)。"""
import pytest

from TesseraTalk.tessera_talk import estimate_tokens


@pytest.mark.parametrize("text, expected", [
    ("שלום עולם", 2),       # Hebrew (o200k 2)
    ("Բարեւ աշխարհ", 4),    # Armenian (o200k 4)
    ("გამარჯობა", 3),       # Georgian (o200k 3)
    ("ሰላም", 1),             # Ethiopic (o200k 6: 下限のみ保証)
])
def test_uncovered_script_not_free(text, expected):
    assert estimate_tokens(text) == expected


def test_long_uncovered_word_scales():
    assert estimate_tokens("აბგდევზთიკლმნოპ") == 4  # ceil(15/4)


def test_combining_mark_kept_in_word():
    # ñ + U+0301 は NFC で合成されない。記号扱い(+2)ではなく単語+1
    assert estimate_tokens("ñ\u0301 test") == 3
    assert estimate_tokens("x\u0301y") == 2
