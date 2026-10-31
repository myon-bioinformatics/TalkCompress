"""#106 フォローアップ（3bot レビューの Should 2 点）。"""
import pytest

from MorphoZip.morpho_zip import compress


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
    from MorphoZip.morpho_zip import restore_a_hyphen
    assert restore_a_hyphen(compress(src)) == src


@pytest.mark.parametrize(
    "src, want",
    [
        ("A dog ran.", "dog ran."),
        ("The dog ran. A dog ran.", "dog ran. dog ran."),
        ("A Ford is fast.", "A-Ford is fast."),
        ("I have a cat.", "I have cat."),
    ],
)
def test_english_article_drop_unchanged(src, want):
    assert compress(src) == want


@pytest.mark.parametrize('literal', ['\ue0a10', '\ue0a11', '\ue0a1', '\ue0a1\ue0a10', 'x\ue0a10y'])
def test_personal_a_does_not_decode_user_placeholder_text(literal):
    from MorphoZip.morpho_zip import strip_articles
    source = f'A Maria {literal}.'
    want = source.replace('A Maria', 'A-Maria', 1)
    # 私用領域の文字は内部記号として復号されないこと（ハイフン化の有無は問わない）。
    assert strip_articles(source) in {source, want}
    assert compress(source) in {source, want}


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
    ('I met a Łukasz.', 'I met a-Łukasz.'),
    ('Veo a łukasz.', 'Veo łukasz.'),
    ('A Maria come. I have a cat.', 'A-Maria come. I have cat.'),
])
def test_personal_a_offsets_survive_quotes_and_respect_sentence_cues(source, want):
    from MorphoZip.morpho_zip import strip_articles
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
