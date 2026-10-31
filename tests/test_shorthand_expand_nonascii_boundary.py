"""expand: non-ASCII short forms respect Latin word edges; ASCII shorts stay bounded."""

import unicodedata

from ShorthandEdge.shorthand_edge import expand


def test_ascii_short_not_inside_word():
    assert expand("Problem with PR") == "Problem with pull request"


def test_nonascii_latin_short_not_inside_word():
    m = {"sécurité": "séc"}
    assert expand("La sécheresse, séc.", mapping=m) == "La sécheresse, sécurité."


def test_nonascii_latin_short_not_after_letter():
    m = {"señal": "ñal"}
    assert expand("Señal y ñal", mapping=m) == "Señal y señal"


def test_nonascii_short_not_before_nfd_mark():
    m = {"señal": "señ"}
    out = expand("sen\u0303\u0301 señ", mapping=m)
    assert out == unicodedata.normalize("NFC", "sen\u0303\u0301 señal")


def test_kana_short_stays_substring():
    assert "りょ" not in expand("おkりょ")
