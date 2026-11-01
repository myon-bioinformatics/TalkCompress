"""estimate_tokens: 非 BMP 文字・emoji 結合列・タイ語・ベトナム語の o200k_base 合わせ込み。

期待値はすべて tiktoken o200k_base の実測値。
"""
import json
from pathlib import Path

import pytest

from TesseraTalk.tessera_talk import estimate_tokens

CORPUS = json.loads((Path(__file__).resolve().parents[1] / "TesseraTalk/fixtures/estimate_rare_corpus.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("text, o200k", [
    ("\U0002A700\U0002A701\U0002A702", 12),   # CJK 拡張 C: 語彙なし → 4 バイト/字
    ("\U00031350\U00031351\U00031352", 12),   # CJK 拡張 H
    ("\U000F0000\U000F0001\U000F0002", 12),   # 補助私用領域 A
    ("\U00100000\U00100001\U00100002", 12),   # 補助私用領域 B
    ("𠮟られた", 7),                           # 拡張 B の後のかなは従来どおり
    ("👍🏽", 3),
    ("👨\u200d👩\u200d👧\u200d👦", 11),
    ("🧑🏽\u200d💻", 8),
    ("❤️\u200d🔥", 3),                         # U+2764 U+FE0F は 1 トークン
    ("ภาษาไทยไม่มีการเว้นวรรคระหว่างคำ", 11),
    ("วันนี้อากาศดีมาก", 6),
    ("Hôm nay trời đẹp quá", 6),
    ("Hệ thống sẽ nén văn bản trước khi gửi đi", 12),
])
def test_rare_exact(text, o200k):
    assert estimate_tokens(text) == o200k


# 下限は tiktoken 実測との絶対誤差合計（main: th 327 / th_heldout 134 / vi 25 / vi_heldout 8 /
# emoji 56 / nonbmp 117）。ゆるい上限で退行だけを止める。
@pytest.mark.parametrize("key, total, max_abs", [
    ("th", 227, 14), ("th_heldout", 87, 5), ("vi", 201, 12), ("vi_heldout", 86, 5),
    ("emoji_seq", 168, 4), ("nonbmp", 145, 8),
])
def test_corpus_abs_error(key, total, max_abs):
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    xs = CORPUS[key]
    assert sum(len(enc.encode(s)) for s in xs) == total
    assert sum(abs(estimate_tokens(s) - len(enc.encode(s))) for s in xs) <= max_abs
