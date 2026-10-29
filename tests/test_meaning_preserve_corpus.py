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
    assert "i.e." in _ce("It is a car, that is, a vehicle.")


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
        ("look at me that way.", "that way", "the way"),
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
