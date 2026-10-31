from MorphoZip.morpho_zip import _CURLY_MERGE_WORDS, normalize_quotes


def test_line_start_merge_word_keeps_curly():
    assert normalize_quotes("“Well,” he said.") == "“Well,” he said."
    assert normalize_quotes("x\n“With it,” she said.") == "x\n“With it,” she said."


def test_after_space_or_other_word_goes_straight():
    assert normalize_quotes('He said “Well, ok”.') == 'He said "Well, ok".'
    assert normalize_quotes("“But no,” he said.") == '"But no," he said.'
    assert normalize_quotes("“Wellington” x") == '"Wellington" x'


def test_after_bracket_goes_straight():
    assert normalize_quotes("(“Well,” he said.)") == '("Well," he said.)'
    assert normalize_quotes("[“With it”]") == '["With it"]'


def test_after_bracket_straight_not_more_tokens():
    tiktoken = __import__("pytest").importorskip("tiktoken")
    e = tiktoken.get_encoding("o200k_base")
    for src in ("(“Well,” he said.)", "[“With it”]"):
        assert len(e.encode(normalize_quotes(src))) <= len(e.encode(src)), src


def test_merge_word_table_matches_o200k():
    tiktoken = __import__("pytest").importorskip("tiktoken")
    e = tiktoken.get_encoding("o200k_base")
    for w in _CURLY_MERGE_WORDS:
        assert len(e.encode("“" + w)) == 1 < len(e.encode('"' + w)), w
