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


def test_corpus_rules_do_not_overlap_and_roundtrip():
    """規則どうしの重なり検出: 実コーパスで学習した全規則の組で往復できること。"""
    import itertools
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent
    lines = []
    for f in sorted((root / "fixtures" / "pd_corpus").glob("*.txt")):
        lines += [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    book = RuleBook(threshold=3)
    for ln in lines:
        book.observe(ln)
    rules = book.rules
    assert len(rules) >= 20
    for a, c in itertools.permutations(rules, 2):
        assert not re.search(_bounded(c.long), a.short, re.I)
        assert not re.search(_bounded(c.short), a.long)
        t = f"{a.long} {c.long}"
        assert book.decode_with_rules(book.encode_with_rules(t)).lower() == t.lower()
    for ln in lines:
        assert book.decode_with_rules(book.encode_with_rules(ln)).lower() == ln.lower()
