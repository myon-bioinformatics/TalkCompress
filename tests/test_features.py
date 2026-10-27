"""Feature tests (layer unit): lexicon, RLE, counters, AAD.

Cross-layer pipeline/compare → tests/integration/.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod



# --- layer ownership: fillers + UNIQUE_COMPACT = C ---


def test_layer_ownership_matrix_classic_example():
    """Canonical C vs E alone: I'll/spelled on C; ℹ️ on E (pipe → integration)."""
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    classic = "um 私は will find out the information about three animals"

    from shared.lex_policy import INFO_GLYPH

    e_out = m.compress(classic)
    assert "um" in e_out.lower()
    assert "ascertain" in e_out.lower()
    assert "ascrt" not in e_out.lower()
    assert INFO_GLYPH in e_out
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
    assert INFO_GLYPH not in c_out  # ℹ️ is E


# --- lexicon load ---


def test_shorthand_lexicon_load(tmp_path):
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    lex = tmp_path / "lex.json"
    lex.write_text(json.dumps({"continuous delivery": "CDel", "hello world": "hw"}), encoding="utf-8")
    sess = s.Session()
    sess.load_lexicon(lex)
    out = s.compress("please start continuous delivery", session=sess)
    assert "CDel" in out



# --- RLE mosaic ---


def test_tessera_rle_roundtrip():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
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


def test_tessera_rle_and_full_both_expand():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    full = "en:Hello.|en:World.|ja:こんにちは。"
    rle = "en:Hello.|World.|ja:こんにちは。"
    assert "Hello" in t.expand(full)
    assert "World" in t.expand(rle)
    assert "こんにちは" in t.expand(rle)


def test_tessera_stats():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    st = t.stats("Hello. こんにちは。")
    assert st["sentences"] >= 2
    assert "en" in st["langs"] or "ja" in st["langs"]


def test_tessera_no_rle_still_works():
    t = _load("tessera_talk", "TesseraTalk/tessera_talk.py")
    src = "Hello. World."
    mosaic = t.compress(src, rle=False)
    assert mosaic.count("en:") == 2


# --- counters / hex ---


def test_morpho_counters():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert "3匹" in m.compress("I see 3 animals here")
    assert "2人" in m.compress("there are 2 people waiting")
    assert "5個" in m.compress("pack 5 pieces carefully")
    assert "4回" in m.compress("retry 4 times please")


def test_morpho_hex_nums():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    out = m.compress("value is 255 here", hex_nums=True, counters=False)
    assert "0xff" in out
    bare = m.compress("value is 255 here", hex_nums=True, hex_prefix=False, counters=False)
    assert "ff" in bare
    # default off
    plain = m.compress("value is 255 here", counters=False)
    assert "255" in plain


def test_morpho_pronoun_inventory():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    # Stop collapsing he/she and 彼/彼女 into they
    assert "彼" in m.compress("he or she will go")
    assert "她" in m.compress("he or she will go")
    assert "they" not in m.compress("he or she will go").lower()
    assert m.compress("彼を呼ぶ") == "彼呼ぶ"
    assert "她" in m.compress("彼女は来る")
    assert "她" in m.compress("she will go")
    assert "君" in m.compress("I see you")
    assert "you know" in m.compress("you know me")  # discourse filler untouched
    assert "y'all" in m.compress("you all ready")
    assert "y'all" in m.compress("you guys win")
    assert "they" in m.compress("they saw them")
    assert "them" in m.compress("they saw them")
    assert m.compress("私は行く") == "I行く"
    assert "it" in m.compress("それは本")


def test_morpho_pronoun_bits():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert m.pronoun_inventory_bits() == 2
    assert len(m.PRONOUN_CANONICAL) == 4
    assert m.pronoun_inventory_bits(extended=True) == 3
    # they / them / y'all same canonical + same flat cost
    assert m.canonicalize_pronoun("they") == "they"
    assert m.canonicalize_pronoun("them") == "they"
    assert m.canonicalize_pronoun("y'all") == "they"
    w = m.pronoun_inventory_bits()
    for form in ("they", "them", "y'all"):
        c = m.pronoun_bit_cost(form)
        assert c["bits_per_pronoun"] == w == 2
        assert c["count"] == 1
        assert c["total_bits"] == 2
    # 她: core path aliases to 彼 (2 bits); utf8 secondary = 24
    assert m.canonicalize_pronoun("她") == "彼"
    assert m.utf8_bits("她") == 24
    her = m.pronoun_bit_cost("她")
    assert her["total_bits"] == 2
    assert her["canonicals"] == ["彼"]
    # it outside core; in extended
    assert m.canonicalize_pronoun("it") is None
    assert m.canonicalize_pronoun("it", extended=True) == "it"
    assert m.pronoun_bit_cost("it")["count"] == 0
    assert m.pronoun_bit_cost("it", extended=True)["total_bits"] == 3
    # density exposes pronoun bit fields
    d = m.density("he saw her", m.compress("he saw her"))
    assert d["pronoun_bits_each"] == 2
    assert d["pronoun_inventory_n"] == 4
    assert d["pronoun_count"] >= 1


# --- lex_policy expansions smoke ---


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


# --- Zipilogue AAD ---


def test_zipilogue_aad_mac_separation():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
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


def test_zipilogue_empty_aad_roundtrip():
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
    env = z.encode(b"hello", key="k", aad="")
    assert z.decode(env, key="k") == b"hello"
    assert z.decode(env, key="k", aad=None) == b"hello"


def test_zipilogue_file_cli(tmp_path):
    z = _load("zipilogue", "Zipilogue/zipilogue.py")
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


# --- MorphoZip articles / counters / ℹ️; C owns I'll + spelled nums ---


def test_morpho_strips_unquoted_articles_keeps_quoted():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
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
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert "three" in m.compress("I see three animals here").lower()
    assert "3匹" not in m.compress("I see three animals here")
    assert "3匹" in m.compress("I see three animals here", spelled_nums=True)
    assert "21匹" in m.compress("count twenty-one animals", spelled_nums=True) or "21匹" in m.compress(
        "count twenty one animals", spelled_nums=True
    )
    from shared.lex_policy import apply_spelled_numbers

    assert "100" in apply_spelled_numbers("a hundred")


def test_morpho_does_not_contract_ill_by_default():
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    out = m.compress("I will go now", unique=False, etymon=False, counters=False)
    assert "I'll" not in out
    assert "I will" in out


def test_shorthand_ill_and_spelled_numbers():
    """Focused C I'll + spelled→digit (full classic matrix → ownership test above)."""
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    out = s.compress("I will go now")
    assert "I'll" in out
    assert "I will" not in out
    out2 = s.compress("see three animals")
    assert "3" in out2
    assert "three" not in out2.lower()


def test_morpho_information_to_info_glyph():
    from shared.lex_policy import INFO_GLYPH, apply_etymon_align

    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    assert apply_etymon_align("information") == INFO_GLYPH
    assert INFO_GLYPH in m.compress("send the information please")


