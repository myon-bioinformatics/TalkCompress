"""Collision guard: auxiliary tokens and conversion-time banks (follow-up to #27)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests._helpers import load

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tense_matrix as tm  # noqa: E402

BANK = json.loads(tm.BANK_PATH.read_text(encoding="utf-8"))
REG = tm.form_registry(json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"])


def _t():
    return load("tessera_talk", "TesseraTalk/tessera_talk.py")


def _c(form, lang, shape="compound"):
    return {"form": form, "lang": lang, "shape": shape}


# --- auxiliary tokens ------------------------------------------------------


@pytest.mark.parametrize(
    ("cand", "tense", "verb", "aux"),
    [
        (_c("a vu", "fr"), "perf", "see", "a"),  # pt article a
        (_c("as vu", "fr"), "perf", "see", "as"),  # pt article as
        (_c("es allé", "fr"), "perf", "go", "es"),  # de pronoun es
        (_c("sei andato", "it"), "perf", "go", "sei"),  # pt sei 'I know'
        (_c("es en train de voir", "fr", "prog-en-train-de"), "presprog", "see", "es"),
    ],
)
def test_aux_collision_rejects(cand, tense, verb, aux):
    assert aux in tm.candidate_aux(cand)
    assert tm.aux_collision(aux, cand["lang"], REG)
    assert tm.collision(cand, tense, verb, REG)


@pytest.mark.parametrize(
    ("cand", "tense", "verb"),
    [
        (_c("aurai eu", "fr"), "futperf", "have"),  # pp after aux: pronoun reading exempt
        (_c("ho visto", "it"), "perf", "see"),
        (_c("ai vu", "fr"), "perf", "see"),
        (_c("estoy yendo", "es", "prog-gerund"), "presprog", "go"),
        (_c("estou a ir", "pt", "prog-a-inf"), "presprog", "go"),  # particle a skipped
        (_c("ben aan het gaan", "nl", "prog-aan-het"), "presprog", "go"),
    ],
)
def test_aux_collision_allows(cand, tense, verb):
    assert tm.collision(cand, tense, verb, REG) == []


def test_candidate_aux_shapes():
    assert tm.candidate_aux(_c("ve", "es", "simple")) == []
    assert tm.candidate_aux(_c("estou a ir", "pt", "prog-a-inf")) == ["estou"]
    assert tm.candidate_aux(_c("a vu", "fr")) == ["a"]
    assert tm.candidate_aux(_c("zal aan het gaan zijn", "nl", "prog-aan-het")) == ["zal", "zijn"]


def test_aux_meaning():
    assert tm._aux_meaning("fr", "perf") == "have"
    assert tm._aux_meaning("fr", "perf+e") == "be"
    assert tm._aux_meaning("es", "presprog") == "be"
    assert tm._aux_meaning("nl", "futprog") == "will"
    assert tm._aux_meaning("nl", "presprog") == "be"


def test_aux_unknown_token_no_clash():
    assert tm.aux_collision("zzz", "fr", REG) == []


# --- conversion-time banks -------------------------------------------------


@pytest.mark.parametrize(
    ("form", "lang", "meanings", "cls"),
    [
        ("vim", "pt", {"go"}, "past"),  # pt 'I came'
        ("di", "es", {"give"}, "past"),  # it preposition
        ("pensé", "es", {"think"}, "past"),  # fr past participle
        ("via", "pt", {"<phrase>"}, "phrase"),  # pt 'saw' (ver imperfect)
    ],
)
def test_bank_form_collision_rejects(form, lang, meanings, cls):
    assert tm.bank_form_collision(form, lang, meanings, cls, REG)


@pytest.mark.parametrize(
    ("form", "lang", "meanings", "cls"),
    [
        ("fui", "es", {"go"}, "past"),
        ("pensei", "pt", {"think"}, "past"),
        ("quero ir", "pt", {"want", "go"}, "pres"),
        ("de novo", "pt", {"<phrase>"}, "phrase"),
        ("μέσω", "el", {"<phrase>"}, "phrase"),
    ],
)
def test_bank_form_collision_allows(form, lang, meanings, cls):
    assert tm.bank_form_collision(form, lang, meanings, cls, REG) == []


def test_collision_blocked_generated():
    rows = {(r["bank"], r["id"], r["form"]) for r in BANK["collision_blocked"]}
    assert ("es_fr_tense", "go-past-1s", "vim") in rows
    assert ("es_fr_tense", "give-past-1s", "di") in rows
    assert ("pt_el_latin_phrases", "by-means-of-pt-el", "via") in rows
    t = _t()
    assert t.collision_blocked("es_fr_tense") >= {("go-past-1s", "vim"), ("think-past-1s", "pensé")}
    assert t.collision_blocked("nope") == frozenset()


@pytest.mark.parametrize(
    ("s", "want"),
    [("I went", "fui"), ("I gave", "I gave"), ("I thought", "pensei"), ("I have given", "dei")],
)
def test_runtime_tense_bank_guarded(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_runtime_phrase_bank_guarded():
    assert _t().apply_zh_de_phrases("by means of") == "μέσω"


def test_bank_phrase_pairs_blocked_falls_back():
    t = _t()
    data = {"entries": [{"id": "x", "from": ["by means of"], "to": "via", "lang": "pt",
                         "candidates": [{"form": "via", "lang": "pt"}, {"form": "μέσω", "lang": "el"}]}]}
    forms = {f for _s, f, _l in t._bank_phrase_pairs(data, blocked=frozenset({("x", "via")}))}
    assert forms == {"μέσω"}
    assert "via" in {f for _s, f, _l in t._bank_phrase_pairs(data)}
