"""Opt-in noun-case experiment (scripts/noun_case.py): A/B/C marking."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("noun_case", ROOT / "scripts/noun_case.py")
nc = importlib.util.module_from_spec(_spec)
sys.modules["noun_case"] = nc
_spec.loader.exec_module(nc)

LEX = frozenset({"book", "cats", "day"})
CLOSED = frozenset({"the", "my", "it", "with"})


def test_expand_alternation_forms():
    assert nc.expand_alternation("cats?|fish|bus(?:es)?") == {"cat", "cats", "fish", "bus", "buses"}
    assert nc.expand_alternation("glasses|Bad-1") == {"glasses"}


def test_lexicon_from_real_tables():
    mz = nc.load_morpho()
    assert nc.load_morpho() is mz
    lex = nc.noun_lexicon(mz)
    for w in ("cat", "cats", "people", "day", "days", "buses", "book", "idea", "sorts", "times"):
        assert w in lex
    assert "that" not in lex and "those" not in lex
    assert len(nc.determiner_rules(mz)) >= 1


def test_closed_surfaces_include_function_words():
    closed = nc.closed_surfaces(nc.load_morpho())
    for w in ("the", "my", "with", "because", "can", "u", "you", "w/o"):
        assert w in closed
    assert all(w == w.lower() for w in closed)


def test_noun_spans_lexicon_and_determiner():
    text = "my dog saw the book with cats.My it"
    got = [text[a:b] for a, b in nc.noun_spans(text, LEX, CLOSED)]
    assert got == ["dog", "book", "cats"]


def test_noun_spans_needs_single_space_and_skips_closed():
    assert nc.noun_spans("the  dog", LEX, CLOSED) == []
    assert nc.noun_spans("my\tdog", LEX, CLOSED) == []
    assert nc.noun_spans("the it", LEX, CLOSED) == []
    assert nc.noun_spans("Book", LEX, CLOSED) == [(0, 4)]
    assert nc.noun_spans("x the dog", frozenset(), CLOSED) == [(6, 9)]
    assert nc.noun_spans("dog", frozenset(), frozenset()) == []


def test_mark_schemes():
    text = "a book, the cats"
    spans = [(2, 6), (12, 16)]
    assert nc.mark(text, "A", spans) == text
    assert nc.mark(text, "B", spans) == "a Book, the Cats"
    assert nc.mark(text, "C", spans) == "a BOOK, the CATS"
    assert nc.mark("ok", "C", []) == "ok"
    with pytest.raises(ValueError, match="unknown scheme 'D'"):
        nc.mark(text, "D", spans)


def _count(t: str) -> int:
    # Fake tokenizer: uppercase letters cost one each, else per whitespace word.
    return len(t.split()) + sum(c.isupper() for c in t)


def test_measure_totals_words_short_forms():
    texts = {"b.txt": "the book day", "a.txt": "gonna see day"}
    res = nc.measure(texts, lambda s: s.replace("gonna", "wanna"), _count, LEX, CLOSED)
    assert res["totals"] == {
        "A": {"tokens": 6, "bytes": 25},
        "B": {"tokens": 9, "bytes": 25},
        "C": {"tokens": 16, "bytes": 25},
    }
    w = res["words"]
    assert res["noun_tokens"] == 3
    assert w["day"] == {"n": 2, "A": 1, "B": 2, "C": 4, "short_form": False, "rare": False}
    assert w["book"]["n"] == 1
    assert res["short_forms"] == {"wanna": {"n": 1, "A": 1, "B": 2, "C": 6}}
    res2 = nc.measure({"x": "wanna wanna"}, lambda s: s.replace("wanna", "zz zz"), _count, LEX, CLOSED)
    assert res2["short_forms"]["zz"]["n"] == 4


def test_measure_short_and_rare_flags():
    res = nc.measure({"x": "my ab"}, lambda s: s.replace("ab", "cd"), lambda t: len(t) - 1, LEX, CLOSED)
    assert res["words"]["cd"]["short_form"] is True
    assert res["words"]["cd"]["rare"] is True
    res = nc.measure({"x": "my a"}, lambda s: s, lambda t: len(t) - 2, LEX, CLOSED)
    assert res["words"]["a"]["rare"] is False


def test_worst_orders_by_total_increase():
    words = {
        "x": {"n": 1, "A": 1, "B": 3},
        "y": {"n": 3, "A": 1, "B": 2},
        "z": {"n": 5, "A": 2, "B": 2},
        "a": {"n": 2, "A": 1, "B": 2},
        "b": {"n": 2, "A": 1, "B": 2},
    }
    assert [w for w, _ in nc.worst(words, "B", 10)] == ["y", "a", "b", "x"]
    assert [w for w, _ in nc.worst(words, "B", 1)] == ["y"]


def test_load_corpus_reads_nested(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "a.txt").write_text("é", encoding="utf-8")
    (tmp_path / "sub/b.txt").write_text("x", encoding="utf-8")
    (tmp_path / "c.md").write_text("no", encoding="utf-8")
    assert nc.load_corpus(tmp_path) == {"a.txt": "é", "b.txt": "x"}
    assert len(nc.load_corpus()) >= 40


def test_default_compress_unchanged_by_experiment():
    mz = nc.load_morpho()
    src = "I saw the book and that idea yesterday."
    before = mz.compress(src)
    nc.noun_lexicon(mz)
    assert mz.compress(src) == before


def test_real_o200k_ordering_on_corpus():
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    mz = nc.load_morpho()
    texts = dict(list(nc.load_corpus().items())[:5])
    res = nc.measure(texts, mz.compress, lambda t: len(enc.encode(t)), nc.noun_lexicon(mz), nc.closed_surfaces(mz))
    t = res["totals"]
    assert t["A"]["bytes"] == t["B"]["bytes"] == t["C"]["bytes"]
    assert t["A"]["tokens"] <= t["B"]["tokens"] <= t["C"]["tokens"]


def test_cli_text_and_json(capsys, monkeypatch):
    pytest.importorskip("tiktoken")
    monkeypatch.setattr(nc, "load_corpus", lambda: {"x.txt": "I lost my handkerchief and the cats left, though my waistcoat stayed."})
    assert nc.main(["--top", "2"]) == 0
    out = capsys.readouterr().out
    assert re.search(r"^noun occurrences: \d+  distinct: \d+$", out, re.M)
    assert re.search(r"^  handkerchief: A=3 C=4 n=1$", out, re.M)
    assert re.search(r"^  tho: A=1 B=2 C=2 n=1$", out, re.M)
    assert re.search(r"^A: tokens=\d+ bytes=\d+$", out, re.M)
    assert "-- worst B (all)" in out and "-- worst C (rare)" in out and "-- compressor-introduced short forms" in out
    assert nc.main(["--json"]) == 0
    import json

    data = json.loads(capsys.readouterr().out)
    assert set(data["totals"]) == {"A", "B", "C"}


def test_rank_short_forms_uses_c_increase():
    sf = {"b": {"n": 1, "A": 1, "B": 5, "C": 2}, "a": {"n": 2, "A": 1, "B": 1, "C": 2}, "c": {"n": 1, "A": 1, "B": 1, "C": 4}}
    assert [w for w, _ in nc.rank_short_forms(sf, 5)] == ["c", "a", "b"]
    assert [w for w, _ in nc.rank_short_forms(sf, 1)] == ["c"]


def test_unicode_word_never_splits_determiner():
    # ``ça`` is one word: its trailing ``a`` is not an article.
    assert nc.noun_spans("ça dog", LEX, CLOSED) == []
    assert nc.noun_spans("ça book", LEX, CLOSED) == [(3, 7)]
    # symbol-glued fragments (w/a, x+a) neither act as determiners nor get tagged
    for t in ("w/a dog", "x+a dog", "a-dog", "a’dog", "日a dog", "the book/x"):
        assert nc.noun_spans(t, LEX, CLOSED) == [], t
    assert nc.noun_spans("the bookç", LEX, CLOSED) == []
    assert nc.standalone("a dog", 0, 1) and not nc.standalone("ça", 1, 2)
    assert nc.standalone("(a) x", 1, 2)


def test_ambiguous_lexicon_and_det_adjectives():
    lex = nc.noun_lexicon(nc.load_morpho())
    assert "one" not in lex and "fish" not in lex
    for adj in ("own", "first", "proper", "real", "domestic", "dear"):
        assert adj in nc.DET_ADJECTIVES
        assert nc.noun_spans(f"the {adj}", frozenset(), CLOSED) == []
    assert nc.noun_spans("the dog", frozenset(), CLOSED) == [(4, 7)]


def test_capital_stats():
    text = "Book is here. The dog met Tom. my Cats"
    spans = nc.noun_spans(text, LEX, CLOSED)
    st = nc.capital_stats(text, spans)
    assert st == {"noun_sentence_start": 1, "noun_proper": 1, "other_sentence_start": 1, "other_capital": 1}
    assert nc.capital_stats("w/O ça Éa", []) == dict.fromkeys(st, 0)
    assert nc.capital_stats("x\nThe", [])["other_sentence_start"] == 1


def test_standalone_digit_and_unicode_punct_neighbours():
    assert nc.standalone("3dog", 1, 4)
    assert nc.standalone("—dog—", 1, 4)
    assert not nc.standalone("édog", 1, 4)


def test_standalone_rejects_word_cut_before_combining_mark():
    import unicodedata

    nfd = unicodedata.normalize("NFD", "the café is")
    assert nfd[4:8] == "cafe"
    assert not nc.standalone(nfd, 4, 8)
    assert nc.standalone("the cafe is", 4, 8)
    # 結合文字が左側にある場合（é の直後に続く語）も切れた語として扱う
    glued = unicodedata.normalize("NFD", "é") + "x y"
    assert not nc.standalone(glued, 2, 3)
    assert nc.standalone(glued, 4, 5)


def test_standalone_rejects_spacing_and_enclosing_marks():
    # Mc (U+093E) / Me (U+20DD) are combining too, not just Mn.
    assert not nc.standalone("a dog\u093e x", 2, 5)
    assert not nc.standalone("a dog\u20dd x", 2, 5)
    assert not nc.standalone("a \u093edog x", 3, 6)


def test_mark_c_sharp_s_growth_keeps_surroundings():
    text = "der fuß ist da, the dog"
    spans = [(4, 7), (20, 23)]
    assert nc.mark(text, "C", spans) == "der FUSS ist da, the DOG"
