"""監査: rulebook の語境界と Unicode 対応。"""
from Zipilogue.rulebook import Rule, RuleBook, _bounded, _extract_phrases


def _book():
    return RuleBook(rules=[Rule("r1", "in the", "r1"), Rule("r2", "ありがとう", "r2")])


def test_encode_does_not_rewrite_inside_words():
    b = _book()
    assert b.encode_with_rules("within these walls") == "within these walls"
    assert b.encode_with_rules("sit in the car") == "sit r1 car"
    assert b.encode_with_rules("In the end") == "r1 end"


def test_cjk_rule_roundtrips_without_spaces():
    b = _book()
    enc = b.encode_with_rules("はいありがとう")
    assert enc == "はいr2"
    assert b.decode_with_rules(enc) == "はいありがとう"


def test_decode_keeps_latin_word_boundary():
    b = _book()
    assert b.decode_with_rules("xr1 r1y r1") == "xr1 r1y in the"
    assert b.decode_with_rules("r1, r1") == "in the, in the"


def test_bounded_edges():
    assert _bounded("ab") == r"(?<![^\W\u3040-\u30ff\u3400-\u9fff])ab(?![^\W\u3040-\u30ff\u3400-\u9fff])"
    assert _bounded("あa") == r"あa(?![^\W\u3040-\u30ff\u3400-\u9fff])"
    assert _bounded("aあ") == r"(?<![^\W\u3040-\u30ff\u3400-\u9fff])aあ"
    assert _bounded("!") == "!"
    assert _bounded("") == ""


def test_extract_phrases_keeps_accented_words():
    got = _extract_phrases("ça va très bien")
    assert "ça va" in got and "très bien" in got
    assert "a va" not in got and "tr s" not in got
    assert "Привет мир" in _extract_phrases("Привет мир")
