"""監査: ShorthandEdge.expand が単語の途中を展開しないこと。"""
from ShorthandEdge import shorthand_edge as s


def test_expand_skips_inside_words():
    assert s.expand("pretty cute city") == "pretty cute city"
    assert s.expand("it's tyx") == "it's tyx"
    assert s.expand("don'ty") == "don'ty"


def test_expand_whole_tokens():
    assert s.expand("ty, cu") == "thank you, see you"
    assert s.expand("TY") == "TY"
    assert s.expand("wdyt?") == "what do you think?"


def test_expand_long_with_backslash():
    assert s.expand("zz", mapping={"a\\1b": "zz"}) == "a\\1b"


def test_word_bounded_edges():
    assert s._word_bounded("ab") == r"(?<![\w'’])(?a:ab)(?![\w'’])"
    assert s._word_bounded("w/") == r"(?<![\w'’])(?a:w/)"
    assert s._word_bounded("/w") == r"(?a:/w)(?![\w'’])"
