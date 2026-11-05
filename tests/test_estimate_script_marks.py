"""ヘブライ語の点・アラビア語のハラカートは o200k が語をその位置で分割するので、
記号 1 つにつき 1 トークン数える。デーヴァナーガリーは Brahmic レート(ceil(len/3))。"""
import pytest

from TesseraTalk.tessera_talk import estimate_tokens


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
