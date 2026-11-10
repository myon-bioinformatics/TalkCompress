"""Re-audit context round-trip (class b + bonus; 30 forms x 9 sentences) by GitHubヘルプ4bot.

docs/reaudit_b_4bot_context_roundtrip_20261110.md. Gate = exact match (norm-nfc-v1);
meaning match is reference only. roundtrip.json is not modified by this study.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reaudit_b_4bot_roundtrip as rb  # noqa: E402
import roundtrip as rt  # noqa: E402

FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
RJ = FIX / "roundtrip_judge"


def j(path):
    return json.loads(path.read_text(encoding="utf-8"))


SRC = j(RJ / "reaudit_b_4bot_sources.json")
BLIND = j(RJ / "reaudit_b_4bot_blind.json")
RAW = j(RJ / "reaudit_b_4bot_raw.json")
MEANING = j(RJ / "reaudit_b_4bot_meaning.json")
RES = j(RJ / "reaudit_b_4bot_results.json")
DATA = rt.load()

# key -> (exact /9, meaning ref /9, status)
EXPECTED = {
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
    conv = [s["converted"] for s in SRC["sentences"]]
    assert len(conv) == len(set(conv)) == 270 and set(BLIND) == set(conv)
    assert list(SRC["forms"]) == list(EXPECTED)
    assert SRC["official_templates"] == DATA["templates"]
    for key, spec in SRC["forms"].items():
        mine = [s for s in SRC["sentences"] if s["key"] == key]
        assert len(mine) == 9 and len(spec["templates"]) == 9
        probe = {**DATA, "templates": spec["templates"]}
        assert [cv for _, cv in rt.sentences(probe, spec["adopted_source"], spec["form"])] == \
            [s["converted"] for s in sorted(mine, key=lambda s: (s["context_id"], s["template_id"]))]


def test_request_never_shows_the_adopted_english():
    for s in SRC["sentences"]:
        assert s["adopted_source"].lower() not in s["converted"].lower()


def test_raw_answers_are_verbatim_with_sha256():
    assert set(RAW["by_id"]) == {s["id"] for s in SRC["sentences"]}
    for s in SRC["sentences"]:
        r = RAW["by_id"][s["id"]]
        assert hashlib.sha256(r["raw"].encode("utf-8")).hexdigest() == r["raw_sha256"]
        assert r["converted"] == s["converted"] and BLIND[s["converted"]] == r["raw"].strip()


def test_meaning_is_reference_only_and_complete():
    assert MEANING["gating"] is False and set(MEANING["by_converted"]) == set(BLIND)
    assert {v["meaning_match_ref"] for v in MEANING["by_converted"].values()} <= {"same", "different"}
    assert sum(v["meaning_match_ref"] == "same" for v in MEANING["by_converted"].values()) == 260


@pytest.mark.parametrize("key", EXPECTED)
def test_per_form_exact_meaning_and_gate(key):
    exact, meaning, status = EXPECTED[key]
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


@pytest.mark.parametrize("key", EXPECTED)
def test_bank_matches_gate(key):
    lang, form = key.split(":", 1)
    bank = j(FIX / f"{BANK[lang]}.json")
    live = [e for e in bank["entries"] if e["lang"] == lang and e["to"] == form]
    if key in rb.UNDONE:
        assert len(live) == 1 and "why_dropped" not in live[0] and "roundtrip_reversed" not in live[0]
        assert not [e for e in bank["examples_not_registered"] if e["id"] == live[0]["id"]]
    elif key == "la:inter alia":
        # among others stays reversed; the among other things entry and its 9/9 record are untouched
        assert [e["from"] for e in live] == [["among other things"]]
        assert rt.status(DATA, "la", "inter alia") == "pass"
        assert [e["from"] for e in bank["examples_not_registered"] if e.get("to") == form] == [["among others"]]
    else:
        assert not live
        assert [e for e in bank["examples_not_registered"] if e.get("lang") == lang and e.get("to") == form]


def test_failures_recorded_as_hidden_context_studies():
    studies = RES["context_studies"]["reaudit_b_4bot"]
    assert set(studies) == set(EXPECTED) - set(rb.UNDONE) and len(studies) == 24
    for key, s in studies.items():
        assert s["gate_visible"] is False and s["cohort"]["complete"] and s["cohort"]["completed"] == 27
        assert s["cohort"]["restored"] == EXPECTED[key][0] * 3
    assert "separate_from_record" in studies["la:inter alia"]
    assert set(RES["passed_cohorts"]) == set(rb.UNDONE)


def test_roundtrip_json_untouched_by_this_study():
    assert "reaudit_b_4bot" not in DATA.get("context_studies", {})
    for key in rb.UNDONE:
        lang, form = key.split(":", 1)
        assert rt.status(DATA, lang, form) == "never"  # bare cohort kept; evidence is in roundtrip_judge
