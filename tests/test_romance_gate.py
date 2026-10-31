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


@pytest.mark.parametrize('form', ['NFC', 'NFD'])
@pytest.mark.parametrize(('src', 'want'), [
    ('Il vous aide.', 'he vous aide.'),
    ('Elle vous aide.', 'she vous aide.'),
    ('Il nous aide.', 'he nous aide.'),
    ('S il vous plaît.', 'S he vous plaît.'),
])
def test_source_guard_survives_pronoun_pivot(form, src, want):
    assert compress(unicodedata.normalize(form, src)) == want


@pytest.mark.parametrize('boundary', ['. ', '!\n', '? ', '.\" '])
def test_source_guard_is_local_to_sentence(boundary):
    source = 'Il vous aide' + boundary + 'He chooses four chairs.'
    assert compress(source, spelled_nums=True) == 'he vous aide' + boundary + 'He choose 4 chairs.'


def test_english_do_is_not_a_romance_only_cue():
    assert not is_romance('Do four tests.')
    assert apply_spelled_numbers('Do four tests.') == 'Do 4 tests.'
    assert compress('Do four tests.', spelled_nums=True) == 'Do 4 tests.'
    assert strip_articles('Do a dance.') == 'Do dance.'
    # Portuguese do remains a cue, but cannot by itself outweigh English.
    assert is_romance('Eu vou do parque a casa.')
    assert ' a ' in compress('Eu vou do parque a casa.')


def test_source_context_keeps_protected_spans_and_english_path():
    assert compress('Il vous aide. [[keep:He chooses four.]]', spelled_nums=True) == 'he vous aide. He chooses four.'
    from shared.romance_gate import transform_with_romance_context
    calls = []
    def record(text, protected):
        calls.append((text, protected))
        return text
    text = 'He chooses. Do four tests.\n'
    assert transform_with_romance_context(text, record) == text
    assert calls == [(text, False)]
    calls.clear()
    assert transform_with_romance_context('', record) == ''
    assert calls == [('', False)]


@pytest.mark.parametrize('english', [
    'Get married\nto her.',
    'I need 3\nbooks.',
    'I saw that\nthing.',
    'He\nchooses four chairs.',
    'I need 3\n or 4 books.',
    'I need 3 or\n -4 books.',
    "Can't\nyou?",
    'She said that\nI have a cat.',
])
def test_romance_neighbor_keeps_english_multiline_context(english):
    prefix = 'Il vous aide. '
    assert compress(prefix + english, spelled_nums=True) == (
        'he vous aide. ' + compress(english, spelled_nums=True)
    )


def test_public_gate_preserves_english_multiline_number_context():
    assert apply_spelled_numbers('Le four est chaud. one\nhundred') == 'Le four est chaud. 100'
    assert drop_3sg_after_inventory_pronoun('Il vous aide. He\nchooses.') == 'Il vous aide. He\nchoose.'


@pytest.mark.parametrize('source', [
    'Je veux 3\nou 4.',
    'Je veux 3 ou\n4.',
    '3\nou 4 avec vous.',
])
def test_global_pivot_keeps_numeric_alternative_context(source):
    out = compress(source)
    assert 'ou' in out
    assert '/' not in out


def test_pivot_tracking_preserves_global_context_and_replacement_origins():
    import re
    from shared.romance_gate import substitute_with_romance_context
    source = 'Il vous aide. He chooses.'
    substitutions = [(re.compile('Il'), 'he'), (re.compile(r'He (chooses)'), r'He always \1')]
    seen = []
    def finish(text, protected):
        seen.append((text, protected))
        return text if protected else drop_3sg_after_inventory_pronoun(text)
    assert substitute_with_romance_context(source, substitutions, finish) == 'he vous aide. He always choose.'
    assert seen == [('he vous aide.', True), (' He always chooses.', False)]
    # Callable replacements and full-text lookbehind across language boundaries.
    substitutions = [(re.compile(r'(?<=aide\.) He'), lambda m: ' She')]
    assert substitute_with_romance_context(source, substitutions, finish) == 'Il vous aide. She choose.'


@pytest.mark.parametrize('source', ['', 'abc', 'Il vous aide.', 'Il vous plaît. He chooses.'])
def test_pivot_tracking_identity(source):
    from shared.romance_gate import substitute_with_romance_context
    assert substitute_with_romance_context(source, [], lambda text, protected: text) == source
