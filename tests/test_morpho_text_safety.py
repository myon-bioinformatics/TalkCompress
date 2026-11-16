"""MorphoGrammarMinimal (E): 文字種・数値・引用符まわりの安全性（ASCII 畳み込み、数値の or、結合文字、引用符）。

- morpho_ascii_casefold: MorphoGrammarMinimal の手書き re.I パターンは ASCII 字母を ı/İ/ſ/U+212A に畳み込まない。
- morpho_numeric_alternatives
- morpho_or_between_numbers: MorphoGrammarMinimal: or/oder/ou between two numbers must not turn into a fraction-like "3 / 4".
- pack_tokens_combining: pack_tokens: 結合文字(NFD のアクセント・ベトナム語の声調)で単語が分割されないこと。
- quote_normalize: Curly→straight quote normalisation (MorphoGrammarMinimal) and scripts/quote_roundtrip.py.
"""

from __future__ import annotations

from MorphoGrammarMinimal import morpho_grammar_minimal as M
from MorphoGrammarMinimal import morpho_grammar_minimal as mz
from MorphoGrammarMinimal.morpho_grammar_minimal import pack_tokens
from pathlib import Path
from tests._helpers import load
import ast
import importlib.util
import re
import sys
import typing
import unicodedata

import pytest


# ──── morpho_ascii_casefold ───────────────────────────────────────

"""MorphoGrammarMinimal の手書き re.I パターンは ASCII 字母を ı/İ/ſ/U+212A に畳み込まない。"""


SRC = Path(M.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "text",
    ["Thıs is fine.", "because of thıs", "Alſo the user."],
)
def test_compress_leaves_non_ascii_lookalikes(text):
    out = M.compress(text)
    word = next(w for w in re.findall(r"\w+", text) if not w.isascii())
    assert word in out


def test_compress_ascii_still_case_insensitive():
    assert M.compress("This is fine.") == M.compress("this is fine.")
    assert M.compress("Also the user.") != "Also the user."


@pytest.mark.parametrize("bad", ["\u0131", "\u0130", "\u017f", "\u212a"])
def test_ci_compile_rejects_lookalikes(bad):
    ascii_ch = {"\u0131": "i", "\u0130": "i", "\u017f": "s", "\u212a": "k"}[bad]
    pat = M._ci_compile(rf"\bx{ascii_ch}y\b", re.I)
    assert pat.search(f"x{ascii_ch.upper()}y")
    assert not pat.search(f"x{bad}y")
    cls = M._ci_compile(r"\b[a-z]+\b", re.I)
    assert cls.fullmatch(f"ab{bad}") is None


def test_boundaries_stay_unicode():
    pat = M._ci_compile(r"\bor\b", re.I)
    assert pat.search("café OR thé")
    assert not pat.search("éor")
    plain = re.compile(r"\bor\b", re.I)
    for text in ("éor", unicodedata.normalize("NFD", "éor x"), "naïve or", "e\u0301 or"):
        assert [m.span() for m in pat.finditer(text)] == [m.span() for m in plain.finditer(text)]
    assert M.compress(unicodedata.normalize("NFD", "café or thé")) == M.compress("café or thé")
    assert M._ci_compile(r"\w+", re.I).fullmatch("café")
    assert M._ci_compile(r"caf[eé]", re.I).fullmatch("CAFÉ")


@pytest.mark.parametrize(
    "src,want",
    [
        (r"colou?r", "(?a:colo)(?a:u)?(?a:r)"),
        (r"ab{2}", "(?a:a)(?a:b){2}"),
        (r"x*", "(?a:x)*"),
        (r"[a-z]+\s", r"(?a:[a-z])+\s"),
        (r"[^]a]", "(?a:[^]a])"),
        (r"[\w']", r"[\w']"),
        (r"[eé]", "[eé]"),
        (r"[\]a]b", r"(?a:[\]a])(?a:b)"),
        (r"\xab", r"\xab"),
        (r"[\u0041b][\x41b]", r"[\u0041b][\x41b]"),
        (r"[\t ]", r"[\t ]"),
        ("café", "(?a:caf)é"),
        ("cafe\u0301s", "(?a:caf)e\u0301(?a:s)"),
        ("e\u0301", "e\u0301"),
        (r"[0-9]", "[0-9]"),
        (r"\u00e9t\x41\U0001F600\N{LATIN SMALL LETTER A}b", r"\u00e9(?a:t)\x41\U0001F600\N{LATIN SMALL LETTER A}(?a:b)"),
        (r"(?P<w>ab)(?P=w)", "(?P<w>(?a:ab))(?P=w)"),
        (r"(?<!x)(?<=y)(?=z)(?!q)(?:r)", "(?<!(?a:x))(?<=(?a:y))(?=(?a:z))(?!(?a:q))(?:(?a:r))"),
        (r"(?i)a(?s:b)", "(?i)(?a:a)(?s:(?a:b))"),
        (r"\bdon't\b", r"\b(?a:don)'(?a:t)\b"),
    ],
)
def test_ascii_case_rewrite(src, want):
    assert M._ascii_case(src) == want
    re.compile(want)


def test_no_unscoped_ignorecase_compiles_left():
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "re"
        ):
            for sub in ast.walk(node):
                assert not (
                    isinstance(sub, ast.Attribute)
                    and isinstance(sub.value, ast.Name)
                    and sub.value.id == "re"
                    and sub.attr in ("I", "IGNORECASE")
                ), f"line {node.lineno}: use _ci_compile"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "(?i" not in node.value, f"line {node.lineno}: use _ci_compile"


def test_pattern_source_keeps_hand_written_text():
    pat = M._ci_compile(r"\bkind of\b", re.I)
    assert pat.pattern == r"\b(?a:kind) (?a:of)\b"
    assert M.pattern_source(pat) == r"\bkind of\b"
    assert M.pattern_source(re.compile("zz")) == "zz"
    for name in ("_SUBS", "_PHRASE_GRAMMAR", "_COUNTER_SUBS"):
        for pat, _ in getattr(M, name):
            assert "(?a:" not in M.pattern_source(pat)


def test_build_surface_re_ascii_case_only():
    pat = M._build_surface_re(["kind", "cafés", "∅", ""])
    assert pat.fullmatch("KIND") and pat.fullmatch("CAFÉS")
    assert not pat.fullmatch("Kınd") and not pat.fullmatch("\u212aind")
    assert M.pattern_source(pat) == r"cafés|\bkind\b"


# ──── morpho_numeric_alternatives ─────────────────────────────────

@pytest.mark.parametrize('word',['or','OR','oder','ODER','ou','OU'])
@pytest.mark.parametrize('left,right',[('3\n ',' 4'),('3 ','\n 4'),('3\n\t','\t\n -4'),('-3 ',' -4'),('3 ',' +4'),('3.5 ',' −4.5'),('3 ',' -.5')])
def test_numeric_alternative_keeps_conjunction(word,left,right):
    output=mz.compress(left+word+right)
    assert word in output
    assert '/' not in output


@pytest.mark.parametrize('text,expected',[('tea or coffee','tea / coffee'),('tea\n or coffee','tea\n/ coffee'),('3 or later','3 / later'),('either or -4','either / -4')])
def test_non_numeric_alternative_keeps_shortening(text,expected):
    assert mz.compress(text)==expected


# ──── morpho_or_between_numbers ───────────────────────────────────

"""MorphoGrammarMinimal: or/oder/ou between two numbers must not turn into a fraction-like "3 / 4"."""


mz_morpho_or_between_numbers = load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")


@pytest.mark.parametrize(
    "src, kept",
    [
        ("He did not say 3 or 4.", "3 or 4"),
        ("Es dauert 2 oder 3 Tage.", "2 oder 3"),
        ("Il faut 2 ou 3 jours.", "2 ou 3"),
    ],
)
def test_conjunction_between_numbers_kept(src, kept):
    out = mz_morpho_or_between_numbers.compress(src)
    assert kept in out
    assert "/" not in out


@pytest.mark.parametrize(
    "src, short",
    [
        ("tea or coffee", "tea / coffee"),
        ("option 3 or later", "3 / later"),
        ("either or 4", "/ 4"),
        ("Tee oder Kaffee", "Tee / Kaffee"),
        ("Seite 3 oder später", "3 / später"),
        ("entweder oder 4", "/ 4"),
        ("page 3 ou plus tard", "3 / plus"),
        ("soit ou 4", "/ 4"),
        ("thé ou café", "thé / café"),
    ],
)
def test_conjunction_still_shortened_elsewhere(src, short):
    out = mz_morpho_or_between_numbers.compress(src)
    assert short in out


def test_protect_rule_hints_resolve():
    # from __future__ annotations: an undefined name only fails when hints are resolved
    hints = typing.get_type_hints(mz_morpho_or_between_numbers._protect_rule)
    assert hints["return"].__args__[1] is typing.Any


# ──── pack_tokens_combining ───────────────────────────────────────

"""pack_tokens: 結合文字(NFD のアクセント・ベトナム語の声調)で単語が分割されないこと。

出力は NFC (#65)。NFD 入力は NFC 等価な出力になり、語は結合文字の位置で分割されない。
"""


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


@pytest.mark.parametrize("word", ["Tiếng Việt", "Hà Nội", "naïve", "café", "İstanbul"])
def test_nfd_word_not_split(word):
    s = unicodedata.normalize("NFD", f"The {word} team, ready.")
    out = pack_tokens(s)
    assert out == _nfc(s)
    assert out == pack_tokens(_nfc(s))
    for w in _nfc(word).split():
        assert f" {w}" in f" {out} ".replace(",", " ")


def test_mark_after_nonfoldable_base():
    # x + U+0301 は NFC でも合成されない: 結合文字は語に残り、分割されない
    assert pack_tokens("x\u0301y z") == "x\u0301y z"


def test_mark_word_before_bracket():
    out = pack_tokens("cafe\u0301 (ok)")
    assert out == "caf\u00e9 (ok)"
    assert out.split()[0] == "caf\u00e9"


def test_noncomposable_mark_word_before_bracket():
    # NFC 後も結合文字が残る語でも、括弧の前の空白は保たれる
    assert pack_tokens("x\u0301 (ok)") == "x\u0301 (ok)"


def test_noncomposable_interior_mark_word_before_bracket():
    # Preserve the #63 interior-mark boundary regression alongside #90.
    assert pack_tokens("x\u0301y (ok)") == "x\u0301y (ok)"


# ──── quote_normalize ─────────────────────────────────────────────

"""Curly→straight quote normalisation (MorphoGrammarMinimal) and scripts/quote_roundtrip.py."""


ROOT = Path(__file__).resolve().parents[1]


_spec = importlib.util.spec_from_file_location("quote_roundtrip", ROOT / "scripts/quote_roundtrip.py")


qr = importlib.util.module_from_spec(_spec)


sys.modules["quote_roundtrip"] = qr


_spec.loader.exec_module(qr)


mz_quote_normalize = qr.load_mz()


@pytest.mark.parametrize(
    ("src", "out"),
    [
        ("he said “go now”.", 'he said "go now".'),
        ("‘don’t go’ she said", "'don’t go' she said"),
        ("don’t", "don’t"),
        ("the dogs’ bones", "the dogs’ bones"),
        ("‘tis", "'tis"),
        ("‘a’\n‘b’", "'a'\n'b'"),
        ("‘it’s Zu\u0308rich’", "'it’s Zürich'"),
        ("“Café”, ‘naïve’", "\"Café\", 'naïve'"),
    ],
)
def test_normalize_quotes(src, out):
    import unicodedata

    assert mz_quote_normalize.normalize_quotes(unicodedata.normalize("NFC", src)) == unicodedata.normalize("NFC", out)


def test_compress_uses_straight_quotes_and_keeps_protected():
    assert "“" not in mz_quote_normalize.compress("He said “go home” now.")
    assert mz_quote_normalize.compress("I don’t know, the dogs’ bones.") == "I don’t know, dogs’ bones."
    assert "“kept”" in mz_quote_normalize.compress("[[keep:“kept”]] here")


@pytest.mark.parametrize(
    "src",
    ["“Hi,” he said. “Go.”", "‘one’ and “two”", "road—”\nWe", "(“x”)", "“a—b”"],
)
def test_restore_roundtrip(src):
    assert qr.restore_quotes(mz_quote_normalize.normalize_quotes(src)) == src


def test_corner_roundtrip():
    s = "“a” ‘b’"
    assert qr.to_corner(s) == "「a」 ‘b’" and qr.from_corner(qr.to_corner(s)) == s


def test_check_and_main(capsys):
    texts = {"a.txt": "He said “go” now.", "b.txt": 'plain "x"', "c.txt": "x“a”"}
    res = qr.check(texts, mz_quote_normalize, len)
    assert res["spans"] == 2 and res["roundtrip"]['Q""']["checked"] == 2
    assert res["roundtrip"]['Q""']["mismatches"] == ["c.txt"]
    assert res["rows"]['Q""']["bytes"] < res["rows"]["curly"]["bytes"]
    assert list(res["heavy"]) == ["a.txt"]
    empty = qr.check({}, mz_quote_normalize, len)
    assert empty["heavy"] == {} and empty["per_span"] == {'Q""': 0.0, "Q「」": 0.0}
    pytest.importorskip("tiktoken")
    assert qr.main([]) == 0 and "roundtrip" in capsys.readouterr().out
    assert qr.main(["--json"]) == 0 and '"spans"' in capsys.readouterr().out
