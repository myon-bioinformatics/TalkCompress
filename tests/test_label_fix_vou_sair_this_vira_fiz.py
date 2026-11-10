"""Data-label fixes: vou sair (pt label), this virá (parity follower of reversed virá), fiz (meanings)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402
from tests._helpers import load  # noqa: E402

FIX = ROOT / "SentenceCalibratedMosaic/fixtures"


def _t():
    return load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")


def _read(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def _entry(bank, eid):
    return next(e for e in _read(bank)["entries"] if e["id"] == eid)


# 1. leave-fut-goingto-1s: vou sair is Portuguese and is the runtime winner.
def test_vou_sair_labelled_pt_and_is_runtime_winner():
    e = _entry("es_fr_tense", "leave-fut-goingto-1s")
    assert (e["to"], e["lang"]) == ("vou sair", "pt")
    assert {(c["form"], c["lang"]) for c in e["candidates"]} == {("saldré", "es"), ("vou sair", "pt")}
    assert e["metrics"]["utf8_after"] == len("vou sair".encode("utf-8"))
    t = _t()
    for src in e["from"]:
        assert t.apply_es_fr_tense(src) == "vou sair"


def test_vou_sair_beats_es_alternatives_on_o200k_tokens():
    # tokens first, then bytes: vou sair 2/8 < saldré 3/7, voy a salir 3/11 (EN 5/19, I'm 4/18).
    score = lambda s: (tm.o200k_tokens(s), len(s.encode("utf-8")))  # noqa: E731
    assert score("vou sair") == (2, 8)
    assert score("vou sair") < score("saldré") < score("voy a salir")
    assert score("vou sair") < score("I'm going to leave")


def test_vou_sair_evidence_is_the_es_keyed_surface_record():
    data = rt.load()
    # measured once under the old es label (prompt is language-agnostic); no pt key yet = 未測定.
    assert rt.status(data, "es", "vou sair") == "pass"
    assert rt.key("pt", "vou sair") not in data["records"]
    assert rt.key("es", "saldré") not in data["records"]


# 2. this virá: demonstrative parity follower of the reversed pt virá stays EN.
def test_this_vira_follower_of_reversed_base_is_not_adopted():
    assert ("pt", "virá") in tm.ROUNDTRIP_REVERSED
    assert ("pt", "this virá") not in tm.ROUNDTRIP_REVERSED  # its own round-trip passed 9/9
    assert rt.status(rt.load(), "pt", "this virá") == "pass"
    bank = _read("tense_matrix")
    assert not [e for e in bank["entries"] if e["to"] == "this virá"]
    cells = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]
    cell = next(c for c in cells if c["src"] == "this will come")
    assert cell["status"] == "reject" and cell["parity_verb"] == "virá"
    assert cell["reason"] == "parity: number-matched pronoun verb winner reversed (EN kept)"
    assert _t().apply_es_fr_tense("Maybe this will come today.") == "Maybe this will come today."


def test_no_adopted_follower_of_a_reversed_base():
    cells = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]
    for c in cells:
        if c.get("status") == "adopt" and c.get("parity_verb"):
            assert (c["lang"], c["parity_verb"]) not in tm.ROUNDTRIP_REVERSED, c["src"]


# 3. fiz: do-it:past unregistered (object never restored); do:past and do:perf kept.
def test_fiz_do_it_past_unregistered_with_roundtrip_reason():
    tense = _read("pt_el_latin_tense")
    assert all(e["id"] != "do-it-past-1s" for e in tense["entries"])
    dropped = next(e for e in tense["examples_not_registered"] if e["id"] == "do-it-past-1s")
    assert dropped["to"] == "fiz" and "roundtrip_reversed" not in dropped
    assert "I did it." in dropped["why_dropped"] and "0/9" in dropped["why_dropped"]
    rec = rt.latest_cohort(rt.load()["records"][rt.key("pt", "fiz")])
    responses = {rt.norm(x["response"]) for x in rec["targets"]}
    assert responses == {"i did", "maybe i did today", "she told me that i did"}
    assert all(x["matched_source"] and x["matched_via_alternate"] for x in rec["targets"])


def test_fiz_keeps_past_and_perfect_and_keeps_the_object():
    assert _entry("es_fr_tense", "do-past-1s")["to"] == "fiz"
    assert _entry("tense_matrix", "mx-do-perf-1s")["to"] == "fiz"
    t = _t()
    assert t.apply_es_fr_tense("I did.") == "fiz."
    assert t.apply_es_fr_tense("I have done.") == "fiz."
    assert t.apply_es_fr_tense("I did it.") == "fiz it."
    assert tm.o200k_tokens("fiz it") < tm.o200k_tokens("I did it")


def test_mapping_graph_has_no_label_or_meaning_collisions():
    import mapping_graph as mg

    col = mg.collisions(mg.build())
    assert col["lang_label_mismatch"] == [] and col["multi_meaning"] == []
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
