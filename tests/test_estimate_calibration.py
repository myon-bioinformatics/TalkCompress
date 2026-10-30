"""The committed o200k calibration table is reproducible and generalises."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cal():
    spec = importlib.util.spec_from_file_location("calibrate_estimate", ROOT / "scripts/calibrate_estimate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_calib_file_is_regenerated():
    mod = _cal()
    committed = json.loads(mod.CALIB.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(mod.build(), ensure_ascii=False))


def test_calib_matches_wordlist():
    mod = _cal()
    d = json.loads(mod.CALIB.read_text(encoding="utf-8"))
    assert d["wordlist_sha256"] == hashlib.sha256(mod.WORDLIST.read_bytes()).hexdigest()


def test_heldout_and_natural_agreement_floors():
    r = _cal().report()
    # held-out matrix cells (sha1(src) % 5 == 0) never feed the tables
    # miss-count floor: dropped cells shrink the held-out pool, not accuracy
    assert r["heldout"]["n"] - r["heldout"]["exact"] <= 7 and r["heldout"]["n"] >= 590
    assert r["heldout"]["flips"] == 0
    # independent natural sentences (not drawn from any bank); main scored 2/60
    assert r["natural"]["n"] == 60 and r["natural"]["exact"] >= 32
    assert r["natural"]["abs_err"] <= 56
