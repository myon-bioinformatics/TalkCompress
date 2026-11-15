"""往復の再監査と再採点（3bot class a、4bot class b、2026-11-10 再採点）。

- reaudit_a_3bot_roundtrip: 3bot reaudit (class a): 13 reversed forms re-measured in designed contexts, one
- reaudit_b_4bot_context_roundtrip_gate: Re-audit context round-trip (class b + bonus; 30 forms x 9 sentences) by GitHubヘルプ4bot.
- roundtrip_rescore_20261110: Accepted-sources re-score + owner-approved leading que≡that (docs/roundtrip_rescore_20261110.md).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import copy
import hashlib
import json
import reaudit_a_3bot_roundtrip as ra
import reaudit_b_4bot_roundtrip as rb
import roundtrip as rt
import runpy
import shlex
import shutil
import sys
import tense_matrix as tm

import pytest


# ──── reaudit_a_3bot_roundtrip ────────────────────────────────────

"""3bot reaudit (class a): 13 reversed forms re-measured in designed contexts, one
independent judge call per sentence (docs/reaudit_a_3bot_roundtrip_20261110.md)."""


ROOT = Path(__file__).resolve().parents[1]


FIX = ROOT / "SentenceCalibratedMosaic/fixtures"


RJ = FIX / "roundtrip_judge"


JUDGE, SRC, MEANING = ra.inputs()


RESULTS = json.loads(ra.RESULTS.read_text(encoding="utf-8"))["results"]


FAST_CMD = f"{shlex.quote(sys.executable)} {shlex.quote(str(ROOT / 'scripts/roundtrip_replay.py'))} {ra.NAME}"


# key -> (exact /9, meaning same /9 (reference), status)
EXPECTED = {
    "fr:vis": (8, 9, "pass"), "fr:vins": (7, 9, "pass"), "fr:sus": (6, 6, "pass"),
    "fr:voulus": (9, 9, "pass"), "fr:prends": (6, 6, "pass"), "fr:avais su": (9, 9, "pass"),
    "fr:ira": (9, 9, "pass"), "fr:arrivé": (6, 9, "pass"), "pt:virá": (9, 9, "pass"),
    "pt:essayé": (6, 7, "pass"), "pt:farei": (4, 8, "fail"), "es:pensamos": (9, 9, "pass"),
    "zh:几点": (4, 9, "fail"),
}


RESTORED = {("fr", f) for f in ("vis", "vins", "sus", "voulus", "prends", "avais su", "ira", "arrivé", "essayé")} | {("pt", "virá")}


def read(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def test_frozen_inputs_cover_117_designed_sentences_once():
    assert list(SRC["forms"]) == ra.KEYS and len(SRC["sentences"]) == len(JUDGE) == 117
    assert set(JUDGE) == {s["converted"] for s in SRC["sentences"]} == set(MEANING["by_converted"])
    assert MEANING["gating"] is False and "NOT independent" in MEANING["judge"]
    assert SRC["official_templates"] == rt.load()["templates"]
    assert SRC["prompt_sha256"] == hashlib.sha256(rt.PROMPT.encode("utf-8")).hexdigest()
    raw = (RJ / f"{ra.NAME}_raw_answers.txt").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SRC["raw_answers_sha256"]
    # every verbatim reply is used by exactly one sentence (content-matched bijection)
    assert Counter(raw.decode("utf-8").splitlines()) == Counter(JUDGE.values())
    assert sorted(s["request_id"] for s in SRC["sentences"]) == [f"s{i:03d}" for i in range(1, 118)]


@pytest.mark.parametrize("key", ra.KEYS)
def test_form_spec_is_three_contexts_times_official_templates(key):
    spec = SRC["forms"][key]
    rows = [s for s in SRC["sentences"] if s["key"] == key]
    assert len(spec["templates"]) == len(rows) == 9 and len(spec["contexts"]) == 3
    assert spec["adopted_source"] == spec["accepted_sources"][0]
    for s in rows:
        assert s["converted"] in JUDGE
        # the judge never sees the adopted English phrase
        assert spec["adopted_source"].lower() not in s["converted"].lower()


def test_replay_reproduces_committed_results():
    got = ra.measure(rt.load(), FAST_CMD)
    assert got["results"] == RESULTS
    assert got["thresholds"] == {"lt100m": 0.9, "ge100m": 0.6} and got["min_trials"] == 9


@pytest.mark.parametrize("key", ra.KEYS)
def test_per_form_exact_meaning_and_status(key):
    exact, meaning, status = EXPECTED[key]
    r = RESULTS[key]
    assert (r["exact"], r["meaning_same"], r["status"]) == (exact, meaning, status)
    assert r["sentences"] == 9 and r["completed"] == 27 and r["restored"] == 3 * exact and r["complete"]
    assert r["gate_visible"] is False
    for cv, t in r["targets"].items():
        assert t["response"] == JUDGE[cv]
        assert t["restored"] is (t["matched_source"] is not None)
        assert t["meaning_match_ref"] == MEANING["by_converted"][cv]["meaning_match_ref"]


def test_restored_set_and_custom_results():
    assert ra.restored() == RESTORED
    assert ra.restored({"es:pensamos": {"status": "pass"}, "pt:farei": {"status": "fail"}, "x:y": {"status": "pass"}}) == set()
    assert ra.restored({"pt:essayé": {"status": "pass"}}) == {("fr", "essayé")}


def test_bank_data_follows_the_results():
    entries = {(e["lang"], e["to"]) for name in ("tense_matrix", "es_fr_tense") for e in read(name)["entries"]}
    assert RESTORED <= entries
    assert not RESTORED & tm.ROUNDTRIP_REVERSED
    essaye = next(e for e in read("es_fr_tense")["entries"] if e["id"] == "try-past-1s")
    assert (essaye["to"], essaye["lang"]) == ("essayé", "fr")
    assert {"lang": "fr", "form": "essayé"} in essaye["candidates"]
    # failures keep their reversal; es pensamos is reported only (SOURCES side is 2bot's)
    nr = {e["id"]: e for name in ("pt_el_latin_tense", "zh_de_phrases") for e in read(name)["examples_not_registered"]}
    assert nr["do-it-fut-1s"]["to"] == "farei" and nr["time-zh"]["to"] == "几点"
    assert ("es", "pensamos") in tm.ROUNDTRIP_REVERSED and "we thought" in tm.ROUNDTRIP_REVERSED_SOURCES
    assert ("fr", "this ira") in entries and tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})


@pytest.mark.parametrize("raw,out", [("you saw", "vis"), ("you came", "vins"), ("you knew", "sus"),
                                     ("you wanted", "voulus"), ("you take", "prends"), ("you had known", "avais su"),
                                     ("it will go", "ira"), ("this will go", "this ira"), ("I arrived", "arrivé"),
                                     ("it will come", "virá"), ("I tried", "essayé"), ("we thought", "we thought")])
def test_runtime_conversion(raw, out):
    from tests._helpers import load
    talk = load("reaudit_a_runtime", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    assert talk.apply_es_fr_tense(raw) == out


def test_hash_guard(monkeypatch):
    monkeypatch.setitem(ra.SHA256, "blind", "0" * 64)
    with pytest.raises(ValueError, match="hash mismatch"):
        ra.inputs()


def _drop_one(obj):
    obj.popitem()


@pytest.mark.parametrize("part,corrupt", [
    ("blind", _drop_one),
    ("meaning", lambda m: _drop_one(m["by_converted"])),
    ("sources", lambda s: s.update(forms=dict(reversed(list(s["forms"].items()))))),
])
def test_coverage_guards(monkeypatch, tmp_path, part, corrupt):
    for name in ("blind", "sources", "meaning"):
        shutil.copy(RJ / f"{ra.NAME}_{name}.json", tmp_path)
    path = tmp_path / f"{ra.NAME}_{part}.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    corrupt(obj)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ra, "FIX", tmp_path)
    monkeypatch.setitem(ra.SHA256, part, hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError, match="same designed sentences"):
        ra.inputs()


def test_unexpected_configuration_is_refused():
    data = rt.load()
    bad = copy.deepcopy(data)
    bad["seeds"] = [1]
    with pytest.raises(ValueError, match="configuration"):
        ra.measure(bad, FAST_CMD)


def test_main_write_and_check(monkeypatch, tmp_path, capsys):
    out = tmp_path / "results.json"
    monkeypatch.setattr(ra, "RESULTS", out)
    assert ra.main(["--write"], FAST_CMD) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["results"] == RESULTS
    assert ra.main(["--check"], FAST_CMD) == 0 and "up to date" in capsys.readouterr().err
    out.write_text("{}\n", encoding="utf-8")
    assert ra.main(["--check"], FAST_CMD) == 1 and "drifted" in capsys.readouterr().err


def test_script_entry_point_checks_committed_results(monkeypatch):
    monkeypatch.setattr(sys, "argv", [str(ROOT / "scripts/reaudit_a_3bot_roundtrip.py"), "--check"])
    monkeypatch.chdir(ROOT)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / "scripts/reaudit_a_3bot_roundtrip.py"), run_name="__main__")
    assert exc.value.code == 0


# ──── reaudit_b_4bot_context_roundtrip_gate ───────────────────────

"""Re-audit context round-trip (class b + bonus; 30 forms x 9 sentences) by GitHubヘルプ4bot.

docs/reaudit_b_4bot_context_roundtrip_20261110.md. Gate = exact match (norm-nfc-v1);
meaning match is reference only. roundtrip.json is not modified by this study.
"""


def j(path):
    return json.loads(path.read_text(encoding="utf-8"))


SRC_reaudit_b_4bot_context_roundtrip_gate = j(RJ / "reaudit_b_4bot_sources.json")


BLIND = j(RJ / "reaudit_b_4bot_blind.json")


RAW = j(RJ / "reaudit_b_4bot_raw.json")


MEANING_reaudit_b_4bot_context_roundtrip_gate = j(RJ / "reaudit_b_4bot_meaning.json")


RES = j(RJ / "reaudit_b_4bot_results.json")


DATA = rt.load()


# key -> (exact /9, meaning ref /9, status)
EXPECTED_reaudit_b_4bot_context_roundtrip_gate = {
    "de:Tankstelle": (0, 9, "never"), "de:Parkplatz": (0, 9, "never"), "de:wenn": (0, 7, "never"),
    "la:interim": (3, 9, "fail"), "la:per capita": (0, 9, "never"), "la:a fortiori": (2, 9, "fail"),
    "la:in memoriam": (8, 9, "fail"), "la:seriatim": (1, 9, "fail"), "la:sua sponte": (0, 9, "never"),
    "la:iterum": (0, 9, "never"), "la:ergo": (0, 9, "never"), "la:circa": (0, 9, "never"),
    "la:coram": (0, 9, "never"), "la:cotidie": (0, 8, "never"), "la:quotidie": (0, 8, "never"),
    "la:inter alia": (2, 9, "fail"), "la:ideo": (0, 9, "never"), "la:pro": (0, 9, "never"),
    "la:re": (0, 9, "never"), "el:πάλι": (0, 9, "never"), "el:υπέρ": (3, 9, "fail"),
    "pt:cel": (0, 9, "never"), "es:pude": (9, 9, "pass"), "zh:明白": (6, 6, "pass"),
    "zh:界面": (0, 9, "never"), "zh:电话": (7, 9, "pass"), "pt:tensão": (8, 9, "pass"),
    "zh:餐厅": (6, 6, "pass"), "zh:心脏病": (9, 9, "pass"), "zh:邮箱": (0, 9, "never"),
}


BANK = {"es": "es_fr_tense", "zh": "zh_de_phrases", "de": "zh_de_phrases",
        "pt": "pt_el_latin_phrases", "el": "pt_el_latin_phrases", "la": "pt_el_latin_phrases"}


def test_fixtures_frozen():
    for name, sha in rb.SHA256.items():
        assert hashlib.sha256((RJ / f"reaudit_b_4bot_{name}.json").read_bytes()).hexdigest() == sha


def test_judge_covers_exactly_the_designed_sentences():
    conv = [s["converted"] for s in SRC_reaudit_b_4bot_context_roundtrip_gate["sentences"]]
    assert len(conv) == len(set(conv)) == 270 and set(BLIND) == set(conv)
    assert list(SRC_reaudit_b_4bot_context_roundtrip_gate["forms"]) == list(EXPECTED_reaudit_b_4bot_context_roundtrip_gate)
    assert SRC_reaudit_b_4bot_context_roundtrip_gate["official_templates"] == DATA["templates"]
    for key, spec in SRC_reaudit_b_4bot_context_roundtrip_gate["forms"].items():
        mine = [s for s in SRC_reaudit_b_4bot_context_roundtrip_gate["sentences"] if s["key"] == key]
        assert len(mine) == 9 and len(spec["templates"]) == 9
        probe = {**DATA, "templates": spec["templates"]}
        assert [cv for _, cv in rt.sentences(probe, spec["adopted_source"], spec["form"])] == \
            [s["converted"] for s in sorted(mine, key=lambda s: (s["context_id"], s["template_id"]))]


def test_request_never_shows_the_adopted_english():
    for s in SRC_reaudit_b_4bot_context_roundtrip_gate["sentences"]:
        assert s["adopted_source"].lower() not in s["converted"].lower()


def test_raw_answers_are_verbatim_with_sha256():
    assert set(RAW["by_id"]) == {s["id"] for s in SRC_reaudit_b_4bot_context_roundtrip_gate["sentences"]}
    for s in SRC_reaudit_b_4bot_context_roundtrip_gate["sentences"]:
        r = RAW["by_id"][s["id"]]
        assert hashlib.sha256(r["raw"].encode("utf-8")).hexdigest() == r["raw_sha256"]
        assert r["converted"] == s["converted"] and BLIND[s["converted"]] == r["raw"].strip()


def test_meaning_is_reference_only_and_complete():
    assert MEANING_reaudit_b_4bot_context_roundtrip_gate["gating"] is False and set(MEANING_reaudit_b_4bot_context_roundtrip_gate["by_converted"]) == set(BLIND)
    assert {v["meaning_match_ref"] for v in MEANING_reaudit_b_4bot_context_roundtrip_gate["by_converted"].values()} <= {"same", "different"}
    assert sum(v["meaning_match_ref"] == "same" for v in MEANING_reaudit_b_4bot_context_roundtrip_gate["by_converted"].values()) == 260


@pytest.mark.parametrize("key", EXPECTED_reaudit_b_4bot_context_roundtrip_gate)
def test_per_form_exact_meaning_and_gate(key):
    exact, meaning, status = EXPECTED_reaudit_b_4bot_context_roundtrip_gate[key]
    items = [i for i in RES["items"] if i["key"] == key]
    assert len(items) == 9
    assert sum(rt.norm(BLIND[i["converted"]]) == rt.norm(i["expected"]) for i in items) == exact
    assert sum(i["meaning_match_ref"] == "same" for i in items) == meaning
    f = RES["forms"][key]
    assert (f["exact"], f["meaning_ref"], f["status"]) == (exact, meaning, status)
    assert f["exact_targets"] == f"{exact * 3}/27"
    assert f["reversal_undone"] == (status == "pass") == (key in rb.UNDONE)


def test_lt100m_forms_adopt_only_on_ai_roundtrip_success():
    for key, f in RES["forms"].items():
        if f["band"] == "lt100m":
            assert f["status"] != "pass" and f["threshold"] == 0.9


@pytest.mark.parametrize("key", EXPECTED_reaudit_b_4bot_context_roundtrip_gate)
def test_bank_matches_gate(key):
    lang, form = key.split(":", 1)
    bank = j(FIX / f"{BANK[lang]}.json")
    live = [e for e in bank["entries"] if e["lang"] == lang and e["to"] == form]
    if key in rb.UNDONE:
        assert len(live) == 1 and "why_dropped" not in live[0] and "roundtrip_reversed" not in live[0]
        assert not [e for e in bank["examples_not_registered"] if e["id"] == live[0]["id"]]
    elif key == "la:inter alia":
        # This context study (among others, 2/9) is gate-invisible. The bank entry for among others
        # was restored on main by the owner-approved form-level re-score (#182: the inter alia
        # record passes 9/9 and among others is one of its official sources), so both sources are live.
        assert sorted(e["from"] for e in live) == [["among other things"], ["among others"]]
        assert rt.status(DATA, "la", "inter alia") == "pass"
        assert not [e for e in bank["examples_not_registered"] if e.get("to") == form and e["from"] == ["among others"]]
    else:
        assert not live
        assert [e for e in bank["examples_not_registered"] if e.get("lang") == lang and e.get("to") == form]


def test_failures_recorded_as_hidden_context_studies():
    studies = RES["context_studies"]["reaudit_b_4bot"]
    assert set(studies) == set(EXPECTED_reaudit_b_4bot_context_roundtrip_gate) - set(rb.UNDONE) and len(studies) == 24
    for key, s in studies.items():
        assert s["gate_visible"] is False and s["cohort"]["complete"] and s["cohort"]["completed"] == 27
        assert s["cohort"]["restored"] == EXPECTED_reaudit_b_4bot_context_roundtrip_gate[key][0] * 3
    assert "separate_from_record" in studies["la:inter alia"]
    assert set(RES["passed_cohorts"]) == set(rb.UNDONE)


def test_roundtrip_json_untouched_by_this_study():
    assert "reaudit_b_4bot" not in DATA.get("context_studies", {})
    for key in rb.UNDONE:
        lang, form = key.split(":", 1)
        assert rt.status(DATA, lang, form) == "never"  # bare cohort kept; evidence is in roundtrip_judge


# ──── roundtrip_rescore_20261110 ──────────────────────────────────

"""Accepted-sources re-score + owner-approved leading que≡that (docs/roundtrip_rescore_20261110.md)."""


SNAP = FIX / "roundtrip_judge/accepted_sources_v1.json"


TEMPLATES = ["{s}.", "Maybe {s} today.", "She told me that {s}."]


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


def test_la_quotidie_marked_unmeasured_not_invented():
    bank = json.loads((FIX / "pt_el_latin_phrases.json").read_text(encoding="utf-8"))
    nr = {e["id"]: e for e in bank["examples_not_registered"]}
    assert nr["day-by-day-la-quotidie"]["roundtrip_status"] == "untested"
    assert nr["day-by-day-la-quotidie"]["roundtrip_note"]
    assert rt.key("la", "quotidie") not in DATA["records"]
    assert not any(e["id"] in nr for e in bank["entries"])


def test_la_inter_alia_among_others_restored_by_form_level_rule():
    """Owner-approved: inter alia passed 9/9 and 'among others' is an official source of that form."""
    bank = json.loads((FIX / "pt_el_latin_phrases.json").read_text(encoding="utf-8"))
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    assert "among others" in snap["forms"]["la:inter alia"]["accepted_sources"]
    assert rt.status(DATA, "la", "inter alia") == "pass"
    live = {e["id"]: e for e in bank["entries"]}
    assert (live["among-others-la"]["from"], live["among-others-la"]["to"]) == (["among others"], "inter alia")
    assert not any(e["id"] == "among-others-inter-alia" for e in bank["examples_not_registered"])


def test_enforced_langs_unchanged():
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
