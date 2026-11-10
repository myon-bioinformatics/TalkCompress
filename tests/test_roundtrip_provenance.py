"""Round-trip run provenance: origin/main SHA and timestamp on every new run (no backfill)."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mapping_graph as mg  # noqa: E402
import roundtrip as rt  # noqa: E402

SHA = "0123456789abcdef0123456789abcdef01234567"
TS = "2026-11-10T09:55:00+00:00"
PROV = {"origin_main_sha": SHA, "timestamp": TS}
ENTRY = [{"lang": "nl", "from": ["I have eaten"], "to": "ik at"}]
DOC = ROOT / "docs/ontology/tense-merge-collisions.md"


def data() -> dict:
    return {"templates": ["{s}.", "Maybe {s} today."], "seeds": [1, 2], "records": {}, "min_trials": 2,
            "thresholds": {"lt100m": .9, "ge100m": .9}, "ge100m_langs": ["en"]}


@pytest.fixture
def restorer(monkeypatch):
    def call(cmd, **kw):
        source = kw["input"].rsplit("\n", 1)[-1].replace("Ik at", "I have eaten").replace("ik at", "I have eaten")
        return subprocess.CompletedProcess(cmd, 0, source, "")
    monkeypatch.setattr(rt.subprocess, "run", call)


def test_injected_provenance_on_invocation_and_every_cohort(restorer):
    d = data()
    prov = copy.deepcopy(PROV)
    rt.run(d, "fake", entries=ENTRY + [{"lang": "nl", "from": ["I have seen"], "to": "ik zag"}], provenance=prov)
    assert d["run_history"][-1]["provenance"] == PROV
    for k in ("nl:ik at", "nl:ik zag"):
        assert d["records"][k]["cohorts"][-1]["provenance"] == PROV
    assert prov == PROV  # caller's dict is copied, not shared
    d["run_history"][-1]["provenance"]["timestamp"] = "x"
    assert d["records"]["nl:ik at"]["cohorts"][-1]["provenance"] == PROV


def test_default_provenance_uses_git_and_clock(restorer, monkeypatch):
    monkeypatch.setattr(rt, "origin_main_sha", lambda root=rt.ROOT: SHA)
    monkeypatch.setattr(rt, "utc_now", lambda: TS)
    d = data()
    rt.run(d, "fake", entries=ENTRY)
    assert d["run_history"][-1]["provenance"] == PROV
    assert d["records"]["nl:ik at"]["cohorts"][-1]["provenance"] == PROV


def test_missing_git_is_recorded_as_none(restorer, monkeypatch):
    monkeypatch.setattr(rt, "origin_main_sha", lambda root=rt.ROOT: None)
    monkeypatch.setattr(rt, "utc_now", lambda: TS)
    d = data()
    rt.run(d, "fake", entries=ENTRY)
    assert d["run_history"][-1]["provenance"] == {"origin_main_sha": None, "timestamp": TS}


def test_existing_records_are_not_backfilled(restorer):
    d = data()
    rt.run(d, "fake", entries=ENTRY, provenance=PROV)
    old = d["records"]["nl:ik at"]["cohorts"][0]
    old_history = d["run_history"][0]
    del old["provenance"], old_history["provenance"]  # simulate a pre-provenance run
    later = {"origin_main_sha": SHA[::-1], "timestamp": "2026-11-11T00:00:00+09:00"}
    rt.run(d, "fake", entries=ENTRY, provenance=later)
    assert "provenance" not in d["records"]["nl:ik at"]["cohorts"][0]
    assert "provenance" not in d["run_history"][0]
    assert d["records"]["nl:ik at"]["cohorts"][1]["provenance"] == later


def test_provenance_does_not_change_scoring(restorer):
    a, b = data(), data()
    rt.run(a, "fake", entries=ENTRY, provenance=PROV)
    rt.run(b, "fake", entries=ENTRY, provenance={"origin_main_sha": None, "timestamp": "2020-01-01T00:00:00-05:00"})
    assert rt.status(a, "nl", "ik at") == rt.status(b, "nl", "ik at") == "pass"
    assert rt.rate(a["records"]["nl:ik at"]) == rt.rate(b["records"]["nl:ik at"]) == 1
    # an older cohort without provenance still validates
    del a["records"]["nl:ik at"]["cohorts"][-1]["provenance"]
    assert rt.status(a, "nl", "ik at") == "pass"


@pytest.mark.parametrize("bad", [
    {"origin_main_sha": SHA, "timestamp": "2026-11-10T09:55:00"},          # naive
    {"origin_main_sha": SHA, "timestamp": "yesterday"},
    {"origin_main_sha": SHA, "timestamp": None},
    {"origin_main_sha": SHA.upper(), "timestamp": TS},
    {"origin_main_sha": SHA[:12], "timestamp": TS},
    {"origin_main_sha": SHA, "timestamp": TS, "extra": 1},
    {"timestamp": TS},
    [SHA, TS],
])
def test_invalid_provenance_is_rejected_before_execution(monkeypatch, bad):
    d = data()
    before = copy.deepcopy(d)
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **k: pytest.fail("must not execute"))
    with pytest.raises(ValueError):
        rt.run(d, "fake", entries=ENTRY, provenance=bad)
    assert json.dumps(d, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_malformed_default_clock_is_rejected(restorer, monkeypatch):
    monkeypatch.setattr(rt, "utc_now", lambda: "2026-11-10 09:55")
    with pytest.raises(ValueError):
        rt.run(data(), "fake", entries=ENTRY)


def test_utc_now_is_timezone_aware_iso8601():
    parsed = datetime.fromisoformat(rt.utc_now())
    assert parsed.utcoffset() is not None and parsed.utcoffset().total_seconds() == 0
    assert rt.valid_provenance({"origin_main_sha": None, "timestamp": rt.utc_now()})


def test_origin_main_sha_matches_git_and_ignores_run_fakes(monkeypatch, tmp_path):
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **k: pytest.fail("restore-command fake must not be used"))
    sha = rt.origin_main_sha()
    p = subprocess.Popen(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", "origin/main^{commit}"],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    expected = p.communicate()[0].strip() or None
    assert sha == (expected if p.returncode == 0 else None)
    assert rt.origin_main_sha(tmp_path) is None  # not a git checkout


# ---------------------------------------------------------------- mapping_graph reads it
def _cohort(run_id: str, **extra) -> dict:
    return {"run_id": run_id, "config": {"command_sha256": "a" * 64, "templates": ["{s}.", "Maybe {s} today."]},
            "targets": [{"status": "completed", "restored": True, "source": "I came."},
                        {"status": "completed", "restored": False, "source": "Maybe I came today."}], **extra}


def _graph(rtd: dict) -> mg.Graph:
    g = mg.Graph()
    g.add("form:de:kam", "Form")
    mg._record_nodes(g, rtd, "de", "kam", "form:de:kam")
    return g


def test_graph_reads_cohort_then_history_provenance():
    other = {"origin_main_sha": SHA[::-1], "timestamp": "2026-11-09T00:00:00+09:00"}
    rtd = {"records": {"de:kam": {"lang": "de", "form": "kam", "cohorts": [
        _cohort("r1", provenance=PROV), _cohort("r2"), _cohort("r3", provenance={"timestamp": "bad"})]}},
           "run_history": [{"run_id": "r1", "provenance": other}, {"run_id": "r2", "provenance": other}]}
    g = _graph(rtd)
    r1, r2, r3 = (g.nodes[f"rt:de:kam:{r}"] for r in ("r1", "r2", "r3"))
    assert (r1["measured_at_main"], r1["timestamp"]) == (SHA, TS)  # cohort wins over run_history
    assert (r2["measured_at_main"], r2["timestamp"]) == (SHA[::-1], "2026-11-09T00:00:00+09:00")
    assert (r3["measured_at_main"], r3["timestamp"]) == (None, None)  # malformed is ignored
    assert r1["measured_sources"] == ["i came"] and r3["latest"] is True


def test_judge_snapshot_sha_keeps_priority_for_measured_at_main():
    judge = {"kind": "independent_blind_judge", "origin_main_sha": "c" * 40}
    rtd = {"records": {"de:kam": {"lang": "de", "form": "kam", "cohorts": [_cohort("r1", provenance=PROV)]}},
           "run_history": [{"run_id": "r1", "judge_provenance": judge}]}
    n = _graph(rtd).nodes["rt:de:kam:r1"]
    assert n["measured_at_main"] == "c" * 40 and n["run_origin_main_sha"] == SHA and n["timestamp"] == TS
    assert n["evaluator"] == "independent_blind_judge"


def test_new_run_is_counted_by_check(restorer):
    d = data()
    rt.run(d, "fake", entries=ENTRY, provenance=PROV)
    n = _graph({**d, "records": {"de:kam": {**d["records"]["nl:ik at"], "lang": "de", "form": "kam"}}}).nodes
    rec = n[f"rt:de:kam:{d['run_history'][-1]['run_id']}"]
    assert rec["measured_at_main"] == SHA and rec["timestamp"] == TS
    assert rec["measured_sources"] == ["i have eaten"]


def test_measured_sources_prefers_the_most_specific_template():
    c = {"config": {"templates": ["{s}.", "Maybe {s} today.", "She told me that {s}."]},
         "targets": [{"source": s} for s in ("He came.", "Maybe he came today.", "She told me that he came.")]}
    assert mg.measured_sources(c) == ["he came"]
    assert mg.measured_sources({"targets": [{"source": "x"}]}) == []


# ---------------------------------------------------------------- tense_merge report
@pytest.fixture(scope="module")
def g():
    return mg.build()


def test_tense_merge_doc_is_generated_from_the_graph(g):
    assert DOC.read_text(encoding="utf-8") == mg.tense_merge_doc(g), (
        "regenerate: uv run python scripts/mapping_graph.py --collisions --markdown > docs/ontology/tense-merge-collisions.md")


def test_tense_merge_rows_match_collisions(g):
    rows = mg.tense_merge_rows(g)
    col = mg.collisions(g)["tense_merge"]
    assert [r["id"] for r in rows] == [c["id"] for c in col]
    assert sum(Counter(r["lang"] for r in rows).values()) == len(col)
    for r in rows:
        assert len(r["tenses"]) >= 2
        assert {s["meaning"] for s in r["sources"]} == set(r["meanings"])
        assert {s["source"] for s in r["sources"] if s["measured"]} <= set(r["measured_sources"])


def test_cli_markdown_needs_collisions():
    out = subprocess.run([sys.executable, str(ROOT / "scripts/mapping_graph.py"), "--check", "--markdown"],
                         capture_output=True, text=True)
    assert out.returncode == 2 and "--markdown needs --collisions" in out.stderr
    out = subprocess.run([sys.executable, str(ROOT / "scripts/mapping_graph.py"), "--collisions", "--markdown"],
                         capture_output=True, text=True, check=True)
    assert out.stdout == DOC.read_text(encoding="utf-8")
