"""Article dropped right after an opening quote/bracket leaves no stray space."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("morpho_zip", ROOT / "MorphoZip/morpho_zip.py")
mz = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("morpho_zip", mz)
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
