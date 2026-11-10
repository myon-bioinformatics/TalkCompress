"""Frozen independent pt judge, any-source evidence, and narrowly scoped reversals."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import roundtrip as rt
import tense_matrix as tm

FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
JUDGE = FIX / "roundtrip_judge/pt_blind.json"
SNAPSHOT = json.loads((FIX / "roundtrip_judge/pt_sources.json").read_text(encoding="utf-8"))
SOURCES = SNAPSHOT["forms"]
JUDGE_SHA = "d161afaef0b6f8dea08c5ff5babb69f349a7baea60f697ddaf5e85b36dd369df"
BASE_OTHER_LANG_HASHES = {
    "tense_matrix": "78992b4cc8accacf30e7e3e3e3475789d0ceaed99ac6257f062811098a466b4d",  # after #172 (es reversals)
    "es_fr_tense": "5c4d9e525a8df17eef85c4128698ccd65c5d4f4a4d10610a0d8fc0ef97c4a045",  # after #164 (el reversals) + #161 (la entries / el υπέρ reversal)
    "pt_el_latin_phrases": "869f7e00ff4b11e188588ec4bf3c61f81609213c0fdde45e980a935c692e8a7b",  # after #164 (el reversals) + #161 (la entries / el υπέρ reversal)
    "pt_el_latin_tense": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
}


def read(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def test_judge_is_unchanged_and_covers_official_converted_sentences():
    assert hashlib.sha256(JUDGE.read_bytes()).hexdigest() == JUDGE_SHA
    judge = json.loads(JUDGE.read_text(encoding="utf-8"))
    data = rt.load()
    converted = {cv for f in SOURCES for _, cv in rt.sentences(data, f["entry"]["from"][0], f["entry"]["to"])}
    assert len(SOURCES) == 270 and len(converted) == len(judge) == 810
    assert set(judge) == converted
    assert sum(len(f["source_entries"]) for f in SOURCES) == 404
    assert sum(len(f["accepted_sources"]) > 1 for f in SOURCES) == 65
    assert sum(len(f["source_entries"]) > 1 for f in SOURCES) == 63


def test_each_receipt_recomputes_from_immutable_judge_without_inflated_trials():
    data = rt.load()
    judge = json.loads(JUDGE.read_text(encoding="utf-8"))
    statuses = []
    for f in SOURCES:
        rec = data["records"][f["key"]]
        cohort = rt.latest_cohort(rec)
        assert cohort is not None and cohort["complete"]
        assert cohort["completed"] == cohort["attempted"] == 9
        assert rec["trials"] == sum(c["completed"] for c in rec["cohorts"])
        assert len(cohort["targets"]) == 9
        assert cohort["config"]["source_acceptance"] == "any-official-source-v1"
        assert cohort["judge_provenance"]["judge_sha256"] == JUDGE_SHA
        for target in cohort["targets"]:
            assert target["response"] == judge[target["converted"]]
            expected = []
            for source in f["accepted_sources"]:
                expected += [en for en, cv in rt.sentences(data, source, f["entry"]["to"]) if cv == target["converted"]]
            assert set(target["accepted_sources"]) == set(expected)
            restored = any(rt.norm(target["response"]) == rt.norm(en) for en in expected)
            assert target["restored"] is restored
        statuses.append(rt.status(data, "pt", f["entry"]["to"]))
    assert statuses.count("pass") == 210 and statuses.count("never") == 60
    # other language cohorts (it / zh from #168 / #169, ...) share run_history
    latest = [r for r in data["run_history"] if r["config"].get("only_lang") == "pt"][-1]
    assert latest["completed"] == latest["attempted"] == latest["scheduled"] == 2430
    assert latest["duplicate_targets"] == 0


@pytest.mark.parametrize("name", BASE_OTHER_LANG_HASHES)
def test_existing_other_language_winners_and_losing_pt_candidates_unchanged(name):
    # es/fr/de have their own independently verified reversals (#172–174).
    # Preserve every other language and its candidates from main after #168/#169.
    entries = [e for e in read(name)["entries"] if e["lang"] not in {"pt", "es", "fr", "de"}]
    canonical = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode()
    assert hashlib.sha256(canonical).hexdigest() == BASE_OTHER_LANG_HASHES[name]


@pytest.mark.parametrize("name", BASE_OTHER_LANG_HASHES)
def test_only_failed_pt_entries_removed_no_unmeasured_promotions(name):
    data = rt.load()
    expected = {
        e["id"]: f["entry"]["to"] for f in SOURCES for e in f["source_entries"]
        if e["file"] == f"SentenceCalibratedMosaic/fixtures/{name}.json" and rt.status(data, "pt", f["entry"]["to"]) == "pass"
    }
    got = {e["id"]: e["to"] for e in read(name)["entries"] if e["lang"] == "pt"}
    # #161 (la reversal of ergo / ideo) and #164 (el βρω reversal) promoted pt runner-ups
    # before the pt round-trip (#171) existed; they are NOT in the pt blind judge. Measured
    # separately on 2026-11-10: acharei passed in designed contexts (kept), logo / por isso
    # failed (reversed). Listed explicitly so no other unmeasured pt promotion slips in.
    measured_later = {"es_fr_tense": {"find-fut-1s": "acharei", "find-fut-goingto-1s": "acharei"}}
    for k, v in measured_later.get(name, {}).items():
        assert got.pop(k) == v and rt.status(data, "pt", v) == "pass"
    assert got == expected


def test_generated_reversals_are_per_form_and_leave_empty_english_cells():
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    data = rt.load()
    failed = {
        ("pt", f["entry"]["to"]) for f in SOURCES
        if any(e["file"].endswith("/tense_matrix.json") for e in f["source_entries"])
        and rt.status(data, "pt", f["entry"]["to"]) != "pass"
    }
    # ROUNDTRIP_REVERSED is a union across languages (it from #168, ...); pt part only here.
    assert {r for r in tm.ROUNDTRIP_REVERSED if r[0] == "pt"} == failed
    cells = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]
    pt_rev = {f for _, f in failed}
    reversed_cells = [c for c in cells if set(c.get("roundtrip_reversed") or ()) & pt_rev]
    assert len(reversed_cells) == 63
    assert all(c["status"] == "reject" and c["candidates"] == [] for c in reversed_cells)


# pt_el_latin_phrases 4 → 6: logo / por isso reversed on 2026-11-10 (0/9 bare and in context).
@pytest.mark.parametrize("name,removed", [("es_fr_tense", 3), ("pt_el_latin_phrases", 6), ("pt_el_latin_tense", 1)])
def test_quarantined_failure_evidence_and_sources_reserved(name, removed):
    data = read(name)
    reversed_entries = [e for e in data["examples_not_registered"] if e.get("roundtrip_reversed")]
    assert len(reversed_entries) == removed
    assert all(e["lang"] == "pt" and "0/9" in e["why_dropped"] and "actual restorations" in e["why_dropped"] for e in reversed_entries)
    if name != "pt_el_latin_phrases":
        from tests._helpers import load
        talk = load("pt_source_guard", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
        reserved = tm._existing_sources(talk)
        assert all(s.lower() in reserved for e in reversed_entries for s in e["from"])


def test_alt_only_passes_are_transparently_documented():
    data = rt.load()
    alternate = []
    strict = total = 0
    for f in SOURCES:
        c = data["records"][f["key"]]["cohorts"][-1]
        first = sum(t["first_source_match"] for t in c["targets"])
        strict += first
        total += c["restored"]
        if c["restored"] >= 6 and first < 6:
            alternate.append(f["entry"]["to"])
    assert len(alternate) == 21 and strict == 1701 and total == 1890
    results = (FIX / "roundtrip_judge/pt_results.md").read_text(encoding="utf-8")
    assert all(f"`{form}`" in results for form in alternate)


def test_any_source_run_keeps_first_source_identity_and_judge_response(monkeypatch):
    data = {"templates": ["{s}."], "seeds": [1, 2, 3], "min_trials": 3,
            "thresholds": {"lt100m": 0.9, "ge100m": 0.6}, "ge100m_langs": ["pt"], "records": {}}
    entry = {"lang": "pt", "from": ["he had seen"], "to": "vira"}
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="She had seen.\n", returncode=0))
    rt.run(data, "fake", entries=[entry], accepted_sources={"pt:vira": ["he had seen", "she had seen"]})
    c = rt.latest_cohort(data["records"]["pt:vira"])
    assert c["completed"] == c["restored"] == 3
    assert all(t["source"] == "He had seen." and t["response"] == "She had seen." and t["matched_via_alternate"] for t in c["targets"])
    forged = copy.deepcopy(c)
    forged["targets"][0]["response"] = "She saw."
    assert not rt._valid_cohort(forged)
    default = {**data, "records": {}, "run_history": []}
    rt.run(default, "fake", entries=[entry])
    assert default["records"]["pt:vira"]["restored"] == 0


@pytest.mark.parametrize("invalid", [{"pt:x": []}, {"pt:x": "not a list"}, {"pt:x": [None]}])
def test_invalid_alternate_sources_do_not_execute_or_mutate(monkeypatch, invalid):
    data = {"templates": ["{s}."], "seeds": [1], "records": {}}
    before = copy.deepcopy(data)
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **kw: pytest.fail("must not execute"))
    with pytest.raises(ValueError, match="accepted_sources"):
        rt.run(data, "fake", entries=[], accepted_sources=invalid)
    assert data == before


def test_evidence_is_loaded_once_per_build_cache(monkeypatch):
    data = rt.load()
    calls = []
    monkeypatch.setattr(rt, "load", lambda: calls.append(1) or data)
    monkeypatch.setattr(tm, "_RT_DATA", {})
    tm._rt_status("denkt", "nl")
    tm._rt_status("denkt", "nl")
    tm._rt_ok("denkt", "nl")
    assert len(calls) == 1


@pytest.mark.parametrize("remove_hash", [False, True])
@pytest.mark.parametrize("tamper_response", [False, True])
def test_any_source_receipt_cannot_downgrade_to_single_source(remove_hash, tamper_response):
    cohort = copy.deepcopy(rt.load()["records"][SOURCES[0]["key"]]["cohorts"][-1])
    assert rt._valid_cohort(cohort)
    if tamper_response:
        cohort["targets"][0]["response"] = "Unrelated synthetic tampering probe."
    del cohort["config"]["source_acceptance"]
    if remove_hash:
        del cohort["config"]["accepted_sources_sha256"]
    assert not rt._valid_cohort(cohort)


@pytest.mark.parametrize("field", ["accepted_sources", "first_source_match", "matched_source", "matched_via_alternate"])
def test_single_source_receipt_rejects_any_source_fields(monkeypatch, field):
    data = {"templates": ["{s}."], "seeds": [1], "min_trials": 1,
            "thresholds": {"lt100m": 0.9, "ge100m": 0.6}, "ge100m_langs": ["pt"], "records": {}}
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="He had seen.", returncode=0))
    rt.run(data, "fake", entries=[{"lang": "pt", "from": ["he had seen"], "to": "vira"}])
    cohort = rt.latest_cohort(data["records"]["pt:vira"])
    assert rt._valid_cohort(cohort)
    cohort["targets"][0][field] = None
    assert not rt._valid_cohort(cohort)


def test_single_source_receipt_rejects_orphan_hash(monkeypatch):
    data = {"templates": ["{s}."], "seeds": [1], "min_trials": 1,
            "thresholds": {"lt100m": 0.9, "ge100m": 0.6}, "ge100m_langs": ["pt"], "records": {}}
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="He had seen.", returncode=0))
    rt.run(data, "fake", entries=[{"lang": "pt", "from": ["he had seen"], "to": "vira"}])
    cohort = rt.latest_cohort(data["records"]["pt:vira"])
    assert rt._valid_cohort(cohort)
    cohort["config"]["accepted_sources_sha256"] = "0" * 64
    assert not rt._valid_cohort(cohort)
