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
    # ブラーフミー系は記号込みの語全体で ceil(len/3)、ミャンマー・クメールは ceil(2*len/3)。
    # main は母音記号ごとに記号扱いで分割し、実コーパスで 1.6〜2 倍の過大評価だった。
    ("வணக்கம் உலகம்", 5),      # Tamil (o200k 5, main 6)
    ("নমস্কার পৃথিবী", 5),      # Bengali (o200k 6, main 10)
    ("નમસ્તે દુનિયા", 6),       # Gujarati (o200k 6, main 10; block rate 2.5)
    ("မင်္ဂလာပါ ကမ္ဘာ", 9),    # Myanmar (o200k 9, main 11; rate 1.75)
    # ZWSP が直前の母音記号と同じ記号連にまとまらなくなったため main の 10 から +1
    ("សួស្តី​ពិភពលោក", 10),       # Khmer (o200k 10, main 10)
    # 子音だけの語は main では 0 だった(o200k 8)
    ("\u1780" * 8, 6),
])
def test_indic_word_costs(text, expected):
    assert estimate_tokens(text) == expected


def test_pointed_hebrew_closer_than_main():
    # ニクード付きヘブライ語: o200k 13、main 15、点ごとに分割して 11
    assert estimate_tokens("שָׁלוֹם עוֹלָם") == 11


@pytest.mark.parametrize("text", ["কর", "তম", "ကက", "\u1780\u1781", "ජන"])
def test_brahmic_consonant_only_word_not_free(text):
    # 母音記号を持たない語(子音だけ)も 0 トークンにしない
    assert estimate_tokens(text) >= 1
    assert estimate_tokens(text + " " + text) >= 2


@pytest.mark.parametrize("text, expected", [
    # Lao / Tibetan は i クラス外で子音が 0 トークンだった(o200k と一致)
    ("\u0f40", 2),              # ཀ  (o200k 2)
    ("\u0e81", 2),              # ກ  (o200k 2)
    ("\u0f40\u0f0b\u0f41", 4),  # ཀ་ཁ (o200k 4)
])
def test_lao_tibetan_not_free(text, expected):
    assert estimate_tokens(text) == expected


@pytest.mark.parametrize("text, expected", [
    # ブロック別レート(_BRAHMIC_RATES)の回帰。Tatoeba held-out (seed 1104) から抽出
    ("ຂ້ອຍຄິດວ່າ ຂ້ອຍເສັຍຂໍກະແຈ", 48),                 # Lao (o200k 48)
    ("སྔ་དྲོ་བདེ་ལེགས", 20),                          # Tibetan (o200k 22)
    ("ਟੌਮ ਨੇ ਮੈਰੀ ਨੂੰ ਦੱਸਿਅਾ ਕਿ ਓਹ ਗ਼ਲਤ ਸੀ।", 23),       # Gurmukhi (o200k 23)
    ("ඔයා ඇහැරිනකොට මං මෙහෙන් ගිහින්.", 19),          # Sinhala (o200k 19)
    ("నువ్వు ఎప్పుడైనా పారిస్ వెళ్ళావా?", 15),          # Telugu (o200k 15)
    ("ಅವನು ಠಾಣೆಗೆ ಐದು ಗಂಟೆಗೆ ತಲುಪಿದ.", 14),            # Kannada (o200k 14)
    ("હું પનિર ખાવ છું", 8),                          # Gujarati (o200k 8)
    ("သူမက အလုပ်ခန့်အပ်တာကို ငြင်းဆန်လိုက်တယ်။", 23),  # Myanmar (o200k 23)
    ("ខ្ញុំគ្រាន់តែគិតថាអ្នកចង់ទៅនោះទេ។", 22),          # Khmer (o200k 22)
])
def test_brahmic_block_rates(text, expected):
    assert estimate_tokens(text) == expected
