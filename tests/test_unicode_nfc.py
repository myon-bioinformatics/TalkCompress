"""層横断の Unicode 監査: NFC / NFD、結合記号、アクセント付きラテン文字。

- unicode_nfc_audit: 監査: NFD 入力とアクセント付きラテン文字の扱い。
- unicode_key_marks
- nfc_latin
"""

from MorphoGrammarMinimal import morpho_grammar_minimal as M
from MorphoGrammarMinimal.morpho_grammar_minimal import compress
from RulePeerCodec.rule_peer_codec import derive_key
from SentenceCalibratedMosaic import sentence_calibrated_mosaic as T
from pathlib import Path
from shared.qa_fidelity import Probe
from shared.qa_fidelity import matches
import dialogue_lab as d
import sys
import unicodedata


# ──── unicode_nfc_audit ───────────────────────────────────────────

"""監査: NFD 入力とアクセント付きラテン文字の扱い。"""


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

    from DensityFacadeRoute import density_facade_route as D

    a = argparse.Namespace()
    # アクセント付きラテン文字だけでもラテン文字種として数える（2文字種 → B）
    assert D.choose_auto_layers("ééé ü 日本です", a)[:2] == ["B", "E"]
    assert D.choose_auto_layers(_nfd("ééé ü 日本です"), a)[:2] == ["B", "E"]
    assert D.choose_auto_layers("ḗḗḗ ḗḗḗ ḗḗḗ ḗḗḗ ḗḗḗ 日本です", a)[:2] == ["B", "E"]


def test_shorthand_suggest_keeps_accented_words():
    from ShorthandSessionEdge import shorthand_session_edge as S

    longs = {d["long"] for d in S.suggest_hereafter("café latte now. café latte again.")}
    assert "café latte" in longs
    assert not any("caf " in x for x in longs)
    longs2 = {d["long"] for d in S.suggest_hereafter(_nfd("café latte now. café latte again."))}
    assert "café latte" in longs2
    assert not any("_" in x for x in {d["long"] for d in S.suggest_hereafter("a_b c_d. a_b c_d.")})


def test_zh_de_phrase_latin_word_edges():
    # 多谢 failed the zh round-trip gate; edge checks use the passing 思维链.
    assert T.apply_zh_de_phrases("chain-of-thought") == "思维链"
    for t in ("échain-of-thought", "chain-of-thoughté", "chain-of-thoughtñ", _nfd("chain-of-thoughté")):
        assert T.apply_zh_de_phrases(t) == unicodedata.normalize("NFC", t)
    assert T.apply_zh_de_phrases("chain-of-thought́") == "chain-of-thought́"
    assert T.apply_zh_de_phrases("ḁchain-of-thought") == "ḁchain-of-thought"


def test_relative_que_accented_left_edge():
    assert T.apply_relative_que("the book which eats") == "the book que eats"
    assert T.apply_relative_que("the bookéwhich eats") == "the bookéwhich eats"
    assert T.apply_relative_que("the bookḁwhich eats") == "the bookḁwhich eats"
    assert T.apply_relative_que(_nfd("the booké") + "which eats") == _nfd("the booké") + "which eats"


# ──── unicode_key_marks ───────────────────────────────────────────

def test_derive_key_nfc_nfd_equal():
    nfc = "café"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    assert derive_key(nfc, key_normalization="NFC") == derive_key(nfd, key_normalization="NFC")


def test_derive_key_bytes_unchanged():
    nfd = unicodedata.normalize("NFD", "café").encode()
    assert derive_key(nfd) != derive_key("café".encode())


def test_article_with_non_basic_combining_mark_kept():
    # U+1DC4 is a combining mark outside U+0300-036F
    out = compress("I saw a\u1DC4 b")
    assert "a\u1DC4" in out
    assert not unicodedata.combining(out.lstrip()[0])


# 3bot レビュー Should 2: U+0300–036F 版に戻すと落ちるテスト（U+1DC4 は範囲外の結合文字）
def test_article_surface_re_rejects_extended_mark():
    from MorphoGrammarMinimal.morpho_grammar_minimal import _ARTICLE_SURFACE_RE

    assert _ARTICLE_SURFACE_RE.search("a\u1dc4") is None
    assert _ARTICLE_SURFACE_RE.search("a cat") is not None


def test_pack_tokens_keeps_extended_mark_in_word():
    from MorphoGrammarMinimal.morpho_grammar_minimal import _PACK_SPLIT, pack_tokens

    assert pack_tokens("ka\u1dc4la x").startswith("ka\u1dc4la")
    assert "ka\u1dc4la" in _PACK_SPLIT.split("ka\u1dc4la x")


def test_is_wordish_extended_mark():
    from MorphoGrammarMinimal.morpho_grammar_minimal import pack_tokens

    # _is_wordish が拡張結合文字を語扱いしないと、語の前後で区切りが変わる
    # 語の直後の ( の前に空白が入るのは、直前のトークンが語扱いのときだけ
    assert pack_tokens("ka\u1dc4la (x)") == "ka\u1dc4la (x)"


def test_suggest_hereafter_extended_mark_not_split():
    from ShorthandSessionEdge.shorthand_session_edge import suggest_hereafter

    text = " ".join(["xa\u1dc4yword appears"] * 4)
    longs = [str(d["long"]) for d in suggest_hereafter(text)]
    assert longs, longs
    assert not any("xa yword" in s for s in longs), longs


def test_derive_key_nfc_not_nfkc():
    # 互換文字（ﬁ リガチャ）は fi と別の鍵（NFKC ではなく NFC）
    assert derive_key("\ufb01", key_normalization="NFC") != derive_key("fi", key_normalization="NFC")


# ──── nfc_latin ───────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "RulePeerCodec"))


NFD = lambda s: unicodedata.normalize("NFD", s)  # noqa: E731


def test_encode_nfd_does_not_hit_base_letters():
    assert d.encode(NFD("café"), [{"long": "cafe", "short": "c"}]) == "café"


def test_encode_nfd_matches_nfc_rule():
    assert d.encode(NFD("café crème ok"), [{"long": "café crème", "short": "cc"}]) == "cc ok"


def test_validate_accepts_nfd_training():
    rules = d.validate_mapping({"mapping": [{"long": "café crème", "short": "Q1"}]},
                               [{"text": NFD("Order café crème now.")}])
    assert rules == [{"long": "café crème", "short": "Q1"}]


def test_matches_nfd_answer():
    assert matches(Probe("term", "q", "München"), NFD("Er wohnt in München."))
    assert matches(Probe("id", "q", "Ä-1"), NFD("Ä-1"))


def test_matches_rejects_accented_neighbor():
    assert not matches(Probe("term", "q", "Rene"), NFD("René"))


def test_encode_nfd_rule_key():
    assert d.encode("café crème ok", [{"long": NFD("café crème"), "short": "cc"}]) == "cc ok"


def test_encode_always_returns_nfc():
    s = NFD("Ça va, café?")
    assert d.encode(s, []) == unicodedata.normalize("NFC", s)
    assert d.encode(s, [{"long": "zzzz", "short": "z"}]) == unicodedata.normalize("NFC", s)


def test_validate_nfd_long_form():
    rules = d.validate_mapping({"mapping": [{"long": NFD("café crème"), "short": "Q1"}]},
                               [{"text": "Order café crème now."}])
    assert rules == [{"long": "café crème", "short": "Q1"}]


def test_matches_nfd_expected():
    assert matches(Probe("term", "q", NFD("München")), "Er wohnt in München.")
    assert matches(Probe("id", "q", NFD("Ä-1")), "Ä-1")
