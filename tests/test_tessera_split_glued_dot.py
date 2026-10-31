"""TesseraTalk: 英数字に密着した . ! ? (1.2.3 / $3.50 / example.com / ?q=) で文を分割しない。

分割すると expand が区切りを空白で戻すため ``1. 2. 3`` のように意味が変わる。
"""

import pytest

from TesseraTalk import tessera_talk as t


@pytest.mark.parametrize(
    "text",
    [
        "Version 1.2.3 is out.",
        "It costs $3.50 now.",
        "See example.com today.",
        "Go to /s?q=x now.",
        "Wait!Really?",
    ],
)
def test_glued_terminator_roundtrips(text):
    packed = t.compress(text)
    assert "|" not in packed
    assert t.expand(packed) == text


@pytest.mark.parametrize(
    "text,parts",
    [("Done. Next.", 2), ("end.次", 2), ("Is it? Yes! Ok.", 3), ("Fin.\u201cQuote\u201d", 1)],
)
def test_real_sentence_ends_still_split(text, parts):
    packed = t.compress(text)
    assert packed.count("|") == parts - 1
    assert t.expand(packed) == text
