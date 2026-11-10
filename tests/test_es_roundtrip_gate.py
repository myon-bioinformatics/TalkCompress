"""es (ge100m) adopted winners: independent blind AI round-trip (docs/es_roundtrip_20261109.md)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402

DATA = rt.load()
FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
BANK = json.loads((FIX / "tense_matrix.json").read_text(encoding="utf-8"))
ES_FR = json.loads((FIX / "es_fr_tense.json").read_text(encoding="utf-8"))
JUDGE = json.loads((FIX / "roundtrip_judge/es_blind.json").read_text(encoding="utf-8"))

REVERSED = [
    "viste",
    "dijiste",
    "hizo",
    "dijo",
    "pensamos",
    "this hizo",
    "this dijo",
    "these dijeron",
    "those dijeron",
    "who hizo",
    "who dijo",
    "which hizo",
    "which dijo",
    "which dijeron",
    "que va",
    "que ve",
    "que toma",
    "que hizo",
    "que dijo",
    "que dan",
    "que dijeron",
    "vamos",
    "fue",
]


def _es_entries():
    return [e for bank in (BANK, ES_FR) for e in bank["entries"] if e.get("lang") == "es"]


def _short_forms():
    """Adopted es surfaces that are not English-identity leftovers."""
    return {e["to"] for e in _es_entries() if e["to"] != e["from"][0]}


def test_es_is_ge100m():
    assert "es" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_every_short_es_winner_passed_independent_blind_roundtrip():
    forms = _short_forms()
    # #164 relabeled the el-tagged ``tomaré`` rows to es after reversing el πάρω; that
    # es form was not in the es blind judge (#172) and is not yet measured. Listed
    # explicitly so no other unmeasured es winner slips in.
    unmeasured_from_164 = {"tomaré"}
    assert unmeasured_from_164 <= forms
    forms -= unmeasured_from_164
    # pude: bare 0/9 kept in roundtrip.json (untouched); its reversal was undone by the
    # reaudit_b_4bot context round-trip (9/9), whose evidence lives in roundtrip_judge.
    context_undone = {"pude"}
    assert context_undone <= forms
    forms -= context_undone
    ctx = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge/reaudit_b_4bot_results.json").read_text(encoding="utf-8"))
    for form in context_undone:
        assert rt.status(DATA, "es", form) == "never"
        assert ctx["forms"][f"es:{form}"]["status"] == "pass" and ctx["forms"][f"es:{form}"]["reversal_undone"]
    # 100 → 99: #161 replaced es ``vendré`` (I will come) with la ``veniam``.
    assert len(forms) == 99
    for form in forms:
        assert rt.status(DATA, "es", form) == "pass", form
        cohort = rt.latest_cohort(DATA["records"][rt.key("es", form)])
        assert cohort["complete"] and cohort["completed"] >= DATA["min_trials"]
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        for t in cohort["targets"]:
            assert t["converted"] in JUDGE


@pytest.mark.parametrize("form", REVERSED)
def test_failed_es_forms_reversed(form):
    assert rt.status(DATA, "es", form) == "never"
    assert all(not (e.get("lang") == "es" and e["to"] == form) for e in _es_entries())


def test_pude_reversal_undone_entry_is_live():
    live = [e for e in ES_FR["entries"] if e["id"] == "could-past-1s"]
    assert len(live) == 1 and live[0]["to"] == "pude" and live[0]["lang"] == "es"
    assert not any(e["id"] == "could-past-1s" for e in ES_FR["examples_not_registered"])


@pytest.mark.parametrize("form,eid", [("vamos", "go-fut-1p"), ("fue", "go-past-3s")])
def test_es_fr_short_forms_recorded_as_not_registered(form, eid):
    dropped = next(e for e in ES_FR["examples_not_registered"] if e["id"] == eid and e["to"] == form)
    assert "0/9" in dropped["why_dropped"]
    # EN leftover kept in entries so tense_matrix does not adopt a next-language form
    identity = next(e for e in ES_FR["entries"] if e["id"] == eid)
    assert identity["lang"] == "es" and identity["to"] == identity["from"][0]


def test_roundtrip_enforced_langs_unchanged():
    import tense_matrix as tm

    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    assert "es" not in tm.ROUNDTRIP_ENFORCED_LANGS
