"""shared/romance_gate.py: es / pt / fr の文で英語専用規則を発火させない。

- romance_gate: es / pt / fr の文では英語専用の規則（冠詞 a 削除・数詞→数字・3sg -s 落とし）を発火させない。
- romance_followup: #106 フォローアップ（3bot レビューの Should 2 点）。
- romance_con: Regression: ``con`` is never rewritten to ``with`` (Romance or English).
"""

from MorphoGrammarMinimal.morpho_grammar_minimal import compress
from MorphoGrammarMinimal.morpho_grammar_minimal import drop_3sg_after_inventory_pronoun
from MorphoGrammarMinimal.morpho_grammar_minimal import strip_articles
from shared.lex_policy import apply_spelled_numbers
from shared.romance_gate import apply_outside_romance
from shared.romance_gate import is_romance
import morpho_grammar_minimal as m
import unicodedata

import pytest


# ──── romance_gate ────────────────────────────────────────────────

"""es / pt / fr の文では英語専用の規則（冠詞 a 削除・数詞→数字・3sg -s 落とし）を発火させない。"""


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
    ('Il vous aide.', 'Il vous aide.'),
    ('Elle vous aide.', 'Elle vous aide.'),
    ('Il nous aide.', 'Il nous aide.'),
    ('S il vous plaît.', 'S il vous plaît.'),
])
def test_source_guard_survives_pronoun_pivot(form, src, want):
    assert compress(unicodedata.normalize(form, src)) == want


@pytest.mark.parametrize('boundary', ['. ', '!\n', '? ', '.\" '])
def test_source_guard_is_local_to_sentence(boundary):
    source = 'Il vous aide' + boundary + 'He chooses four chairs.'
    assert compress(source, spelled_nums=True) == 'Il vous aide' + boundary + 'He choose 4 chairs.'


def test_english_do_is_not_a_romance_only_cue():
    assert not is_romance('Do four tests.')
    assert apply_spelled_numbers('Do four tests.') == 'Do 4 tests.'
    assert compress('Do four tests.', spelled_nums=True) == 'Do 4 tests.'
    assert strip_articles('Do a dance.') == 'Do dance.'
    # Portuguese do remains a cue, but cannot by itself outweigh English.
    assert is_romance('Eu vou do parque a casa.')
    assert ' a ' in compress('Eu vou do parque a casa.')


def test_source_context_keeps_protected_spans_and_english_path():
    assert compress('Il vous aide. [[keep:He chooses four.]]', spelled_nums=True) == 'Il vous aide. He chooses four.'
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
        'Il vous aide. ' + compress(english, spelled_nums=True)
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
    # skip_in_protected: 保護文に触れる置換は適用しない（#106 フォローアップ）
    assert substitute_with_romance_context(
        source, substitutions, lambda t, p: t, skip_in_protected=frozenset({0})
    ) == 'Il vous aide. He always chooses.'
    assert seen == [('he vous aide.', True), (' He always chooses.', False)]
    # Callable replacements and full-text lookbehind across language boundaries.
    substitutions = [(re.compile(r'(?<=aide\.) He'), lambda m: ' She')]
    assert substitute_with_romance_context(source, substitutions, finish) == 'Il vous aide. She choose.'


@pytest.mark.parametrize('source', ['', 'abc', 'Il vous aide.', 'Il vous plaît. He chooses.'])
def test_pivot_tracking_identity(source):
    from shared.romance_gate import substitute_with_romance_context
    assert substitute_with_romance_context(source, [], lambda text, protected: text) == source


# ──── romance_followup ────────────────────────────────────────────

"""#106 フォローアップ（3bot レビューの Should 2 点）。"""


@pytest.mark.parametrize(
    "src",
    ["Il a un chat.", "Je vais au marché.", "Elle est très belle.", "Ella es muy alta.", "Ils sont avec nous."],
)
def test_romance_sentence_keeps_pronoun(src):
    out = compress(src)
    assert out.split()[0] == src.split()[0], out


def test_english_sentence_still_pivots_pronoun():
    # 英語文中の je は従来どおり I へ（ゲート外では挙動不変）
    assert compress("I said je. He left.") == "I said I. He left."


def test_mixed_text_only_romance_sentence_protected():
    out = compress("Il a un chat. You see the dog.")
    assert out.startswith("Il a un chat.")
    assert "dog" in out and " the " not in out


@pytest.mark.parametrize("src", ["A Maria come.", "Veo a Juan.", "A Pedro le gusta."])
def test_spanish_personal_a_without_cues_kept(src):
    # #122: 文頭 A＋名前は A\u2011Maria（U+2011）で保護され、実際の復元経路 expand で元に戻る。
    from MorphoGrammarMinimal.morpho_grammar_minimal import expand
    assert expand(compress(src)) == src


@pytest.mark.parametrize(
    "src, want",
    [
        ("A dog ran.", "dog ran."),
        ("The dog ran. A dog ran.", "dog ran. dog ran."),
        ("A Ford is fast.", "A\u2011Ford is fast."),  # #122: 英語 A＋大文字語はハイフン保護
        ("I have a cat.", "I have cat."),
    ],
)
def test_english_article_drop_unchanged(src, want):
    assert compress(src) == want


@pytest.mark.parametrize('literal', ['\ue0a10', '\ue0a11', '\ue0a1', '\ue0a1\ue0a10', 'x\ue0a10y'])
def test_personal_a_does_not_decode_user_placeholder_text(literal):
    from MorphoGrammarMinimal.morpho_grammar_minimal import strip_articles
    source = f'A Maria {literal}.'
    from MorphoGrammarMinimal.morpho_grammar_minimal import expand, restore_a_hyphen
    assert restore_a_hyphen(strip_articles(source)) == source
    assert expand(compress(source)) == source


@pytest.mark.parametrize('name', ['Łukasz', 'Žan', 'İpek', 'ǅuro', 'Στέφανος', 'Дмитрий', '𐐀name', 'Álvaro'])
@pytest.mark.parametrize('form', ['NFC', 'NFD'])
def test_personal_a_supports_unicode_capital_and_titlecase_names(name, form):
    import unicodedata
    source = unicodedata.normalize(form, f'Veo a {name}.')
    assert compress(source) == unicodedata.normalize('NFC', source)


@pytest.mark.parametrize('source,want', [
    ('"a" Veo a Łukasz.', 'a Veo a Łukasz.'),
    ('"a" "a" Veo a ǅuro.', 'a a Veo a ǅuro.'),
    ('Veo a Łukasz. "a" A Maria come.', 'Veo a Łukasz. a A Maria come.'),
    ('I met a Łukasz.', 'I met a\u2011Łukasz.'),
    ('Veo a łukasz.', 'Veo łukasz.'),
    ('A Maria come. I have a cat.', 'A\u2011Maria come. I have cat.'),
])
def test_personal_a_offsets_survive_quotes_and_respect_sentence_cues(source, want):
    from MorphoGrammarMinimal.morpho_grammar_minimal import strip_articles
    assert strip_articles(source) == want


@pytest.mark.parametrize("source", ["Lleva a Ana.", "Dame a mí.", "Llámame a mí.", "Todo vuelve a ti.", "Se mira a sí mismo."])
@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_sparse_spanish_personal_a(source, form):
    import unicodedata
    assert compress(unicodedata.normalize(form, source)) == source


def test_sparse_spanish_mixed_with_english():
    assert compress("Dame a mí. I have a cat. Lleva a Ana.") == (
        "Dame a mí. I have cat. Lleva a Ana."
    )


@pytest.mark.parametrize("source,want", [
    ("Give a minute.", "provide minute."),
    ("A mime ran.", "mime ran."),
    ("I saw a mí label.", "I saw mí label."),
])
def test_personal_pronoun_guard_does_not_expand_english_scope(source, want):
    assert compress(source) == want


# ──── romance_con ─────────────────────────────────────────────────

"""Regression: ``con`` is never rewritten to ``with`` (Romance or English)."""


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
