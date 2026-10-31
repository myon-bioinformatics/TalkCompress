"""ASCII lexicon rows must not case-fold onto Turkish ı/İ or the Kelvin sign (U+212A)."""

from shared import ledger as G
from shared import lex_policy as L


def test_contractions():
    assert L.apply_en_contractions("İ wıll") == "İ wıll"
    assert L.apply_en_contractions("I WILL") != "I WILL"


def test_spelled_numbers():
    assert L.apply_spelled_numbers("fıve") == "fıve"
    assert L.apply_spelled_numbers("FIVE") == "5"


def test_fillers():
    assert L.strip_fillers("Kınd of, ok") == "Kınd of, ok"
    assert L.strip_fillers("Kind of, ok") == "ok"


def test_unique_readings_and_compact():
    kelvin_make = "ma\u212ae"
    assert L.apply_unique_readings(kelvin_make, compact=False) == kelvin_make
    assert L.apply_unique_compact("obtaın") == "obtaın"
    assert L.apply_unique_compact("OBTAIN") == "obt"


def test_etymon_align():
    assert L.apply_etymon_align("communıcatıon") == "communıcatıon"
    assert L.apply_etymon_align("COMMUNICATION") == "comm"


def test_ledger_word_present_and_replace():
    assert G._word_present("in my opınıon", "in my opinion") is False
    assert G._word_present("IN MY OPINION", "in my opinion") is True
    assert G._replace_src("in my opınıon", "in my opinion", "IMO") == "in my opınıon"
    assert G._replace_src("In My Opinion", "in my opinion", "IMO") == "IMO"


def test_ascii_ci_keeps_unicode_case_folding_for_non_ascii_words():
    import re

    for mod in (G, L):
        assert re.fullmatch(mod._ascii_ci("été"), "ÉTÉ", re.I)
        assert not re.fullmatch(mod._ascii_ci("it"), "ıt", re.I)
