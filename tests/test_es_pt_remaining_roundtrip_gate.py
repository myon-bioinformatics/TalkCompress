"""es tomaré / pt acharei, logo, por isso: the adopted forms #161/#164 promoted without a
round-trip record, measured by independent blind judges, bare and in designed contexts
(docs/es_pt_remaining_roundtrip_20261110.md)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import remaining_roundtrip_20261110 as rem  # noqa: E402
import roundtrip as rt  # noqa: E402
import tense_matrix as tm  # noqa: E402

FIX = ROOT / "SentenceCalibratedMosaic/fixtures"
RJ = FIX / "roundtrip_judge"
JUDGE_PATH = RJ / "remaining_20261110_blind.json"
JUDGE = json.loads(JUDGE_PATH.read_text(encoding="utf-8"))
SNAPSHOT = json.loads((RJ / "remaining_20261110_sources.json").read_text(encoding="utf-8"))
CTX_JUDGE = json.loads((RJ / "remaining_20261110_ctx_blind.json").read_text(encoding="utf-8"))
CTX_SRC = json.loads((RJ / "remaining_20261110_ctx_sources.json").read_text(encoding="utf-8"))
MEANING = json.loads((RJ / "remaining_20261110_ctx_meaning.json").read_text(encoding="utf-8"))
DATA = rt.load()
KEYS = ["es:tomaré", "pt:acharei", "pt:logo", "pt:por isso"]
# key -> (bare exact, context exact distinct /9, meaning ref /9, final status)
EXPECTED = {"es:tomaré": (0, 9, 9, "pass"), "pt:acharei": (0, 9, 9, "pass"),
            "pt:logo": (0, 0, 9, "never"), "pt:por isso": (0, 0, 9, "never")}
KEPT = {"es_fr_tense": {"take-fut-1s": ("tomaré", "es"), "take-fut-goingto-1s": ("tomaré", "es"),
                        "find-fut-1s": ("acharei", "pt"), "find-fut-goingto-1s": ("acharei", "pt")}}
REVERSED = {"pt_el_latin_phrases": {"as-a-result-la-pt-el": "logo", "for-this-reason-la-pt": "por isso"}}


def read(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def _cohorts(key):
    rec = [c for c in DATA["records"][key]["cohorts"]]
    study = DATA.get("context_studies", {}).get("remaining_20261110", {}).get(key)
    return rec, study


def test_judges_frozen_and_cover_exactly_the_converted_sentences():
    assert hashlib.sha256(JUDGE_PATH.read_bytes()).hexdigest() == rem.JUDGE_SHA256
    converted = [cv for f in SNAPSHOT["forms"] for _, cv in rt.sentences(DATA, f["entry"]["from"][0], f["entry"]["to"])]
    assert list(JUDGE) == converted and len(converted) == 12
    assert hashlib.sha256(("\n".join(converted) + "\n").encode()).hexdigest() == rem.CONVERTED_SHA256
    assert hashlib.sha256((RJ / "remaining_20261110_ctx_blind.json").read_bytes()).hexdigest() == rem.CTX_JUDGE_SHA256
    assert hashlib.sha256((RJ / "remaining_20261110_ctx_meaning.json").read_bytes()).hexdigest() == rem.CTX_MEANING_SHA256
    assert set(CTX_JUDGE) == {s["converted"] for s in CTX_SRC["sentences"]} and len(CTX_JUDGE) == 36
    assert MEANING["gating"] is False and set(MEANING["by_converted"]) == set(CTX_JUDGE)


def test_request_never_shows_the_adopted_english():
    shown = " ".join(s["converted"].lower() for s in CTX_SRC["sentences"])
    for spec in CTX_SRC["forms"].values():
        assert spec["adopted_source"].lower() not in shown
        assert len(spec["templates"]) == 9


@pytest.mark.parametrize("key", KEYS)
def test_bare_cohort_history_kept_and_context_cohort_recorded(key):
    lang, form = key.split(":", 1)
    bare_exact, ctx_exact, meaning, final = EXPECTED[key]
    cohorts, study = _cohorts(key)
    bare = cohorts[0]
    assert bare["judge_provenance"]["judge_sha256"] == rem.JUDGE_SHA256
    assert (bare["restored"], bare["completed"], bare["config"]["templates"]) == (bare_exact, 9, DATA["templates"])
    for t in bare["targets"]:
        assert t["response"] == JUDGE[t["converted"]]
    if final == "pass":
        assert study is None and len(cohorts) == 2
        ctx = rt.latest_cohort(DATA["records"][key])
    else:
        assert len(cohorts) == 1 and rt.latest_cohort(DATA["records"][key]) is bare
        assert study["gate_visible"] is False
        ctx = study["cohort"]
        assert rt._valid_cohort(ctx)
    spec = CTX_SRC["forms"][key]
    assert ctx["config"]["templates"] == spec["templates"] and ctx["config"]["seeds"] == [1, 2, 3]
    assert ctx["config"]["normalization"] == "norm-nfc-v1"
    assert ctx["judge_provenance"]["judge_sha256"] == rem.CTX_JUDGE_SHA256
    assert ctx["complete"] and ctx["completed"] == 27
    distinct = {}
    for t in ctx["targets"]:
        assert t["response"] == CTX_JUDGE[t["converted"]]
        assert t["accepted_sources"] == [t["source"]]
        assert t["restored"] is (rt.norm(t["response"]) == rt.norm(t["source"]))
        distinct[t["converted"]] = t["restored"]
    assert len(distinct) == 9 and sum(distinct.values()) == ctx_exact
    assert ctx["restored"] == 3 * ctx_exact
    assert sum(v == "same" for v in ctx["meaning_match_ref"].values()) == meaning
    assert rt.status(DATA, lang, form) == final


def test_passing_forms_restored_and_failing_forms_reversed():
    for name, ids in KEPT.items():
        bank = read(name)
        got = {e["id"]: (e["to"], e["lang"]) for e in bank["entries"] if e["id"] in ids}
        assert got == ids
        assert not any(e.get("roundtrip_reversed") and e["id"] in ids for e in bank["examples_not_registered"])
    for name, ids in REVERSED.items():
        bank = read(name)
        assert not any(e["id"] in ids for e in bank["entries"])
        nr = {e["id"]: e for e in bank["examples_not_registered"] if e.get("roundtrip_reversed") and e["id"] in ids}
        assert {k: e["to"] for k, e in nr.items()} == ids
        assert all("0/9" in e["why_dropped"] and "actual restorations" in e["why_dropped"] for e in nr.values())


@pytest.mark.parametrize("raw,out", [("I will take", "tomaré"), ("I will find", "acharei")])
def test_restored_futures_convert_at_runtime(raw, out):
    from tests._helpers import load
    talk = load("rt4_tense_guard", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    assert talk.apply_es_fr_tense(raw) == out


@pytest.mark.parametrize("raw", ["as a result", "for this reason"])
def test_reversed_phrases_stay_english_at_runtime(raw):
    from tests._helpers import load
    talk = load("rt4_phrase_guard", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    assert talk.apply_zh_de_phrases(raw) == raw


def test_enforced_langs_unchanged():
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
