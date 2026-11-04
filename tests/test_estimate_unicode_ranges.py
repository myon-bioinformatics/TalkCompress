"""Range-based estimate rules: fullwidth / halfwidth / math alphanumerics, Ethiopic,
Hebrew / Arabic / Urdu / Georgian / Greek word-length factor, stacked marks, control chars.

Reference o200k counts were measured with tiktoken 0.14.0; no tokenizer is needed for the
estimate tests. Approximation gaps stay visible in the case data.
"""
import pytest
from TesseraTalk.tessera_talk import estimate_tokens

CASES = [('ＨＥＬＬＯ\u3000ＷＯＲＬＤ１２３', 18, 18), ('ｱｲｳｴｵ ｶﾀｶﾅ', 17, 17), ('𝐇𝐞𝐥𝐥𝐨 𝑤𝑜𝑟𝑙𝑑', 24, 25), ('𝔉𝔯𝔞𝔨𝔱𝔲𝔯', 21, 21), ('ሰላም ለዓለም', 15, 15), ('ኢትዮጵያ', 10, 10), ('בראשית ברא אלהים', 6, 7), ('מה שלומך היום', 4, 5), ('مرحبا بالعالم', 4, 4), ('میں کل اسٹیشن جاؤں گا', 6, 7), ('გამარჯობა მსოფლიო', 6, 4), ('Καλημέρα κόσμε', 5, 6), ('Z̵̶̡algo', 8, 8), ('\x00\x01\x02', 3, 3), ('a\x07b', 3, 3)]


@pytest.mark.parametrize("text, estimate, reference", CASES)
def test_range_estimates(text, estimate, reference):
    assert estimate_tokens(text) == estimate


@pytest.mark.parametrize("text, estimate, reference", CASES)
def test_range_reference_counts(text, estimate, reference):
    tiktoken = pytest.importorskip("tiktoken")
    assert len(tiktoken.get_encoding("o200k_base").encode(text)) == reference

