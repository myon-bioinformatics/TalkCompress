"""Non-ASCII Latin ledger/etymon sources must not fire inside a longer word."""
from __future__ import annotations


from shared import ledger as G
from shared import lex_policy as L


def _e(t: str) -> str:
    return G.apply_ledger_lex(t, apply_layer="E")


def test_ledger_nonascii_latin_src_word_edges():
    assert _e("für dich") == "for dich"
    assert _e("él come") == "he come"
    assert _e("tú y yo") == "U & I"
    # mid-word: dafür / draußen / aquél / virtú stay intact
    for t in ("Danke dafür", "wofür ist das", "wir sind draußen", "aquél día", "virtú", "fürs"):
        assert _e(t) == t
    # NFD trailing combining mark after the source (é = e + U+0301) is mid-word
    nfd = "für" + "\u0301"
    assert _e(nfd) == nfd
    # CJK sources keep plain-substring semantics
    assert _e("彼の本") == "he本"
    assert _e("外です") == "外です"


def test_ledger_pattern_edges():
    p = G.nonascii_word_pattern
    assert p("彼の") == "彼の"
    assert p("für").startswith("(?<!") and "(?!" in p("für")
    assert p("°") == "°"


def test_ledger_word_present_and_collision():
    assert G._word_present("ok für dich", "für")
    assert not G._word_present("Danke dafür", "für")
    conv = {"ambiguity_sensitive": True}
    # dst still present as a whole word after removing src → keep original
    assert G._ambiguity_skip("für x for", "für", "for", conv, prefer_precision=False) is True
    assert G._ambiguity_skip("dafür x", "für", "for", conv, prefer_precision=False) is False
    # mid-word src (dafür) must not be stripped when probing the collision
    assert G._ambiguity_skip("dafür x", "für", "da", conv, prefer_precision=False) is False
    assert G._replace_src("dafür für", "für", "for") == "dafür for"


def test_etymon_nonascii_word_edges():
    assert L.apply_etymon_align("l'insécurité du réseau") == "l'insécurité du net"
    assert L.apply_etymon_align("les réseaux") == "les réseaux"
    assert L.apply_etymon_align("subversión") == "subversión"
    assert L.apply_etymon_align("la versión") == "la ver"
    assert L.apply_etymon_align("Sécurité ok") == "sec ok"
    assert L.apply_etymon_align("base de données") == "db"
    nfd_tail = "réseau" + "\u0301"
    assert L.apply_etymon_align(nfd_tail) == nfd_tail
    p = L.nonascii_word_pattern
    assert p("彼の") == "彼の" and p("°") == "°"
