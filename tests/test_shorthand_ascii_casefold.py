"""ASCII shorthand phrases must not case-fold onto Turkish ı/İ, ſ or the Kelvin sign."""

from ShorthandEdge.shorthand_edge import Session, _apply_map, expand


def test_apply_map_ignores_dotless_i():
    m = Session().effective
    assert _apply_map("in my opınıon", m) == "in my opınıon"
    assert _apply_map("İN MY OPİNİON", m) == "İN MY OPİNİON"


def test_apply_map_keeps_ascii_case_insensitivity():
    m = Session().effective
    assert _apply_map("In My Opinion", m) == "IMO"


def test_expand_ignores_turkish_i_variants():
    assert expand("ımo, İMO") == "ımo, İMO"
    assert expand("IMO, imo") == "in my opinion, in my opinion"


def test_suggest_hereafter_keeps_dotted_capital_i_word_whole():
    from ShorthandEdge.shorthand_edge import suggest_hereafter

    longs = [d["long"] for d in suggest_hereafter("İstanbul güzel. İstanbul güzel.")]
    assert "i\u0307stanbul güzel" in longs
    assert not any(p.startswith("i stanbul") or "stanbul i" in p for p in longs)
