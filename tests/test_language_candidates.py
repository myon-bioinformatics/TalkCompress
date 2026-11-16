"""言語別の候補とラベル: de / nl / cs / pl / la / pt、Tatoeba つまみ食い。

- de_candidate: German (de) candidate + de-over-nl tie rule (tokens → utf8).
- de_nl_preterite_perfect: de / nl preterite as candidates for EN present perfect (same policy as es/pt).
- de_nl_you_singular: Regression: EN `you` never takes de ihr / nl jullie (plural) forms.
- de_wenn: German ``wenn`` was adopted then reversed after AI round-trip failure (0/9).
- slavic_futperf_nlrestore: Follow-up to #49: cs/pl stative perfect, future-perfect `you` sg/pl, and the
- latin_la: ラテン語 (la, <100M) 拡充: 学術ラテン短形 + 古典活用 2 形、AI 往復ゲート、多言語つまみ食い文テスト。
- tatoeba_nibble: 多言語つまみ食い (it / nl / el / la): Tatoeba 実文を final pass に通し、壊さず token を増やさない。
- label_fix_vou_sair_this_vira_fiz: Data-label fixes: vou sair (pt label), this virá (parity follower of virá), fiz (meanings).
"""

from __future__ import annotations

from pathlib import Path
from tests._helpers import load
from tests._helpers import load as _load
import importlib.util
import json
import roundtrip as rt
import sys
import tense_matrix as tm

import pytest


# ──── de_candidate ────────────────────────────────────────────────

"""German (de) candidate + de-over-nl tie rule (tokens → utf8)."""


ROOT = Path(__file__).resolve().parents[1]


BANK = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/tense_matrix.json").read_text(encoding="utf-8"))


REPORT = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))


BY_SRC = {e["from"][0]: e for e in BANK["entries"]}


def _t():
    return _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")


def test_de_in_tense_langs():
    t = _t()
    assert "de" in t.FINAL_TENSE_LANGS and "de" in t.FINAL_TENSE_MATRIX_LANGS


@pytest.mark.parametrize("s,want", [("I came", "kam"), ("he came", "kam"), ("she came", "kam")])
def test_de_strictly_wins_kam(s, want):
    assert _t().apply_es_fr_tense(s) == want
    assert BY_SRC[s]["lang"] == "de"


@pytest.mark.parametrize(
    "s,want",
    [("he thinks", "denkt"), ("we think", "denken"), ("they think", "denken"), ("we found", "fanden"),
     ("they found", "fanden")],
)
def test_tie_goes_to_de(s, want):
    assert BY_SRC[s]["to"] == want and BY_SRC[s]["lang"] == "de"
    assert _t().apply_es_fr_tense(s) == want


def test_fand_restored_after_rescore():
    """he found / I found share surface fand. The recorded blind answer 'I found' is an official
    source of fand, so the any-official-source re-score passes 9/9 and the reversal is undone."""
    t = _t()
    assert BY_SRC["he found"]["to"] == "fand" and BY_SRC["he found"]["lang"] == "de"
    assert t.apply_es_fr_tense("he found") == "fand"
    assert t.apply_es_fr_tense("I found") == "fand"


@pytest.mark.parametrize(
    "s,want",
    # #29: matrix nl wil/ging/nam/wilden failed the AI round-trip (< 0.9) and are gated
    [("I come", "kom"), ("I take", "neem"), ("I think", "denk")],
)
def test_nl_kept_where_strictly_cheaper(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_de_will_rejected_by_homograph_guard():
    t = _t()
    assert t.en_homograph_tokens("will")
    for s in ("he wants", "I want", "who wants"):
        assert "will" not in t.apply_es_fr_tense(s).split()
    cell = next(c for c in REPORT["cells"] if c["src"] == "he wants")
    assert any(h["form"] == "will" for h in cell.get("homograph_dropped", []))


def test_compounds_nl_kept_when_cheaper():
    t = _t()
    assert t.apply_zh_de_phrases("swimming pool") == "zwembad"
    # o200k tie: " washing machine" = 2 = " wasmachine" -> source kept
    assert t.apply_zh_de_phrases("washing machine") == "washing machine"


def test_prefer_on_tie_only_de_over_nl():
    t = _t()
    m = lambda r: (t.estimate_tokens(r), len(r.encode()))  # noqa: E731
    assert t.prefer_on_tie(("vond", "nl"), [("vond", "nl"), ("fand", "de")], m) == ("fand", "de")
    assert t.prefer_on_tie(("wil", "nl"), [("wil", "nl"), ("nahm", "de")], m) == ("wil", "nl")
    assert t.prefer_on_tie(("vis", "fr"), [("vis", "fr"), ("sah", "de")], m) == ("vis", "fr")


def test_no_formal_sie_for_you():
    for e in BANK["entries"]:
        if e["subject"] == "2" and e["lang"] == "de":
            assert e["to"] not in {"denken", "kommen", "fanden", "wollen", "kamen"}


def test_de_plain_tie_vs_romance_uses_normal_order():
    # sah (1 tok / 3 B) ties fr vis / es vio; normal token → utf8 → len → form order picks sah.
    assert _t().apply_es_fr_tense("I saw") == "sah"


# ──── de_nl_preterite_perfect ─────────────────────────────────────

"""de / nl preterite as candidates for EN present perfect (same policy as es/pt)."""


BY_ID = {e["id"]: e for e in BANK["entries"]}


CONJ = json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"]


@pytest.mark.parametrize("eid,to,lang", [
    ("mx-see-perf-3s-he", "sah", "de"),
    # stative have/know/want: no preterite (continuative perfect) -> fr passé composé
    ("mx-have-perf-1p", "avons eu", "fr"),
])
def test_winner(eid, to, lang):
    e = BY_ID[eid]
    assert (e["to"], e["lang"]) == (to, lang)


@pytest.mark.parametrize("eid", ["mx-see-perf-1p", "mx-give-perf-3s-she"])  # take-perf-1s: de nahm reversed (#174)
def test_nl_preterite_gated_for_perfect(eid):
    # #29: nl preterite for EN perfect restores as simple past (0/9 etc.) -> gated
    assert BY_ID[eid]["lang"] != "nl"


def test_de_nahm_perfect_reversed_leaves_english():
    # de nahm (I have taken) failed independent blind round-trip 0/9 → ROUNDTRIP_REVERSED
    assert "mx-take-perf-1s" not in BY_ID


@pytest.mark.parametrize("person,de,nl", [("1s", "sah", "zag"), ("1p", "sahen", "zagen"), ("3", "sah", "zag")])
def test_candidates_offered_with_number(person, de, nl):
    p = "3s" if person == "3" else person
    forms = {(c["form"], c["lang"], c["shape"]) for c in tm._candidates(CONJ, p, "perf", "see", "")}
    assert (de, "de", "simple-preterite") in forms
    assert (nl, "nl", "simple-preterite") in forms
    # parity: no plural form offered for singular slot and vice versa
    other = {"sah": "sahen", "sahen": "sah"}[de]
    assert (other, "de", "simple-preterite") not in forms


def test_not_offered_outside_perfect():
    for t in ("pluperf", "futperf", "fut"):
        shapes = {(c["lang"], c["shape"]) for c in tm._candidates(CONJ, "1p", t, "see", "")}
        assert ("de", "simple-preterite") not in shapes and ("nl", "simple-preterite") not in shapes


def test_nl_perfect_winners_require_roundtrip():
    data = rt.load()
    assert data["required"] == rt.required_keys(BANK)
    nl = {rt.key(e["lang"], e["to"]) for e in BANK["entries"] if e["lang"] == "nl" and e["tense"] == "perf"}
    assert nl <= set(data["required"])  # empty after #29 gating
    assert "nl" not in data["ge100m_langs"]


def test_nl_perfect_listed_in_impact_doc():
    doc = (ROOT / "docs/roundtrip-impact.md").read_text(encoding="utf-8")
    for e in BANK["entries"]:
        if e["lang"] == "nl" and e["tense"] == "perf":
            assert e["id"] in doc


def test_bank_to_still_cheapest_and_collision_free():
    assert tm.main(["--check"]) == 0


# ──── de_nl_you_singular ──────────────────────────────────────────

"""Regression: EN `you` never takes de ihr / nl jullie (plural) forms."""


ENTRIES = BANK["entries"]


BY_SRC_de_nl_you_singular = {e["from"][0]: e for e in ENTRIES}


NL_PLURAL = {"deden", "hadden", "wisten", "gingen", "kwamen", "zagen", "namen", "vonden",
             "wilden", "dachten", "zeiden", "gaven"}


def test_you_think_is_singular_not_de_ihr():
    e = BY_SRC_de_nl_you_singular["you think"]
    # de ihr `denkt` is gone; the surviving `denkt` is nl jij (singular), not de.
    assert not (e["lang"] == "de" and e["to"] == "denkt")
    assert all(c["form"] != "denkt" or c["lang"] == "nl" for c in e["candidates"])


@pytest.mark.parametrize("src", ["you have done", "you have had", "you have known"])
def test_nl_plural_rejected_for_you(src):
    e = BY_SRC_de_nl_you_singular.get(src)
    if e is not None:
        assert e["to"] not in {"deden", "hadden", "wisten"}


def test_no_nl_plural_for_any_you_cell():
    for e in ENTRIES:
        if e.get("subject") == "2":
            for c in e["candidates"]:
                assert not (c["lang"] == "nl" and c["form"] in NL_PLURAL), e["id"]


# ──── de_wenn ─────────────────────────────────────────────────────

"""German ``wenn`` was adopted then reversed after AI round-trip failure (0/9)."""


BANK_de_wenn = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/zh_de_phrases.json").read_text(encoding="utf-8"))


WENN = next(e for e in BANK_de_wenn["examples_not_registered"] if e["id"] == "wenn")


def _t_de_wenn():
    return load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")


def _o200k():
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    return lambda s: (len(enc.encode(s)), len(s.encode("utf-8")))


def test_entry_moved_to_not_registered():
    assert WENN["to"] == "wenn" and WENN["lang"] == "de"
    assert set(WENN["from"]) == {"if and when", "when and if", "if or when", "when or if"}
    assert "0/9" in WENN["why_dropped"]
    assert all(e.get("id") != "wenn" for e in BANK_de_wenn["entries"])


@pytest.mark.parametrize("src", ["if and when", "when and if", "if or when", "when or if"])
def test_wenn_still_cheaper_on_o200k_but_not_applied(src):
    """Token win remains true; runtime no longer applies the reversed form."""
    m = _o200k()
    for pre in ("", " "):
        assert m(pre + "wenn") < m(pre + src)
        assert m(pre + "wenn")[0] < m(pre + src)[0]
    s = f"Call me {src} you arrive."
    assert _t_de_wenn().apply_zh_de_phrases(s) == s


@pytest.mark.parametrize("src", ["if", "when"])
def test_bare_if_when_not_adopted(src):
    m = _o200k()
    assert not m("wenn") < m(src)
    assert src not in WENN["from"]
    s = f"Call me {src} you arrive."
    assert _t_de_wenn().apply_zh_de_phrases(s) == s


def test_iff_untouched():
    assert "wenn" not in _t_de_wenn().apply_zh_de_phrases("x if and only if y")


def test_wenn_only_in_not_registered_of_zh_de():
    for p in (ROOT / "SentenceCalibratedMosaic/fixtures").glob("*.json"):
        txt = p.read_text(encoding="utf-8")
        if p.name == "zh_de_phrases.json":
            # id + to inside examples_not_registered; not in live entries
            assert txt.count('"wenn"') >= 2
            assert all(e.get("to") != "wenn" for e in BANK_de_wenn["entries"])
        elif p.name == "roundtrip.json":
            continue  # failure evidence retained
        else:
            assert '"wenn"' not in txt, p.name


# ──── slavic_futperf_nlrestore ────────────────────────────────────

"""Follow-up to #49: cs/pl stative perfect, future-perfect `you` sg/pl, and the
nl restore rule (a round-trip-gated nl form may come back only when dropping it
costs >= 1 token, never for bytes, and never when its round-trip was measured
as failing)."""


spec = importlib.util.spec_from_file_location("tm_fu", ROOT / "scripts/tense_matrix.py")


tm_slavic_futperf_nlrestore = importlib.util.module_from_spec(spec)


spec.loader.exec_module(tm_slavic_futperf_nlrestore)


CONJ = json.loads(tm_slavic_futperf_nlrestore.CONJ_PATH.read_text(encoding="utf-8"))["conj"]


REPORT_slavic_futperf_nlrestore = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]


def test_slavic_stative_perf_has_no_form():
    for verb in ("know", "have", "want"):
        for slot in ("1s", "1p", "2s", "2p"):
            assert tm_slavic_futperf_nlrestore._slavic(verb, "perf", slot) == []
    assert tm_slavic_futperf_nlrestore._slavic("find", "perf", "1s")  # non-stative keeps cs/pl perfect


def test_futperf_you_has_no_romance_form():
    for verb in ("know", "do", "go"):
        langs = {c["lang"] for c in tm_slavic_futperf_nlrestore._candidates(CONJ, "2", "futperf", verb, "")}
        assert not langs & {"es", "pt", "it", "fr"}, verb
    we = {c["lang"] for c in tm_slavic_futperf_nlrestore._candidates(CONJ, "1p", "futperf", "do", "")}
    assert "fr" in we


def test_futperf_you_cells_stay_english():
    cells = [c for c in REPORT_slavic_futperf_nlrestore if c["tense"] == "futperf" and c["src"].startswith("you ")]
    assert len(cells) == 12
    assert all(c["status"] != "adopt" for c in cells)


def _tok(f):
    return len(f.split())


def test_restore_nl_needs_a_token_gain():
    nl = {"form": "a", "lang": "nl"}
    de = {"form": "b c", "lang": "de"}
    cell = {}
    cands = tm_slavic_futperf_nlrestore.restore_nl(cell, [de, nl], [nl], 3, _tok)
    assert cell == {"roundtrip_restored": ["a"]} and nl in cands and de in cands
    # tie on tokens (byte-only difference) -> not restored
    de1 = {"form": "bbbbbbbb", "lang": "de"}
    cell = {}
    assert tm_slavic_futperf_nlrestore.restore_nl(cell, [de1, nl], [nl], 3, _tok) == [de1] and cell == {}
    # EN floor counts too
    assert tm_slavic_futperf_nlrestore.restore_nl({}, [nl], [nl], 1, _tok) == []
    assert tm_slavic_futperf_nlrestore.restore_nl({}, [nl], [nl], 2, _tok) == [nl]


def test_measured_failures_never_restored():
    assert tm_slavic_futperf_nlrestore._rt_status("ging", "nl") == "never"
    for c in REPORT_slavic_futperf_nlrestore:
        for f in c.get("roundtrip_restored", []):
            assert tm_slavic_futperf_nlrestore._rt_status(f, "nl") == "unverified"


# ──── latin_la ────────────────────────────────────────────────────

"""ラテン語 (la, <100M) 拡充: 学術ラテン短形 + 古典活用 2 形、AI 往復ゲート、多言語つまみ食い文テスト。"""


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
            "day by day": "cotidie", "for this reason": "ideo", "in favor of": "pro", "with respect to": "re"}


REJECTED = ["interim", "bona fide", "per capita", "a fortiori", "in memoriam", "seriatim", "sua sponte"]


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
    assert rt.status(RT, "la", form) != "pass"
    assert (src, form, "la") not in set(t.pt_el_latin_phrase_pairs())
    assert form not in t.apply_zh_de_phrases(f"We did it {src} today.").replace(src, "")


def test_among_others_restored_but_tie_keeps_english():
    """among-others-la is adopted again (form-level re-score, docs/roundtrip_rescore_20261110.md);
    'among others' and 'inter alia' tie (2 = 2), so the strict-cut rule keeps EN at runtime."""
    t = _t()
    assert rt.status(RT, "la", "inter alia") == "pass"
    assert t.estimate_tokens("among others") == t.estimate_tokens("inter alia")
    assert ("among others", "inter alia", "la") not in set(t.pt_el_latin_phrase_pairs())
    assert t.apply_zh_de_phrases("We did it among others today.") == "We did it among others today."


def test_gradatim_kept():
    t = _t()
    assert ("step by step", "gradatim", "la") in set(t.pt_el_latin_phrase_pairs())
    assert rt.status(RT, "la", "gradatim") == "pass"


def test_in_favor_of_hyper_reversed():
    t = _t()
    assert all(not (s == "in favor of" and d == "υπέρ") for s, d, _ in t.pt_el_latin_phrase_pairs())
    assert "υπέρ" not in t.apply_zh_de_phrases("We voted in favor of the plan.")


# ──── tatoeba_nibble ──────────────────────────────────────────────

"""多言語つまみ食い (it / nl / el / la): Tatoeba 実文を final pass に通し、壊さず token を増やさない。

#161 (es/fr/pt/de/zh/ja/en) と重複しない言語のみ。文は Tatoeba (https://tatoeba.org) の実文で、
CC BY 2.0 FR (https://creativecommons.org/licenses/by/2.0/fr/)。各行の author / url が帰属先。
"""


NIBBLE = ROOT / "tests/fixtures/tatoeba_nibble.jsonl"


ROWS = [json.loads(x) for x in NIBBLE.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_nibble_rows_licensed_and_attributed():
    assert {r["lang"] for r in ROWS} == {"it", "nl", "el", "la"}
    for r in ROWS:
        assert r["source"] == "Tatoeba" and r["license"] == "CC BY 2.0 FR"
        assert r["author"] and r["url"].startswith("https://tatoeba.org/sentences/show/")


@pytest.mark.parametrize("lang", ["it", "nl", "el", "la"])
def test_tatoeba_nibble_final_pass(lang):
    t = _t()
    texts = [r["text"] for r in ROWS if r["lang"] == lang]
    assert len(texts) == 3
    for s in texts:
        out = t.final_token_pass(s)
        assert out == s, (lang, s, out)  # EN-source banks must not touch non-EN text
        assert t.estimate_tokens(out) <= t.estimate_tokens(s), (lang, s, out)


# ──── label_fix_vou_sair_this_vira_fiz ────────────────────────────

"""Data-label fixes: vou sair (pt label), this virá (parity follower of virá), fiz (meanings)."""


FIX = ROOT / "SentenceCalibratedMosaic/fixtures"


def _t_label_fix_vou_sair_this_vira_fiz():
    return load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")


def _read(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def _entry(bank, eid):
    return next(e for e in _read(bank)["entries"] if e["id"] == eid)


# 1. leave-fut-goingto-1s: vou sair is Portuguese and is the runtime winner.
def test_vou_sair_labelled_pt_and_is_runtime_winner():
    e = _entry("es_fr_tense", "leave-fut-goingto-1s")
    assert (e["to"], e["lang"]) == ("vou sair", "pt")
    assert {(c["form"], c["lang"]) for c in e["candidates"]} == {("saldré", "es"), ("vou sair", "pt")}
    assert e["metrics"]["utf8_after"] == len("vou sair".encode("utf-8"))
    t = _t_label_fix_vou_sair_this_vira_fiz()
    for src in e["from"]:
        assert t.apply_es_fr_tense(src) == "vou sair"


def test_vou_sair_beats_es_alternatives_on_o200k_tokens():
    # tokens first, then bytes: vou sair 2/8 < saldré 3/7, voy a salir 3/11 (EN 5/19, I'm 4/18).
    score = lambda s: (tm.o200k_tokens(s), len(s.encode("utf-8")))  # noqa: E731
    assert score("vou sair") == (2, 8)
    assert score("vou sair") < score("saldré") < score("voy a salir")
    assert score("vou sair") < score("I'm going to leave")


def test_vou_sair_evidence_is_the_es_keyed_surface_record():
    data = rt.load()
    # measured once under the old es label (prompt is language-agnostic); no pt key yet = 未測定.
    assert rt.status(data, "es", "vou sair") == "pass"
    assert rt.key("pt", "vou sair") not in data["records"]
    assert rt.key("es", "saldré") not in data["records"]


# 2. this virá: demonstrative parity follower of pt virá. #178 kept it EN while virá was
# reversed; #181 (3bot in-context round-trip, virá 9/9) re-enabled virá, so the follower is
# adopted again. The follower guard in tense_matrix.build() stays for any other reversed base.
def test_this_vira_adopted_again_with_restored_base():
    assert ("pt", "virá") not in tm.ROUNDTRIP_REVERSED
    assert ("pt", "this virá") not in tm.ROUNDTRIP_REVERSED  # its own round-trip passed 9/9
    assert rt.status(rt.load(), "pt", "this virá") == "pass"
    bank = _read("tense_matrix")
    assert [e["from"] for e in bank["entries"] if e["to"] == "this virá"] == [["this will come"]]
    cells = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]
    cell = next(c for c in cells if c["src"] == "this will come")
    assert cell["status"] == "adopt" and cell["parity_verb"] == "virá"


def test_follower_guard_still_fires_if_base_is_reversed(monkeypatch):
    monkeypatch.setattr(tm, "ROUNDTRIP_REVERSED", tm.ROUNDTRIP_REVERSED | {("pt", "virá")})
    bank, report, _ = tm.build()
    assert not [e for e in bank["entries"] if e["to"] == "this virá"]
    cell = next(c for c in report["cells"] if c["src"] == "this will come")
    assert cell["status"] == "reject" and cell["parity_verb"] == "virá"
    assert cell["reason"] == "parity: number-matched pronoun verb winner reversed (EN kept)"


def test_no_adopted_follower_of_a_reversed_base():
    cells = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]
    for c in cells:
        if c.get("status") == "adopt" and c.get("parity_verb"):
            assert (c["lang"], c["parity_verb"]) not in tm.ROUNDTRIP_REVERSED, c["src"]


# 3. fiz: do-it:past unregistered (object never restored); do:past and do:perf kept.
def test_fiz_do_it_past_unregistered_with_roundtrip_reason():
    tense = _read("pt_el_latin_tense")
    assert all(e["id"] != "do-it-past-1s" for e in tense["entries"])
    dropped = next(e for e in tense["examples_not_registered"] if e["id"] == "do-it-past-1s")
    assert dropped["to"] == "fiz" and "roundtrip_reversed" not in dropped
    assert "I did it." in dropped["why_dropped"] and "0/9" in dropped["why_dropped"]
    rec = rt.latest_cohort(rt.load()["records"][rt.key("pt", "fiz")])
    responses = {rt.norm(x["response"]) for x in rec["targets"]}
    assert responses == {"i did", "maybe i did today", "she told me that i did"}
    assert all(x["matched_source"] and x["matched_via_alternate"] for x in rec["targets"])


def test_fiz_keeps_past_and_perfect_and_keeps_the_object():
    assert _entry("es_fr_tense", "do-past-1s")["to"] == "fiz"
    assert _entry("tense_matrix", "mx-do-perf-1s")["to"] == "fiz"
    t = _t_label_fix_vou_sair_this_vira_fiz()
    assert t.apply_es_fr_tense("I did.") == "fiz."
    assert t.apply_es_fr_tense("I have done.") == "fiz."
    assert t.apply_es_fr_tense("I did it.") == "fiz it."
    assert tm.o200k_tokens("fiz it") < tm.o200k_tokens("I did it")


def test_mapping_graph_has_no_label_or_meaning_collisions():
    import mapping_graph as mg

    col = mg.collisions(mg.build())
    assert col["lang_label_mismatch"] == [] and col["multi_meaning"] == []
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
