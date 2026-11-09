"""it (ge100m) adopted winners: independent blind AI round-trip (docs/it_roundtrip_20261108.md)."""

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
PHRASES = json.loads((FIX / "pt_el_latin_phrases.json").read_text(encoding="utf-8"))
JUDGE = json.loads((FIX / "roundtrip_judge/it_blind.json").read_text(encoding="utf-8"))


def test_it_is_ge100m():
    assert "it" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_every_it_winner_passed_independent_blind_roundtrip():
    forms = {e["to"] for bank in (BANK, PHRASES) for e in bank["entries"] if e["lang"] == "it"}
    assert len(forms) == 28
    for form in forms:
        assert rt.status(DATA, "it", form) == "pass", form
        cohort = rt.latest_cohort(DATA["records"][rt.key("it", form)])
        assert cohort["complete"] and cohort["completed"] >= DATA["min_trials"]
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        for t in cohort["targets"]:
            assert t["converted"] in JUDGE


@pytest.mark.parametrize("form", ["que sa", "que dà", "ciao"])
def test_failed_it_forms_reversed(form):
    assert rt.status(DATA, "it", form) == "never"
    assert all(not (e["lang"] == "it" and e["to"] == form) for b in (BANK, PHRASES) for e in b["entries"])


def test_ciao_recorded_as_not_registered():
    dropped = next(e for e in PHRASES["examples_not_registered"] if e["id"] == "see-you-soon-it-pt-el")
    assert dropped["to"] == "ciao" and "0/9" in dropped["why_dropped"]
