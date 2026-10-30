"""de / nl preterite as candidates for EN present perfect (same policy as es/pt)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
BY_ID = {e["id"]: e for e in BANK["entries"]}
CONJ = json.loads(tm.CONJ_PATH.read_text(encoding="utf-8"))["conj"]


@pytest.mark.parametrize("eid,to,lang", [
    ("mx-see-perf-3s-he", "sah", "de"),
    ("mx-have-perf-1p", "hatten", "de"),
])
def test_winner(eid, to, lang):
    e = BY_ID[eid]
    assert (e["to"], e["lang"]) == (to, lang)


@pytest.mark.parametrize("eid", ["mx-see-perf-1p", "mx-take-perf-1s", "mx-say-perf-3s-she"])
def test_nl_preterite_gated_for_perfect(eid):
    # #29: nl preterite for EN perfect restores as simple past (0/9 etc.) -> gated
    assert BY_ID[eid]["lang"] != "nl"


@pytest.mark.parametrize("person,de,nl", [("1s", "sah", "zag"), ("1p", "sahen", "zagen"), ("3", "sah", "zag")])
def test_candidates_offered_with_number(person, de, nl):
    p = "3s" if person == "3" else person
    forms = {(c["form"], c["lang"], c["shape"]) for c in tm._candidates(CONJ, p, "perf", "see", "")}
    assert (de, "de", "simple-preterite") in forms
    assert (nl, "nl", "simple-preterite") in forms
    # parity: no plural form offered for singular slot and vice versa
    other = {"sah": "sahen", "sahen": "sah"}[de]
    assert (other, "de", "simple-preterite") not in forms


def test_not_offered_outside_perfect():
    for t in ("pluperf", "futperf", "fut"):
        shapes = {(c["lang"], c["shape"]) for c in tm._candidates(CONJ, "1p", t, "see", "")}
        assert ("de", "simple-preterite") not in shapes and ("nl", "simple-preterite") not in shapes


def test_nl_perfect_winners_require_roundtrip():
    data = rt.load()
    assert data["required"] == rt.required_keys(BANK)
    nl = {rt.key(e["lang"], e["to"]) for e in BANK["entries"] if e["lang"] == "nl" and e["tense"] == "perf"}
    assert nl <= set(data["required"])  # empty after #29 gating
    assert "nl" not in data["ge100m_langs"]


def test_nl_perfect_listed_in_impact_doc():
    doc = (ROOT / "docs/roundtrip_impact.md").read_text(encoding="utf-8")
    for e in BANK["entries"]:
        if e["lang"] == "nl" and e["tense"] == "perf":
            assert e["id"] in doc


def test_bank_to_still_cheapest_and_collision_free():
    assert tm.main(["--check"]) == 0
