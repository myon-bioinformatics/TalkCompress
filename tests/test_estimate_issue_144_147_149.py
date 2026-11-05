"""#144 / #147 / #149: Devanagari rate, Oriya rate, Hebrew factor, NEL, mojibake Ã/Â.

Reference o200k counts measured with tiktoken; estimate tests need no tokenizer.
"""
import pytest
from TesseraTalk.tessera_talk import estimate_tokens


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
