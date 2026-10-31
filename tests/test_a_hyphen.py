"""英語の A/a ＋大文字語は半角スペースを `-` に置換して保護し、restore_a_hyphen で戻す（#111）。"""
import unicodedata

import pytest

from MorphoZip.morpho_zip import compress, restore_a_hyphen, strip_articles

HYPHEN = [
    ("A Maria come.", "A-Maria come."),  # 文頭
    ("She said hi. A Maria came.", "She said hi. A-Maria came."),  # 文中の文頭
    ("I met a John yesterday.", "I met a-John yesterday."),  # 文中（英語）
    ("It was a Tesla.", "It was a-Tesla."),  # 文末
    ("A Boy Named Sue.", "A-Boy Named Sue."),
    ("(A Maria come.)", "(A-Maria come.)"),  # 括弧
    ("[A Maria come.]", "[A-Maria come.]"),
    ('"A Maria" come.', '"A-Maria" come.'),  # straight 引用符
    ("I met a Émile there.", "I met a-Émile there."),  # 非 ASCII 大文字
]

KEEP = [
    "Veo a Juan.",  # es 機能語 a
    "Vi a Pedro.",
    "Il est à Paris.",  # fr à
    "Y a-t-il un chat?",  # fr -t-il
    "Vou buscá-la.",  # pt 接語
    "Plan A Fails.",  # ラベル
    "Plan A is fine.",
    "A, B, and C.",  # 列挙
]

WHITELIST = ["A-list", "A-League", "e-mail", "B-boy", "C-section", "D-day", "X-ray", "T-shirt", "U-turn", "F-15"]


@pytest.mark.parametrize(("src", "want"), HYPHEN)
def test_hyphen_and_roundtrip(src, want):
    assert strip_articles(src) == want
    assert restore_a_hyphen(want) == src


def test_curly_quotes_via_compress():
    out = compress("\u201cA Maria\u201d come.")
    assert "A-Maria" in out
    assert "A Maria" in restore_a_hyphen(out)


@pytest.mark.parametrize("src", KEEP)
def test_out_of_scope_untouched(src):
    out = strip_articles(src)
    assert "-" not in out.replace(src, "") or out == src
    assert restore_a_hyphen(out) == out


@pytest.mark.parametrize("form", WHITELIST)
def test_whitelist_not_split(form):
    s = f"See the {form} now."
    assert restore_a_hyphen(s) == s
    assert form in compress(s)


@pytest.mark.parametrize(("src", "want"), HYPHEN)
def test_nfd_rerun(src, want):
    nfd = unicodedata.normalize("NFD", src)
    assert strip_articles(nfd) == unicodedata.normalize("NFC", want)
    assert restore_a_hyphen(strip_articles(nfd)) == unicodedata.normalize("NFC", src)
