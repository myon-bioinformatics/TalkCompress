"""Regression: meaning-changing rewrites found in the dialogue dry run
(Tatoeba / Gutenberg #844 Earnest / #3825 Pygmalion). Sentences are verbatim."""
from __future__ import annotations

import pytest

from tests._helpers import load, ns

dz = load("density_zip", "DensityZip/density_zip.py")
lp = load("lex_policy", "shared/lex_policy.py")


def _ce(s: str) -> str:
    return dz.run_pipeline(["C", "E"], s, ns())


# (1) would ≠ will
@pytest.mark.parametrize(
    "s",
    [
        "Frightening people like that! How would he like it himself.",  # Pygmalion
        "She said it would rain.",
        "He wouldn't go.",
    ],
)
def test_would_not_folded_to_will(s: str) -> None:
    out = _ce(s)
    assert "would" in out.lower()
    assert "will" not in out.lower()


# (2) dropped interjection never leaves a dangling comma
@pytest.mark.parametrize(
    "s,start",
    [
        ("Oh, before the end of the week I shall have got rid of him.", "B"),  # Earnest
        ("Well, if you want to know, Cecily happens to be my aunt.", "I"),  # Earnest
        ("Ah, I see.", "I"),
        ("Um, I think so.", "I"),
    ],
)
def test_initial_interjection_drops_with_comma(s: str, start: str) -> None:
    out = _ce(s)
    assert not out.lstrip().startswith(",")
    assert out[0] == start
    assert ",," not in out


def test_pygmalion_stage_direction_interjection() -> None:
    out = _ce("EYNSFORD HILL [rising] Well, after that, I think it’s time for us to go.")
    assert "] ," not in out and "],"not in out
    assert "Well" not in out


@pytest.mark.parametrize(
    "s,keep",
    [
        ("I feel well.", "well"),
        ("Me as well.", "well"),
        ("He did it well, I think.", "well"),
        ("Oh no!", "Oh"),
    ],
)
def test_content_well_oh_kept(s: str, keep: str) -> None:
    assert keep in lp.strip_fillers(s)


def test_mid_sentence_fillers_no_double_comma() -> None:
    assert lp.strip_fillers("So, uh, well, ok.") == "So, ok."


# (3) article drop is documented default (--keep-articles opts out); for these
# colloquial cases the meaning is preserved ("have coffee" / "catch cold").
@pytest.mark.parametrize(
    "s,out",
    [
        ("Shall we have a coffee?", "Shall we have coffee?"),  # Tatoeba
    ],
)
def test_colloquial_article_drop_documented(s: str, out: str) -> None:
    assert _ce(s) == out
    a = ns()
    a.keep_articles = True
    assert " a coffee" in dz.run_pipeline(["C", "E"], s, a)
