"""Unicode boundary regressions. Expected estimates and reference counts are distinct.

The o200k counts were measured with tiktoken 0.14.0; no tokenizer is needed here.
Known approximation errors are deliberately visible in the case data.
"""
import pytest
from TesseraTalk.tessera_talk import estimate_tokens

CASES = [('한국어', 2, 2), ('x 한국어 y', 4, 4), ('한국어', 24, 24), ('x 한국어 y', 26, 27), ('안녕하세요 세계', 3, 3), ('x 안녕하세요 세계 y', 5, 5), ('안녕하세요 세계', 48, 49), ('x 안녕하세요 세계 y', 50, 52), ('Tiếng Việt', 3, 3), ('x Tiếng Việt y', 5, 5), ('Tiếng Việt', 9, 8), ('x Tiếng Việt y', 11, 10), ('café', 2, 2), ('x café y', 4, 3), ('café', 2, 3), ('x café y', 4, 4), ('क़', 1, 2), ('x क़ y', 3, 4), ('क्ष', 1, 1), ('x क्ष y', 3, 3), ('क्\u200dष', 4, 4), ('x क्\u200dष y', 6, 6), ('क्\u200cष', 4, 4), ('x क्\u200cष y', 6, 6), ('שָׁלוֹם', 6, 7), ('x שָׁלוֹם y', 8, 9), ('مَرْحَبًا', 9, 6), ('x مَرْحَبًا y', 11, 8), ('☺️', 2, 2), ('x ☺️ y', 4, 5), ('❤️', 1, 1), ('x ❤️ y', 3, 3), ('葛󠄀城', 7, 6), ('x 葛󠄀城 y', 9, 9), ('ᄒᆞᆫ', 9, 9), ('x ᄒᆞᆫ y', 11, 12), ('ꥠힰ', 6, 5), ('x ꥠힰ y', 8, 7), ('क्ॹ', 1, 4), ('x क्ॹ y', 3, 6), ('க்ஷ', 1, 3), ('x க்ஷ y', 3, 5), ('👨\u200d👩\u200d👧\u200d👦', 11, 11), ('x 👨\u200d👩\u200d👧\u200d👦 y', 13, 13), ('x  y', 2, 3)]

@pytest.mark.parametrize("text, estimate, reference", CASES)
def test_unicode_boundary_estimates(text, estimate, reference):
    assert estimate_tokens(text) == estimate

@pytest.mark.parametrize("text, estimate, reference", CASES)
def test_unicode_reference_counts(text, estimate, reference):
    tiktoken = pytest.importorskip("tiktoken")
    assert len(tiktoken.get_encoding("o200k_base").encode(text)) == reference
