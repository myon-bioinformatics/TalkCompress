"""es tomaré / pt acharei, logo, por isso: the adopted forms #161/#164 promoted without a
round-trip record, measured by an independent blind judge (docs/es_pt_remaining_roundtrip_20261110.md)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import remaining_roundtrip_20261110 as rem  # noqa: E402
import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
JUDGE_PATH = FIX / "roundtrip_judge/remaining_20261110_blind.json"
JUDGE = json.loads(JUDGE_PATH.read_text(encoding="utf-8"))
SNAPSHOT = json.loads((FIX / "roundtrip_judge/remaining_20261110_sources.json").read_text(encoding="utf-8"))
DATA = rt.load()
EXPECTED = {"es:tomaré": (0, "never"), "pt:acharei": (0, "never"), "pt:logo": (0, "never"), "pt:por isso": (0, "never")}
REVERSED_IDS = {
    "es_fr_tense": {"take-fut-1s": "tomaré", "take-fut-goingto-1s": "tomaré",
                    "find-fut-1s": "acharei", "find-fut-goingto-1s": "acharei"},
    "pt_el_latin_phrases": {"as-a-result-la-pt-el": "logo", "for-this-reason-la-pt": "por isso"},
}


def read(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def test_judge_frozen_and_covers_exactly_the_converted_sentences():
    assert hashlib.sha256(JUDGE_PATH.read_bytes()).hexdigest() == rem.JUDGE_SHA256
    converted = [cv for f in SNAPSHOT["forms"] for _, cv in rt.sentences(DATA, f["entry"]["from"][0], f["entry"]["to"])]
    assert list(JUDGE) == converted and len(converted) == 12
    assert hashlib.sha256(("\n".join(converted) + "\n").encode()).hexdigest() == rem.CONVERTED_SHA256


@pytest.mark.parametrize("k", EXPECTED)
def test_cohort_is_run_counted_and_replays_the_judge(k):
    lang, form = k.split(":", 1)
    rec = DATA["records"][k]
    c = rt.latest_cohort(rec)
    assert c["complete"] and c["completed"] == c["attempted"] == DATA["min_trials"] == 9
    assert c["config"]["seeds"] == [1, 2, 3] and c["config"]["templates"] == DATA["templates"]
    assert c["config"]["normalization"] == "norm-nfc-v1"
    assert c["judge_provenance"]["kind"] == "independent_blind_judge"
    assert c["judge_provenance"]["judge_sha256"] == rem.JUDGE_SHA256
    src = next(f for f in SNAPSHOT["forms"] if f["key"] == k)
    for t in c["targets"]:
        assert t["response"] == JUDGE[t["converted"]]
        restored = any(rt.norm(t["response"]) == rt.norm(s) for s in t["accepted_sources"])
        assert t["restored"] is restored
        assert len(t["accepted_sources"]) == len(src["accepted_sources"])
    assert (c["restored"], rt.status(DATA, lang, form)) == EXPECTED[k]


def test_failed_forms_reversed_without_promotion():
    for name, ids in REVERSED_IDS.items():
        bank = read(name)
        assert not any(e["id"] in ids for e in bank["entries"])
        nr = {e["id"]: e for e in bank["examples_not_registered"] if e.get("roundtrip_reversed") and e["id"] in ids}
        assert set(nr) == set(ids)
        for eid, form in ids.items():
            assert nr[eid]["to"] == form and "0/9" in nr[eid]["why_dropped"]
            assert "actual restorations" in nr[eid]["why_dropped"]


def test_reversed_sources_stay_reserved_and_enforced_langs_unchanged():
    from tests._helpers import load
    talk = load("rt4_source_guard", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    reserved = tm._existing_sources(talk)
    for e in read("es_fr_tense")["examples_not_registered"]:
        if e["id"] in REVERSED_IDS["es_fr_tense"]:
            assert all(s.lower() in reserved for s in e["from"])
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})


@pytest.mark.parametrize("raw", ["as a result", "for this reason"])
def test_reversed_phrases_stay_english_at_runtime(raw):
    from tests._helpers import load
    talk = load("rt4_phrase_guard", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    assert talk.apply_zh_de_phrases(raw) == raw
