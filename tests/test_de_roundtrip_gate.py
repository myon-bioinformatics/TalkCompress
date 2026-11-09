"""de (ge100m) adopted winners: independent blind AI round-trip (docs/de_roundtrip_20261109.md)."""

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
PHRASES = json.loads((FIX / "zh_de_phrases.json").read_text(encoding="utf-8"))
ES = json.loads((FIX / "es_fr_tense.json").read_text(encoding="utf-8"))
JUDGE = json.loads((FIX / "roundtrip_judge/de_blind.json").read_text(encoding="utf-8"))

PASS_FORMS = ['kam', 'sah', 'dachtest', 'denkt', 'nehmen', 'finden', 'wollen', 'denken', 'sagen', 'kamen', 'sahen', 'nahmen', 'fanden', 'wollten', 'sagten', 'dachten', 'who denkt', 'which denkt', 'Bahnhof', 'Datenschutz', 'Handy', 'Ampel', 'Stau', 'Lenkrad', 'Mikrowelle', 'Klimawandel', 'Haustür', 'Kraftwerk', 'Kernenergie', 'Geburtsurkunde', 'Telefonnummer', 'Erderwärmung']
FAIL_FORMS = ['nahm', 'fand', 'dachte', 'kamst', 'tatest', 'nahmst', 'taten', 'this kam', 'this sah', 'this nahm', 'this fand', 'this dachte', 'these kamen', 'these sahen', 'these nahmen', 'these fanden', 'these dachten', 'those kamen', 'those sahen', 'those nahmen', 'those fanden', 'those dachten', 'who kam', 'who sah', 'who nahm', 'who fand', 'who dachte', 'who kamen', 'who fanden', 'which kam', 'which sah', 'which nahm', 'which fand', 'which dachte', 'which kamen', 'which sahen', 'which nahmen', 'which fanden', 'which dachten', 'que denkt', 'que kam', 'que sah', 'que nahm', 'que fand', 'que dachte', 'que kamen', 'que sahen', 'que nahmen', 'que fanden', 'que dachten', 'Tankstelle', 'Parkplatz', 'wenn']


def test_de_is_ge100m():
    assert "de" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_every_remaining_de_winner_passed_independent_blind_roundtrip():
    forms = {e["to"] for bank in (BANK, PHRASES, ES) for e in bank["entries"] if e.get("lang") == "de"}
    assert forms == set(PASS_FORMS)
    assert len(forms) == 32
    for form in forms:
        assert rt.status(DATA, "de", form) == "pass", form
        cohort = rt.latest_cohort(DATA["records"][rt.key("de", form)])
        assert cohort["complete"] and cohort["completed"] >= DATA["min_trials"]
        assert cohort["restored"] == 9 and cohort["completed"] == 9
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        assert cohort["config"]["normalization"] == "norm-nfc-v1"
        for t in cohort["targets"]:
            assert t["converted"] in JUDGE


@pytest.mark.parametrize("form", FAIL_FORMS)
def test_failed_de_forms_reversed(form):
    assert rt.status(DATA, "de", form) == "never"
    assert all(not (e.get("lang") == "de" and e["to"] == form)
               for b in (BANK, PHRASES, ES) for e in b["entries"])


def test_zh_de_failures_recorded_as_not_registered():
    dropped = {e["id"]: e for e in PHRASES["examples_not_registered"]}
    for eid, form in ("tankstelle", "Tankstelle"), ("parkplatz", "Parkplatz"), ("wenn", "wenn"):
        assert dropped[eid]["to"] == form and "0/9" in dropped[eid]["why_dropped"]


def test_es_fr_fand_recorded_as_not_registered():
    dropped = next(e for e in ES["examples_not_registered"] if e["id"] == "find-past-1s")
    assert dropped["to"] == "fand" and "0/9" in dropped["why_dropped"]


def test_zh_entries_untouched_count():
    # 62 → 37 after the zh round-trip gate (#169); this PR does not touch zh entries.
    assert sum(1 for e in PHRASES["entries"] if e["lang"] == "zh") == 37


def test_roundtrip_enforced_langs_unchanged():
    import tense_matrix as tm
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    assert ("de", "fand") in tm.ROUNDTRIP_REVERSED
