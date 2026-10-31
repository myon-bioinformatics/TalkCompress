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


@pytest.mark.parametrize("text, expected", [
    # 期待値は本実装の値。括弧内は o200k_base 実測(tiktoken)
    ("biết", 2),               # 文頭は空白なしで分割 (o200k 2、" biết" は 1)
    ("x biết", 2),             # 空白ありは 1 音節 1 (o200k 2)
    ("Đà Nẵng", 4),            # 文頭 +1、まれな声調文字 ẵ +1 (o200k 5、main 3)
    ("Hà Nội, Việt Nam", 6),   # ベトナム語文中の文頭非 ASCII 語 +1 (o200k 6)
    ("x biếtđâu", 3),          # 7 文字の連結音節は 2 (o200k 4)
])
def test_vietnamese_exact(text, expected):
    assert estimate_tokens(text) == expected
