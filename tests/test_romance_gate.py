"""es / pt / fr の文では英語専用の規則（冠詞 a 削除・数詞→数字・3sg -s 落とし）を発火させない。"""
import unicodedata

import pytest

from MorphoZip.morpho_zip import compress, drop_3sg_after_inventory_pronoun, strip_articles
from shared.lex_policy import apply_spelled_numbers
from shared.romance_gate import apply_outside_romance, is_romance

ROMANCE = [
    "Voy a la playa.",
    "Vamos a ver.",
    "Dé a Juan el libro.",
    "Ella va a Madrid y a Roma.",
    "Vou a casa.",
    "Eu vou com você para a escola amanhã.",
    "Il a un chat.",
    "On a fait une pause.",
    "Elle a dit oui.",
    "J'ai a faire.",
    "Le four est chaud.",
    "Une seconde, s'il vous plaît.",
]
ENGLISH = [
    "I have a cat.",
    "A cat sat.",
    "Take a break.",
    "We need four chairs.",
    "He went to a cafe in Paris.",
    "It's a dog.",
    "Plan A failed.",
    "Bring a pastel de nata.",
]


@pytest.mark.parametrize("s", ROMANCE)
def test_is_romance(s):
    assert is_romance(s)


@pytest.mark.parametrize("s", ENGLISH)
def test_is_not_romance(s):
    assert not is_romance(s)


@pytest.mark.parametrize("form", ["NFC", "NFD"])
@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("Voy a la playa.", "Voy a la playa."),
        ("Vou a casa.", "Vou a casa."),
        ("Il a un chat.", "Il a un chat."),
        ("Ella va a Málaga.", "Ella va a Málaga."),
        ("Ça a été dur.", "Ça a été dur."),
        ("I have a cat. Voy a la playa. Take an apple.", "I have cat. Voy a la playa. Take apple."),
    ],
)
def test_strip_articles_keeps_romance_a(form, src, want):
    out = strip_articles(unicodedata.normalize(form, src))
    assert unicodedata.normalize("NFC", out) == want


@pytest.mark.parametrize("s", ["Voy a la playa.", "Vou a casa.", "On a fait une pause."])
def test_compress_keeps_romance_a(s):
    assert " a " in compress(s)


def test_spelled_numbers_skip_french_four():
    assert apply_spelled_numbers("Le four est chaud.") == "Le four est chaud."
    assert apply_spelled_numbers("Mettez le gâteau au four.") == "Mettez le gâteau au four."
    assert apply_spelled_numbers("We need four chairs.") == "We need 4 chairs."
    assert apply_spelled_numbers("Le four est chaud. We need four.") == "Le four est chaud. We need 4."


def test_3sg_fold_skips_french_vous():
    assert drop_3sg_after_inventory_pronoun("Et s he vous plaît.") == "Et s he vous plaît."
    assert drop_3sg_after_inventory_pronoun("he chooses") == "he choose"
    assert "vous" in compress("Une seconde, s il vous plaît.")


def test_apply_outside_romance_preserves_every_char():
    s = "Voy a la playa!\nI have a cat.  Il a un chat?"
    assert apply_outside_romance(s, lambda t: t) == s
    assert apply_outside_romance(s, str.upper) == "Voy a la playa!\nI HAVE A CAT.  Il a un chat?"
    assert apply_outside_romance("", str.upper) == ""
