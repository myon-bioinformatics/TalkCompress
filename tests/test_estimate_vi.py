"""estimate_tokens: ベトナム語の過大評価修正。声調付き音節はほぼ o200k 1 トークン(tiktoken 実測)。"""
import pytest

from TesseraTalk.tessera_talk import estimate_tokens


@pytest.mark.parametrize("text, o200k", [
    ("Xin chào thế giới", 5),
    ("Tôi đang học tiếng Việt mỗi ngày", 8),
    ("Thành phố Hồ Chí Minh là thành phố lớn nhất nước.", 14),
])
def test_vietnamese_close_to_o200k(text, o200k):
    assert abs(estimate_tokens(text) - o200k) <= 1


def test_transliteration_not_vietnamese():
    # ḥ ẓ ā ī は翻字。ベトナム語規則を適用しない(main と同じ 6、o200k 9)
    assert estimate_tokens("Ẓāhir ḥadīth") == 6
