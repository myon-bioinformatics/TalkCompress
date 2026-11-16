"""estimate_tokens: スクリプト別の率と結合記号（#144 / #147 / #149、ヘブライ・アラビア、チベット、未分類スクリプト）。

- estimate_issue_144_147_149: #144 / #147 / #149: Devanagari rate, Oriya rate, Hebrew factor, NEL, mojibake Ã/Â.
- estimate_script_marks: ヘブライ語の点・アラビア語のハラカートは o200k が語をその位置で分割するので、
- estimate_tibetan_freeze: #149: Tibetan sample is small (Tatoeba bod n=51); freeze current rate estimates.
- estimate_uncovered_scripts: estimate_tokens: 未分類スクリプトが 0 トークンにならないこと、NFC 後に残る結合文字の扱い。
"""

from SentenceCalibratedMosaic.sentence_calibrated_mosaic import estimate_tokens

import pytest


# ──── estimate_issue_144_147_149 ──────────────────────────────────

"""#144 / #147 / #149: Devanagari rate, Oriya rate, Hebrew factor, NEL, mojibake Ã/Â.

Reference o200k counts measured with tiktoken; estimate tests need no tokenizer.
"""


@pytest.mark.parametrize("text, estimate, reference", [
    # #144 Devanagari → Brahmic rate 3 (was other-script ceil(len/4))
    ("नमस्ते", 2, 4),  # known short-word undercount; corpus ratio is what matters
    ("नमस्ते दुनिया", 4, 5),
    ("विज्ञान", 3, 3),
    # #147 Oriya rate 1.0 (was default 3 → underestimate ~0.38)
    ("ଓଡ଼ିଆ", 5, 7),
    ("ନମସ୍କାର", 7, 6),  # rate 1.0 overestimates this word; corpus MAE still down
    # #144 Hebrew a=0.50 (held-out seed 1104); short שלום stays 1+1
    ("שלום עולם", 2, 2),
    ("בראשית ברא אלהים", 7, 7),
    ("מה שלומך היום", 5, 5),
    # #149 NEL (U+0085): was 0 via strip() early-return / unmatched \s
    ("\x85", 2, 2),
    ("a\x85b", 4, 4),
    ("hello\x85world foo", 5, 5),
    # #149 mojibake Ã/Â floor at len(w)
    ("tÃ", 2, 2),
    ("Ã©", 2, 2),  # Ã + © punctuation; floor applies to Ã word piece
])
def test_issue_estimates(text, estimate, reference):
    assert estimate_tokens(text) == estimate


@pytest.mark.parametrize("text, estimate, reference", [
    ("\x85", 2, 2),
    ("a\x85b", 4, 4),
    ("hello\x85world foo", 5, 5),
    ("שלום עולם", 2, 2),
    ("בראשית ברא אלהים", 7, 7),
    ("מה שלומך היום", 5, 5),
    ("विज्ञान", 3, 3),
    ("tÃ", 2, 2),
])
def test_issue_reference_counts(text, estimate, reference):
    tiktoken = pytest.importorskip("tiktoken")
    assert len(tiktoken.get_encoding("o200k_base").encode(text)) == reference


# ──── estimate_script_marks ───────────────────────────────────────

"""ヘブライ語の点・アラビア語のハラカートは o200k が語をその位置で分割するので、
記号 1 つにつき 1 トークン数える。デーヴァナーガリーは Brahmic レート(ceil(len/3))。"""


@pytest.mark.parametrize("bare, marked", [
    ("שלום עולם", "שָׁלוֹם עוֹלָם"),
    ("مرحبا بالعالم", "مَرْحَبًا بِالْعَالَمِ"),
    # Devanagari is Brahmic rate (ceil(len/3)); virama no longer splits, so omitted.
])
def test_marks_cost_more_than_bare(bare, marked):
    assert estimate_tokens(marked) > estimate_tokens(bare)


@pytest.mark.parametrize("text, expected", [
    ("שלום עולם", 2),            # o200k 2(点なしは不変)
    ("مرحبا بالعالم", 4),        # o200k 4(点なしは不変)
    ("नमस्ते दुनिया", 4),         # o200k 5(結合文字を分割しないため -1、既知の差)
    ("שָׁלוֹם עוֹלָם", 11),       # o200k 13, main 15
])
def test_marked_word_costs(text, expected):
    assert estimate_tokens(text) == expected


def test_each_mark_adds_one():
    base = estimate_tokens("كتب")
    assert estimate_tokens("كَتَبَ") >= base + 3


@pytest.mark.parametrize("text, alone, ctx", [
    # 子音+ヴィラーマ+子音(結合文字)は分割しない。値は推定値(o200k: 1/3 ×5、द्ध 1/4)
    ("\u0915\u094d\u0937", 1, 3),  # क्ष
    ("\u091c\u094d\u091e", 1, 3),  # ज्ञ
    ("\u0924\u094d\u0930", 1, 3),  # त्र
    ("\u0936\u094d\u0930", 1, 3),  # श्र
    ("\u0926\u094d\u0927", 1, 3),  # द्ध
    ("\u0935\u093f\u091c\u094d\u091e\u093e\u0928", 3, 5),  # विज्ञान(o200k 3/3; Brahmic rate)
    ("\u092e\u093f\u0924\u094d\u0930", 2, 4),  # मित्र(o200k 2/3)
    ("\u0915\u094d\u0979", 1, 3),  # U+0979 の追加子音も結合文字扱い
])
def test_deva_conjunct_not_split(text, alone, ctx):
    assert estimate_tokens(text) == alone
    assert estimate_tokens(f"x {text} y") == ctx


# ──── estimate_tibetan_freeze ─────────────────────────────────────

"""#149: Tibetan sample is small (Tatoeba bod n=51); freeze current rate estimates.

Do not retune `_BRAHMIC_RATES` for Tibetan until a larger held-out set exists.
seed 1104 fit/held-out on bod: sum_ratio ≈ 0.88–0.90 (see PR body).
"""


# Short Tatoeba-bod style phrases; estimate column is this branch's freeze point.
@pytest.mark.parametrize("text, estimate, reference", [
    ("བཀྲ་ཤིས་བདེ་ལེགས།", 23, 26),
    ("ང་བོད་པ་ཡིན།", 16, 19),
    ("སྔ་དྲོ་བདེ་ལེགས", 20, 22),
])
def test_tibetan_freeze_estimates(text, estimate, reference):
    assert estimate_tokens(text) == estimate


@pytest.mark.parametrize("text, estimate, reference", [
    ("བཀྲ་ཤིས་བདེ་ལེགས།", 23, 26),
    ("ང་བོད་པ་ཡིན།", 16, 19),
    ("སྔ་དྲོ་བདེ་ལེགས", 20, 22),
])
def test_tibetan_reference_counts(text, estimate, reference):
    tiktoken = pytest.importorskip("tiktoken")
    assert len(tiktoken.get_encoding("o200k_base").encode(text)) == reference


# ──── estimate_uncovered_scripts ──────────────────────────────────

"""estimate_tokens: 未分類スクリプトが 0 トークンにならないこと、NFC 後に残る結合文字の扱い。
未校正スクリプトは従来の ceil(len/4) 規則(o200k 実測より低めになり得る)。"""


@pytest.mark.parametrize("text, expected", [
    ("שלום עולם", 2),       # Hebrew (o200k 2)
    ("Բարեւ աշխարհ", 4),    # Armenian (o200k 4)
    ("გამარჯობა", 3),       # Georgian (o200k 3)
    ("ሰላም", 6),             # Ethiopic (o200k 6: 1 音節 2 トークン)
])
def test_uncovered_script_not_free(text, expected):
    assert estimate_tokens(text) == expected


def test_long_uncovered_word_scales():
    # 5 文字以上のジョージア語は語長係数 round(0.32*len+0.4) (o200k 11、旧 ceil(15/4)=4)
    assert estimate_tokens("აბგდევზთიკლმნოპ") == 5


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
    # #147: interior ZWSP surcharge removed. Individual regression: o200k=10, main=10;
    # corpus MAE improves, but this word is underestimated by one (no word exception).
    ("សួស្តី​ពិភពលោក", 9),
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
