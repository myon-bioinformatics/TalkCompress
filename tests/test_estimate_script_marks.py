"""ヘブライ語の点・アラビア語のハラカート・デーヴァナーガリーのヴィラーマ(Mn)は
o200k が語をその位置で分割するので、記号 1 つにつき 1 トークン数える。"""
import pytest

from TesseraTalk.tessera_talk import estimate_tokens


@pytest.mark.parametrize("bare, marked", [
    ("שלום עולם", "שָׁלוֹם עוֹלָם"),
    ("مرحبا بالعالم", "مَرْحَبًا بِالْعَالَمِ"),
    ("नमसत", "नमस्त"),
])
def test_marks_cost_more_than_bare(bare, marked):
    assert estimate_tokens(marked) > estimate_tokens(bare)


@pytest.mark.parametrize("text, expected", [
    ("שלום עולם", 2),            # o200k 2(点なしは不変)
    ("مرحبا بالعالم", 4),        # o200k 4(点なしは不変)
    ("नमस्ते दुनिया", 5),         # o200k 5
    ("שָׁלוֹם עוֹלָם", 11),       # o200k 13, main 15
])
def test_marked_word_costs(text, expected):
    assert estimate_tokens(text) == expected


def test_each_mark_adds_one():
    base = estimate_tokens("كتب")
    assert estimate_tokens("كَتَبَ") >= base + 3


def test_deva_ksa_conjunct_not_split():
    # क्ष は o200k で 1 トークン。ヴィラーマ分割の例外(分割すると 3)
    assert estimate_tokens("\u0915\u094d\u0937") == 1
    assert estimate_tokens("x \u0915\u094d\u0937 y") == 3
