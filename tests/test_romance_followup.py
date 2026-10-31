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
    assert out.startswith("Il a-un chat.")
    assert "dog" in out and " the " not in out


@pytest.mark.parametrize(
    "src, want",
    [
        ("A Maria come.", "A-Maria come."),
        ("Veo a Juan.", "Veo a-Juan."),
        ("A Pedro le gusta.", "A-Pedro le gusta."),
    ],
)
def test_spanish_personal_a_kept_with_hyphen(src, want):
    assert compress(src) == want


# 1文字の単語は直後の半角スペースをハイフンにして守る（言語によらず同じ決まり）
@pytest.mark.parametrize(
    "src, want",
    [
        ("Juan y María comen pan.", "Juan y-María comen pan."),
        ("Quiero té o café.", "Quiero té o-café."),
        ("Padre e hijo comen.", "Padre e-hijo comen."),
        ("Siete u ocho perros.", "Siete u-ocho perros."),
        ("Vejo a casa hoje.", "Vejo a-casa hoje."),
        ("Ele é muito bom.", "Ele é-muito bom."),
        ("Vou à praia hoje.", "Vou à-praia hoje."),
        ("Il y a du pain.", "Il y-a-du pain."),
        ("Lui è molto bravo.", "Lui è-molto bravo."),
        ("O Vejo o menino.", "O-Vejo o-menino."),
        ("a veo a Juan.", "a-veo a-Juan."),
    ],
)
def test_one_letter_words_kept_with_hyphen(src, want):
    assert compress(src) == want


@pytest.mark.parametrize(
    "src, want",
    [
        ("A dog ran.", "A-dog ran."),
        ("A Ford is fast.", "A-Ford is fast."),
        ("I have a cat.", "I have a-cat."),
        ("He sent an e-mail.", "He sent e-mail."),
    ],
)
def test_english_one_letter_rule(src, want):
    assert compress(src) == want
