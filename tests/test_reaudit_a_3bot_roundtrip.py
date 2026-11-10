"""3bot reaudit (class a): 13 reversed forms re-measured in designed contexts, one
independent judge call per sentence (docs/reaudit_a_3bot_roundtrip_20261110.md)."""
from __future__ import annotations

import copy
import hashlib
import json
import runpy
import shlex
import shutil
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reaudit_a_3bot_roundtrip as ra  # noqa: E402
import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

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
