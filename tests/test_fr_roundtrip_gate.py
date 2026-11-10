"""fr (ge100m) adopted winners: independent blind AI round-trip (docs/fr_roundtrip_20261109.md)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

DATA = rt.load()
FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
BANK = json.loads((FIX / "tense_matrix.json").read_text(encoding="utf-8"))
ES_FR = json.loads((FIX / "es_fr_tense.json").read_text(encoding="utf-8"))
JUDGE = json.loads((FIX / "roundtrip_judge/fr_blind.json").read_text(encoding="utf-8"))
REPORT = {c["src"]: c for c in json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]}

REVERSED_TM = ["prends", "vins", "vis", "voulus", "sus", "avoir voulu", "avoir eu", "avoir su",
               "avais su", "ira"]
REVERSED_ES_FR = {"arrive-past-1s": "arrivé"}
# Re-score (docs/roundtrip_rescore_20261110.md): pris / ont su matched another official source of
# the same form; que dit / que ont voulu / que ont eu / que ont su matched with leading que≡that.
RESCUED_TM = ["pris", "ont su", "que dit", "que ont voulu", "que ont eu", "que ont su"]
# passed themselves (9/9) but number parity follows the reversed pronoun winner (ira)
PARITY_EN = {"this will go": "this ira"}
# parity followers of ont su, adopted again with their restored base
PARITY_RESTORED = {"these have known": "these ont su", "those have known": "those ont su"}


def _fr_forms() -> set[str]:
    return {e["to"] for bank in (BANK, ES_FR) for e in bank["entries"] if e["lang"] == "fr"}


def test_fr_is_ge100m():
    assert "fr" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_policy_scope_unchanged():
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    assert {f for lang, f in tm.ROUNDTRIP_REVERSED if lang == "fr"} == set(REVERSED_TM)


def test_every_fr_winner_passed_independent_blind_roundtrip():
    forms = _fr_forms()
    assert len(forms) == 101  # 93 + 6 rescued + these / those ont su (parity)
    for form in forms:
        assert rt.status(DATA, "fr", form) == "pass", form
        cohort = rt.latest_cohort(DATA["records"][rt.key("fr", form)])
        assert cohort["complete"] and cohort["completed"] >= DATA["min_trials"]
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        for t in cohort["targets"]:
            assert t["converted"] in JUDGE


def test_all_113_fr_forms_recorded():
    recs = [k for k in DATA["records"] if k.startswith("fr:")]
    assert len(recs) == 113
    st = [rt.status(DATA, "fr", DATA["records"][k]["form"]) for k in recs]
    assert st.count("pass") == 102 and st.count("never") == 11


@pytest.mark.parametrize("form", REVERSED_TM + ["arrivé"])
def test_failed_fr_forms_reversed(form):
    assert rt.status(DATA, "fr", form) == "never"
    assert form not in _fr_forms()


@pytest.mark.parametrize("eid,form", sorted(REVERSED_ES_FR.items()))
def test_es_fr_reversal_recorded_as_not_registered(eid, form):
    assert all(e["id"] != eid for e in ES_FR["entries"])
    dropped = next(e for e in ES_FR["examples_not_registered"] if e["id"] == eid)
    assert dropped["to"] == form and dropped["lang"] == "fr" and "0/9" in dropped["why_dropped"]


@pytest.mark.parametrize("form", RESCUED_TM)
def test_rescued_fr_forms_adopted_again(form):
    assert rt.status(DATA, "fr", form) == "pass"
    assert form in _fr_forms()
    assert ("fr", form) not in tm.ROUNDTRIP_REVERSED


def test_es_fr_pris_restored_after_rescore():
    # judge restored 'I took' for Pris.; the cohort had been scored against 'you took' only
    restored = next(e for e in ES_FR["entries"] if e["id"] == "take-past-1s")
    assert (restored["to"], restored["lang"]) == ("pris", "fr")
    assert all(e["id"] != "take-past-1s" for e in ES_FR["examples_not_registered"])


@pytest.mark.parametrize("src,form", sorted(PARITY_RESTORED.items()))
def test_parity_followers_restored_with_base(src, form):
    assert rt.status(DATA, "fr", form) == "pass"
    assert any(src in e["from"] and e["to"] == form for e in BANK["entries"])


@pytest.mark.parametrize("src", ["I arrived"])
def test_reversed_es_fr_sources_stay_english(src):
    # no next-language candidate (e.g. de ``nahm``) is promoted by the matrix
    assert all(src not in e["from"] for e in BANK["entries"])
    assert src not in REPORT or REPORT[src]["status"] == "reject"
    assert tm.build()[0]["entries"] == BANK["entries"]


@pytest.mark.parametrize("src,form", sorted(PARITY_EN.items()))
def test_parity_followers_stay_english(src, form):
    assert rt.status(DATA, "fr", form) == "pass"
    assert all(src not in e["from"] for e in BANK["entries"])
    assert REPORT[src]["status"] == "reject"
