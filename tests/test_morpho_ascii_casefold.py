"""MorphoZip の手書き re.I パターンは ASCII 字母を ı/İ/ſ/U+212A に畳み込まない。"""

import ast
import re
import unicodedata
from pathlib import Path

import pytest

from MorphoZip import morpho_zip as M

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
