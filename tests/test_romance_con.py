"""Regression: ``con`` is never rewritten to ``with`` (Romance or English)."""
import pytest

import morpho_zip as m


def _c(s: str) -> str:
    return m.compress(s, unique=False, etymon=False, counters=False)


@pytest.mark.parametrize(
    "src",
    [
        "Vado al cinema con Marco.",  # IT
        "Io parlo con lui.",  # IT
        "Esco con la mia amica.",  # IT
        "Caffè con latte.",  # ES/IT
        "Voy a la playa con mis amigos.",  # ES
        "Ela saiu com o irmão.",  # PT (com)
    ],
)
def test_romance_con_kept(src):
    assert _c(src) == src


@pytest.mark.parametrize("src", ["pro and con", "He is a con man."])
def test_english_con_not_with(src):
    assert "with" not in _c(src) and "con" in _c(src).split()


def test_mixed_text_con_never_with():
    out = _c("Vado al cinema con Marco. He is a con man.")
    assert "with" not in out and out.startswith("Vado al cinema con Marco.")


def test_con_word_boundary():
    out = _c("I like the concert and icons.")
    assert "concert" in out and "icons" in out


def test_inventory_alias_unchanged():
    assert m.canonicalize_closed("preposition", "con") == "with"
