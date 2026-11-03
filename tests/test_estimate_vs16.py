"""テキスト既定の記号 + VS16(U+FE0F)は絵文字の実測表で数える(o200k_base 実測値)。"""
import pytest

from TesseraTalk.tessera_talk import estimate_tokens


@pytest.mark.parametrize("text, expected", [
    ("❤️", 1),     # 1 トークンに結合
    ("☺️", 2),
    ("☀️", 3),
    ("✅", 1),
    ("©️", 2),
    ("™️", 2),
    ("⁉️", 3),
    ("㊗️", 4),
    ("☺️☺️", 4),
    ("ok ☺️", 3),  # o200k 4(前の空白との結合は未対応)
])
def test_symbol_vs16(text, expected):
    assert estimate_tokens(text) == expected


def test_plain_symbols_unchanged():
    # VS16 が付かない記号は従来どおり記号の連なりとして数える
    assert estimate_tokens("© 2026") == 3
    assert estimate_tokens("→") == 1


def test_vs16_pair_is_emoji_group():
    # 回帰: main では "❤️" が記号(p)扱いで、表の "❤️"=1 が使われていなかった
    from TesseraTalk import tessera_talk as T
    assert [m.lastgroup for m in T._PRETOKEN.finditer("\u2764\ufe0f")] == ["e"]


def test_lone_bmp_symbol_unchanged():
    # VS16 なしの "☺" は o200k 1 だが従来どおり 2。単独記号を実測表で数えると
    # 実コーパスの矢印などを含む行で一致率が 37%→28% に下がったため見送り。
    assert estimate_tokens("☺") == 2
