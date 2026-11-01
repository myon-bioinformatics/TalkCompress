"""英語の A/a ＋大文字語は半角スペースを `-` に置換して保護し、restore_a_hyphen で戻す（#111）。"""
import unicodedata

import pytest

from MorphoZip.morpho_zip import compress, expand, restore_a_hyphen, strip_articles

HYPHEN = [
    ("A Maria come.", "A\u2011Maria come."),  # 文頭
    ("She said hi. A Maria came.", "She said hi. A\u2011Maria came."),  # 文中の文頭
    ("I met a John yesterday.", "I met a\u2011John yesterday."),  # 文中（英語）
    ("It was a Tesla.", "It was a\u2011Tesla."),  # 文末
    ("A Boy Named Sue.", "A\u2011Boy Named Sue."),
    ("(A Maria come.)", "(A\u2011Maria come.)"),  # 括弧
    ("[A Maria come.]", "[A\u2011Maria come.]"),
    ('"A Maria" come.', '"A\u2011Maria" come.'),  # straight 引用符
    ("I met a Émile there.", "I met a\u2011Émile there."),  # 非 ASCII 大文字
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

# 利用者が書いた ASCII ハイフンの A-/a- 形は、compress でも expand でも変わらない。
A_FORMS = ["A-list", "A-League", "A-Team", "A-Teams", "A-Level", "A-Levels", "A-Bombs",
           "A-OK", "A-Z", "A-Rod", "A-Side", "A-Wing", "A-ha", "A-Class", "A-Train",
           "A-Line", "A-Plus", "A-Maria", "a-priori", "a-La"]
OTHER_FORMS = ["e-mail", "E-mail", "B-boy", "C-section", "D-day", "X-ray", "T-shirt", "U-turn", "F-15"]
WHITELIST = A_FORMS + OTHER_FORMS


@pytest.mark.parametrize(("src", "want"), HYPHEN)
def test_hyphen_and_roundtrip(src, want):
    assert strip_articles(src) == want
    assert restore_a_hyphen(want) == src


def test_curly_quotes_via_compress():
    out = compress("\u201cA Maria\u201d come.")
    assert "A\u2011Maria" in out
    assert "A Maria" in restore_a_hyphen(out)


@pytest.mark.parametrize("src", KEEP)
def test_out_of_scope_untouched(src):
    out = strip_articles(src)
    assert "\u2011" not in out
    assert restore_a_hyphen(out) == out


@pytest.mark.parametrize("form", WHITELIST)
def test_whitelist_not_split(form):
    s = f"See the {form} now."
    assert restore_a_hyphen(s) == s
    assert form in compress(s)
    if form in A_FORMS:  # expand の既存の短縮語展開（U→you 等）は本 PR の対象外
        assert expand(compress(s)) == compress(s)


@pytest.mark.parametrize(("src", "want"), HYPHEN)
def test_nfd_rerun(src, want):
    nfd = unicodedata.normalize("NFD", src)
    assert strip_articles(nfd) == unicodedata.normalize("NFC", want)
    assert restore_a_hyphen(strip_articles(nfd)) == unicodedata.normalize("NFC", src)


@pytest.mark.parametrize(("src", "want"), HYPHEN)
def test_end_to_end_expand(src, want):
    # 実際の復元経路: compress → expand
    out = compress(src)
    assert "\u2011" in out
    assert expand(out) == src


def test_quoted_article_offset():
    # 引用符付き "a" のマスクで offset がずれても、正しい a にハイフンが付く。
    assert strip_articles('"a" I met a Canadian.') == "a I met a\u2011Canadian."
    assert strip_articles('"the" and "a" so I met a Canadian.') == "the and a so I met a\u2011Canadian."


def test_all_caps_word_branch():
    # 全大文字語は名前ではないので従来どおり（英語文は削除、それ以外は保持）。
    assert strip_articles("A USB funciona.") == "A USB funciona."
    assert strip_articles("I have a USB.") == "I have USB."


def test_dash_counts_as_sentence_start():
    # 英語の手がかり語がない文で、ダッシュ直後の大文字 A は文頭扱い。
    assert strip_articles("x\u2014A Maria come.") == "x\u2014A\u2011Maria come."
    assert strip_articles("x\u2013A Maria come.") == "x\u2013A\u2011Maria come."


def test_restore_lookbehind():
    for t in ["l'A\u2011Maria", "l\u2019A\u2011Maria", "x-A\u2011Maria", "xA\u2011Maria", "x\u2011A\u2011Maria"]:
        assert restore_a_hyphen(t) == t


def test_restore_normalizes_nfd():
    assert restore_a_hyphen(unicodedata.normalize("NFD", "A\u2011\u00c9mile")) == "A \u00c9mile"


def test_restore_only_u2011():
    # ASCII ハイフンは利用者の文字として扱い、分割しない。
    assert restore_a_hyphen("I drive an A-Class car. A-Maria came.") == "I drive an A-Class car. A-Maria came."
    assert restore_a_hyphen("A\u2011Sides") == "A Sides"


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("I drive an A-Class car.", "I drive A-Class car."),
        ("A-Maria came.", "A-Maria came."),
        ("We met a-La Paz.", "We met a-La Paz."),
        ("It was a-priori known.", "It was a-priori known."),
    ],
)
def test_user_hyphen_roundtrip(src, want):
    assert compress(src) == want
    assert expand(compress(src)) == want


def test_input_u2011_folded_to_ascii():
    # 入力に元からある U+2011 は ASCII - に畳み、復元で空白にならない（仕様）。
    src = "A\u2011Maria came. Use the A\u2011Class."
    out = compress(src)
    assert out.count("\u2011") == 0
    assert expand(out) == out


def test_u2011_survives_densityzip():
    import argparse
    import importlib.util
    from pathlib import Path

    src = "I met a John. A Maria come."
    out = compress(src)
    # DensityZip 経由（engine e）
    spec = importlib.util.spec_from_file_location("dz", Path(__file__).resolve().parents[1] / "DensityZip/density_zip.py")
    dz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dz)
    assert "\u2011" in dz._run_e(src, argparse.Namespace(mode="compress"))
    assert dz._run_e(out, argparse.Namespace(mode="expand")) == src


def test_u2011_estimate_tokens():
    from TesseraTalk.tessera_talk import estimate_tokens

    assert estimate_tokens("A\u2011Maria come.") >= estimate_tokens("A Maria come.")


def test_u2011_survives_morphozip_cli(capsys):
    from MorphoZip import morpho_zip

    morpho_zip.main(["--text", "I met a John. A Maria come."])
    out = capsys.readouterr().out.strip()
    assert "a\u2011John" in out and "A\u2011Maria" in out
    morpho_zip.main(["--mode", "expand", "--text", out])
    assert capsys.readouterr().out.strip() == "I met a John. A Maria come."


KEEP_SRC = "A\u2011Maria came."  # 利用者入力の U+2011 → ASCII '-' に正規化


def test_keep_articles_input_u2011_morphozip():
    out = compress(KEEP_SRC, keep_articles=True)
    assert "\u2011" not in out and "A-Maria" in out
    assert expand(out) == expand(compress("A-Maria came.", keep_articles=True))
    assert "A-Maria" in expand(out)


def test_keep_articles_input_u2011_densityzip():
    import argparse
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("dz", Path(__file__).resolve().parents[1] / "DensityZip/density_zip.py")
    dz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dz)
    out = dz._run_e(KEEP_SRC, argparse.Namespace(mode="compress", keep_articles=True))
    assert "\u2011" not in out and "A-Maria" in out
    assert "A-Maria" in dz._run_e(out, argparse.Namespace(mode="expand", keep_articles=True))


def test_keep_articles_input_u2011_cli(capsys):
    from MorphoZip import morpho_zip

    morpho_zip.main(["--keep-articles", "--text", KEEP_SRC])
    out = capsys.readouterr().out.strip()
    assert "\u2011" not in out and "A-Maria" in out
    morpho_zip.main(["--mode", "expand", "--text", out])
    assert "A-Maria" in capsys.readouterr().out


@pytest.mark.parametrize("src", ["x-a test", "well-an expert", "x\u2011a test", "the-end"])
def test_hyphen_adjacent_article_guard(src):
    want = src.replace("\u2011", "-")
    assert strip_articles(src) == want


@pytest.mark.parametrize("keep", [False, True])
def test_u2011_in_keep_span_preserved(keep):
    out = compress("[[keep:A\u2011Maria]] came.", keep_articles=keep)
    assert "A\u2011Maria" in out


@pytest.mark.parametrize("keep", [False, True])
def test_u2011_in_protect_regex_preserved(keep):
    out = compress("see x\u2011y the cat now", protect_regexes=[r"x\u2011y the cat"], keep_articles=keep)
    assert "x\u2011y the cat" in out


@pytest.mark.parametrize("keep", [False, True])
def test_u2011_outside_protected_still_folded(keep):
    out = compress("[[keep:x\u2011y]] and A\u2011Maria came.", keep_articles=keep)
    assert "x\u2011y" in out and "A-Maria" in out
