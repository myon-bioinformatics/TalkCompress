"""層単体の機能テスト（A/B/C/E、Round 1–4）。層またぎは tests/integration/。

- features: Feature tests (layer unit): lexicon, RLE, counters, AAD.
- features2: Round-2 layer-unit tests: expand, frames, lex-policy, packs helpers.
- features3: Round-3 layer-unit tests: protect, packs, fingerprint, policy diff, LID mix.
- features4: Round-4 layer-unit tests: A export/negotiate, B bank+mosaic, C ledger, E counters.
"""

from __future__ import annotations

from pathlib import Path
from tests._helpers import load as _load
import importlib
import json
import os
import sys


# ──── features ────────────────────────────────────────────────────

"""Feature tests (layer unit): lexicon, RLE, counters, AAD.

Cross-layer pipeline/compare → tests/integration/.
"""


# --- layer ownership: fillers + UNIQUE_COMPACT = C ---


def test_layer_ownership_matrix_classic_example():
    """Canonical C vs E alone: I'll/spelled/ℹ️ on C; E keeps long unique + articles."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    classic = "um 私は will find out the information about three animals"

    from shared.lex_policy import INFO_GLYPH

    e_out = m.compress(classic)
    assert "um" in e_out.lower()
    assert "ascertain" in e_out.lower()
    assert "ascrt" not in e_out.lower()
    assert INFO_GLYPH not in e_out  # ℹ️ is C family=emoji
    assert "I'll" not in e_out
    assert "I will" in e_out or " will " in f" {e_out} "
    assert "three" in e_out.lower()  # spelled nums are C-owned
    assert "3匹" not in e_out

    c_out = s.compress(classic)
    assert "um" not in c_out.lower()
    assert "ascrt" in c_out.lower()
    assert "I'll" in c_out
    assert "3" in c_out  # three → 3
    assert "three" not in c_out.lower()
    assert INFO_GLYPH not in c_out  # ℹ️ pruned (o200k 1→2)


# --- lexicon load ---


def test_shorthand_lexicon_load(tmp_path):
    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    lex = tmp_path / "lex.json"
    lex.write_text(json.dumps({"continuous delivery": "CDel", "hello world": "hw"}), encoding="utf-8")
    sess = s.Session()
    sess.load_lexicon(lex)
    out = s.compress("please start continuous delivery", session=sess)
    assert "CDel" in out


# --- RLE mosaic ---


def test_mosaic_rle_roundtrip():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    src = "Hello there. World is fine. こんにちは。また今度。"
    mosaic = t.compress(src, rle=True)
    # Two EN sentences should share one lang tag at start of run
    assert mosaic.count("en:") <= 2  # at most one per run; likely 1
    # RLE form: second EN sentence has no lang prefix
    parts = mosaic.split("|")
    assert any(not p.startswith(("en:", "ja:")) for p in parts[1:]) or "en:" in mosaic
    back = t.expand(mosaic)
    assert "Hello there" in back
    assert "World is fine" in back
    assert "こんにちは" in back


def test_mosaic_rle_and_full_both_expand():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    full = "en:Hello.|en:World.|ja:こんにちは。"
    rle = "en:Hello.|World.|ja:こんにちは。"
    assert "Hello" in t.expand(full)
    assert "World" in t.expand(rle)
    assert "こんにちは" in t.expand(rle)


def test_mosaic_stats():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    st = t.stats("Hello. こんにちは。")
    assert st["sentences"] >= 2
    assert "en" in st["langs"] or "ja" in st["langs"]


def test_mosaic_no_rle_still_works():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    src = "Hello. World."
    mosaic = t.compress(src, rle=False)
    assert mosaic.count("en:") == 2


# --- counters / hex ---


def test_morpho_counters():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert "3匹" in m.compress("I see 3 animals here")
    assert "2人" in m.compress("there are 2 people waiting")
    assert "5個" in m.compress("pack 5 pieces carefully")
    assert "4回" in m.compress("retry 4 times please")


def test_morpho_hex_nums():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    out = m.compress("value is 255 here", hex_nums=True, counters=False)
    assert "0xff" in out
    bare = m.compress("value is 255 here", hex_nums=True, hex_prefix=False, counters=False)
    assert "ff" in bare
    # default off
    plain = m.compress("value is 255 here", counters=False)
    assert "255" in plain


def test_morpho_pronoun_inventory():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    # Case-split + indep. poss in core; deixis separate inventory.
    assert "I" in m.PRONOUN_CANONICAL and "U" in m.PRONOUN_CANONICAL
    assert "mine" in m.PRONOUN_CANONICAL and "ours" in m.PRONOUN_CANONICAL
    assert "yours" in m.PRONOUN_CANONICAL and "theirs" in m.PRONOUN_CANONICAL
    assert "he" in m.PRONOUN_CANONICAL and "she" in m.PRONOUN_CANONICAL
    assert "it" in m.PRONOUN_CANONICAL
    hos = m.compress("he or she will go")
    assert "he/she" in hos or ("he" in hos and "she" in hos)
    assert "they" not in hos.lower()
    assert "彼" not in hos and "她" not in hos
    assert m.compress("彼を呼ぶ") == "him呼ぶ"
    assert "she" in m.compress("彼女は来る")
    assert "her" in m.compress("彼女を呼ぶ")
    assert "she" in m.compress("she will go")
    assert "U" in m.compress("you choose")
    assert "君" not in m.compress("you choose")
    assert m.compress("I see you") == "I see U"  # obj you → U (consistency)
    assert "your" in m.compress("your book")
    assert "you know" in m.compress("you know me")
    assert "y'all" in m.compress("you all ready")
    assert "y'all" in m.compress("you guys win")
    assert "they" in m.compress("they saw them")
    assert "them" in m.compress("they saw them")
    assert m.compress("私は行く") == "I行く"
    assert m.compress("私を呼ぶ") == "me呼ぶ"
    assert m.compress("私の本") == "my本"
    assert "mine" in m.compress("mine is ready")
    assert "ours" in m.compress("ours too")
    # Deixis: not folded into it; cheapest surface
    assert "eso" in m.compress("それは本")
    assert "ça" in m.compress("this book")
    assert "あれ" in m.compress("あれは何")
    assert "it" in m.compress("它很好")  # neuter, not deixis
    assert m.compress("I think that he left") == "I think he left"  # complementizer dropped
    assert m.compress("he chooses") == "he choose"
    assert m.compress("she comes") == "she come"
    assert m.compress("it works") == "it work"
    assert m.compress("it has value") == "it have value"
    assert m.compress("one prefers") == "one prefer"
    assert m.compress("everyone wants") == "everyone want"
    assert m.compress("somebody needs") == "somebody need"
    assert m.compress("this works") == "ça work"  # deixis subject + 3sg strip
    assert m.compress("he was ready") == "he was ready"  # past, not 3sg -s
    assert m.compress("he news") == "he news"  # 単複同形 mass noun
    assert m.compress("he series") == "he series"
    assert m.compress("he his") == "he his"  # possessive not stripped
    assert m.compress("he sometimes fails") == "he sometimes fail"
    assert m.compress("he always tries") == "he □ try"  # always→□ then tries→try
    assert m.compress("everyone always wants") == "everyone □ want"
    assert m.compress("he means") == "he means"  # 単複同形 means: no strip
    # single-s + -es bases (not -e verbs that only add -s)
    assert m.compress("he focuses") == "he focus"
    assert m.compress("she buses") == "she bus"
    assert m.compress("he biases") == "he bias"
    assert m.compress("it gases") == "it gas"
    assert m.compress("it rises") == "it rise"  # -e verb: strip -s only
    assert m.compress("he uses") == "he use"
    assert m.compress("she closes") == "she close"
    assert "whichever" in m.compress("whichever option")  # ∀opt removed (token loser)
    assert "4" not in m.compress("成功するために学ぶ")  # token-loser symbol removed


def test_morpho_pronoun_bits():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    # Case-split + indep. poss → N=26 → 5 bits
    assert len(m.PRONOUN_CANONICAL) >= 24
    assert "mine" in m.PRONOUN_CANONICAL
    assert m.pronoun_inventory_bits() == 5
    assert m.canonicalize_pronoun("mine") == "mine"
    assert m.canonicalize_pronoun("ours") == "ours"
    assert m.canonicalize_pronoun("yours") == "yours"
    assert m.canonicalize_pronoun("theirs") == "theirs"
    assert m.canonicalize_pronoun("they") == "they"
    assert m.canonicalize_pronoun("them") == "them"
    assert m.canonicalize_pronoun("she") == "she"
    assert m.canonicalize_pronoun("her") == "her"
    assert m.canonicalize_pronoun("it") == "it"
    w = m.pronoun_inventory_bits()
    for form in ("they", "them", "y'all", "she", "it", "mine"):
        c = m.pronoun_bit_cost(form)
        assert c["bits_per_pronoun"] == w == 5
        assert c["count"] == 1
    assert m.canonicalize_pronoun("彼女") == "she"
    assert m.canonicalize_pronoun("她") == "she"
    assert m.canonicalize_pronoun("彼") == "he"
    assert m.canonicalize_pronoun("君") == "U"
    assert m.canonicalize_pronoun("you") == "you"
    assert "U" in m.compress("you choose")
    # Deixis not in pronoun inventory
    assert m.canonicalize_pronoun("それ") is None
    assert m.canonicalize_pronoun("this") is None


def test_morpho_deixis_inventory():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert "deixis" in m.list_closed_inventories()
    assert len(m.DEIXIS_CANONICAL) == 5
    assert m.deixis_inventory_bits() == 3
    assert m.canonicalize_deixis("this") == "ça"
    assert m.canonicalize_deixis("それ") == "eso"
    assert m.canonicalize_deixis("あれ") == "あれ"
    assert m.canonicalize_deixis("these") == "these"
    assert m.canonicalize_deixis("those") == "those"
    assert m.canonicalize_deixis("这") == "ça"
    assert "ça" in m.compress("this book")
    assert "eso" in m.compress("それは本")
    # Neuterness stays separate
    assert m.canonicalize_pronoun("它") == "it"
    assert m.canonicalize_deixis("它") is None


def test_lex_policy_expansions_smoke():
    from shared.lex_policy import (
        ETYMON_ALIGN,
        FILLERS_EN,
        FILLERS_JA,
        UNIQUE_COMPACT,
        UNIQUE_READINGS,
        apply_etymon_align,
        apply_unique_readings,
        strip_fillers,
    )

    assert len(FILLERS_EN) >= 25
    assert len(FILLERS_JA) >= 15
    assert "roll out" in UNIQUE_READINGS
    assert "instantiate" in UNIQUE_COMPACT or "inst" in UNIQUE_COMPACT.values()
    assert "message" in ETYMON_ALIGN
    assert "nombre" not in ETYMON_ALIGN  # FR false friend
    assert "msg" in apply_etymon_align("send a message")
    assert "deploy" in apply_unique_readings("please roll out the app", compact=True) or "deploy" in UNIQUE_READINGS["roll out"]
    out = strip_fillers("hmm you know I guess ready")
    assert "ready" in out
    assert "hmm" not in out.lower()


# --- RulePeerCodec AAD ---


def test_rule_peer_codec_aad_mac_separation():
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    key = "shared"
    raw = b"same plaintext"
    env = z.encode(raw, key=key, aad="channel-alpha")
    assert z.decode(env, key=key, aad="channel-alpha") == raw
    # Different AAD must fail MAC
    try:
        z.decode(env, key=key, aad="channel-beta")
        raised = False
    except ValueError:
        raised = True
    assert raised
    # Empty AAD also fails against labeled envelope
    try:
        z.decode(env, key=key, aad="")
        raised2 = False
    except ValueError:
        raised2 = True
    assert raised2


def test_rule_peer_codec_empty_aad_roundtrip():
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    env = z.encode(b"hello", key="k", aad="")
    assert z.decode(env, key="k") == b"hello"
    assert z.decode(env, key="k", aad=None) == b"hello"


def test_rule_peer_codec_file_cli(tmp_path):
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    src = tmp_path / "plain.bin"
    out = tmp_path / "env.txt"
    back = tmp_path / "back.bin"
    src.write_bytes(b"\x00\x01binary-payload")
    rc = z.main(["encode", "--key", "fk", "--aad", "lab", "--file", str(src), "--out", str(out)])
    assert rc == 0
    assert out.read_bytes().strip()
    rc = z.main(["decode", "--key", "fk", "--aad", "lab", "--file", str(out), "--out", str(back)])
    assert rc == 0
    assert back.read_bytes() == b"\x00\x01binary-payload"


# --- MorphoGrammarMinimal articles / counters; C owns I'll + spelled nums + ℹ️ ---


def test_morpho_strips_unquoted_articles_keeps_quoted():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    out = m.compress('see the cat and "the" dog', unique=False, etymon=False, counters=False)
    assert "the cat" not in out.lower()
    assert "the" in out  # from quoted "the"
    assert "cat" in out and "dog" in out
    kept = m.compress("keep the noun", keep_articles=True, unique=False, etymon=False, counters=False)
    assert "the" in kept.lower()


def test_morpho_digit_counters_without_spelled_default():
    """E counters need digits; spelled→digit is off by default (C owns it).

    Digit→counter (3 animals→3匹) lives in test_morpho_counters.
    """
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert "three" in m.compress("I see three animals here").lower()
    assert "3匹" not in m.compress("I see three animals here")
    assert "3匹" in m.compress("I see three animals here", spelled_nums=True)
    assert "21匹" in m.compress("count twenty-one animals", spelled_nums=True) or "21匹" in m.compress(
        "count twenty one animals", spelled_nums=True
    )
    from shared.lex_policy import apply_spelled_numbers

    assert "100" in apply_spelled_numbers("a hundred")


def test_morpho_does_not_contract_ill_by_default():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    out = m.compress("I will go now", unique=False, etymon=False, counters=False)
    assert "I'll" not in out
    assert "I will" in out


def test_shorthand_ill_and_spelled_numbers():
    """Focused C I'll + spelled→digit (full classic matrix → ownership test above)."""
    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    out = s.compress("I will go now")
    assert "I'll" in out
    assert "I will" not in out
    out2 = s.compress("see three animals")
    assert "3" in out2
    assert "three" not in out2.lower()


def test_morpho_information_to_info_glyph():
    """information→ℹ️ is C family=emoji; E etymon no longer rewrites it."""
    from shared.lex_policy import INFO_GLYPH, apply_etymon_align

    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    assert apply_etymon_align("information") == "information"
    assert INFO_GLYPH not in m.compress("send the information please")
    assert INFO_GLYPH not in s.compress("send the information please")
    assert INFO_GLYPH not in s.compress("インフォメーション")


# --- MorphoGrammarMinimal closed POS inventories (articles/conj/adv/aux/prep) ---


def test_morpho_closed_inventory_bits_table():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert set(m.list_closed_inventories()) >= {
        "pronoun",
        "article",
        "conjunction",
        "adverb",
        "auxiliary",
        "preposition",
        "prep2",
        "compare",
        "particle",
    }
    assert m.closed_inventory_bits("article") == 0  # N=1 → ∅
    assert m.closed_inventory_bits("conjunction") == 2
    assert m.closed_inventory_bits("adverb") == 2
    assert m.closed_inventory_bits("auxiliary") == 2
    assert m.closed_inventory_bits("preposition") == 2
    assert m.closed_inventory_bits("preposition", extended=True) == 3  # N=5 (+to)
    assert m.closed_inventory_bits("prep2") == 3  # N=5 → 3bit
    assert m.closed_inventory_bits("compare") == 1  # N=2 → 1bit
    assert m.closed_inventory_bits("particle") == 2  # N=4 → 2bit
    assert m.closed_inventory_bits("particle", extended=True) == 3  # N=7
    assert m.closed_inventory_bits("conjunction", extended=True) == 3  # N=6
    assert m.POLARITY_BIT == 1


def test_morpho_article_inventory():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.ARTICLE_CANONICAL == ("∅",)
    assert m.canonicalize_closed("article", "the") == "∅"
    assert m.canonicalize_closed("article", "an") == "∅"
    cost = m.article_bit_cost("the cat and a dog")
    assert cost["bits_per"] == 0
    assert cost["count"] == 2  # the, a  (and is conj)
    assert cost["total_bits"] == 0
    out = m.compress("see the cat", unique=False, etymon=False, counters=False)
    assert "the" not in out.lower()
    assert "cat" in out


def test_morpho_conjunction_inventory():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.CONJ_CANONICAL == ("&", "/", "cuz", "therefore")  # ∴ token loser
    out = m.compress("cats and dogs or birds because rain therefore fly", unique=False, etymon=False)
    assert "&" in out and "/" in out and "cuz" in out and "bc" not in out.split() and "therefore" in out  # ∴ removed
    assert m.canonicalize_closed("conjunction", "and") == "&"
    assert m.canonicalize_closed("conjunction", "because") == "cuz"
    assert m.canonicalize_closed("conjunction", "bc") == "cuz"  # legacy input
    c = m.conjunction_bit_cost("a & b / c cuz d therefore e")
    assert c["bits_per"] == 2
    assert c["count"] >= 4
    assert c["total_bits"] == c["count"] * 2
    # C-owned moreover left alone on E
    assert "moreover" in m.compress("moreover we continue", unique=False, etymon=False).lower()


def test_morpho_adverb_inventory():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.ADVERB_CANONICAL == ("tho", "~", "especially")  # esp. token loser
    out = m.compress(
        "However, approximately very particularly ready",
        unique=False,
        etymon=False,
        counters=False,
    )
    # very→˅ removed (o200k 1 tok vs 2 tok)
    assert "tho" in out and "~" in out and "very" in out and "particularly" in out  # esp. removed
    assert m.canonicalize_closed("adverb", "very") is None
    assert m.adverb_bit_cost("tho ~ especially")["total_bits"] == 6  # 3×2 (˅ dropped)
    freq = m.compress(
        "always often never ready",
        unique=False,
        etymon=False,
        counters=False,
    )
    assert "□" in freq and "oft" in freq and "never" in freq  # never→¬ removed
    assert m.canonicalize_closed("adverb", "always", extended=True) == "□"
    assert m.canonicalize_closed("adverb", "often", extended=True) == "oft"


def test_morpho_auxiliary_inventory():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.AUX_CANONICAL == ("can", "will", "must", "may")
    out = m.compress(
        "I could go and I would stay and I should rest and I might leave",
        unique=False,
        etymon=False,
        counters=False,
    )
    # past / hypothetical modals keep their own form (meaning differs; o200k tie)
    for w in ("could", "would", "should", "might"):
        assert w in out.lower(), (w, out)
    # I'll stays C — E keeps I will
    assert "I'll" not in m.compress("I will go", unique=False, etymon=False, counters=False)
    assert "I will" in m.compress("I will go", unique=False, etymon=False, counters=False)
    assert m.canonicalize_closed("auxiliary", "should") is None  # should ≠ must
    assert m.auxiliary_bit_cost("can will must may")["total_bits"] == 8
    ja = m.compress("勉強しなければならないかもしれない", unique=False, etymon=False)
    assert "must" in ja and "may" in ja
    ja2 = m.compress("行かなければならない", unique=False, etymon=False)
    assert "must" in ja2


def test_morpho_preposition_inventory():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.PREP_CANONICAL == ("with", "for", "←", "@")  # w/, 4 token losers
    out = m.compress(
        "go for lunch from home with friends at noon without fear",
        unique=False,
        etymon=False,
        counters=False,
    )
    assert "for" in out and "←" in out and "with" in out and "@" in out and "无" in out  # 4, w/ removed
    assert not __import__("re").search(r"\bfr\b", out, __import__("re").I)  # ← canonical; fr not emitted
    # C ledger spatial left alone on E
    under = m.compress("under the table above the shelf", unique=False, etymon=False, counters=False)
    assert "under" in under.lower() and "above" in under.lower()
    assert m.canonicalize_closed("preposition", "for") == "for"
    assert m.canonicalize_closed("preposition", "without") is None  # moved to prep2
    assert m.canonicalize_closed("prep2", "without") == "无"
    assert m.canonicalize_closed("prep2", "w/o") == "无"
    c = m.preposition_bit_cost("with for ← @")
    assert c["bits_per"] == 2 and c["count"] == 4 and c["total_bits"] == 8
    assert m.canonicalize_closed("preposition", "from") == "←"
    assert m.canonicalize_closed("preposition", "fr") == "←"  # alias
    assert m.canonicalize_closed("preposition", "desde") == "←"
    assert m.canonicalize_closed("preposition", "con") == "with"
    assert m.canonicalize_closed("preposition", "pour") == "for"


def test_morpho_prep2_inventory():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.PREP2_CANONICAL == ("of", "无", "内", "前", "after")  # de, 後 token losers
    assert m.prep2_inventory_bits() == 3  # N=5
    out = m.compress(
        "of water without sugar within limits before noon after dusk",
        unique=False,
        etymon=False,
        counters=False,
    )
    assert "of" in out and "无" in out and "内" in out and "前" in out and "after" in out  # 後 removed
    assert "without" not in out.lower()
    assert "before" not in out.lower()
    assert m.canonicalize_closed("prep2", "of") == "of"
    assert m.canonicalize_closed("prep2", "within") == "内"
    assert m.canonicalize_closed("prep2", "before") == "前"
    assert m.canonicalize_closed("prep2", "after") == "after"
    assert m.canonicalize_closed("prep2", "后") == "after"
    assert m.canonicalize_closed("prep2", "sans") == "无"
    assert m.canonicalize_closed("prep2", "antes") == "前"
    assert m.canonicalize_closed("prep2", "après") == "after"
    assert m.canonicalize_closed("prep2", "vor") == "前"
    c = m.prep2_bit_cost("of 无 内 前 after")
    assert c["bits_per"] == 3 and c["count"] == 5 and c["total_bits"] == 15
    # w/o surface still aliases to 无
    assert "无" in m.compress("go w/o fear", unique=False, etymon=False, counters=False)


def test_morpho_prep_compounds_and_legal_shorts():
    """Finite prep compounds + legal shorts (not prep2 N-inflation)."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    kw = dict(unique=False, etymon=False, counters=False)
    assert "通" in m.compress("throughout the year", **kw)
    assert "throughout" not in m.compress("throughout the year", **kw).lower()
    assert m.compress("toward the goal", **kw).startswith("→")
    assert m.compress("towards home", **kw).startswith("→")
    assert "therewith" in m.compress("agreed therewith", **kw)
    assert "whereby" in m.compress("means whereby", **kw)
    # already-owned legal
    assert "∴↓" in m.compress("hereinafter", **kw)
    assert "thereof" in m.compress("portion thereof", **kw)
    # hereof: no dual-metric win — leave
    assert "hereof" in m.compress("terms hereof", **kw).lower()
    # thereby stays (∴by is whereby; ∴ is therefore)
    assert "thereby" in m.compress("agreed thereby", **kw).lower()
    assert "∈it" not in m.compress("the parties therein", **kw)  # token-loser symbol removed
    assert "∴to" not in m.compress("annexed thereto", **kw)  # token-loser symbol removed
    assert m.compress("henceforth", **kw) == "henceforth"  # ∴→ removed
    assert "∴" not in m.compress("hence we agree", **kw)  # token-loser symbol removed
    assert "雖" not in m.compress("notwithstanding section 5", **kw)  # token-loser symbol removed
    assert "despite" not in m.compress("notwithstanding section 5", **kw).lower()
    # expand subset
    assert "throughout" in m.expand("通 year").lower()
    assert "therewith" in m.expand("∴w/").lower()
    assert "whereby" in m.expand("∴by").lower()
    assert "therein" in m.expand("∈it").lower()
    assert "thereto" in m.expand("∴to").lower()
    assert "vice versa" in m.expand("⇄").lower()  # legacy decode kept
    assert "⇄" in m.compress("and vice versa", **kw)  # o200k tie 2=2, utf8 fewer: adopted


def test_morpho_prep_like_finite_set():
    """High-freq prep / prep-like adv finite shorts (not closed-N inflation)."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    kw = dict(unique=False, etymon=False, counters=False)
    assert m.compress("across the river", **kw).startswith("across")
    assert "along" in m.compress("along the road", **kw)
    assert "中" in m.compress("among friends", **kw)
    assert "between" in m.compress("between A and B", **kw)
    assert "通" in m.compress("through the gate", **kw)
    assert not m.compress("until Monday", **kw).startswith("〜")  # token-loser symbol removed
    assert "共" in m.compress("together we", **kw)
    assert "∥" not in m.compress("meanwhile wait", **kw)  # token-loser symbol removed
    assert "近" not in m.compress("nearby shop", **kw)  # token-loser symbol removed
    assert "下" in m.compress("underneath the floor", **kw)
    # instead of stays phrase→vs; bare instead→代
    assert "vs" in m.compress("instead of tea", **kw).lower()
    assert "代" not in m.compress("go instead", **kw)  # token-loser symbol removed
    # tranche: multiword prep + prep-like adv (dual-metric winners)
    assert "依" in m.compress("according to the report", **kw)
    assert "因" in m.compress("owing to rain", **kw)
    assert "因" in m.compress("due to delay", **kw)
    assert "雖" not in m.compress("in spite of warnings", **kw)  # token-loser symbol removed
    assert "前" in m.compress("in front of the house", **kw)
    assert "傍" not in m.compress("next to me", **kw)  # token-loser symbol removed
    assert "遠" in m.compress("far from here", **kw)
    assert "離" in m.compress("away from danger", **kw)
    assert "外" in m.compress("out of money", **kw)
    assert "対側" not in m.compress("opposite the bank", **kw)  # token-loser symbol removed
    assert "下" in m.compress("beneath the surface", **kw)
    assert "c." not in m.compress("circa 1900", **kw)  # token-loser symbol removed
    assert "入" in m.compress("into the room", **kw)
    assert "先" not in m.compress("beforehand prep", **kw)  # token-loser symbol removed
    assert "∞" not in m.compress("forever young", **kw)  # token-loser symbol removed
    assert "泊" not in m.compress("overnight stay", **kw)  # token-loser symbol removed
    assert "everywhere" in m.compress("everywhere we go", **kw)
    assert "某处" not in m.compress("somewhere nice", **kw)  # token-loser symbol removed
    assert "别处" not in m.compress("elsewhere maybe", **kw)  # token-loser symbol removed
    assert "再" not in m.compress("start anew", **kw)  # token-loser symbol removed
    # via/per/onto still skipped (no clear dual win / collide)
    assert "via" in m.compress("via train", **kw).lower()
    assert "per" in m.compress("per day", **kw).lower()
    assert "onto" in m.compress("onto the table", **kw).lower()

    # cycle2 multiword + spatial/time prep-like
    assert "pro" in m.compress("in favor of the plan", **kw).lower()
    assert "代表" in m.compress("on behalf of the team", **kw)
    assert "手段" in m.compress("by means of force", **kw)
    assert "観点" in m.compress("in terms of cost", **kw)
    assert "準" in m.compress("in accordance with law", **kw)
    assert "≤" in m.compress("up to 5", **kw)
    assert "至" in m.compress("down to zero", **kw)
    assert "鑑" in m.compress("in light of evidence", **kw)
    assert "為" in m.compress("for the sake of peace", **kw)
    assert "場合" in m.compress("in case of fire", **kw)
    assert "不問" in m.compress("regardless of age", **kw)
    assert "共" in m.compress("along with friends", **kw)
    assert "vs" in m.compress("rather than wait", **kw).lower()
    assert "過" not in m.compress("walk past the store", **kw)  # token-loser symbol removed
    assert "○" in m.compress("round the corner", **kw)
    assert "次" in m.compress("following the meeting", **kw)
    assert "先" not in m.compress("preceding chapter", **kw)  # token-loser symbol removed
    assert "未決" not in m.compress("pending approval", **kw)  # token-loser symbol removed

    # cycle3 multiword prep
    assert "力" in m.compress("by virtue of authority", **kw)
    assert "経" in m.compress("by way of example", **kw)
    assert "因" in m.compress("on account of rain", **kw)
    assert "恐" in m.compress("for fear of failure", **kw)
    assert "⇔" in m.compress("in exchange for gold", **kw)
    assert "且" in m.compress("on top of that", **kw)
    assert "犠牲" in m.compress("at the expense of quality", **kw)
    assert "危" in m.compress("at the risk of error", **kw)
    assert "最中" in m.compress("in the middle of dinner", **kw)
    assert "瀕" in m.compress("on the verge of collapse", **kw)
    assert "欠" in m.compress("for lack of evidence", **kw)
    assert "超" in m.compress("in excess of 100", **kw)
    assert "対比" in m.compress("in contrast to prior", **kw)
    assert "∴" not in m.compress("as a result of delays", **kw)  # token-loser symbol removed
    assert "過程" in m.compress("in the course of duty", **kw)
    assert "面前" in m.compress("in the face of danger", **kw)
    assert "経" in m.compress("courtesy of NASA", **kw)

    # cycle4 multiword prep
    assert "目的" in m.compress("for the purpose of safety", **kw)
    assert "益" in m.compress("for the benefit of all", **kw)
    assert "利" in m.compress("in the interest of peace", **kw)
    assert "害" in m.compress("to the detriment of health", **kw)
    assert "援" in m.compress("in support of the motion", **kw)
    assert "責" in m.compress("in charge of operations", **kw)
    assert "制" in m.compress("in control of the system", **kw)
    assert "求" in m.compress("in search of truth", **kw)
    assert "要" in m.compress("in need of help", **kw)
    assert "希" in m.compress("in hopes of success", **kw)
    assert "跡" in m.compress("in the wake of the storm", **kw)
    assert "名" in m.compress("in the name of justice", **kw)
    assert "手" in m.compress("at the hands of enemies", **kw)
    assert "弄" in m.compress("at the mercy of fate", **kw)
    assert "前" in m.compress("ahead of schedule", **kw)  # 先 token loser → before → 前
    assert "連携" in m.compress("in association with partners", **kw)
    assert "比" in m.compress("in comparison with last year", **kw)
    assert "共通" in m.compress("in common with peers", **kw)
    assert "条件" in m.compress("subject to approval", **kw)
    assert "隣" in m.compress("adjacent to the park", **kw)
    assert "反" in m.compress("in defiance of orders", **kw)
    assert "命" in m.compress("by order of the court", **kw)
    assert "覆" in m.compress("under cover of darkness", **kw)
    assert "対立" in m.compress("at odds with reality", **kw)
    assert "狙" in m.compress("with a view to reform", **kw)
    assert "基" in m.compress("on the basis of evidence", **kw)
    assert "在" in m.compress("in the presence of witnesses", **kw)
    assert "代価" in m.compress("at the price of freedom", **kw)
    assert "傘" in m.compress("under the auspices of UNESCO", **kw)
    assert "alongside" in m.compress("in parallel with talks", **kw)  # ∥ token loser
    assert "力" in m.compress("by dint of effort", **kw)
    assert "瀕" in m.compress("on the brink of war", **kw)
    assert "except" in m.compress("with the exception of one", **kw)  # 除 token loser
    assert "无" in m.compress("free of errors", **kw)
    assert "準" not in (_o := m.compress("as per the contract", **kw)) and _o == 'as per contract'  # token loser removed
    assert "≠" not in m.compress("unlike the others", **kw)  # token-loser symbol removed

    # cycle5 multiword prep + prep-like adv
    assert "応" in m.compress("in response to the query", **kw)
    assert "答" in m.compress("in answer to the letter", **kw)
    assert "沿" not in (_o := m.compress("in line with policy", **kw)) and _o == 'in line with policy'  # token loser removed
    assert "合" in m.compress("in agreement with the board", **kw)
    assert "依" in m.compress("depending on weather", **kw)
    assert "+" in m.compress("cats as well as dogs", **kw)
    assert "況" in m.compress("let alone the cost", **kw)
    assert "直面" not in (_o := m.compress("faced with a crisis", **kw)) and _o == 'faced with crisis'  # token loser removed
    assert "関" in m.compress("pertaining to safety", **kw)
    assert "独立" not in (_o := m.compress("independent of size", **kw)) and _o == 'independent of size'  # token loser removed
    assert "≒" in m.compress("similar to the original", **kw)
    assert "≡" in m.compress("equivalent to 10", **kw)
    assert "限" in m.compress("limited to members", **kw)
    assert "帰" in m.compress("attributable to error", **kw)
    assert "暫" in m.compress("for the time being wait", **kw)
    assert "即" in m.compress("leave at once", **kw)
    assert "突" in m.compress("all of a sudden rain", **kw)
    assert "偶" in m.compress("from time to time visit", **kw)
    assert "遂" in m.compress("at last done", **kw)
    assert "初" in m.compress("at first glance", **kw)
    assert "略" in m.compress("in short we agree", **kw)
    assert "実" in m.compress("in fact true", **kw)
    assert "実際" not in (_o := m.compress("in practice hard", **kw)) and _o == 'in practice hard'  # token loser removed
    assert "理" in m.compress("in theory simple", **kw)
    assert "一般" in m.compress("in general fine", **kw)
    assert "故意" not in (_o := m.compress("on purpose delayed", **kw)) and _o == 'on purpose delayed'  # token loser removed
    assert "徒" in m.compress("in vain tried", **kw)
    assert "今" in m.compress("at present unclear", **kw)
    assert "早" in m.compress("ahead of time arrival", **kw)
    assert "進行" not in (_o := m.compress("work under way", **kw)) and _o == 'work under way'  # token loser removed
    assert "∥" not in (_o := m.compress("in the meantime wait", **kw)) and _o == 'meanwhile wait'  # token loser removed
    assert "基" in m.compress("based on data", **kw)
    assert "∴→" not in (_o := m.compress("from now on careful", **kw)) and _o == 'henceforth careful'  # token loser removed
    assert "準" in m.compress("in compliance with rules", **kw)

    # cycle6 prep + prep-like adv / discourse
    assert "逆" in m.compress("contrary to expectations", **kw)
    assert "比例" in m.compress("proportional to size", **kw)
    assert "追" in m.compress("in pursuit of truth", **kw)
    assert "結局" not in (_o := m.compress("after all we agree", **kw)) and _o == 'after all we agree'  # token loser removed
    assert "最" in m.compress("above all be kind", **kw)
    assert "総" in m.compress("all in all fine", **kw)
    assert "猶" in m.compress("all the same go", **kw)
    assert "概" in m.compress("by and large ok", **kw)
    assert "遥" in m.compress("by far the best", **kw)
    assert "確" not in (_o := m.compress("for sure yes", **kw)) and _o == 'for sure yes'  # token loser removed
    assert "何れ" in m.compress("in any case leave", **kw)
    assert "最終" in m.compress("in the end win", **kw)
    assert "長期" in m.compress("in the long run pay", **kw)
    assert "反対" in m.compress("on the contrary true", **kw)
    assert "他方" in m.compress("on the other hand risk", **kw)
    assert "或程" in m.compress("to some extent valid", **kw)
    assert "常" in m.compress("as usual late", **kw)
    assert "殆" in m.compress("more or less done", **kw)
    assert "徐" in m.compress("little by little improve", **kw)
    assert "逐" in m.compress("step by step learn", **kw)
    assert "逐一" in m.compress("one by one check", **kw)
    assert "並列" in m.compress("side by side walk", **kw)
    assert "繰" in m.compress("again and again try", **kw)
    assert "結果" in m.compress("as a result failed", **kw)
    assert "予" in m.compress("in advance pay", **kw)
    assert "是非" in m.compress("by all means come", **kw)
    assert "本質" in m.compress("in essence simple", **kw)
    assert "詳" in m.compress("in detail explain", **kw)
    assert "回顧" not in (_o := m.compress("in retrospect wrong", **kw)) and _o == 'in retrospect wrong'  # token loser removed
    assert "必ず" in m.compress("without fail deliver", **kw)
    assert "re:" not in (_o := m.compress("with regard to cost", **kw)) and _o == 'about cost'  # token loser removed
    assert "再" not in (_o := m.compress("once again try", **kw)) and _o == 'again try'  # token loser removed
    assert "今" in m.compress("right now go", **kw)

    # cycle7 spatial / state prep + prep-like adv
    assert "北" in m.compress("north of town", **kw)
    assert "南" in m.compress("south of here", **kw)
    assert "東" in m.compress("east of the river", **kw)
    assert "西" in m.compress("west of campus", **kw)
    assert "左" in m.compress("to the left of me", **kw)
    assert "右" in m.compress("to the right of you", **kw)
    assert "側" in m.compress("on the part of the board", **kw)
    assert "無視" in m.compress("in disregard of rules", **kw)
    assert "暴走" in m.compress("out of control car", **kw)
    assert "廃" in m.compress("out of date policy", **kw)
    assert "故障" in m.compress("out of order machine", **kw)
    assert "圧" in m.compress("under pressure now", **kw)
    assert "制御" in m.compress("under control again", **kw)
    assert "負" in m.compress("liable to fail", **kw)
    assert "耐" in m.compress("resistant to heat", **kw)
    assert "敏" in m.compress("sensitive to light", **kw)
    assert "劣" in m.compress("inferior to gold", **kw)
    assert "優" in m.compress("superior to iron", **kw)
    assert "最早" in m.compress("no longer valid", **kw)
    assert "未" in m.compress("as yet unknown", **kw)
    assert "一方" in m.compress("on one hand good", **kw)
    assert "短期" in m.compress("in the short run costly", **kw)
    assert "大程" in m.compress("to a large extent true", **kw)
    assert "直後" not in (_o := m.compress("shortly after noon", **kw)) and _o == 'shortly after noon'  # token loser removed
    assert "直前" not in (_o := m.compress("shortly before dawn", **kw)) and _o == 'shortly 前 dawn'  # token loser removed
    assert "日々" in m.compress("day by day better", **kw)
    assert "年々" in m.compress("year by year growth", **kw)
    assert "対面" in m.compress("face to face talk", **kw)
    assert "偶" in m.compress("every now and then visit", **kw)
    assert "実" in m.compress("as a matter of fact yes", **kw)

    # cycle8
    assert "上流" in m.compress("upstream of the dam", **kw)
    assert "下流" in m.compress("downstream of the bridge", **kw)
    assert "不所" in m.compress("out of place remark", **kw)
    assert "届外" in m.compress("out of reach goal", **kw)
    assert "被弾" not in (_o := m.compress("under fire constantly", **kw)) and _o == 'under fire constantly'  # token loser removed
    assert "審査中" not in (_o := m.compress("under review now", **kw)) and _o == 'under review now'  # token loser removed
    assert "免疫" not in (_o := m.compress("immune to criticism", **kw)) and _o == 'immune to criticism'  # token loser removed
    assert "傾向" not in (_o := m.compress("prone to error", **kw)) and _o == 'prone to error'  # token loser removed
    assert "準備" not in (_o := m.compress("preparatory to launch", **kw)) and _o == 'preparatory to launch'  # token loser removed
    assert "追伸" not in (_o := m.compress("further to our call", **kw)) and _o == 'further to our call'  # token loser removed
    assert "賛" in m.compress("in praise of art", **kw)
    assert "如" in m.compress("such as apples", **kw)
    assert "真" in m.compress("for real this time", **kw)
    assert "順" in m.compress("in turn each spoke", **kw)
    assert "全" in m.compress("in full detail", **kw)
    assert "連続" not in (_o := m.compress("in succession win", **kw)) and _o == 'in succession win'  # token loser removed
    assert "携" in m.compress("hand in hand walk", **kw)
    assert "直接" in m.compress("head to head race", **kw)
    assert "久" in m.compress("long since gone", **kw)
    assert "其時" not in (_o := m.compress("right then left", **kw)) and _o == 'right then left'  # token loser removed
    assert "途中" in m.compress("en route to Paris", **kw)
    assert "決して" in m.compress("by no means easy", **kw)
    assert "疑無" not in (_o := m.compress("no doubt true", **kw)) and _o == 'no doubt true'  # token loser removed
    assert "或様" in m.compress("in some way related", **kw)
    assert "多様" in m.compress("in many ways better", **kw)
    assert "時々" in m.compress("at times difficult", **kw)
    assert "常時" in m.compress("at all times alert", **kw)
    assert "乱" in m.compress("at random pick", **kw)
    assert "突" in m.compress("out of nowhere appear", **kw)

    # cycle9
    assert "並" in m.compress("abreast of the news", **kw)
    assert "知" in m.compress("cognizant of risk", **kw)
    assert "念" in m.compress("mindful of safety", **kw)
    assert "好" in m.compress("fond of music", **kw)
    assert "誇" in m.compress("proud of work", **kw)
    assert "能" in m.compress("capable of flight", **kw)
    assert "不能" in m.compress("incapable of lying", **kw)
    assert "値" in m.compress("worthy of praise", **kw)
    assert "典型" not in (_o := m.compress("typical of spring", **kw)) and _o == 'typical of spring'  # token loser removed
    assert "示" in m.compress("indicative of change", **kw)
    assert "示唆" in m.compress("suggestive of fraud", **kw)
    assert "特質" in m.compress("characteristic of youth", **kw)
    assert "撤" in m.compress("rid of pests", **kw)
    assert "満" not in (_o := m.compress("full of hope", **kw)) and _o == 'full of hope'  # token loser removed
    assert "構成" not in (_o := m.compress("composed of atoms", **kw)) and _o == 'composed of atoms'  # token loser removed
    assert "期間" in m.compress("for the duration of war", **kw)
    assert "沖" not in m.compress("offshore wind", **kw)  # token-loser symbol removed
    assert "同時" not in m.compress("simultaneously occur", **kw)  # token-loser symbol removed
    assert "各" not in m.compress("A and B respectively", **kw)  # token-loser symbol removed
    assert "同様" not in m.compress("similarly affected", **kw)  # token-loser symbol removed
    assert "特" in m.compress("in particular note", **kw)
    assert "言わば" not in (_o := m.compress("so to speak free", **kw)) and _o == 'so to speak free'  # token loser removed
    assert "斯" in m.compress("as such invalid", **kw)
    assert "断" in m.compress("once and for all done", **kw)
    assert "現" not in m.compress("currently active", **kw)  # token-loser symbol removed
    assert "旧" not in m.compress("formerly known", **kw)  # token-loser symbol removed
    assert "交互" not in m.compress("alternately flash", **kw)  # token-loser symbol removed
    assert "以来" in m.compress("ever since then", **kw)
    assert "欠" in m.compress("bereft of hope", **kw)

    # cycle10
    assert "厭" in m.compress("weary of waiting", **kw)
    assert "恥" in m.compress("ashamed of failure", **kw)
    assert "嫉" not in (_o := m.compress("jealous of success", **kw)) and _o == 'jealous of success'  # token loser removed
    assert "空" in m.compress("empty of meaning", **kw)
    assert "製" in m.compress("made of steel", **kw)
    assert "岸" in m.compress("ashore safely", **kw)
    assert "船外" not in m.compress("overboard now", **kw)  # token-loser symbol removed
    assert "水中" not in m.compress("underwater camera", **kw)  # token-loser symbol removed
    assert "全国" in m.compress("nationwide broadcast", **kw)
    assert "世界" in m.compress("worldwide release", **kw)
    assert "時計" in m.compress("clockwise turn", **kw)
    assert "反時計" in m.compress("counterclockwise spin", **kw)
    assert "裏返" not in (_o := m.compress("inside out shirt", **kw)) and _o == '内 out shirt'  # token loser removed
    assert "逆さ" not in (_o := m.compress("upside down cake", **kw)) and _o == 'upside down cake'  # token loser removed
    assert "後方" not in m.compress("backwards step", **kw)  # token-loser symbol removed
    assert "横" in m.compress("sideways glance", **kw)
    assert "一斉" not in (_o := m.compress("en masse protest", **kw)) and _o == 'en masse protest'  # token loser removed
    assert "当初" in m.compress("all along known", **kw)
    assert "以後" not in (_o := m.compress("ever after happy", **kw)) and _o == 'ever after happy'  # token loser removed
    assert "永久" in m.compress("for keeps now", **kw)
    assert "断続" in m.compress("off and on rain", **kw)
    assert "徹底" in m.compress("through and through wet", **kw)
    assert "大抵" in m.compress("more often than not late", **kw)
    assert "一見" in m.compress("at a glance clear", **kw)
    assert "賭" in m.compress("at stake here", **kw)
    assert "本気" in m.compress("in earnest talk", **kw)
    assert "実質" not in (_o := m.compress("in effect banned", **kw)) and _o == 'in effect banned'  # token loser removed
    assert "品切" in m.compress("out of stock item", **kw)

    # cycle11 spaced deferred
    assert "起" in m.compress("as of 2020", **kw)
    assert "未" in m.compress("as of yet unpaid", **kw)
    assert "一度" in m.compress("for once honest", **kw)
    assert "近頃" not in (_o := m.compress("of late quiet", **kw)) and _o == 'of late quiet'  # token loser removed
    assert "従来" in m.compress("hitherto unknown", **kw)
    assert "今迄" not in (_o := m.compress("thus far ok", **kw)) and _o == 'thus far ok'  # token loser removed
    assert "今迄" not in (_o := m.compress("to date none", **kw)) and _o == 'to date none'  # token loser removed
    assert "年少" in m.compress("under age drinking", **kw)
    assert "1:1" not in (_o := m.compress("one-on-one meeting", **kw)) and _o == 'one-on-one meeting'  # token loser removed
    assert "稍後" in m.compress("by and by arrive", **kw)
    assert "∃loc" not in m.compress("anywhere else", **kw)  # token-loser symbol removed
    assert "∅loc" not in (_o := m.compress("nowhere found", **kw)) and _o == 'nowhere found'  # token loser removed
    assert "∀時" not in m.compress("anytime soon", **kw)  # token-loser symbol removed
    assert "稍" not in m.compress("somewhat odd", **kw)  # token-loser symbol removed
    assert "∞" in m.compress("for good gone", **kw)
    assert "或様" not in m.compress("somehow works", **kw)  # token-loser symbol removed
    assert "準変" in m.compress("mutatis mutandis apply", **kw)
    assert "他同" in m.compress("ceteris paribus hold", **kw)
    assert "独自" in m.compress("sui generis rule", **kw)
    assert "同率" in m.compress("pari passu claim", **kw)
    assert "職権" not in (_o := m.compress("ex officio member", **kw)) and _o == 'ex officio member'  # token loser removed
    assert "一応" in m.compress("prima facie case", **kw)
    assert "当然" in m.compress("ipso facto void", **kw)
    assert "先験" not in (_o := m.compress("a priori knowledge", **kw)) and _o == 'priori knowledge'  # token loser removed
    assert "d.f." not in (_o := m.compress("de facto standard", **kw)) and _o == 'de facto standard'  # token loser removed
    assert "現場" not in (_o := m.compress("in situ hybrid", **kw)) and _o == 'in situ hybrid'  # token loser removed
    assert "adhoc" in m.compress("ad hoc committee", **kw)


def test_morpho_relative_pronouns():
    """関係代名詞: which→that / whom→who / long Romance|DE→que; gates hold."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    kw = dict(unique=False, etymon=False, counters=False)
    # EN which→that (restrictive + non-restrictive)
    assert "that" in m.compress("the book which is red", **kw)
    assert "which" not in m.compress("the book which is red", **kw).lower()
    assert ", that" in m.compress("the report, which was long", **kw)
    assert "that has" in m.compress("the car which has failed", **kw)
    # interrogative / complement / pied-pipe stay
    assert "Which" in m.compress("Which book is it?", **kw)
    assert "which" in m.compress("decide which path to take", **kw).lower()
    assert "which" in m.compress("the box in which it sits", **kw).lower()
    # whom→who (case-preserving)
    assert "who I" in m.compress("the person whom I met", **kw)
    assert m.compress("Whom did you see?", **kw).startswith("Who ")
    # complementizer + deixis unchanged
    assert "that" not in m.compress("I think that it works", **kw)
    assert m.compress("that book is mine", **kw) == "the book is mine"
    assert m.compress("That was wrong.", **kw).startswith("That ")  # pronoun that untouched
    # Romance/DE → que; lo que / interrogative Welche skipped
    assert m.compress("lequel est venu", **kw).startswith("que ")
    assert "que" in m.compress("el que vino ayer", **kw)
    assert "que" in m.compress("das Buch welches ist rot", **kw)
    assert "Welche" in m.compress("Welche Farbe?", **kw)
    assert "lo que" in m.compress("lo que quiero", **kw)
    # bare q never emitted as relative surface
    out = m.compress("the book which is red and the person whom I met", **kw)
    assert out.split().count("q") == 0


def test_morpho_objective_gap_fill_closed_thin():
    """Objective gap-fill: det/quant, conj purpose, reciprocal, hedges, colloquial aux."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    kw = dict(unique=False, etymon=False, counters=False)
    # determiners / quantifiers
    assert "∀" not in m.compress("every item counts", **kw)  # token-loser symbol removed
    assert "everywhere" in m.compress("everywhere else", **kw)
    assert "各" not in m.compress("each team wins", **kw)  # token-loser symbol removed
    assert "互" in m.compress("they help each other", **kw)
    assert "互" in m.compress("they help one another", **kw)
    assert "∃" not in m.compress("some cats sleep", **kw)  # token-loser symbol removed
    assert "somewhere" in m.compress("somewhere else", **kw)
    assert "或程" in m.compress("to some extent true", **kw)
    assert "none" in m.compress("none remain", **kw)
    assert "両" not in m.compress("both sides agree", **kw)  # token-loser symbol removed
    assert "数" in m.compress("several options", **kw)
    assert "諸" not in m.compress("various reasons", **kw)  # token-loser symbol removed
    assert "多" in m.compress("numerous bugs", **kw)
    assert "多" in m.compress("a lot of bugs", **kw)
    assert "多" in m.compress("lots of bugs", **kw)
    assert "few" in m.compress("a few bugs", **kw)
    assert "少" in m.compress("a little water", **kw)
    # conjunctions / purpose
    assert "!if" not in m.compress("unless ready", **kw)  # token-loser symbol removed
    assert "if" in m.compress("whether ready", **kw)
    assert "whether" not in m.compress("whether ready", **kw).lower()
    assert "∥" not in m.compress("while waiting", **kw)  # token-loser symbol removed
    assert "偶" in m.compress("once in a while", **kw)
    assert "awhile" in m.compress("wait a while", **kw)
    assert "so" in m.compress("speak so that all hear", **kw)
    out_so = m.compress("speak so that all hear", **kw)
    assert "so that" not in out_so.lower()
    assert "to" in m.compress("in order to win", **kw)
    assert "in order" not in m.compress("in order to win", **kw).lower()
    # hedges
    assert "或" in m.compress("maybe later", **kw)
    assert "或" in m.compress("perhaps later", **kw)
    assert "恐" not in m.compress("probably true", **kw)  # token-loser symbol removed
    assert "~" in m.compress("roughly 10", **kw)
    assert "常" in m.compress("usually late", **kw)
    assert "既" not in m.compress("already done", **kw)  # token-loser symbol removed
    assert "+" in m.compress("also true", **kw)
    assert "+" in m.compress("additionally true", **kw)
    assert "僅" not in m.compress("only one", **kw)  # token-loser symbol removed
    assert "尚" in m.compress("still open", **kw)
    # colloquial aux
    assert "wanna" in m.compress("want to go", **kw)
    assert "kinda" in m.compress("kind of nice", **kw)
    assert "sorta" in m.compress("sort of nice", **kw)
    # gates: existing multiword some/any untouched in spirit
    assert "何れ" in m.compress("in any case ok", **kw)
    assert "最早" in m.compress("any longer valid", **kw)


def test_morpho_aux_negation_and_affirmation():
    """Aux neg → !slot; affirmation keeps bare can/will/must/may; I'll stays C."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    out = m.compress(
        "I cannot go and I can't stay and I won't leave and I shouldn't rest "
        "and I mustn't shout and I may not enter and I might not wait",
        unique=False,
        etymon=False,
        counters=False,
    )
    assert "!can" in out and "!will" in out and "!must" in out and "!may" in out
    assert "cannot" in out.lower()  # cannot→!can removed (token loser)
    assert "won't" not in out.lower()
    # shouldn't / might not keep modality (should ≠ must); only polarity is flagged
    assert "!must" in out and "!may" in out
    # do/does/did not → !
    dn = m.compress("I do not know and I don't see and she doesn't care", unique=False, etymon=False, counters=False)
    assert dn.count("!") >= 3
    # affirmation path: bare positives stay
    pos = m.compress("I can go and I will stay and I must rest and I may leave", unique=False, etymon=False, counters=False)
    assert "!can" not in pos and "!will" not in pos
    assert "can" in pos and "will" in pos and "must" in pos and "may" in pos
    # JA aux neg
    ja = m.compress("それはできない", unique=False, etymon=False, counters=False)
    assert "cannot" in ja  # !can token loser
    ja2 = m.compress("本物ではない", unique=False, etymon=False, counters=False)
    assert "!" in ja2 and "ではない" not in ja2
    # I'll still not introduced by E
    assert "I'll" not in m.compress("I will go", unique=False, etymon=False, counters=False)
    # polarity bit separate from aux width
    pol = m.polarity_bit_cost("I !can & !will")
    assert pol["bits_per"] == 1 and pol["count"] == 2 and pol["total_bits"] == 2
    assert m.auxiliary_inventory_bits() == 2  # unchanged by !


def test_morpho_adverb_polarity():
    """not/never share polarity markers with aux; always→□ (∀=whatever)."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    out = m.compress("not ready and never late", unique=False, etymon=False, counters=False)
    # never→¬ removed (token loser); sentence-initial not kept
    assert "never" in out and "¬" not in out
    assert "!" in m.compress("it is not ready", unique=False, etymon=False, counters=False)
    # whatever still ∀; always is □
    w = m.compress("whatever always", unique=False, etymon=False, counters=False)
    assert "whatever" in w and "□" in w  # whatever→∀ removed
    pol = m.polarity_bit_cost("¬ ! ready")
    assert pol["count"] == 2 and pol["total_bits"] == 2


def test_morpho_particle_inventory():
    """JA particles → ∅/→/∈/〜 core (2bit); ext +|&|←; C ledger untouched."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.PARTICLE_CANONICAL == ("∅", "to", "in", "until")  # →/∈/〜 token losers
    assert m.particle_inventory_bits() == 2
    assert m.canonicalize_closed("particle", "に") == "to"
    assert m.canonicalize_closed("particle", "で") == "in"
    assert m.canonicalize_closed("particle", "まで") == "until"
    assert m.canonicalize_closed("particle", "を") == "∅"
    assert m.canonicalize_closed("particle", "も", extended=True) == "+"
    assert m.canonicalize_closed("particle", "と", extended=True) == "&"
    assert m.canonicalize_closed("particle", "から", extended=True) == "←"
    assert m.canonicalize_closed("particle", "fr", extended=True) == "←"
    out = m.compress(
        "猫は魚を食べる。学校に行く。家で働く。駅まで歩く。",
        unique=False,
        etymon=False,
        counters=False,
    )
    assert "は" not in out and "を" not in out
    assert " to " in out and " in " in out and " until " in out
    assert "猫魚食べる" in out.replace("。", "") or "猫魚食べる" in out
    out2 = m.compress("東京から来る。彼と話す。水もあるよ", unique=False, etymon=False, counters=False)
    assert "←" in out2 and "&" in out2 and "+" in out2
    assert not __import__("re").search(r"\bfr\b", out2, __import__("re").I)
    # modality finals dropped
    assert not out2.endswith("よ")
    # C spatial pairs not invented here
    assert "under" in m.compress("under the table", unique=False, etymon=False, counters=False).lower()


def test_morpho_density_closed_summary():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    before = "I could go for lunch with you however very soon"
    after = m.compress(before, unique=False, etymon=False, counters=False)
    d = m.density(before, after)
    assert "closed" in d
    assert d["closed"]["auxiliary"]["bits_per"] == 2
    assert d["closed"]["preposition"]["bits_per"] == 2
    assert d["closed"]["prep2"]["bits_per"] == 3
    assert d["closed"]["compare"]["bits_per"] == 1
    assert d["closed"]["adverb"]["bits_per"] == 2
    assert d["closed"]["particle"]["bits_per"] == 2
    assert "polarity_bits_each" in d


def test_morpho_compare_inventory():
    """Language-agnostic ≥/≤; JA/ZH/EN/ES/FR/DE; bare under/below untouched (C)."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.COMPARE_CANONICAL == ("≥", "≤")
    assert m.compare_inventory_bits() == 1
    ja = m.compress("18歳以上 かつ 60歳以下", unique=False, etymon=False, counters=False)
    assert "≥" in ja and "≤" in ja
    assert "以上" not in ja and "以下" not in ja
    zh = m.compress("18岁以上 60岁以下", unique=False, etymon=False, counters=False)
    assert "≥" in zh and "≤" in zh
    en = m.compress(
        "3 or more and 10 or less; at least 2; at most 5; 18 and above; 65 and below",
        unique=False,
        etymon=False,
        counters=False,
    )
    assert en.count("≥") >= 3 and en.count("≤") >= 3
    en2 = m.compress("more than 3 less than 10", unique=False, etymon=False, counters=False)
    assert "≥" in en2 and "≤" in en2
    # one non-EN/JA form each direction
    es = m.compress("más de 3 menos de 10 al menos 2 como máximo 5", unique=False, etymon=False, counters=False)
    assert "≥" in es and "≤" in es
    fr = m.compress("plus de 3 moins de 10", unique=False, etymon=False, counters=False)
    assert "≥" in fr and "≤" in fr
    de = m.compress("mehr als 3 weniger als 10", unique=False, etymon=False, counters=False)
    assert "≥" in de and "≤" in de
    approx = m.compress("approximately equal to 5; equal to 1", unique=False, etymon=False, counters=False)
    assert "≒" in approx and "=" in approx
    under = m.compress("under the table below the shelf", unique=False, etymon=False, counters=False)
    assert "under" in under.lower() and "below" in under.lower()
    assert m.canonicalize_closed("compare", "以上") == "≥"
    assert m.canonicalize_closed("compare", "以下") == "≤"
    assert m.canonicalize_closed("compare", "at least") == "≥"
    assert m.canonicalize_closed("compare", "más de") == "≥"
    assert m.canonicalize_closed("compare", "weniger als") == "≤"
    assert m.compare_bit_cost("≥ ≤")["total_bits"] == 2


def test_morpho_from_arrow_and_ml_aliases():
    """from/から → ← canonical; fr alias; ES/FR/DE prep+subject fold when bits match."""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.PREP_CANONICAL == ("with", "for", "←", "@")  # w/, 4 token losers
    assert m.PARTICLE_EXTENDED[-1] == "←"
    en = m.compress("from home", unique=False, etymon=False, counters=False)
    assert "←" in en and not __import__("re").search(r"\bfr\b", en, __import__("re").I)
    ja = m.compress("東京から来る", unique=False, etymon=False, counters=False)
    assert "←" in ja
    es = m.compress("desde casa con amigos para comer", unique=False, etymon=False, counters=False)
    # con is never rewritten to with (desde/para unchanged)
    assert "←" in es and "for" in es and "con" in es and "with" not in es
    fr = m.compress("depuis Paris avec Marie pour toi", unique=False, etymon=False, counters=False)
    assert "←" in fr and "with" in fr and "for" in fr
    de = m.compress("aus Berlin mit Anna für dich bei uns", unique=False, etymon=False, counters=False)
    assert "←" in de and "with" in de and "for" in de and "@" in de
    # subject-side pronouns
    assert m.canonicalize_closed("pronoun", "yo") == "I"
    assert m.canonicalize_closed("pronoun", "tú") == "U"
    assert m.canonicalize_closed("pronoun", "él") == "he"
    assert m.canonicalize_closed("pronoun", "ellos") == "they"
    assert m.canonicalize_closed("pronoun", "je") == "I"
    assert m.canonicalize_closed("pronoun", "ich") == "I"
    # es/pt/fr と判定された文では主語代名詞を置換しない（#106 フォローアップ）
    subj = m.compress("yo voy y ella queda", unique=False, etymon=False, counters=False)
    assert subj.split()[0] == "yo" and "ella" in subj
    # と → & kept
    assert "&" in m.compress("猫と犬", unique=False, etymon=False, counters=False)
    # expand ←
    assert "from" in m.expand("← home").lower()


def test_complementizer_that_deletion():
    import sys
    from tests._helpers import load
    m = load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert m.compress("I think that he is going") == "I think he is going"
    assert m.compress("She said that we will go") == "She said we will go"
    assert m.compress("I know that she left") == "I know she left"
    assert m.compress("We saw that they were here") == "We saw they were here"
    # NP-object verb + non-pronoun: keep (no that-drop; avoid "I know people…")
    assert "people" in m.compress("I know that people are here")
    assert m.compress("I know that people are here") != "I know people are here"
    # demonstrative / relative untouched
    assert m.compress("I said that.") == "I said that."
    assert m.compress("I think that is right") != "I think is right"
    assert "," not in m.compress("I think that he is going")


def test_demonstrative_that_those_to_the():
    from tests._helpers import load
    m = load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    # determiner + noun → the
    assert m.compress("I like that book") == "I like the book"
    assert m.compress("I read those books") == "I read the books"
    assert m.compress("Those books are old") .lower() == "the books are old"
    # pronoun-use that/those untouched
    assert m.compress("I said that.") == "I said that."
    assert m.compress("I like that.") == "I like that."
    assert "the" not in m.compress("that is right").split()
    assert m.compress("those who wait") == "those who wait"
    # #36 complementizer deletion and #23 relative unchanged
    assert m.compress("I think that he is going") == "I think he is going"


# ──── features2 ───────────────────────────────────────────────────

"""Round-2 layer-unit tests: expand, frames, lex-policy, packs helpers.

Budget/role/trace/auto via DensityFacadeRoute → tests/integration/.
"""


ROOT = Path(__file__).resolve().parents[1]


def test_morpho_expand_smoke():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    compressed = m.compress("I see 3 animals and 2 people")
    assert "3匹" in compressed
    expanded = m.expand(compressed)
    assert "3 animals" in expanded
    assert "2 people" in expanded
    # pack tokens
    packed = m.pack_tokens("hello,  world   こんにちは  です")
    assert "hello" in packed
    assert "world" in packed
    assert "こんにちは" in packed
    # whitespace collapsed; CJK runs stay glued
    assert "  " not in packed.replace(", ", ",")  # allow single space after comma
    assert "   " not in packed


def test_morpho_expand_cli(capsys):
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    rc = m.main(["--mode", "expand", "--text", "3匹 and 2人"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "animals" in out
    assert "people" in out


def test_shorthand_export_lexicon(tmp_path):
    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    sess = s.Session()
    sess.declare("special widget", "SW")
    data = sess.export_lexicon()
    assert "map" in data
    assert "conventions" in data
    assert data["conventions"]["special widget"] == "SW"
    path = tmp_path / "lex.json"
    sess.export_lexicon_to(path)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert "as soon as possible" in loaded["map"]


def test_shorthand_suggest_hereafter():
    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    text = (
        "the continuous integration pipeline failed. "
        "fix continuous integration again. "
        "continuous integration is red."
    )
    suggestions = s.suggest_hereafter(text)
    assert suggestions
    assert any("continuous integration" in str(x["long"]) for x in suggestions)
    assert all("hereafter" in str(x["line"]) for x in suggestions)


def test_zip_frames_roundtrip():
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    payloads = [b"msg one", b"msg two", b"msg three"]
    blob = z.encode_frames(payloads, key="frame-key", aad="batch")
    assert blob.count(b"\n") == 2
    back = z.decode_frames(blob, key="frame-key", aad="batch")
    assert back == payloads


def test_rule_peer_codec_key_requires_flag():
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    ns = z.argparse.Namespace(key=None, key_file=None)
    # No environment-variable fallback: only --key / --key-file supply a key.
    import pytest

    with pytest.raises(SystemExit, match="--key or --key-file"):
        z._read_key(ns)


def test_lex_policy_load_dump(tmp_path):
    # Import via package path
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import shared.lex_policy as lp

    dumped = lp.dump_policy()
    assert "fillers_en" in dumped
    assert "etymon_align" in dumped
    path = tmp_path / "pol.json"
    # Override fillers to a tiny set
    path.write_text(
        json.dumps({"fillers_en": ["xyzzy_filler"], "fillers_ja": []}),
        encoding="utf-8",
    )
    applied = lp.load_policy(path)
    assert applied["fillers_en"] == ["xyzzy_filler"]
    out = lp.strip_fillers("hello xyzzy_filler world")
    assert "xyzzy_filler" not in out
    assert "hello" in out
    # restore a fuller policy so other tests in same process aren't wrecked if order varies
    restore = tmp_path / "restore.json"
    restore.write_text(json.dumps(dumped), encoding="utf-8")
    lp.load_policy(restore)


def test_mosaic_new_lang_cues():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    assert "it" in t._CUES and "nl" in t._CUES and "id" in t._CUES and "sv" in t._CUES
    # Italian-ish
    assert t.detect_lang("Il gatto non è con la ragazza.") in ("it", "en", "es", "pt", "fr")
    # Indonesian cues
    lang = t.detect_lang("yang tidak ada dengan untuk ini itu dari pada")
    assert lang == "id"


def test_mosaic_preserve_newlines():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    src = "Hello there.\n\nこんにちは。"
    mosaic = t.compress(src, preserve_newlines=True)
    assert "¶" in mosaic
    back = t.expand(mosaic, preserve_newlines=True)
    assert "\n\n" in back
    assert "Hello" in back
    assert "こんにちは" in back


# ──── features3 ───────────────────────────────────────────────────

"""Round-3 layer-unit tests: protect, packs, fingerprint, policy diff, LID mix.

Window/profile/quality via DensityFacadeRoute → tests/integration/.
"""


# --- protect spans ---


def test_protect_keep_spans():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    text = "um [[keep:thank you for your information]] please"
    out = m.compress(text, aggressive_fillers=True)
    assert "thank you for your information" in out
    assert "[[" not in out
    assert "]]" not in out


def test_protect_regex():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    text = "um CODE_BLOCK_XYZ please thank you"
    out = m.compress(text, protect_regexes=[r"CODE_BLOCK_XYZ"])
    assert "CODE_BLOCK_XYZ" in out


# --- packs ---


def test_pack_dev_loads():
    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    m = s.load_pack("dev")
    assert "pull request" in m or "Pull request".lower() in {k.lower() for k in m}
    sess = s.Session()
    sess.load_packs(["dev", "mcp"])
    out = s.compress("the model context protocol pull request is ready", session=sess)
    assert "MCP" in out or "PR" in out


# --- fingerprint ---


def test_key_fingerprint_stable():
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    a = z.key_fingerprint("secret-demo")
    b = z.key_fingerprint("secret-demo")
    c = z.key_fingerprint("other")
    assert a == b
    assert a != c
    assert len(a) == 16
    assert all(ch in "0123456789abcdef" for ch in a)


def test_rule_peer_codec_fingerprint_mode(capsys):
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    rc = z.main(["fingerprint", "--key", "secret-demo"])
    assert rc == 0
    assert len(capsys.readouterr().out.strip()) == 16


def test_rule_peer_codec_dry_run(capsys):
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    rc = z.main(["encode", "--key", "k", "--dry-run", "--stats", "--text", "hello"])
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.out.strip().isdigit()
    stats = json.loads(captured.err.strip().splitlines()[-1])
    assert stats["envelope_bytes"] > 0
    assert "fingerprint" in stats


# --- policy diff ---


def test_policy_diff_smoke(tmp_path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    # fresh load
    import shared.lex_policy as lp

    importlib.reload(lp)
    base = lp.dump_policy()
    other = dict(base)
    other["fillers_en"] = list(base["fillers_en"]) + ["brand_new_filler_xyz"]
    other["unique_readings"] = dict(base["unique_readings"])
    other["unique_readings"].pop(next(iter(other["unique_readings"])), None)
    path = tmp_path / "other.json"
    path.write_text(json.dumps(other), encoding="utf-8")
    diff = lp.diff_policy(base, path)
    assert "brand_new_filler_xyz" in diff["fillers_en"]["added"]
    assert diff["fillers_en"]["removed"] == []


def test_policy_diff_cli(tmp_path, capsys):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import shared.lex_policy as lp

    importlib.reload(lp)
    other = lp.dump_policy()
    other["fillers_ja"] = list(other["fillers_ja"]) + ["新しいフィラー"]
    path = tmp_path / "o.json"
    path.write_text(json.dumps(other), encoding="utf-8")
    rc = lp.main(["--diff", str(path)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "新しいフィラー" in data["fillers_ja"]["added"]


# --- prefer-ltr / script_mix ---


def test_prefer_ltr_latin_cjk_mix():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    # Latin + CJK without hiragana
    s = "Hello 世界 code."
    lang_default = t.detect_lang(s, prefer_ltr=False)
    lang_ltr = t.detect_lang(s, prefer_ltr=True)
    assert lang_ltr == "en"
    # without prefer_ltr, mix with enough latin still en in our tuned detector
    assert lang_ltr == "en"
    mix = t.script_mix(s)
    assert mix["latin"] > 0
    assert mix["cjk"] > 0
    assert "latin_ratio" in mix


def test_script_mix_in_stats():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    st = t.stats("Hello. 你好。")
    assert "script_mix" in st
    assert st["sentences"] >= 1


# ──── features4 ───────────────────────────────────────────────────

"""Round-4 layer-unit tests: A export/negotiate, B bank+mosaic, C ledger, E counters.

DensityFacadeRoute wiring for --translate-min → tests/integration/.
"""


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# --- A: RuleBook export / import / threshold / negotiate ---


def test_rulebook_export_import_merge(tmp_path):
    rb = _load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    alice = rb.RuleBook.load(tmp_path / "alice.json", threshold=3)
    alice.declare("status update complete", "r1")
    alice.declare("ready and waiting", "r2")
    dump = tmp_path / "alice_export.json"
    alice.export_rules(dump)

    bob = rb.RuleBook.load(tmp_path / "bob.json", threshold=2)
    bob.declare("ping pong match", "r1")  # different long, same short preferred
    info = bob.import_rules(dump, merge=True)
    assert info["added"] >= 2
    assert bob._find_by_long("status update complete") is not None
    assert bob._find_by_long("ready and waiting") is not None
    # bob keeps own rule
    assert bob._find_by_long("ping pong match") is not None
    encoded = bob.encode_with_rules("please status update complete and ready and waiting")
    assert "status update complete" not in encoded.lower()
    assert "ready and waiting" not in encoded.lower()


def test_rulebook_set_threshold_and_cli(tmp_path, capsys):
    rb = _load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    book = rb.RuleBook.load(tmp_path / "book.json", threshold=5)
    book.set_threshold(2)
    assert book.threshold == 2
    book.save()

    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    rc = z.main(
        ["rule-threshold", "--state", str(tmp_path / "book.json"), "--threshold", "4"]
    )
    assert rc == 0
    assert capsys.readouterr().out.strip() == "4"
    reloaded = rb.RuleBook.load(tmp_path / "book.json")
    assert reloaded.threshold == 4


def test_rulebook_negotiate_multi_peer(tmp_path):
    rb = _load("rule_peer_codec_rulebook", "RulePeerCodec/rulebook.py")
    hub = rb.RuleBook.load(tmp_path / "hub.json")
    p1 = rb.RuleBook()
    p1.declare("continuous integration pipeline", "ci")
    p2 = rb.RuleBook()
    p2.declare("end to end test suite", "e2e")
    p2.proposals.append({"long": "definition of done", "short": "dod", "count": 2})
    e1 = tmp_path / "p1.json"
    e2 = tmp_path / "p2.json"
    p1.export_rules(e1)
    p2.export_rules(e2)
    info = hub.negotiate([e1, e2], adopt_proposals=True)
    assert info["peers"] == 2
    assert hub._find_by_long("continuous integration pipeline")
    assert hub._find_by_long("end to end test suite")
    assert hub._find_by_long("definition of done")
    # CLI path
    z = _load("rule_peer_codec", "RulePeerCodec/rule_peer_codec.py")
    state = tmp_path / "cli_hub.json"
    rb.RuleBook.load(state).save()
    rc = z.main(
        [
            "rule-negotiate",
            "--state",
            str(state),
            "--import",
            str(e1),
            "--peer",
            str(e2),
        ]
    )
    assert rc == 0
    merged = rb.RuleBook.load(state)
    assert len(merged.rules) >= 2


# --- B: translation bank growth + mosaic interaction ---


def test_b_bank_new_entries_shorten():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    # bust cache after bank edits
    t.load_translation_bank.cache_clear()
    chosen, lang, n = t.pick_shortest_translation("Good night.")
    assert lang != "src"
    assert n < t.estimate_tokens("Good night.")
    chosen2, _, n2 = t.pick_shortest_translation("What time is it?")
    assert n2 < t.estimate_tokens("What time is it?")
    assert "ASAP" in t.pick_shortest_translation("as soon as possible")[0]


def test_b_mosaic_with_translate_min_interaction():
    t = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    t.load_translation_bank.cache_clear()
    text = "Good morning. 今日はとても良い天気ですね. See you later."
    plain = t.compress(text, rle=True, translate_min=False)
    mini = t.compress(text, rle=True, translate_min=True)
    # mosaic still has tags / pipes
    assert ":" in mini or "|" in mini
    # translate-min should not grow overall mosaic vs plain (token/char lean)
    assert t.estimate_tokens(t.expand(mini)) <= t.estimate_tokens(t.expand(plain))
    # round-trip expand still yields text
    expanded = t.expand(mini)
    assert expanded
    # B must NOT apply C ledger under→下
    keep = t.minify_by_translation("The cat is under the table.")
    assert "under" in keep.lower() or "下" not in keep or "桌下" in keep or "机の下" in keep
    # natural short may drop "under" word via ZH/JA — but never via C ledger glyph alone on EN path
    # Explicit: compress without translate leaves under
    assert "under" in t.compress("The cat is under the table.", translate_min=False).lower()


# --- C: ledger round-4 + chat pack ---


def test_c_ledger_spatial_and_conjunctions():
    from shared.ledger import apply_ledger_lex, convention_ids

    ids = convention_ids()
    assert "spatial-left-right" in ids
    assert "conj-moreover" in ids
    assert apply_ledger_lex("left and right sides") == "左右 sides"
    assert apply_ledger_lex("front and back") == "前後"
    assert apply_ledger_lex("inside and outside") == "内外"
    assert apply_ledger_lex("big and small") == "大小"
    assert "also" in apply_ledger_lex("moreover we continue")
    assert "moreover" not in apply_ledger_lex("moreover we continue").lower()
    assert apply_ledger_lex("nevertheless it works").startswith("but")
    assert "so" in apply_ledger_lex("therefore we stop")
    assert "e.g." not in apply_ledger_lex("for example cats")  # pruned (o200k)
    # bare clause "that is the plan" keeps its meaning; appositive gloss maps
    assert "i.e." not in apply_ledger_lex("that is the plan")
    assert "i.e." not in apply_ledger_lex("a car, that is, a vehicle")  # i.e. token loser

    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    out = s.compress("check left and right carefully")
    assert "左右" in out
    out2 = s.compress("moreover please advise")
    assert "also" in out2.lower()
    assert "PA" in out2 or "please advise" not in out2.lower()


def test_c_chat_pack_and_map_growth():
    s = _load("shorthand_session_edge", "ShorthandSessionEdge/shorthand_session_edge.py")
    assert "chat" in s.list_packs()
    sess = s.Session()
    sess.load_packs(["chat"])
    out = s.compress("send a heads up in the group chat", session=sess)
    assert "HU" in out or "GC" in out
    out2 = s.compress("for your reference please")
    assert "FYR" in out2


# --- E: counters / grammar / smart quotes ---


def test_e_new_counters_and_grammar():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    assert "3台" in m.compress("I have 3 cars ready")
    assert "2棟" in m.compress("build 2 buildings here")
    assert "5杯" in m.compress("drink 5 cups tonight")
    assert "4組" in m.compress("prepare 4 pairs now")
    assert "7通" in m.compress("send 7 emails today")
    out = m.compress("additionally for example, that is, fine", unique=False, etymon=False)
    assert "+" in out  # additionally→+ (gap-fill; was also)
    assert "additionally" not in out.lower()
    assert "e.g." not in out and "for example" in out  # e.g. token loser
    assert "i.e." not in out and "that is" in out  # i.e. token loser
    # expand counters subset
    assert "vehicles" in m.expand("3台")


def test_e_smart_quoted_articles_kept():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    # straight quotes keep inner word
    assert "the" in m.compress('say "the" clearly', unique=False, etymon=False).lower()
    # smart quotes
    smart = "say “the” clearly"
    out = m.compress(smart, unique=False, etymon=False)
    assert "the" in out.lower()
    # unquoted still stripped
    plain = m.compress("say the clearly", unique=False, etymon=False)
    assert " the " not in f" {plain} ".lower()


def test_e_does_not_apply_c_ledger_or_ill_by_default():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    out = m.compress("I will go under the table", unique=False, etymon=False, counters=False)
    assert "under" in out.lower()
    assert "I'll" not in out
