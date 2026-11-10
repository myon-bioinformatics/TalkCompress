"""fr (ge100m) adopted winners: independent blind AI round-trip (docs/fr_roundtrip_20261109.md)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import reaudit_a_3bot_roundtrip as reaudit  # noqa: E402
import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

DATA = rt.load()
FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
BANK = json.loads((FIX / "tense_matrix.json").read_text(encoding="utf-8"))
ES_FR = json.loads((FIX / "es_fr_tense.json").read_text(encoding="utf-8"))
JUDGE = json.loads((FIX / "roundtrip_judge/fr_blind.json").read_text(encoding="utf-8"))
REPORT = {c["src"]: c for c in json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]}

# prends / vins / vis / voulus / sus / avais su / ira (and es_fr arrivé) were reversed here
# first, then re-enabled by the 3bot in-context round-trip (docs/reaudit_a_3bot_roundtrip_20261110.md).
REVERSED_TM = ["pris", "avoir voulu", "avoir eu", "avoir su",
               "ont su", "que dit", "que ont voulu", "que ont eu", "que ont su"]
REVERSED_ES_FR = {"take-past-1s": "pris"}
# fr forms re-enabled by a passing context cohort; roundtrip.json still holds their bare 0/9
# (essayé: no fr record), the context cohort lives in roundtrip_judge/reaudit_a_3bot_results.json
REAUDIT = {f for lang, f in reaudit.restored() if lang == "fr"}
# passed themselves (9/9) but number parity follows the reversed pronoun winner (ont su)
PARITY_EN = {"these have known": "these ont su", "those have known": "those ont su"}


def _fr_forms() -> set[str]:
    return {e["to"] for bank in (BANK, ES_FR) for e in bank["entries"] if e["lang"] == "fr"}


def test_fr_is_ge100m():
    assert "fr" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_policy_scope_unchanged():
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    assert {f for lang, f in tm.ROUNDTRIP_REVERSED if lang == "fr"} == set(REVERSED_TM)


def test_every_fr_winner_passed_independent_blind_roundtrip():
    forms = _fr_forms()
    assert len(forms) == 103 and REAUDIT <= forms
    for form in forms - REAUDIT:
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
    assert st.count("pass") == 96 and st.count("never") == 17


@pytest.mark.parametrize("form", REVERSED_TM)
def test_failed_fr_forms_reversed(form):
    assert rt.status(DATA, "fr", form) == "never"
    assert form not in _fr_forms()


@pytest.mark.parametrize("eid,form", sorted(REVERSED_ES_FR.items()))
def test_es_fr_reversal_recorded_as_not_registered(eid, form):
    assert all(e["id"] != eid for e in ES_FR["entries"])
    dropped = next(e for e in ES_FR["examples_not_registered"] if e["id"] == eid)
    assert dropped["to"] == form and dropped["lang"] == "fr" and "0/9" in dropped["why_dropped"]


@pytest.mark.parametrize("src", ["I took"])
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


def test_reaudit_forms_adopted_on_the_context_cohort_only():
    assert REAUDIT == {"vis", "vins", "sus", "voulus", "prends", "avais su", "ira", "arrivé", "essayé"}
    res = json.loads(reaudit.RESULTS.read_text(encoding="utf-8"))["results"]
    for form in REAUDIT:
        key = "pt:essayé" if form == "essayé" else f"fr:{form}"
        assert res[key]["status"] == "pass" and res[key]["exact"] >= 6
        # gate-visible roundtrip.json is not rewritten by this study (owned by the 2bot audit)
        assert rt.status(DATA, "fr", form) == ("unverified" if form == "essayé" else "never")
    assert rt.status(DATA, "fr", "this ira") == "pass"
    assert any(e["from"] == ["this will go"] and e["to"] == "this ira" for e in BANK["entries"])
