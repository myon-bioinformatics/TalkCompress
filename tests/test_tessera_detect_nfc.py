"""detect_lang / script_mix must not depend on NFC vs NFD input."""
from __future__ import annotations

import unicodedata

import pytest

from TesseraTalk import tessera_talk as T


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


@pytest.mark.parametrize(
    "s,lang",
    [("Ça va très bien.", "fr"), ("Die Straße ist schön.", "de"), ("Não sei.", "pt"), ("¿Dónde está?", "es")],
)
def test_detect_lang_nfd_matches_nfc(s, lang):
    assert T.detect_lang(s) == lang
    assert T.detect_lang(_nfd(s)) == lang


def test_script_mix_counts_vietnamese_and_nfd_equal():
    s = "Tiếng Việt rất khó, you know."
    assert T.script_mix(s)["latin"] == 22
    assert T.script_mix(_nfd(s)) == T.script_mix(s)
    assert T.script_mix("ế")["latin"] == 1
    assert T.detect_lang("ế") == "en"
