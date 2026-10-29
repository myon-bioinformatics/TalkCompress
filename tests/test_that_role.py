"""Explicit role classifier for ``that`` + comma / discourse-adverb handling."""

from __future__ import annotations

import re

import pytest

from tests._helpers import load as _load


def _t():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def _roles(s: str) -> list[str]:
    t = _t()
    return [t.classify_that_role(s, m.start()) for m in re.finditer(r"(?<![A-Za-z])that(?![A-Za-z])", s, re.I)]


COMPLEMENTIZER = [
    "dedicated to the proposition that all men are created equal",
    "the fact that he is going",
    "I think that he is going",
    "She said that we will go",
    "We know that they were here",
    "I believe that it is true",
    "I am sure that we will go",
    "I'm glad that you came",
    "the idea that we could win",
    "the news that he had left",
    "They hope that I am right",
    "It is clear that she is going",
]
RELATIVE = [
    "the man that is going",
    "the car that was here",
    "a book that has gone",
    "the people that were waiting",
    "the book that I read",
    "the house that we built",
    "every plan that they made",
    "the idea that is going",
]
DETERMINER = ["that book is good", "I want that car", "Look at that dog", "That man is here"]
DEMONSTRATIVE = ["that is going", "I like that.", "That was fun", "I know that.", "That, however, is fine"]


@pytest.mark.parametrize("s", COMPLEMENTIZER)
def test_complementizer(s):
    assert _roles(s)[-1] == "complementizer"
    assert re.search(r"\bthat\b", _t().apply_es_fr_tense(s))  # stays EN


@pytest.mark.parametrize("s", RELATIVE)
def test_relative(s):
    assert _roles(s)[-1] == "relative"


@pytest.mark.parametrize("s", DETERMINER)
def test_determiner(s):
    assert _roles(s)[0] == "determiner"
    assert re.search(r"\bthat\b", _t().apply_es_fr_tense(s), re.I)


@pytest.mark.parametrize("s", DEMONSTRATIVE)
def test_demonstrative(s):
    assert "demonstrative" in _roles(s)
    assert re.search(r"\bthat\b", _t().apply_es_fr_tense(s), re.I)


def test_gettysburg_both_roles():
    s = "conceived in Liberty, and dedicated to the proposition that all men are created equal"
    assert _roles(s) == ["complementizer"]
    assert _t().apply_es_fr_tense(s) == s


def test_relative_subject_slot_becomes_que_only():
    t = _t()
    assert t.apply_es_fr_tense("the man that is going").startswith("the man que ")
    # object relative / complementizer / determiner / demonstrative: that stays
    for s in ["the book that I read", "I think that he is going", "that book", "that is", "I like that."]:
        assert re.search(r"\bthat\b", t.apply_es_fr_tense(s), re.I), s


def test_unclassifiable_stays_english():
    t = _t()
    assert t.classify_that_role("people that are going", 7) == "unknown"
    assert "that" in t.apply_es_fr_tense("people that are going")


COMMA_CASES = [
    "However, he is going",
    "Yes. However, he is going",
    "I know, however, he is going",
    "he is, however, going",
    "Therefore, we will go, and he is going",
    "If he goes, he will go",
    "In fact, she is coming",
    "The man, who is going, is here",
]


@pytest.mark.parametrize("s", COMMA_CASES)
def test_commas_always_preserved(s):
    out = _t().apply_es_fr_tense(s)
    assert out.count(",") == s.count(",")


@pytest.mark.parametrize("adv", ["However", "Therefore", "Moreover", "In fact", "Of course", "Nevertheless"])
def test_sentence_initial_discourse_adverb_keeps_clause_start(adv):
    t = _t()
    base = t.apply_es_fr_tense("he is going")
    assert t.apply_es_fr_tense(f"{adv}, he is going") == f"{adv}, {base}"
    assert t.apply_es_fr_tense(f"Yes. {adv}, he is going") == f"Yes. {adv}, {base}"


def test_mid_sentence_parenthetical_does_not_unlock_pro_drop():
    t = _t()
    assert t.apply_es_fr_tense("I know, however, he is going").endswith("however, he is going")
    assert t.apply_es_fr_tense("he is, however, going") == "he is, however, going"
