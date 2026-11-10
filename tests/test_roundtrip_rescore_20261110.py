"""Accepted-sources re-score + owner-approved leading que≡that (docs/roundtrip_rescore_20261110.md)."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
SNAP = FIX / "roundtrip_judge/accepted_sources_v1.json"
TEMPLATES = ["{s}.", "Maybe {s} today.", "She told me that {s}."]
DATA = rt.load()

RESCUED_ALT = [("de", "fand"), ("fr", "pris"), ("fr", "ont su"), ("es", "fue"),
               ("zh", "高速"), ("zh", "短期"), ("zh", "小学"), ("zh", "高铁"), ("zh", "微调")]
QUE_FORMS = [("es", "que dan"), ("es", "que toma"), ("es", "que va"), ("es", "que ve"),
             ("fr", "que dit"), ("fr", "que ont voulu"), ("fr", "que ont eu"), ("fr", "que ont su"),
             ("it", "que sa"), ("it", "que dà"), ("pt", "que acha"), ("pt", "que vem"), ("de", "que denkt")]
STILL_REVERSED = [("es", "dijo"), ("es", "dijiste"), ("es", "pensamos")]


# ---- leading que ≡ that -------------------------------------------------------------

@pytest.mark.parametrize("sentence,want", [
    ("Que give.", ["That give."]),
    ("Maybe que give today.", ["Maybe that give today."]),
    ("She told me that que give.", ["She told me that that give."]),
    ("maybe QUE give today.", ["maybe That give today."]),  # case of the marker's first letter is kept
])
def test_leading_que_maps_to_that(sentence, want):
    assert rt.leading_que_that(sentence, TEMPLATES) == want


@pytest.mark.parametrize("sentence", [
    "Maybe I que give today.",        # not phrase-leading
    "She told me that give que.",     # trailing
    "Queen.",                         # no word boundary
    "Quegive.",
    "That give.",                     # already English
    "Perhaps que give today.",        # template prefix differs
])
def test_non_leading_or_other_differences_do_not_match(sentence):
    assert rt.leading_que_that(sentence, TEMPLATES) == []


def test_equivalence_relaxes_nothing_else():
    pool = ["Maybe que goes today."] + rt.leading_que_that("Maybe que goes today.", TEMPLATES)
    assert any(rt.norm("Maybe that goes today.") == rt.norm(s) for s in pool)
    for wrong in ("Maybe which goes today.", "Maybe that go today.", "Maybe it goes today.", "Maybe that goes."):
        assert not any(rt.norm(wrong) == rt.norm(s) for s in pool), wrong


def test_run_rejects_marker_without_accepted_sources_or_unknown_marker():
    with pytest.raises(ValueError):
        rt.run(copy.deepcopy(DATA), "true", only_lang="es", marker_equivalence=rt.MARKER_EQUIVALENCE)
    with pytest.raises(ValueError):
        rt.run(copy.deepcopy(DATA), "true", only_lang="es", accepted_sources={"es:fue": ["he went"]},
               marker_equivalence="anything-goes")


def _cohort(lang, form):
    return copy.deepcopy(rt.latest_cohort(DATA["records"][rt.key(lang, form)]))


def test_validator_rejects_tampered_marker_cohorts():
    good = _cohort("es", "que va")
    assert rt._valid_cohort(good)
    bad = copy.deepcopy(good)
    bad["config"]["marker_equivalence"] = "leading-que-that-v2"
    assert not rt._valid_cohort(bad)
    bad = copy.deepcopy(good)
    del bad["config"]["marker_equivalence"]
    assert not rt._valid_cohort(bad)          # equivalent fields without a marker
    bad = copy.deepcopy(good)
    bad["targets"][0]["equivalent_sources"] = ["Anything."]
    assert not rt._valid_cohort(bad)
    bad = copy.deepcopy(good)
    bad["targets"][0]["matched_via_marker_equivalence"] = False
    assert not rt._valid_cohort(bad)


# ---- re-score provenance -------------------------------------------------------------

def test_snapshot_rule_and_hash_recorded():
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    assert snap["version"] == 1 and len(snap["snapshots"]) == 6
    assert snap["snapshots"][-1] == "2e5312adc25c445685994aa03211804bd1d7ef4a"
    la = snap["forms"]["la:inter alia"]
    assert la["measured_sources"] == ["among other things"]
    assert la["accepted_sources"] == ["among other things", "among others"]
    assert not any(k.startswith("pt:") for k in snap["forms"])   # pt keeps pt_sources.json (#171)


@pytest.mark.parametrize("lang,form", RESCUED_ALT + QUE_FORMS)
def test_rescued_forms_pass_on_replayed_answers(lang, form):
    rec = DATA["records"][rt.key(lang, form)]
    new, old = rec["cohorts"][-1], rec["cohorts"][-2]
    assert rt.status(DATA, lang, form) == "pass"
    assert new["restored"] == new["completed"] == 9
    assert old["restored"] == 0                      # the original cohort stays in history
    assert [t["target_id"] for t in new["targets"]] == [t["target_id"] for t in old["targets"]]
    judge = json.loads((FIX / f"roundtrip_judge/{lang}_blind.json").read_text(encoding="utf-8"))
    assert all(t["response"] == judge[t["converted"]] for t in new["targets"])   # recorded answers, no new judging
    assert [t["first_source_match"] for t in new["targets"]] == [t["restored"] for t in old["targets"]]
    assert new["config"]["normalization"] == "norm-nfc-v1"
    assert new["config"]["marker_equivalence"] == rt.MARKER_EQUIVALENCE
    assert new["config"]["command_sha256"] == old["config"]["command_sha256"]
    assert new["judge_provenance"]["rescore"]["of_run_id"] == old["run_id"]
    via_marker = all(t["matched_via_marker_equivalence"] for t in new["targets"])
    assert via_marker == ((lang, form) in QUE_FORMS)
    assert (lang, form) not in tm.ROUNDTRIP_REVERSED


@pytest.mark.parametrize("lang,form", STILL_REVERSED)
def test_suspected_over_reversals_stay_reversed(lang, form):
    assert rt.status(DATA, lang, form) == "never"
    assert (lang, form) in tm.ROUNDTRIP_REVERSED


def test_la_records_marked_unmeasured_not_invented():
    bank = json.loads((FIX / "pt_el_latin_phrases.json").read_text(encoding="utf-8"))
    nr = {e["id"]: e for e in bank["examples_not_registered"]}
    for eid in ("among-others-inter-alia", "day-by-day-la-quotidie"):
        assert nr[eid]["roundtrip_status"] == "untested"
        assert nr[eid]["roundtrip_note"]
    assert rt.key("la", "quotidie") not in DATA["records"]
    assert not any(e["id"] in nr for e in bank["entries"])


def test_enforced_langs_unchanged():
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
