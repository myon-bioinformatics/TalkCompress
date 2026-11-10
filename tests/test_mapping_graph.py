"""Read-only mapping ontology graph (docs/ontology/mapping-ontology.md)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mapping_graph as mg  # noqa: E402
import roundtrip as rt  # noqa: E402


@pytest.fixture(scope="module")
def g():
    return mg.build()


def test_settings_read_without_import():
    s = mg.read_settings()
    assert s["ROUNDTRIP_ENFORCED_LANGS"] == frozenset({"nl"})
    assert ("pt", "virá") in s["ROUNDTRIP_REVERSED"]
    assert "i took" in s["ROUNDTRIP_REVERSED_SOURCES"]
    assert s["ROUNDTRIP_REVERSED_ANY_CANDIDATE_LANGS"] == frozenset({"it"})
    assert s["ROUNDTRIP_REVERSED_DROP_CANDIDATE_LANGS"] == frozenset({"es"})


def test_strategies_per_language(g):
    assert g.nodes["lang:it"]["reversal_strategy"] == "any_candidate_empties_cell"
    assert g.nodes["lang:es"]["reversal_strategy"] == "drop_candidate_before_ranking"
    assert g.nodes["lang:pt"]["reversal_strategy"] == "adopted_winner_only"
    assert g.nodes["lang:nl"]["roundtrip_enforced"] is True


def test_ids_are_stable_and_typed(g):
    assert g.nodes["form:pt:foi"]["type"] == "Form"
    assert mg.form_id("pt", "foi") == "form:" + rt.key("pt", "foi")
    for s, _, o in g.edges:
        assert s in g.nodes and o in g.nodes


def test_status_matches_roundtrip_and_no_record_is_untested(g):
    data = rt.load()
    for f in mg.adopted_forms(g).values():
        if f["status"] in ("untested", "not_applicable"):
            assert rt.key(f["lang"], f["form"]) not in data["records"]
        else:
            assert f["status"] == rt.status(data, f["lang"], f["form"])
    # no record is never counted as failed
    assert all(f["status"] != "never" for f in mg.adopted_forms(g).values() if f["lang"] == "de")


def test_summary_counts_cover_every_adopted_form(g):
    summary = mg.status_summary(g)
    assert sum(sum(c.values()) for c in summary.values()) == len(mg.adopted_forms(g))
    assert summary["pt"]["pass"] == 210


def test_reversal_is_linked_to_its_records(g):
    rev = g.nodes["rev:pt:virá"]
    assert rev["strategy"] == "adopted_winner_only"
    assert g.out("rev:pt:virá", "basedOn")
    assert all(g.nodes[r]["type"] == "RoundtripRecord" for r in g.out("rev:pt:virá", "basedOn"))
    assert "en:i took" in g.out("revsrc:i took", "keepsEnglish")


def test_no_reversed_form_is_still_adopted():
    assert mg.check(mg.build())["reversed_still_adopted"] == []


def test_parity_followers_of_reversed_base(g):
    rows = mg.parity_reversed(g)
    assert rows and all(g.nodes[r["id"]]["base_reversed"] for r in rows)
    assert {"this virá"} == {r["follower_form"] for r in rows if r["cell_status"] == "adopt"}


def test_source_query_lists_all_languages(g):
    rows = mg.by_source(g, "I will take")
    langs = {(r["role"], r["lang"], r["form"]) for r in rows}
    # #164 で tomaré の lang ラベルを es に直し、往復 0/9 の πάρω (el) を外した。
    # 2026-11-10: es tomaré も独立ブラインド往復 0/9 で外した（pt tomarei は昇格させない）。
    assert ("reversed", "es", "tomaré") in langs
    assert not any(r[0] == "adopted" for r in langs)
    assert ("not_registered", "el", "πάρω") in langs
    assert all(r["status"] in mg.STATUSES for r in rows)


def test_collisions_report(g):
    col = mg.collisions(g)
    assert set(col) == {"cross_language", "lang_label_mismatch", "multi_meaning", "tense_merge"}
    ids = {r["id"] for r in col["lang_label_mismatch"]}
    assert "adopt:el:tomaré:i will take" not in ids  # #164 で es に修正済み
    assert "adopt:es:vou sair:i am going to leave" in ids


def test_cli_check_is_read_only():
    before = {p: p.stat().st_mtime_ns for p in (ROOT / "SentenceCalibratedMosaic/fixtures").glob("*.json")}
    out = subprocess.run([sys.executable, str(ROOT / "scripts/mapping_graph.py"), "--check", "--json"],
                         capture_output=True, text=True, check=True)
    res = json.loads(out.stdout)
    assert res["enforced_langs"] == ["nl"]
    assert {p: p.stat().st_mtime_ns for p in before} == before


def test_parity_order_puts_bases_first(g):
    order = mg.parity_order(g)
    pos = {n: i for i, n in enumerate(order)}
    for p in g.of_type("ParityFollow"):
        for base in g.out(p["id"], "followsVerbOf"):
            assert pos[base] < pos[p["id"]]
        for derived in g.out(p["id"], "derivesForm"):
            assert pos[p["id"]] < pos[derived]


def test_parity_cycle_is_a_graph_error():
    h = mg.Graph()
    h.add("form:pt:x", "Form")
    h.add("parity:a", "ParityFollow")
    h.link("parity:a", "followsVerbOf", "form:pt:x")
    h.link("parity:a", "derivesForm", "form:pt:x")
    with pytest.raises(mg.GraphError, match="cycle"):
        mg.parity_order(h)
