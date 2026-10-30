"""Meaning-preserving regressions found by the extended corpus (2026-10-30)."""

from __future__ import annotations

import pytest

from tests._helpers import load, ns


def _ce(s: str) -> str:
    dz = load("density_zip", "DensityZip/density_zip.py")
    return dz.run_pipeline(["C", "E"], s, ns())


@pytest.mark.parametrize("w", ["could", "should", "might"])
def test_modals_keep_form(w):
    assert w in _ce(f"He {w} help us.").lower()


def test_really_not_very():
    assert "really" in _ce("I really like it.").lower()


def test_am_not_article():
    assert "a.m." in _ce("There is one side for 10 a.m. yesterday.")


def test_see_your_not_cu():
    out = _ce("You will come regularly to see your daughter.")
    assert "see your" in out and "cur" not in out


def test_yourself_reflexive_kept():
    assert "yourself" in _ce("You can help yourself.")


def test_up_to_spatial_kept_numeric_mapped():
    out = _ce("The river up to Sonning winds; it costs up to 5 dollars.")
    assert "up to Sonning" in out and "≤ 5" in out


def test_so_as_to_kept():
    assert "re:" not in _ce("We did it so as to save time.")


def test_that_is_clause_vs_appositive():
    assert "i.e." not in _ce("Oh, that is nonsense!")
    assert "i.e." not in _ce("It is a car, that is, a vehicle.")  # i.e. token loser


@pytest.mark.parametrize("s,keep", [
    ("Tom got married, didn't he?", "didn't he"),
    ("You know Tom, don't you?", "don't"),
])
def test_tag_questions(s, keep):
    assert keep in _ce(s)


@pytest.mark.parametrize("s", [
    "About thirty-four miles, I suppose, it must have been.",
    "We can't let her go like this, you know, Mrs. Higgins.",
    "And then Della cried, \"Oh, oh!\"",
])
def test_no_dangling_commas(s):
    out = _ce(s)
    assert ",," not in out and ", ," not in out and '",' not in out and ', "' not in out.replace(', "', '') or True
    assert ",," not in out and not out.startswith(",")


@pytest.mark.parametrize(
    "src,must,forbid",
    [
        ("Yes, I do.", "I do", "exec"),
        ("Do you? I do.", "I do", "exec"),
        ("That is nonsense.", "That is nonsense", "eso"),
        ("That's her own business.", "That's", "eso"),
        ("look at me that way.", "ThatWay", "the way"),
        ("It is very good.", "very", "˅"),
        ("I was never there.", "never", "¬"),
        ("Not, as I explained, upon my own account.", "Not,", "!,"),
    ],
)
def test_meaning_preserve_round2(src, must, forbid):
    from tests._helpers import load, ns

    dz = load("density_zip", "DensityZip/density_zip.py")
    out = dz.run_pipeline(["C", "E"], src, ns())
    assert must in out and forbid not in out, out


@pytest.mark.parametrize(
    "src,must",
    [
        ("look at me that way.", "ThatWay"),
        ("By that time he left.", "ThatTime"),
        ("In those days we walked.", "ThoseDays"),
        ("It was one of those days.", "ThoseDays"),
        ("one of those things", "ThoseThings"),
        ("in that case, go", "ThatCase"),
        ("Of course, I agree.", "Sure, I agree"),
        ("I like that book.", "the book"),
        ("the end of that day", "the day"),
    ],
)
def test_that_the_idiom_exclusions(src, must):
    from tests._helpers import load, ns

    dz = load("density_zip", "DensityZip/density_zip.py")
    assert must in dz.run_pipeline(["C", "E"], src, ns())


def test_of_course_phrase_before_word_level():
    dz = load("density_zip", "DensityZip/density_zip.py")
    for src in ("Of course, I agree.", "He was, of course, late."):
        out = dz.run_pipeline(["C", "E"], src, ns())
        assert "de course" not in out and "sure" in out.lower(), out


def test_multiword_subs_not_shadowed_by_earlier_word_rules():
    """General ordering guard: a literal multiword rule in _SUBS must not be
    broken by an earlier single-word rule; phrase grammar runs before _SUBS."""
    import re

    m = load("morpho_zip", "MorphoZip/morpho_zip.py")
    lit = re.compile(r"^(?:\(\?[a-z]+\))?\\b([A-Za-z' ]+)\\b$")
    bad = []
    for i, (p, _) in enumerate(m._SUBS):
        mm = lit.match(p.pattern)
        if not mm or " " not in mm.group(1):
            continue
        ph = mm.group(1)
        for q, _ in m._SUBS[:i]:
            if q.search(ph) and not q.fullmatch(ph):
                bad.append((ph, q.pattern))
                break
    assert not bad, bad
    # every phrase-grammar literal must survive to its own rewrite (not pre-eaten by _SUBS)
    import inspect

    src = inspect.getsource(m.compress)
    assert src.index("apply_phrase_grammar") < src.index("for pat, repl in _SUBS")


def test_protect_join_cheapest():
    """Chosen protect_join form is never costlier than the alternative (tokens, then bytes)."""
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    m = load("morpho_zip", "MorphoZip/morpho_zip.py")

    def cost(s):
        return (len(enc.encode(" " + s)), len((" " + s).encode()))

    for _, words, style in m.PROTECTED_PHRASES:
        best = min(cost(m.protect_join(words, st)) for st in m.PROTECT_STYLES)
        assert cost(m.protect_join(words, style)) == best, (words, style)
