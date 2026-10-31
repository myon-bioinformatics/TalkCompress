"""ShorthandEdge.expand must treat NFD input like NFC."""
from __future__ import annotations

import unicodedata

from ShorthandEdge import shorthand_edge as S


def test_expand_nfd_accent_does_not_expose_short():
    s = "Příliš žluťoučký kůň úpěl."
    assert S.expand(s) == s
    assert S.expand(unicodedata.normalize("NFD", s)) == s
    assert S.expand("PR ok") == "pull request ok"
