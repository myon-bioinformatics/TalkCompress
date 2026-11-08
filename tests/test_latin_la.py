"""ラテン語 (la, <100M) 拡充: 学術ラテン短形 + 古典活用 2 形、AI 往復ゲート、多言語つまみ食い文テスト。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402

RT = rt.load()
CORPUS = ROOT / "tests/fixtures/corpus/tatoeba"

NEW_LA = {
    "in a test tube": "in vitro",
    "in a living organism": "in vivo",
    "word for word": "verbatim",
    "in the middle of things": "in medias res",
    "after the fact": "ex post",
    "among other things": "inter alia",
}
NEW_LA_TENSE = {"I will come": "veniam"}
REVERSED = {"once again": "iterum", "as a result": "ergo", "more or less": "circa", "face to face": "coram",
            "day by day": "cotidie", "for this reason": "ideo", "in favor of": "pro", "with respect to": "re",
            "among others": "inter alia"}
REJECTED = ["interim", "bona fide", "per capita", "a fortiori", "in memoriam", "seriatim", "sua sponte"]


def _t():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def test_la_scope_flags():
    t = _t()
    assert "la" in t.FINAL_TENSE_LANGS and "la" in t.FINAL_PT_EL_LATIN_PHRASE_LANGS
    assert "la" not in t.SCOPE_LANGS
    assert "la" not in RT["ge100m_langs"]


@pytest.mark.parametrize(("src", "form"), sorted(NEW_LA.items()))
def test_new_la_phrase_wins_and_passed_roundtrip(src, form):
    t = _t()
    pairs = {(s, d, l) for s, d, l in t.pt_el_latin_phrase_pairs()}
    assert (src, form, "la") in pairs
    assert t.estimate_tokens(form) < t.estimate_tokens(src)
    assert rt.status(RT, "la", form) == "pass"
    assert form in t.final_token_pass(f"We noted it {src}.", apply_sentences=False)


@pytest.mark.parametrize(("src", "form"), sorted(NEW_LA_TENSE.items()))
def test_la_conjugation_wins_and_passed_roundtrip(src, form):
    t = _t()
    assert (src, form, "la") in set(t.es_fr_tense_pairs())
    assert rt.status(RT, "la", form) == "pass"
    out = t.final_token_pass(f"{src} time tomorrow.", apply_sentences=False)
    assert out.startswith(form)
    assert t.estimate_tokens(out) < t.estimate_tokens(f"{src} time tomorrow.")


@pytest.mark.parametrize("form", REJECTED)
def test_roundtrip_failures_not_adopted(form):
    t = _t()
    assert rt.status(RT, "la", form) != "pass"
    assert all(d != form for _, d, _ in t.pt_el_latin_phrase_pairs())


def test_ero_ibo_not_adopted():
    t = _t()
    forms = {d for _, d, _ in t.es_fr_tense_pairs() + t.pt_el_latin_tense_pairs()}
    assert "ero" not in forms  # it ero = I was
    assert "ibo" not in forms  # ties vou
    assert "habebo" not in forms  # ties terei on tokens, loses utf8
    assert all(d != "obiter" for _, d, _ in t.pt_el_latin_phrase_pairs())  # ties EN


def test_c_latin_abbrevs_not_in_b():
    t = _t()
    forms = {d.lower() for _, d, _ in t.pt_el_latin_phrase_pairs()}
    assert not forms & {"e.g.", "i.e.", "etc.", "vs", "viz", "etal", "adhoc", "ad hoc"}


def _sample(lang, n=3):
    rows = [json.loads(x) for x in (CORPUS / f"{lang}.jsonl").read_text(encoding="utf-8").splitlines()]
    return [r["text"] for r in rows[:n]]


@pytest.mark.parametrize("lang", ["es", "fr", "pt", "de", "zh", "ja", "en"])
def test_multilingual_tatoeba_sample_final_pass(lang):
    """つまみ食い: 英語以外の実文も final pass に通し、壊さず token を増やさない。"""
    t = _t()
    for s in _sample(lang):
        out = t.final_token_pass(s)
        assert t.estimate_tokens(out) <= t.estimate_tokens(s), (lang, s, out)
        if lang != "en":
            assert out == s, (lang, s, out)  # EN-source banks must not touch non-EN text


@pytest.mark.parametrize(
    ("src", "want"),
    [
        ("Lo copié word for word.", "Lo copié verbatim."),
        ("Elle l'a dit in passing.", "Elle l'a dit in passing."),  # obiter ties EN
        ("Ich werde es step by step machen.", "Ich werde es gradatim machen."),
        ("我们 after the fact 才知道。", "我们 ex post 才知道。"),
        ("Il a copié mot pour mot.", "Il a copié mot pour mot."),
    ],
)
def test_code_switched_sentences(src, want):
    t = _t()
    out = t.final_token_pass(src, apply_sentences=False)
    assert out == want
    assert t.estimate_tokens(out) <= t.estimate_tokens(src)


@pytest.mark.parametrize(("src", "form"), sorted(REVERSED.items()))
def test_pre_gate_la_failures_reversed(src, form):
    t = _t()
    assert rt.status(RT, "la", form) == "pass" if form == "inter alia" else rt.status(RT, "la", form) != "pass"
    assert (src, form, "la") not in set(t.pt_el_latin_phrase_pairs())
    assert form not in t.apply_zh_de_phrases(f"We did it {src} today.").replace(src, "")


def test_gradatim_kept():
    t = _t()
    assert ("step by step", "gradatim", "la") in set(t.pt_el_latin_phrase_pairs())
    assert rt.status(RT, "la", "gradatim") == "pass"


def test_in_favor_of_hyper_reversed():
    t = _t()
    assert all(not (s == "in favor of" and d == "υπέρ") for s, d, _ in t.pt_el_latin_phrase_pairs())
    assert "υπέρ" not in t.apply_zh_de_phrases("We voted in favor of the plan.")
