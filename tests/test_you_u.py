"""you → U (1 char): same tokens, utf8 3→1; your/yours/yourself and you'X stay."""

from __future__ import annotations

import pytest

from tests._helpers import load

t = load("tessera_talk", "TesseraTalk/tessera_talk.py")


def test_u_is_cheaper_by_utf8_at_equal_tokens():
    assert t.estimate_tokens("U") == t.estimate_tokens("you")
    assert len("U".encode()) < len("you".encode())
    assert not t.en_homograph_tokens("U")


@pytest.mark.parametrize(
    "src, out",
    [
        ("We see you", " U"),          # object
        ("Thank you", "Thank U"),
        ("You will rejoice", "U will rejoice"),
        ("We think you will go", " U will go"),  # number-neutral EN chain kept
        ("you could have gone", "U could have gone"),  # modal + have-pp guard
        ("you had eaten", "U had eaten"),                # aux + pp guard
        ("you have to go", "U have to go"),              # have-to guard
    ],
)
def test_you_becomes_u(src, out):
    res = t.apply_es_fr_tense(src)
    assert res == out or (out.startswith(" ") and res.endswith(out)), res
    assert "you" not in res.lower().split()


@pytest.mark.parametrize(
    "src", ["your book", "it is yours", "do it yourself", "yourselves", "you'd go", "you're here", "you've seen", "you'll go"]
)
def test_excluded_forms_untouched(src):
    assert t.apply_you_u(src) == src


def test_matrix_row_still_beats_u():
    # clause-start matrix row (2nd-person verb, strictly fewer tokens) wins over U + EN chain
    # (#29: nl ``ging`` was gated by the AI round-trip; use a row that still wins)
    out = t.apply_es_fr_tense("you came")
    assert out != "U came" and t.estimate_tokens(out) < t.estimate_tokens("U came")
    # embedded: pro-drop blocked → subject kept as U
    assert t.apply_es_fr_tense("I know you went").endswith("U went")


def test_idempotent():
    s = t.apply_es_fr_tense("I see you and you see me")
    assert t.apply_es_fr_tense(s) == s
