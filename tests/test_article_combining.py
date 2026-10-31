"""NFD combining marks: ``a\u0301`` (á) is never the article ``a``."""

from __future__ import annotations

import importlib.util
import inspect
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("morpho_zip", ROOT / "MorphoZip/morpho_zip.py")
mz = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("morpho_zip", mz)
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
