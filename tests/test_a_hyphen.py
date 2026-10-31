"""英語の A/a ＋大文字語は半角スペースを `-` に置換して保護し、restore_a_hyphen で戻す（#111）。"""
import unicodedata

import pytest

from MorphoZip.morpho_zip import compress, expand, restore_a_hyphen, strip_articles

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

# A- の既存形（大文字始まりも含む・複数形も）は復元で分割しない。
A_FORMS = ["A-list", "A-League", "A-Team", "A-Teams", "A-Level", "A-Levels", "A-Bombs",
           "A-OK", "A-Z", "A-Rod", "A-Side", "A-Wing", "A-ha"]
# A 以外の単一文字＋ハイフンの既存形は、そもそも規則の対象外で不変。
OTHER_FORMS = ["e-mail", "E-mail", "B-boy", "C-section", "D-day", "X-ray", "T-shirt", "U-turn", "F-15"]
WHITELIST = A_FORMS + OTHER_FORMS


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


@pytest.mark.parametrize(("src", "want"), HYPHEN)
def test_end_to_end_expand(src, want):
    # 実際の復元経路: compress → expand
    out = compress(src)
    assert "-" in out
    assert expand(out) == src


def test_quoted_article_offset():
    # 引用符付き "a" のマスクで offset がずれても、正しい a にハイフンが付く。
    assert strip_articles('"a" I met a Canadian.') == "a I met a-Canadian."
    assert strip_articles('"the" and "a" so I met a Canadian.') == "the and a so I met a-Canadian."


def test_all_caps_word_branch():
    # 全大文字語は名前ではないので従来どおり（英語文は削除、それ以外は保持）。
    assert strip_articles("A USB funciona.") == "A USB funciona."
    assert strip_articles("I have a USB.") == "I have USB."


def test_dash_counts_as_sentence_start():
    # 英語の手がかり語がない文で、ダッシュ直後の大文字 A は文頭扱い。
    assert strip_articles("x\u2014A Maria come.") == "x\u2014A-Maria come."
    assert strip_articles("x\u2013A Maria come.") == "x\u2013A-Maria come."


def test_restore_lookbehind():
    for s in ["l'A-Maria", "l\u2019A-Maria", "x-A-Maria", "xA-Maria"]:
        assert restore_a_hyphen(s) == s


def test_restore_normalizes_nfd():
    assert restore_a_hyphen(unicodedata.normalize("NFD", "A-\u00c9mile")) == "A \u00c9mile"


def test_whitelist_case_insensitive_stem_plural():
    assert restore_a_hyphen("the A-LIST and a-teams") == "the A-LIST and a-teams"
    assert restore_a_hyphen("A-Sides A-Maria") == "A-Sides A Maria"
