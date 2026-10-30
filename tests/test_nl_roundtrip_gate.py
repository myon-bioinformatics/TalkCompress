"""#29: nl (<100M speakers) tense-matrix forms are adopted only after an AI round-trip pass."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

DATA = rt.load()
BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
JUDGE = json.loads((ROOT / "TesseraTalk/fixtures/roundtrip_judge/nl_blind.json").read_text(encoding="utf-8"))


def test_nl_is_enforced_and_lt100m():
    assert "nl" in tm.ROUNDTRIP_ENFORCED_LANGS and "nl" not in DATA["ge100m_langs"]
    assert DATA["thresholds"]["lt100m"] == 0.9


def test_every_nl_bank_winner_passed_roundtrip():
    nl = [e for e in BANK["entries"] if e["lang"] == "nl"]
    assert nl
    for e in nl:
        assert rt.status(DATA, "nl", e["to"]) == "pass", e
        assert rt.rate(DATA["records"][rt.key("nl", e["to"])]) >= 0.9


@pytest.mark.parametrize("form", ["nam", "dacht", "zei", "ging", "wil", "zagen", "namen", "wilden",
                                  "who zei", "these deden"])
def test_failed_forms_not_adopted(form):
    assert rt.status(DATA, "nl", form) in ("fail", "never")
    assert all(not (e["lang"] == "nl" and e["to"] == form) for e in BANK["entries"])


def test_gate_is_per_lang_not_per_form():
    # nl denkt failed, de denkt (same spelling) must survive
    assert rt.status(DATA, "nl", "denkt") != "pass"
    he = next(e for e in BANK["entries"] if e["from"][0] == "he thinks")
    assert (he["to"], he["lang"]) == ("denkt", "de")


def test_nl_records_complete():
    nl_keys = {k for k in DATA["records"] if k.startswith("nl:")}
    assert all(DATA["records"][k]["trials"] >= DATA["min_trials"] for k in nl_keys)


def test_replay_harness_matches_judge_file():
    # reproducible: replay restorer returns the recorded blind judge answer
    conv = "Maybe kom today."
    p = subprocess.run([sys.executable, str(ROOT / "scripts/roundtrip_replay.py"), "nl"],
                       input=rt.PROMPT.format(c=conv), capture_output=True, text=True, check=True)
    assert p.stdout.strip() == JUDGE[conv] == "Maybe I come today."


def test_bank_is_fresh():
    assert tm.main(["--check"]) == 0
