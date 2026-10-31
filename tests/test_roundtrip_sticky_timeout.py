"""A recorded timeout must not exclude a form forever (2bot #97 Should 1)."""
import importlib.util
import json
import subprocess
from pathlib import Path

spec = importlib.util.spec_from_file_location("roundtrip_sticky", Path(__file__).resolve().parents[1] / "scripts/roundtrip.py")
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)

ENTRY = [{"lang": "nl", "from": ["I have eaten"], "to": "ik at"}]


def data():
    return {"templates": ["{s}."], "seeds": [1, 2, 3], "records": {}, "min_trials": 2,
            "thresholds": {"lt100m": 0.9, "ge100m": 0.9}, "ge100m_langs": ["en"]}


def _hang(*a, **k):
    raise subprocess.TimeoutExpired("fake", 1)


def _ok(*a, **k):
    return subprocess.CompletedProcess("fake", 0, "I have eaten.", "")


def test_timeout_then_success_is_verifiable(monkeypatch):
    d = data()
    monkeypatch.setattr(rt.subprocess, "run", _hang)
    rt.run(d, "fake", entries=ENTRY)
    rec = d["records"]["nl:ik at"]
    assert rt.unresolved_timeouts(rec) == 3 and rt.rate(rec) is None
    monkeypatch.setattr(rt.subprocess, "run", _ok)
    rt.run(d, "fake", entries=ENTRY)
    rec = d["records"]["nl:ik at"]
    assert (rec["trials"], rec["timeouts"], rec["completed"], rec["attempted"]) == (3, 3, 3, 6)
    assert rec["pending_timeouts"] == 0
    assert rt.rate(rec) == 1.0
    assert rt.status(d, "nl", "ik at") == "pass"
    assert rt.gate_for(d, "all")("ik at", "nl")


def test_partial_timeout_in_latest_run_stays_unverified(monkeypatch):
    d = data()
    monkeypatch.setattr(rt.subprocess, "run", _ok)
    rt.run(d, "fake", entries=ENTRY)
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **k: _hang() if k["env"]["ROUNDTRIP_SEED"] == "2" else _ok())
    rt.run(d, "fake", entries=ENTRY)
    rec = d["records"]["nl:ik at"]
    assert rec["pending_timeouts"] == 1 and rec["timeouts"] == 1
    assert rt.rate(rec) is None
    assert not rt.gate_for(d, "lt100m")("ik at", "nl")


def test_legacy_record_without_pending_uses_timeouts():
    assert rt.unresolved_timeouts({"trials": 3, "restored": 3, "timeouts": 2}) == 2
    assert rt.unresolved_timeouts(None) == 0


def _cli(monkeypatch, tmp_path, d, fake):
    monkeypatch.setattr(rt, "load", lambda: d)
    monkeypatch.setattr(rt, "DATA_PATH", tmp_path / "r.json")
    monkeypatch.setattr(rt.subprocess, "run", fake)
    import tense_matrix as tm
    monkeypatch.setattr(tm, "build", lambda: ({"entries": ENTRY},))
    return rt.main(["--run", "--cmd", "fake"])


def test_cli_exit_recovers_after_successful_rerun(monkeypatch, tmp_path):
    d = data()
    assert _cli(monkeypatch, tmp_path, d, _hang) == 1
    assert _cli(monkeypatch, tmp_path, d, _ok) == 0
    assert json.loads((tmp_path / "r.json").read_text())["records"]["nl:ik at"]["pending_timeouts"] == 0


def test_cli_exit_ignores_untouched_stale_record(monkeypatch, tmp_path):
    d = data()
    d["records"]["de:x"] = {"lang": "de", "form": "x", "trials": 0, "restored": 0, "failures": [], "timeouts": 3}
    assert _cli(monkeypatch, tmp_path, d, _ok) == 0
