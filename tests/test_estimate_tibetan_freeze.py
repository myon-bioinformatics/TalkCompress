"""#149: Tibetan sample is small (Tatoeba bod n=51); freeze current rate estimates.

Do not retune `_BRAHMIC_RATES` for Tibetan until a larger held-out set exists.
seed 1104 fit/held-out on bod: sum_ratio ≈ 0.88–0.90 (see PR body).
"""
import pytest
from TesseraTalk.tessera_talk import estimate_tokens


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
