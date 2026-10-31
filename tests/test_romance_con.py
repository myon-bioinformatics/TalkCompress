"""Regression: Romance ``con`` must not become ``with`` (English path unchanged)."""
import pytest

import morpho_zip as m


def _c(s: str) -> str:
    return m.compress(s, unique=False, etymon=False, counters=False)


@pytest.mark.parametrize(
    "src",
    [
        "Vado al cinema con Marco.",  # IT
        "Io parlo con lui.",  # IT
        "Il gatto è con la ragazza.",  # IT
        "Caffè con latte.",  # ES/IT
        "Voy a la playa con mis amigos.",  # ES
        "Ela saiu con o irmão.",  # PT-ish
    ],
)
def test_romance_con_kept(src):
    out = _c(src)
    assert "con" in out.split() and "with" not in out


def test_english_sentence_con_still_with():
    assert _c("I went con my friend.") == "I went with my friend."


def test_mixed_text_only_english_sentence_rewritten():
    out = _c("Vado al cinema con Marco. I went con my friend.")
    assert out == "Vado al cinema con Marco. I went with my friend."


def test_con_word_boundary():
    out = _c("I like the concert and icons.")
    assert "concert" in out and "icons" in out


def test_inventory_alias_unchanged():
    assert m.canonicalize_closed("preposition", "con") == "with"
