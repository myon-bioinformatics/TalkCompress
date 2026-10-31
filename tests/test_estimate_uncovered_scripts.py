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


@pytest.mark.parametrize("text, expected", [
    # インド系・東南アジア系文字は main と同じ経路(母音記号を記号扱い)。
    # 未分類文字用の ceil(len/4) で母音記号の位置で分割すると o200k から遠ざかるため。
    ("வணக்கம் உலகம்", 6),      # Tamil (o200k 5)
    ("নমস্কার পৃথিবী", 10),     # Bengali (o200k 6)
    ("નમસ્તે દુનિયા", 10),      # Gujarati (o200k 6)
    ("မင်္ဂလာပါ ကမ္ဘာ", 11),    # Myanmar (o200k 9)
    ("សួស្តី​ពិភពលោក", 10),       # Khmer (o200k 10)
    ("\u1780" * 8, 0),           # Khmer ブロック先頭 U+1780(main と同じ。既知の過小評価)
])
def test_indic_unchanged_from_main(text, expected):
    assert estimate_tokens(text) == expected


def test_pointed_hebrew_closer_than_main():
    # ニクード付きヘブライ語: o200k 13、main 9、本修正 15
    assert estimate_tokens("שָׁלוֹם עוֹלָם") == 15
