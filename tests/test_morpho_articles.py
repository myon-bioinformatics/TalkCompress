"""MorphoGrammarMinimal (E): 冠詞 a / A の削除と保護。

- a_hyphen: 英語の A/a ＋大文字語は半角スペースを `-` に置換して保護し、restore_a_hyphen で戻す（#111）。
- article_after_open: Article dropped right after an opening quote/bracket leaves no stray space.
- article_capital_a: 大文字 A は文頭のときだけ冠詞として落とす（Plan A / vitamin A などのラベルは保持）。
- article_combining: NFD combining marks: ``á`` (á) is never the article ``a``.
- quoted_capital_a
- single_letter_matrix: 大文字1文字 A–Z × 例文の型 × 全経路の総当たり（手選びの例なし）。
"""

from __future__ import annotations

from MorphoGrammarMinimal.morpho_grammar_minimal import compress
from MorphoGrammarMinimal.morpho_grammar_minimal import expand
from MorphoGrammarMinimal.morpho_grammar_minimal import restore_a_hyphen
from MorphoGrammarMinimal.morpho_grammar_minimal import strip_articles
from pathlib import Path
import importlib.util
import inspect
import sys
import unicodedata

import pytest


# ──── a_hyphen ────────────────────────────────────────────────────

"""英語の A/a ＋大文字語は半角スペースを `-` に置換して保護し、restore_a_hyphen で戻す（#111）。"""


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


def test_u2011_survives_densityfacaderoute():
    import argparse
    import importlib.util
    from pathlib import Path

    src = "I met a John. A Maria come."
    out = compress(src)
    # DensityFacadeRoute 経由（engine e）
    spec = importlib.util.spec_from_file_location("dz", Path(__file__).resolve().parents[1] / "DensityFacadeRoute/density_facade_route.py")
    dz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dz)
    assert "\u2011" in dz._run_e(src, argparse.Namespace(mode="compress"))
    assert dz._run_e(out, argparse.Namespace(mode="expand")) == src


def test_u2011_estimate_tokens():
    from SentenceCalibratedMosaic.sentence_calibrated_mosaic import estimate_tokens

    assert estimate_tokens("A\u2011Maria come.") >= estimate_tokens("A Maria come.")


def test_u2011_survives_morphogrammarminimal_cli(capsys):
    from MorphoGrammarMinimal import morpho_grammar_minimal

    morpho_grammar_minimal.main(["--text", "I met a John. A Maria come."])
    out = capsys.readouterr().out.strip()
    assert "a\u2011John" in out and "A\u2011Maria" in out
    morpho_grammar_minimal.main(["--mode", "expand", "--text", out])
    assert capsys.readouterr().out.strip() == "I met a John. A Maria come."


KEEP_SRC = "A\u2011Maria came."  # 利用者入力の U+2011 → ASCII '-' に正規化


def test_keep_articles_input_u2011_morphogrammarminimal():
    out = compress(KEEP_SRC, keep_articles=True)
    assert "\u2011" not in out and "A-Maria" in out
    assert expand(out) == expand(compress("A-Maria came.", keep_articles=True))
    assert "A-Maria" in expand(out)


def test_keep_articles_input_u2011_densityfacaderoute():
    import argparse
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("dz", Path(__file__).resolve().parents[1] / "DensityFacadeRoute/density_facade_route.py")
    dz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dz)
    out = dz._run_e(KEEP_SRC, argparse.Namespace(mode="compress", keep_articles=True))
    assert "\u2011" not in out and "A-Maria" in out
    assert "A-Maria" in dz._run_e(out, argparse.Namespace(mode="expand", keep_articles=True))


def test_keep_articles_input_u2011_cli(capsys):
    from MorphoGrammarMinimal import morpho_grammar_minimal

    morpho_grammar_minimal.main(["--keep-articles", "--text", KEEP_SRC])
    out = capsys.readouterr().out.strip()
    assert "\u2011" not in out and "A-Maria" in out
    morpho_grammar_minimal.main(["--mode", "expand", "--text", out])
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


# ──── article_after_open ──────────────────────────────────────────

"""Article dropped right after an opening quote/bracket leaves no stray space."""


ROOT = Path(__file__).resolve().parents[1]


_spec = importlib.util.spec_from_file_location("morpho_grammar_minimal", ROOT / "MorphoGrammarMinimal/morpho_grammar_minimal.py")


mz = importlib.util.module_from_spec(_spec)


sys.modules.setdefault("morpho_grammar_minimal", mz)


_spec.loader.exec_module(mz)


@pytest.mark.parametrize(
    ("src", "out"),
    [
        ("“the cat”", '"cat"'),
        ('"the cat"', '"cat"'),
        ("'the cat'", "'cat'"),
        ("‘the cat’", "'cat'"),
        ("(the cat)", "(cat)"),
        ("x(the cat)", "x(cat)"),
        ("[a dog]", "[dog]"),
        ("{an owl}", "{owl}"),
        ("「the cat」", "「cat」"),
        ("『the cat』", "『cat』"),
        ("【the cat】", "【cat】"),
        ("（the cat）", "（cat）"),
        ("«the café»", "«café»"),
        ("‹a niño›", "‹niño›"),
        ("“The Zu\u0308rich”", '"Zürich"'),
        ('("the cat")', '("cat")'),
        ('line\n"the cat"', 'line\n"cat"'),
        ('he said "the cat"', 'he said "cat"'),
        ('I said "x" the end', 'I said "x" end'),
        ('x"the cat"', 'x"cat"'),  # article+space dropped independently of the opener
        ('"a" b', "a b"),  # quoted article keeps inner word
        ("(the.x)", "(the.x)"),
        ("(theory)", "(theory)"),
    ],
)
def test_article_after_opener(src, out):
    assert mz.compress(src) == out


@pytest.mark.parametrize(
    ("src", "out"),
    [
        ("‘rock ’n’ roll’", "'rock ’n’ roll'"),
        ("‘a\nb’", "'a\nb’"),  # pairs never cross a newline
        ("‘the dogs’ bones’", "'the dogs' bones’"),  # ambiguous: shortest pair (first word-final ’)
        ("‘x ’n y’", "'x ’n y'"),
        ("‘Bob’s", "'Bob’s"),  # no closer: in-word ’ is not a closing quote
    ],
)
def test_single_pair_edges(src, out):
    assert mz.normalize_quotes(src) == out


# ──── article_capital_a ───────────────────────────────────────────

"""大文字 A は文頭のときだけ冠詞として落とす（Plan A / vitamin A などのラベルは保持）。"""


KEEP_article_capital_a = [
    ("Plan A failed.", "Plan A failed."),
    ("Take vitamin A daily.", "Take vitamin A daily."),
    ("Type A blood.", "Type A blood."),
    ("He got grade A work.", "He got grade A work."),
    ("Use A4 paper.", "Use A4 paper."),
    ("A4 paper.", "A4 paper."),
    ("A/B test.", "A/B test."),
    ("Run A/B tests.", "Run A/B tests."),
    ("J. A. Smith came.", "J. A. Smith came."),
    ("A. Smith came.", "A. Smith came."),
    ("Plan A.", "Plan A."),
    ("Plan A, then B.", "Plan A, then B."),
    ("Plan A\nfailed.", "Plan A\nfailed."),
]


DROP = [
    ("A cat sat.", "cat sat."),
    ("Hi. A cat sat.", "Hi. cat sat."),
    ("Hi! A cat.", "Hi! cat."),
    ("Hi? A cat.", "Hi? cat."),
    ("x\nA cat.", "x\ncat."),
    ("(A cat)", "(cat)"),
    ("[A cat]", "[cat]"),
    ('"A cat"', '"cat"'),
    ("'A cat'", "'cat'"),
    ("river.\u2014A dog.", "river.\u2014dog."),
    ('called "Nurse." A chef.', 'called "Nurse." chef.'),
    ("[aside] A reminder.", "[aside] reminder."),
    ("(aside) A reminder.", "(aside) reminder."),
    ("Plan A. A dog.", "Plan A. dog."),
]


LOWER = [
    ("I saw a cat and an owl.", "I saw cat and owl."),
    ("The end. An ox.", "end. ox."),
    ("THE END", "END"),
    ("Take a vitamin pill.", "Take vitamin pill."),
]


@pytest.mark.parametrize(("src", "want"), KEEP_article_capital_a + DROP + LOWER)
def test_strip_articles_capital_a(src, want):
    assert strip_articles(src) == want


@pytest.mark.parametrize("label", ["Plan A", "vitamin A", "Type A", "grade A"])
def test_compress_keeps_label_a(label):
    assert f"{label} " in compress(f"Then {label} worked well.")


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("A said no.", "A said no."),
        ("A is the key.", "A is key."),
        ("A and B match.", "A and B match."),
        ('He said "A or B".', 'He said "A or B".'),
        ("A furnished flat.", "A furnished flat."),  # -ed 後は安全側で保持
    ],
)
def test_sentence_initial_a_before_predicate_is_symbol(src, want):
    assert strip_articles(src) == want


@pytest.mark.parametrize('predicate', ['is', 'wins', 'said', 'and', 'furnished'])
@pytest.mark.parametrize('case', [str.title, str.upper, lambda s: s[:1]+s[1:].upper()])
def test_symbol_predicate_case_preserved(predicate, case):
    text = 'A ' + case(predicate) + ' B.'
    assert strip_articles(text) == text


@pytest.mark.parametrize('src,want', [
    ('a IS key.', 'IS key.'),
    ('Plan A failed.', 'Plan A failed.'),
    ('A cat sat.', 'cat sat.'),
    ('THE END', 'END'),
    ('An owl.', 'owl.'),
    ('A ıs key.', 'ıs key.'),  # dotless i is not the ASCII predicate is
    ('A İS key is short.', 'İS key is short.'),  # English cue bypasses personal-a guard
])
def test_article_casefold_is_scoped(src, want):
    assert strip_articles(src) == want


# ──── article_combining ───────────────────────────────────────────

"""NFD combining marks: ``a\u0301`` (á) is never the article ``a``."""


sys.modules.setdefault("morpho_grammar_minimal", mz)


_spec.loader.exec_module(mz)


NFD = lambda s: unicodedata.normalize("NFD", s)  # noqa: E731


CASES = [
    ("(á la)", "(á la)"),
    ("à la carte", "à la carte"),
    ("go à la mode", "go à la mode"),
    ("thé vert", "thé vert"),
    ("ań x", "ań x"),
    ("À la", "À la"),
    ("“à la”", "“à la”"),
    ("(the á)", "(á)"),
    ("go a café", "go café"),
]


@pytest.mark.parametrize(("src", "out"), CASES)
@pytest.mark.parametrize("form", ["NFC", "NFD"])
def test_strip_articles_combining(src, out, form):
    assert mz.strip_articles(unicodedata.normalize(form, src)) == out


@pytest.mark.parametrize(("src", "out"), CASES)
def test_regexes_reject_combining_mark(src, out):
    """Defence in depth: the regexes alone (no NFC) leave NFD á/à intact."""
    s = NFD(src)
    for pat in (mz._ARTICLE_WORD, mz._ARTICLE_SURFACE_RE):
        for m in pat.finditer(s):
            assert not unicodedata.combining(s[m.end() : m.end() + 1] or "x")
    assert mz._ARTICLE_WORD.sub("", NFD("a\u0301")) == NFD("a\u0301")
    assert mz._ARTICLE_WORD.sub("", NFD("(a\u0300 la)")) == NFD("(a\u0300 la)")
    assert mz._ARTICLE_SURFACE_RE.findall(NFD("à a")) == ["a"]


def test_compress_and_pack_nfd():
    for src in ("(á la) the cat", "in Zürich à la"):
        assert mz.compress(NFD(src)) == mz.compress(src)
    assert mz.pack_tokens(NFD("in Zürich")) == mz.pack_tokens("in Zürich") == "in Zürich"
    assert mz.pack_tokens("") == ""


def test_no_single_arg_function_breaks_on_nfd():
    """Audit: every 1-arg text function gives the same (NFC) result for NFD input."""
    sample = "(á la) à la carte thé the café, in Zürich “the cat”. I don’t know, ça va"
    for name, fn in inspect.getmembers(mz, inspect.isfunction):
        if fn.__module__ != mz.__name__:
            continue
        req = [p for p in inspect.signature(fn).parameters.values() if p.default is p.empty]
        if len(req) != 1:
            continue
        try:
            a, b = fn(NFD(sample)), fn(sample)
        except Exception:  # non-text helpers
            continue
        if isinstance(a, str):
            assert unicodedata.normalize("NFC", a) == unicodedata.normalize("NFC", b), name


# ──── quoted_capital_a ────────────────────────────────────────────

@pytest.mark.parametrize(
    "text",
    ["Mark it ‘A’ now.", 'Mark it "A" now.', "Mark it 'A' now.", "Grade “A” work."],
)
def test_quoted_capital_a_keeps_quotes(text):
    for fn in (strip_articles, compress):
        out = fn(text)
        assert "A" in out and out.count("A") == text.count("A")
        assert any(q + "A" in out for q in "\"'‘“"), out


def test_quoted_capital_a_same_as_other_letters():
    a = strip_articles('Mark it "A" now.')
    b = strip_articles('Mark it "B" now.')
    assert a.replace("A", "B") == b


def test_quoted_lowercase_article_still_unwrapped():
    assert strip_articles('Say "the" twice.') == "Say the twice."
    assert strip_articles("Say “a” once.") == "Say a once."


# ──── single_letter_matrix ────────────────────────────────────────

"""大文字1文字 A–Z × 例文の型 × 全経路の総当たり（手選びの例なし）。"""


_spec_single_letter_matrix = importlib.util.spec_from_file_location("sla", ROOT / "scripts/single_letter_audit.py")


sla = importlib.util.module_from_spec(_spec_single_letter_matrix)


_spec_single_letter_matrix.loader.exec_module(sla)


CASES_single_letter_matrix = [
    (t, L, p)
    for t, _ in sla.TEMPLATES
    for L in sla.LETTERS
    for p in sla.PIPES
    if (L, t) not in sla.EXEMPT
]


TPL = dict(sla.TEMPLATES)


@pytest.mark.parametrize(("tname", "letter", "pipe"), CASES_single_letter_matrix)
def test_single_capital_survives(tname, letter, pipe):
    ok, got = sla.check(letter, TPL[tname], sla.PIPES[pipe])
    assert ok, got


@pytest.mark.parametrize(("letter", "tname"), sorted(sla.EXEMPT))
def test_exempt_is_dropped_article(letter, tname):
    # 除外一覧は「意図的に落とす」ことの確認（一覧が空洞化しないように）
    got = sla.PIPES["MorphoGrammarMinimal"](TPL[tname].replace("_", letter))
    assert sla.standalone_count(letter, got) == 0, got


def test_exempt_list_is_only_article_a():
    assert {L for L, _ in sla.EXEMPT} == {"A"}
