"""監査: NFD 入力とアクセント付きラテン文字の扱い。"""
import unicodedata

from MorphoZip import morpho_zip as M
from TesseraTalk import tessera_talk as T


def _nfd(s):
    return unicodedata.normalize("NFD", s)


def test_morpho_compress_nfd_keeps_accented_word():
    assert M.compress(_nfd("thé is not the same")) == M.compress("thé is not the same")
    assert "thé" in M.compress(_nfd("thé is good"))


def test_morpho_expand_nfd_same_as_nfc():
    s = "thé w/ café"
    assert M.expand(_nfd(s)) == M.expand(s)


def test_you_u_accent_boundary():
    assert T.apply_you_u("youé and Zoë you") == "youé and Zoë U"
    assert T.apply_you_u(_nfd("youé")) == "youé"
    assert T.apply_you_u("éyou ëyou") == "éyou ëyou"
    assert T.apply_you_u("テストyouです") == "テストUです"
    assert T.apply_you_u("you're your you_x xyou you") == "you're your you_x xyou U"


def test_density_counts_accented_latin():
    import argparse

    from DensityZip import density_zip as D

    a = argparse.Namespace()
    # アクセント付きラテン文字だけでもラテン文字種として数える（2文字種 → B）
    assert D.choose_auto_layers("ééé ü 日本です", a)[:2] == ["B", "E"]
    assert D.choose_auto_layers(_nfd("ééé ü 日本です"), a)[:2] == ["B", "E"]
    assert D.choose_auto_layers("ḗḗḗ ḗḗḗ ḗḗḗ ḗḗḗ ḗḗḗ 日本です", a)[:2] == ["B", "E"]


def test_shorthand_suggest_keeps_accented_words():
    from ShorthandEdge import shorthand_edge as S

    longs = {d["long"] for d in S.suggest_hereafter("café latte now. café latte again.")}
    assert "café latte" in longs
    assert not any("caf " in x for x in longs)
    longs2 = {d["long"] for d in S.suggest_hereafter(_nfd("café latte now. café latte again."))}
    assert "café latte" in longs2
    assert not any("_" in x for x in {d["long"] for d in S.suggest_hereafter("a_b c_d. a_b c_d.")})


def test_zh_de_phrase_latin_word_edges():
    assert T.apply_zh_de_phrases("thank you very much") == "多谢"
    for t in ("éthank you very much", "thank you very muché", "thank you very muchñ", _nfd("thank you very muché")):
        assert T.apply_zh_de_phrases(t) == unicodedata.normalize("NFC", t)
    assert T.apply_zh_de_phrases("thank you very much́") == "thank you very much́"
    assert T.apply_zh_de_phrases("ḁthank you very much") == "ḁthank you very much"


def test_relative_que_accented_left_edge():
    assert T.apply_relative_que("the book which eats") == "the book que eats"
    assert T.apply_relative_que("the bookéwhich eats") == "the bookéwhich eats"
    assert T.apply_relative_que("the bookḁwhich eats") == "the bookḁwhich eats"
    assert T.apply_relative_que(_nfd("the booké") + "which eats") == _nfd("the booké") + "which eats"
