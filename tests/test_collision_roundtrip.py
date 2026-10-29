"""Cross-language collision guard, estimate_tokens Thai / Vietnamese, zh stative
progressive guard, and the report-only AI round-trip infrastructure."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from tests._helpers import load

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
CONJ = json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"]
REG = tm.form_registry(CONJ)


def _t():
    return load("tessera_talk", "TesseraTalk/tessera_talk.py")


def _c(form, lang, shape="simple"):
    return {"form": form, "lang": lang, "shape": shape}


# --- collision guard -------------------------------------------------------


@pytest.mark.parametrize(
    ("cand", "tense", "verb"),
    [
        (_c("das", "es"), "pres", "give"),  # de article
        (_c("da", "pl", "pf-future"), "fut", "give"),  # es/it present
        (_c("da", "es"), "pres", "give"),  # pl future (symmetric)
        (_c("di", "es"), "past", "give"),  # it preposition
        (_c("vimos", "es"), "past", "see"),  # pt 'we come'
        (_c("eu", "fr"), "pres", "have"),  # standalone: pt pronoun eu
        (_c("aurai pensé", "fr", "compound"), "futperf", "think"),  # verb clash kept after aux
        (_c("kom", "sv"), "past", "come"),  # nl present 'I come'
        (_c("ga", "nb"), "past", "give"),  # nl 'I go'
    ],
)
def test_collision_rejects(cand, tense, verb):
    assert tm.collision(cand, tense, verb, REG)


@pytest.mark.parametrize(
    ("cand", "tense", "verb"),
    [
        (_c("tomamos", "es", "simple-preterite"), "perf", "take"),  # es pres=pret syncretism, pt twin
        (_c("kom", "nl"), "pres", "come"),  # its own registration
        (_c("fant", "nb"), "past", "find"),  # unregistered
        (_c("estoy yendo", "es", "prog-gerund"), "presprog", "go"),
        (_c("aurai eu", "fr", "compound"), "futperf", "have"),  # bound participle: pt pronoun eu ignored
        (_c("avez eu", "fr", "compound"), "perf", "have"),
        (_c("mysleli jsme", "cs", tm.SLAVIC_GENDERED), "perf", "think"),
    ],
)
def test_collision_allows(cand, tense, verb):
    assert tm.collision(cand, tense, verb, REG) == []


def test_sa_it_know_vs_nordic_said():
    reg = copy.deepcopy(REG)
    reg["sa"].add(("it", "know", "pres"))
    assert tm.collision(_c("sa", "sv"), "past", "say", reg)


def test_candidate_head():
    assert tm.candidate_head(_c("zijn aan het gaan zijn", "nl", "prog-aan-het"), "futprog") == ("gaan", "inf")
    assert tm.candidate_head(_c("suis en train d'aller", "fr", "prog-en-train-de"), "presprog") == ("aller", "inf")
    assert tm.candidate_head(_c("viděl jsem", "cs", tm.SLAVIC_GENDERED), "perf") == ("viděl", "lpart")
    assert tm.candidate_head(_c("ve", "es"), "pres") == ("ve", "pres")


def test_bank_has_no_collision():
    """Every adopted form passes the guard (bank `to` = guarded runtime winner)."""
    for e in BANK["entries"]:
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
    assert t.estimate_tokens("ฉันไป") == 5
    assert t.estimate_tokens("ไป go") == 3


def test_estimate_tokens_vietnamese_extra_cost():
    t = _t()
    # ế (U+1EBF) is one word with the Latin letters, +1 token per such char
    assert t.estimate_tokens("biết") == 2
    assert t.estimate_tokens("được") == 2
    assert t.estimate_tokens("biet") == 1
    assert t.estimate_tokens("café") == 1  # Latin-1 unchanged


# --- zh stative progressive ------------------------------------------------


@pytest.mark.parametrize(("s", "want"), [("我在有", ["有"]), ("他正在知道", ["知"]), ("我在吃", []),
                                         ("猫在桌下", []), ("现在有人", []), ("存在", [])])
def test_zh_stative_progressive(s, want):
    assert _t().zh_stative_progressive(s) == want


def test_no_zh_stative_progressive_in_banks():
    fx = ROOT / "TesseraTalk/fixtures"
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
    for e in BANK["entries"]:
        assert rt.status(d, e["lang"], e["to"]) != "never", e["id"]


def test_impact_lt100m_lists_sub100m_only():
    d = rt.load()
    rows = rt.impact(d, "lt100m")
    assert rows
    langs = {old[1] for _k, _s, old, _n in rows if old}
    assert langs & {"nl", "cs", "pl"}


def test_guard_falls_to_next_best_not_english():
    """A collided winner hands over to the next-cheapest candidate (not straight to EN)."""
    cells = {c["src"]: c for c in json.loads(tm.REPORT_PATH.read_text(encoding="utf-8"))["cells"]}
    c = cells["we have seen"]
    assert c["crossling_dropped"] == ["vimos"]
    # o200k: vimos (1 tok) dropped → next-best nl zagen (1 tok / 5 B) beats EN "we've seen" (2 / 10)
    assert c["en_best"] == "we've seen"
    assert c["best"] == "zagen" and c["lang"] == "nl"
    assert c["tok"] == [2, 1] and c["status"] == "adopt"
    assert _t().apply_es_fr_tense("you give") == "dai"  # das dropped → it dai adopted
