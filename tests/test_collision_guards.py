"""言語間の衝突ガード: 助動詞トークン、変換時バンク、往復。

- collision_aux_banks: Collision guard: auxiliary tokens and conversion-time banks (follow-up to #27).
- collision_roundtrip: Cross-language collision guard, estimate_tokens Thai / Vietnamese, zh stative
"""

from __future__ import annotations

from pathlib import Path
from tests._helpers import load
import copy
import json
import reaudit_a_3bot_roundtrip as reaudit_a
import roundtrip as rt
import sys
import tense_matrix as tm

import pytest


# ──── collision_aux_banks ─────────────────────────────────────────

"""Collision guard: auxiliary tokens and conversion-time banks (follow-up to #27)."""


ROOT = Path(__file__).resolve().parents[1]


BANK = json.loads(tm.BANK_PATH.read_text(encoding="utf-8"))


REG = tm.form_registry(json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"])


def _t():
    return load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")


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
    # Reversed pt phrase is no longer registered; direct collision rejection
    # remains covered by test_bank_form_collision_rejects above.
    assert ("pt_el_latin_phrases", "by-means-of-pt-el", "via") not in rows
    t = _t()
    assert t.collision_blocked("es_fr_tense") >= {("go-past-1s", "vim"), ("think-past-1s", "pensé")}
    assert t.collision_blocked("nope") == frozenset()


@pytest.mark.parametrize(
    ("s", "want"),
    [("I went", "fui"), ("I gave", "I gave"), ("I thought", "pensei"), ("I have given", "I have given")],
)
def test_runtime_tense_bank_guarded(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_runtime_phrase_bank_guarded():
    assert _t().apply_zh_de_phrases("by means of") == "by means of"
    # The sole remaining pt phrase is labeled /mês but does not beat EN
    # under the runtime estimator; label-level roundtrip coverage is separate.
    assert _t().apply_zh_de_phrases("per month") == "per month"


def test_bank_phrase_pairs_blocked_falls_back():
    t = _t()
    data = {"entries": [{"id": "x", "from": ["by means of"], "to": "via", "lang": "pt",
                         "candidates": [{"form": "via", "lang": "pt"}, {"form": "μέσω", "lang": "el"}]}]}
    forms = {f for _s, f, _l in t._bank_phrase_pairs(data, blocked=frozenset({("x", "via")}))}
    assert forms == {"μέσω"}
    assert "via" in {f for _s, f, _l in t._bank_phrase_pairs(data)}


# ──── collision_roundtrip ─────────────────────────────────────────

"""Cross-language collision guard, estimate_tokens Thai / Vietnamese, zh stative
progressive guard, and the report-only AI round-trip infrastructure."""


BANK_collision_roundtrip = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/tense_matrix.json").read_text(encoding="utf-8"))


CONJ = json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"]


REG_collision_roundtrip = tm.form_registry(CONJ)


def _c_collision_roundtrip(form, lang, shape="simple"):
    return {"form": form, "lang": lang, "shape": shape}


# --- collision guard -------------------------------------------------------


@pytest.mark.parametrize(
    ("cand", "tense", "verb"),
    [
        (_c_collision_roundtrip("das", "es"), "pres", "give"),  # de article
        (_c_collision_roundtrip("da", "pl", "pf-future"), "fut", "give"),  # es/it present
        (_c_collision_roundtrip("da", "es"), "pres", "give"),  # pl future (symmetric)
        (_c_collision_roundtrip("di", "es"), "past", "give"),  # it preposition
        (_c_collision_roundtrip("vimos", "es"), "past", "see"),  # pt 'we come'
        (_c_collision_roundtrip("eu", "fr"), "pres", "have"),  # standalone: pt pronoun eu
        (_c_collision_roundtrip("aurai pensé", "fr", "compound"), "futperf", "think"),  # verb clash kept after aux
        (_c_collision_roundtrip("kom", "sv"), "past", "come"),  # nl present 'I come'
        (_c_collision_roundtrip("ga", "nb"), "past", "give"),  # nl 'I go'
    ],
)
def test_collision_rejects(cand, tense, verb):
    assert tm.collision(cand, tense, verb, REG_collision_roundtrip)


@pytest.mark.parametrize(
    ("cand", "tense", "verb"),
    [
        (_c_collision_roundtrip("tomamos", "es", "simple-preterite"), "perf", "take"),  # es pres=pret syncretism, pt twin
        (_c_collision_roundtrip("kom", "nl"), "pres", "come"),  # its own registration
        (_c_collision_roundtrip("fant", "nb"), "past", "find"),  # unregistered
        (_c_collision_roundtrip("estoy yendo", "es", "prog-gerund"), "presprog", "go"),
        (_c_collision_roundtrip("aurai eu", "fr", "compound"), "futperf", "have"),  # bound participle: pt pronoun eu ignored
        (_c_collision_roundtrip("avez eu", "fr", "compound"), "perf", "have"),
        (_c_collision_roundtrip("mysleli jsme", "cs", tm.SLAVIC_GENDERED), "perf", "think"),
    ],
)
def test_collision_allows(cand, tense, verb):
    assert tm.collision(cand, tense, verb, REG_collision_roundtrip) == []


def test_sa_it_know_vs_nordic_said():
    reg = copy.deepcopy(REG_collision_roundtrip)
    reg["sa"].add(("it", "know", "pres"))
    assert tm.collision(_c_collision_roundtrip("sa", "sv"), "past", "say", reg)


def test_candidate_head():
    assert tm.candidate_head(_c_collision_roundtrip("zijn aan het gaan zijn", "nl", "prog-aan-het"), "futprog") == ("gaan", "inf")
    assert tm.candidate_head(_c_collision_roundtrip("suis en train d'aller", "fr", "prog-en-train-de"), "presprog") == ("aller", "inf")
    assert tm.candidate_head(_c_collision_roundtrip("viděl jsem", "cs", tm.SLAVIC_GENDERED), "perf") == ("viděl", "lpart")
    assert tm.candidate_head(_c_collision_roundtrip("ve", "es"), "pres") == ("ve", "pres")


def test_bank_has_no_collision():
    """Every adopted form passes the guard (bank `to` = guarded runtime winner)."""
    for e in BANK_collision_roundtrip["entries"]:
        if e["subject"].startswith(("dem-", "rel-")):
            continue
        cell = next(c for c in json.loads(tm.REPORT_PATH.read_text(encoding="utf-8"))["cells"]
                    if c["subject"] == e["subject"] and c["tense"] == e["tense"] and c["verb"] == e["id"].split("-")[1])
        assert e["to"] not in (cell.get("crossling_dropped") or []), e["id"]


@pytest.mark.parametrize(
    ("s", "bad"),
    [("you give", "das"), ("he gives", "da"), ("I have given", "di"), ("we have seen", "vimos")],
)
def test_runtime_drops_collided(s, bad):
    assert _t().apply_es_fr_tense(s) != bad


# --- estimate_tokens -------------------------------------------------------


def test_estimate_tokens_thai_counted():
    t = _t()
    # タイ語は o200k の語彙で最長一致（旧: 1 字 1 トークン）。値は o200k_base 実測
    assert t.estimate_tokens("ฉันไป") == 3
    assert t.estimate_tokens("ไป go") == 2


def test_estimate_tokens_vietnamese_extra_cost():
    t = _t()
    # ế (U+1EBF) is one word with the Latin letters, +1 token per such char
    assert t.estimate_tokens("biết") == 2
    assert t.estimate_tokens("được") == 2
    assert t.estimate_tokens("biet") == 1
    # calibrated 4-letter accented bucket is 2 (o200k says " café" = 1: known gap)
    assert t.estimate_tokens("café") == 2


# --- zh stative progressive ------------------------------------------------


@pytest.mark.parametrize(("s", "want"), [("我在有", ["有"]), ("他正在知道", ["知"]), ("我在吃", []),
                                         ("猫在桌下", []), ("现在有人", []), ("存在", [])])
def test_zh_stative_progressive(s, want):
    assert _t().zh_stative_progressive(s) == want


def test_no_zh_stative_progressive_in_banks():
    fx = ROOT / "SentenceCalibratedMosaic/fixtures"
    t = _t()
    for p in fx.glob("*.json"):
        for line in p.read_text(encoding="utf-8").splitlines():
            assert not t.zh_stative_progressive(line), (p.name, line)


# --- round-trip ------------------------------------------------------------


def _data(**rec):
    d = rt.load()
    d = copy.deepcopy(d)
    d["records"] = {k: {"trials": t, "restored": r} for k, (t, r) in rec.items()}
    return d


def test_roundtrip_data_shape():
    d = rt.load()
    th = d["thresholds"]
    assert 0 < th["ge100m"] < th["lt100m"] <= 1
    assert len(d["templates"]) >= 2 and len(d["seeds"]) >= 2
    assert d["min_trials"] <= len(d["templates"]) * len(d["seeds"])
    for L in ("de", "es", "fr", "pt", "it", "zh", "ja", "id", "ru"):
        assert L in d["ge100m_langs"]
    for L in ("nl", "sv", "da", "nb", "is", "af", "cs", "pl", "el"):
        assert L not in d["ge100m_langs"]


def test_roundtrip_status_thresholds():
    d = _data(**{"nl:wil": (9, 8), "es:ve": (9, 6), "pt:quer": (9, 0), "cs:vezme": (9, 9), "it:dà": (3, 3)})
    assert rt.status(d, "nl", "wil") == "fail"  # 0.89 < 0.9
    assert rt.status(d, "cs", "vezme") == "pass"
    assert rt.status(d, "es", "ve") == "pass"  # 0.67 ≥ 0.6
    assert rt.status(d, "pt", "quer") == "never"  # zero rate rejected for ≥100M too
    assert rt.status(d, "it", "dà") == "unverified"  # too few trials
    assert rt.status(d, "fr", "veux") == "unverified"


def test_roundtrip_gate_scopes():
    d = _data(**{"pt:quer": (9, 0)})
    lt, al = rt.gate_for(d, "lt100m"), rt.gate_for(d, "all")
    assert lt("veux", "fr") and not al("veux", "fr")
    assert not lt("wil", "nl") and not al("wil", "nl")
    assert not lt("quer", "pt")


def test_roundtrip_sentences():
    d = rt.load()
    pairs = rt.sentences(d, "he wants", "quer")
    assert pairs[0] == ("He wants.", "Quer.")
    assert len(pairs) == len(d["templates"])


def test_roundtrip_run_counts(tmp_path):
    d = _data()
    d["templates"] = ["{s}.", "Maybe {s} today."]
    d["seeds"] = [1, 2]
    fake = tmp_path / "fake.py"
    # restores only when seed is 1 (echoes the EN it was told via mapping)
    fake.write_text(
        "import os,sys\n"
        "p=sys.stdin.read().rsplit('\\n',1)[-1]\n"
        "m={'Quer.':'He wants.','Maybe quer today.':'Maybe he wants today.'}\n"
        "print(m[p] if os.environ['ROUNDTRIP_SEED']=='1' else 'nope')\n",
        encoding="utf-8",
    )
    out = rt.run(d, f"{sys.executable} {fake}", entries=[{"from": ["he wants"], "to": "quer", "lang": "pt"}])
    rec = out["records"]["pt:quer"]
    assert (rec["trials"], rec["restored"]) == (4, 2)
    assert rt.rate(rec) == 0.5


def test_committed_bank_not_gated_and_no_never_forms():
    """Report-only: bank is the ungated build; but a never-restoring form must not be adopted."""
    d = rt.load()
    # re-enabled on a passing in-context cohort kept outside roundtrip.json (3bot reaudit)
    reaudit = reaudit_a.restored()
    for e in BANK_collision_roundtrip["entries"]:
        if (e["lang"], e["to"]) in reaudit:
            continue
        assert rt.status(d, e["lang"], e["to"]) != "never", e["id"]


def test_impact_lt100m_lists_sub100m_only():
    d = rt.load()
    # All committed winners may pass. Exercise the gate with an explicitly
    # unverified winner instead of depending on unfinished production records.
    d["records"].pop("cs:vezmete", None)
    rows = rt.impact(d, "lt100m")
    assert any(eid == "mx-take-fut-2" and old[1] == "cs"
               for eid, _src, old, _new in rows if old)
    # Demonstrative parity followers reuse their number-matched pronoun winner, so a
    # gated pronoun class can move a ge100m dem row too (pt ``this virá`` follows
    # ``it will come`` after the #171 merge). Direct winners stay sub-100M only.
    # 3bot reaudit forms still carry their bare 0/9 record, so the gate would move them.
    reaudit = reaudit_a.restored()
    langs = {old[1] for k, _s, old, _n in rows if old and "-dem-" not in k and tuple(reversed(old)) not in reaudit}
    assert langs.isdisjoint(d["ge100m_langs"])


def test_committed_cs_pl_winners_have_passing_roundtrips():
    d = rt.load()
    entries = [e for e in BANK_collision_roundtrip["entries"] if e["lang"] in {"cs", "pl"}]
    assert {e["lang"] for e in entries} == {"cs", "pl"}
    for e in entries:
        rec = d["records"][rt.key(e["lang"], e["to"])]
        assert rt.status(d, e["lang"], e["to"]) == "pass", e["id"]
        cohort = rt.latest_cohort(rec)
        assert cohort is not None and cohort["complete"], e["id"]
        assert cohort["completed"] >= d["min_trials"], e["id"]


def test_guard_falls_to_next_best_not_english():
    """A collided winner hands over to the next-cheapest candidate (not straight to EN)."""
    cells = {c["src"]: c for c in json.loads(tm.REPORT_PATH.read_text(encoding="utf-8"))["cells"]}
    c = cells["we have seen"]
    assert c["crossling_dropped"] == ["vimos"]
    # o200k: vimos (1 tok) dropped → nl zagen round-trip-gated (#29) → next-best de sahen
    # (2 tok / 5 B) ties EN "we've seen" on tokens (2 / 10) and wins on bytes
    assert c["en_best"] == "we've seen"
    assert c["roundtrip_gated"] == ["zagen"]
    assert c["best"] == "sahen" and c["lang"] == "de"
    assert c["tok"] == [2, 2] and c["utf8"][1] < c["utf8"][0] and c["status"] == "adopt"
    assert _t().apply_es_fr_tense("you give") == "dai"  # das dropped → it dai adopted
