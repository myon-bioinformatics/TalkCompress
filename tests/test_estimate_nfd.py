"""estimate_tokens: NFD 入力の過小評価修正。o200k は生のバイト列を見るので、分解されたアクセントは
独立トークンになり語を分割する。期待値は o200k_base 実測に近いことを確認(tiktoken で計測)。"""
import unicodedata

import pytest

from TesseraTalk.tessera_talk import estimate_tokens


@pytest.mark.parametrize("text, o200k", [
    ("café naïve résumé déjà vu", 15),
    ("Xin chào thế giới", 12),
])
def test_nfd_not_underestimated(text, o200k):
    nfd = unicodedata.normalize("NFD", text)
    est = estimate_tokens(nfd)
    assert est > estimate_tokens(text)  # NFD は NFC より多く数える
    assert abs(est - o200k) <= 1


def test_nfc_and_ascii_unchanged():
    assert estimate_tokens("café naïve résumé déjà vu") == 9
    assert estimate_tokens("The quick brown fox jumps over the lazy dog.") == 10


def test_uncomposable_mark_unchanged():
    # NFC で合成されない結合文字は従来どおり(#82)
    assert estimate_tokens("x\u0301y") == 2
