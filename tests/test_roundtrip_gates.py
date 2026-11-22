"""言語別の AI 往復ゲート: 採用形は記録済みの往復結果に合格したものだけ（de / el / es / es+pt 残り / fr / it / nl / pt / zh）。

- de_roundtrip_gate: de (ge100m) adopted winners: independent blind AI round-trip (docs/de_roundtrip_20261109.md).
- el_roundtrip_gate: Scoped Greek round-trip evidence and runtime bank regressions.
- es_roundtrip_gate: es (ge100m) adopted winners: independent blind AI round-trip (docs/es_roundtrip_20261109.md).
- es_pt_remaining_roundtrip_gate: es tomaré / pt acharei, logo, por isso: the adopted forms #161/#164 promoted without a
- fr_roundtrip_gate: fr (ge100m) adopted winners: independent blind AI round-trip (docs/fr_roundtrip_20261109.md).
- it_roundtrip_gate: it (ge100m) adopted winners: independent blind AI round-trip (docs/it_roundtrip_20261108.md).
- nl_roundtrip_gate: #29: nl (<100M speakers) tense-matrix forms are adopted only after an AI round-trip pass.
- pt_roundtrip_gate: Frozen independent pt judge, any-source evidence, and narrowly scoped reversals.
- zh_roundtrip_gate: Scoped Chinese (zh) round-trip evidence for the 62 labelled zh_de_phrases winners.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from tests._helpers import load
from types import SimpleNamespace
import copy
import hashlib
import json
import reaudit_a_3bot_roundtrip as reaudit
import reaudit_a_3bot_roundtrip as reaudit_a
import remaining_roundtrip_20261110 as rem
import roundtrip
import roundtrip as rt
import subprocess
import sys
import tense_matrix as tm

import pytest


# ──── de_roundtrip_gate ───────────────────────────────────────────

"""de (ge100m) adopted winners: independent blind AI round-trip (docs/de_roundtrip_20261109.md)."""


ROOT = Path(__file__).resolve().parents[1]


DATA = rt.load()


FIX = ROOT / "SentenceCalibratedMosaic/fixtures"


BANK = json.loads((FIX / "tense_matrix.json").read_text(encoding="utf-8"))


PHRASES = json.loads((FIX / "zh_de_phrases.json").read_text(encoding="utf-8"))


ES = json.loads((FIX / "es_fr_tense.json").read_text(encoding="utf-8"))


JUDGE = json.loads((FIX / "roundtrip_judge/de_blind.json").read_text(encoding="utf-8"))


PASS_FORMS = ['kam', 'sah', 'dachtest', 'denkt', 'nehmen', 'finden', 'wollen', 'denken', 'sagen', 'kamen', 'sahen', 'nahmen', 'fanden', 'wollten', 'sagten', 'dachten', 'who denkt', 'which denkt', 'Bahnhof', 'Datenschutz', 'Handy', 'Ampel', 'Stau', 'Lenkrad', 'Mikrowelle', 'Klimawandel', 'Haustür', 'Kraftwerk', 'Kernenergie', 'Geburtsurkunde', 'Telefonnummer', 'Erderwärmung',
              # re-scored with every official source / leading que≡that (docs/roundtrip_rescore_20261110.md)
              'fand', 'que denkt']


FAIL_FORMS = ['nahm', 'dachte', 'kamst', 'tatest', 'nahmst', 'taten', 'this kam', 'this sah', 'this nahm', 'this fand', 'this dachte', 'these kamen', 'these sahen', 'these nahmen', 'these fanden', 'these dachten', 'those kamen', 'those sahen', 'those nahmen', 'those fanden', 'those dachten', 'who kam', 'who sah', 'who nahm', 'who fand', 'who dachte', 'who kamen', 'who fanden', 'which kam', 'which sah', 'which nahm', 'which fand', 'which dachte', 'which kamen', 'which sahen', 'which nahmen', 'which fanden', 'which dachten', 'que kam', 'que sah', 'que nahm', 'que fand', 'que dachte', 'que kamen', 'que sahen', 'que nahmen', 'que fanden', 'que dachten', 'Tankstelle', 'Parkplatz', 'wenn']


def test_de_is_ge100m():
    assert "de" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_every_remaining_de_winner_passed_independent_blind_roundtrip():
    forms = {e["to"] for bank in (BANK, PHRASES, ES) for e in bank["entries"] if e.get("lang") == "de"}
    assert forms == set(PASS_FORMS)
    assert len(forms) == 34  # 32 + fand / que denkt (re-score)
    for form in forms:
        assert rt.status(DATA, "de", form) == "pass", form
        cohort = rt.latest_cohort(DATA["records"][rt.key("de", form)])
        assert cohort["complete"] and cohort["completed"] >= DATA["min_trials"]
        assert cohort["restored"] == 9 and cohort["completed"] == 9
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        assert cohort["config"]["normalization"] == "norm-nfc-v1"
        for t in cohort["targets"]:
            assert t["converted"] in JUDGE


@pytest.mark.parametrize("form", FAIL_FORMS)
def test_failed_de_forms_reversed(form):
    assert rt.status(DATA, "de", form) == "never"
    assert all(not (e.get("lang") == "de" and e["to"] == form)
               for b in (BANK, PHRASES, ES) for e in b["entries"])


def test_zh_de_failures_recorded_as_not_registered():
    dropped = {e["id"]: e for e in PHRASES["examples_not_registered"]}
    for eid, form in ("tankstelle", "Tankstelle"), ("parkplatz", "Parkplatz"), ("wenn", "wenn"):
        assert dropped[eid]["to"] == form and "0/9" in dropped[eid]["why_dropped"]


def test_es_fr_fand_restored_after_rescore():
    # I found -> fand was reversed at 0/9 against from[0] 'I have found'; the judge restored
    # 'I found', an official source of the same form, so the re-score passes 9/9.
    restored = next(e for e in ES["entries"] if e["id"] == "find-past-1s")
    assert (restored["to"], restored["lang"]) == ("fand", "de")
    assert not any(e["id"] == "find-past-1s" for e in ES["examples_not_registered"])


def test_zh_entries_untouched_count():
    # 62 → 37 after the zh round-trip gate (#169); 37 → 42 after the accepted-sources
    # re-score restored 高速 / 短期 / 小学 / 高铁 / 微调; +4 (明白 / 电话 / 餐厅 / 心脏病) restored by
    # the reaudit_b_4bot context round-trip.
    assert sum(1 for e in PHRASES["entries"] if e["lang"] == "zh") == 46


def test_roundtrip_enforced_langs_unchanged():
    import tense_matrix as tm
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    assert ("de", "fand") not in tm.ROUNDTRIP_REVERSED  # rescued by the re-score
    assert ("de", "nahm") in tm.ROUNDTRIP_REVERSED


# ──── el_roundtrip_gate ───────────────────────────────────────────

"""Scoped Greek round-trip evidence and runtime bank regressions."""


def fixture(name):
    return json.loads((ROOT / "SentenceCalibratedMosaic/fixtures" / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("form,restored,completed", [
    ("ένα ένα", 9, 9), ("βρω", 0, 18), ("πάλι", 0, 9),
    ("πάνω κάτω", 9, 9), ("υπέρ", 0, 9), ("ως προς", 9, 9), ("πάρω", 0, 18),
])
def test_scoped_greek_evidence(form, restored, completed):
    data = roundtrip.load()
    cohort = roundtrip.latest_cohort(data["records"]["el:" + form])
    assert cohort["complete"]
    assert (cohort["restored"], cohort["completed"]) == (restored, completed)
    assert cohort["timeouts"] == cohort["execution_errors"] == 0
    assert cohort["config"]["templates"] == ["{s}.", "Maybe {s} today.", "She told me that {s}."]
    assert cohort["config"]["seeds"] == [1, 2, 3]
    assert cohort["config"]["evaluation_policy"]["min_trials"] == 9
    assert cohort["config"]["evaluation_policy"]["thresholds"]["lt100m"] == 0.9
    assert roundtrip.rate(data["records"]["el:" + form]) == restored / completed
    assert roundtrip.status(data, "el", form) == ("pass" if restored == completed else "never")
    # The recorder's result must agree with the unchanged, separately supplied AI table.
    answers = fixture("roundtrip_judge/el_blind.json")
    for target in cohort["targets"]:
        assert target["restored"] == (roundtrip.norm(answers[target["converted"]]) == roundtrip.norm(target["source"]))
    counts = Counter(target["source"] for target in cohort["targets"])
    assert set(counts.values()) == {3}
    assert len(counts) == completed // 3


def test_parent_judge_table_is_unchanged():
    path = ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge/el_blind.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "9457b13a985fde33e5ec438f67a86b95c8c1e06e0d75534f4e8dbcc97fdb163f"


def test_failed_future_candidates_removed_and_labels_match_runtime():
    t = load("tessera_el_gate", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    bank = fixture("es_fr_tense.json")
    for entry in bank["entries"]:
        if entry["id"] not in {"find-fut-1s", "find-fut-goingto-1s", "take-fut-1s", "take-fut-goingto-1s"}:
            continue
        expected = ("acharei", "pt") if entry["id"].startswith("find-") else ("tomaré", "es")
        assert (entry["to"], entry["lang"]) == expected
        assert not {"βρω", "πάρω"} & {c["form"] for c in entry["candidates"]}
        for source in entry["from"]:
            # Full and going-to variants still convert; I'll take ties and stays EN.
            expected_surface = source if t.estimate_tokens(source) == t.estimate_tokens(entry["to"]) else entry["to"]
            assert t.apply_es_fr_tense(source) == expected_surface
        metrics = entry["metrics"]
        assert metrics["token_before"] == t.estimate_tokens(entry["from"][0])
        assert metrics["token_after"] == t.estimate_tokens(entry["to"])
        assert metrics["utf8_after"] == len(entry["to"].encode("utf-8"))
        assert any(e["id"] == entry["id"] + "-el" and "restored as I" in e["why_dropped"] for e in bank["examples_not_registered"])


def test_once_again_removed_but_passing_greek_and_latin_main_labels_remain():
    bank = fixture("pt_el_latin_phrases.json")
    entries = {e["id"]: e for e in bank["entries"]}
    assert "once-again-el-pt-la" not in entries
    assert entries["one-by-one-el"]["to"] == "ένα ένα"
    # #161 で la circa / pro / re が往復 0/9 で外れたため、#164 で 9/9 だった el 形が勝者になる。
    # in favor of は υπέρ (el) も 0/9 なのでエントリごと削除し英語のまま。
    assert entries["more-or-less-la-el"]["to"] == "πάνω κάτω"
    assert "in-favor-of-la-el" not in entries
    assert entries["with-respect-to-la-el"]["to"] == "ως προς"
    dropped_ids = {e["id"] for e in bank["examples_not_registered"]}
    assert {"more-or-less-la-el-circa", "in-favor-of-la-el-pro", "with-respect-to-la-el-re", "in-favor-of-el-hyper"} <= dropped_ids
    dropped = next(e for e in bank["examples_not_registered"] if e["id"] == "once-again-el-pt-la")
    assert dropped["to"] == "πάλι" and "restored as again" in dropped["why_dropped"]


# ──── es_roundtrip_gate ───────────────────────────────────────────

"""es (ge100m) adopted winners: independent blind AI round-trip (docs/es_roundtrip_20261109.md)."""


ES_FR = json.loads((FIX / "es_fr_tense.json").read_text(encoding="utf-8"))


JUDGE_es_roundtrip_gate = json.loads((FIX / "roundtrip_judge/es_blind.json").read_text(encoding="utf-8"))


REVERSED = [
    "viste",
    "dijiste",
    "hizo",
    "dijo",
    "pensamos",
    "this hizo",
    "this dijo",
    "these dijeron",
    "those dijeron",
    "who hizo",
    "who dijo",
    "which hizo",
    "which dijo",
    "which dijeron",
    "que hizo",
    "que dijo",
    "que dijeron",
    "vamos",
]


# Re-score (docs/roundtrip_rescore_20261110.md): fue's judge answer 'he went' is from[1] of its own
# entry; que va / ve / toma / dan matched with the owner-approved leading que≡that equivalence.
RESCUED = ["que va", "que ve", "que toma", "que dan", "fue"]


def _es_entries():
    return [e for bank in (BANK, ES_FR) for e in bank["entries"] if e.get("lang") == "es"]


def _short_forms():
    """Adopted es surfaces that are not English-identity leftovers."""
    return {e["to"] for e in _es_entries() if e["to"] != e["from"][0]}


def test_es_is_ge100m():
    assert "es" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_every_short_es_winner_passed_independent_blind_roundtrip():
    forms = _short_forms()
    # #164 relabeled the el-tagged ``tomaré`` rows to es after reversing el πάρω; that
    # es form was not in the es blind judge (#172). It was measured separately on
    # 2026-11-10 in designed contexts (es_pt_remaining_roundtrip_gate section below).
    # Listed explicitly so no other unmeasured es winner slips in.
    measured_in_context = {"tomaré"}
    assert measured_in_context <= forms
    assert all(rt.status(DATA, "es", f) == "pass" for f in measured_in_context)
    forms -= measured_in_context
    # pude: bare 0/9 kept in roundtrip.json (untouched); its reversal was undone by the
    # reaudit_b_4bot context round-trip (9/9), whose evidence lives in roundtrip_judge.
    context_undone = {"pude"}
    assert context_undone <= forms
    forms -= context_undone
    ctx = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge/reaudit_b_4bot_results.json").read_text(encoding="utf-8"))
    for form in context_undone:
        assert rt.status(DATA, "es", form) == "never"
        assert ctx["forms"][f"es:{form}"]["status"] == "pass" and ctx["forms"][f"es:{form}"]["reversal_undone"]
    # 100 → 99: #161 replaced es ``vendré`` (I will come) with la ``veniam``.
    # 99 → 98: ``vou sair`` (leave-fut-goingto-1s) is Portuguese; its label is now pt.
    # 98 → 103: the accepted-sources / que≡that re-score restored RESCUED.
    assert "vou sair" not in forms
    assert set(RESCUED) <= forms
    assert len(forms) == 103
    for form in forms:
        assert rt.status(DATA, "es", form) == "pass", form
        cohort = rt.latest_cohort(DATA["records"][rt.key("es", form)])
        assert cohort["complete"] and cohort["completed"] >= DATA["min_trials"]
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        for t in cohort["targets"]:
            assert t["converted"] in JUDGE_es_roundtrip_gate


@pytest.mark.parametrize("form", REVERSED)
def test_failed_es_forms_reversed(form):
    assert rt.status(DATA, "es", form) == "never"
    assert all(not (e.get("lang") == "es" and e["to"] == form) for e in _es_entries())


def test_pude_reversal_undone_entry_is_live():
    live = [e for e in ES_FR["entries"] if e["id"] == "could-past-1s"]
    assert len(live) == 1 and live[0]["to"] == "pude" and live[0]["lang"] == "es"
    assert not any(e["id"] == "could-past-1s" for e in ES_FR["examples_not_registered"])


def test_fue_entry_restored_after_rescore():
    restored = next(e for e in ES_FR["entries"] if e["id"] == "go-past-3s")
    assert (restored["to"], restored["lang"], restored["from"]) == ("fue", "es", ["she went", "he went"])
    assert not any(e["id"] == "go-past-3s" for e in ES_FR["examples_not_registered"])


@pytest.mark.parametrize("form,eid", [("vamos", "go-fut-1p")])
def test_es_fr_short_forms_recorded_as_not_registered(form, eid):
    dropped = next(e for e in ES_FR["examples_not_registered"] if e["id"] == eid and e["to"] == form)
    assert "0/9" in dropped["why_dropped"]
    # EN leftover kept in entries so tense_matrix does not adopt a next-language form
    identity = next(e for e in ES_FR["entries"] if e["id"] == eid)
    assert identity["lang"] == "es" and identity["to"] == identity["from"][0]


def test_roundtrip_enforced_langs_unchanged_es_roundtrip_gate():
    import tense_matrix as tm

    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    assert "es" not in tm.ROUNDTRIP_ENFORCED_LANGS


# ──── es_pt_remaining_roundtrip_gate ──────────────────────────────

"""es tomaré / pt acharei, logo, por isso: the adopted forms #161/#164 promoted without a
round-trip record, measured by independent blind judges, bare and in designed contexts
(docs/es_pt_remaining_roundtrip_20261110.md)."""


RJ = FIX / "roundtrip_judge"


JUDGE_PATH = RJ / "remaining_20261110_blind.json"


JUDGE_es_pt_remaining_roundtrip_gate = json.loads(JUDGE_PATH.read_text(encoding="utf-8"))


SNAPSHOT = json.loads((RJ / "remaining_20261110_sources.json").read_text(encoding="utf-8"))


CTX_JUDGE = json.loads((RJ / "remaining_20261110_ctx_blind.json").read_text(encoding="utf-8"))


CTX_SRC = json.loads((RJ / "remaining_20261110_ctx_sources.json").read_text(encoding="utf-8"))


MEANING = json.loads((RJ / "remaining_20261110_ctx_meaning.json").read_text(encoding="utf-8"))


KEYS = ["es:tomaré", "pt:acharei", "pt:logo", "pt:por isso"]


# key -> (bare exact, context exact distinct /9, meaning ref /9, final status)
EXPECTED = {"es:tomaré": (0, 9, 9, "pass"), "pt:acharei": (0, 9, 9, "pass"),
            "pt:logo": (0, 0, 9, "never"), "pt:por isso": (0, 0, 9, "never")}


KEPT = {"es_fr_tense": {"take-fut-1s": ("tomaré", "es"), "take-fut-goingto-1s": ("tomaré", "es"),
                        "find-fut-1s": ("acharei", "pt"), "find-fut-goingto-1s": ("acharei", "pt")}}


REVERSED_es_pt_remaining_roundtrip_gate = {"pt_el_latin_phrases": {"as-a-result-la-pt-el": "logo", "for-this-reason-la-pt": "por isso"}}


def read(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def _cohorts(key):
    rec = [c for c in DATA["records"][key]["cohorts"]]
    study = DATA.get("context_studies", {}).get("remaining_20261110", {}).get(key)
    return rec, study


def test_judges_frozen_and_cover_exactly_the_converted_sentences():
    assert hashlib.sha256(JUDGE_PATH.read_bytes()).hexdigest() == rem.JUDGE_SHA256
    converted = [cv for f in SNAPSHOT["forms"] for _, cv in rt.sentences(DATA, f["entry"]["from"][0], f["entry"]["to"])]
    assert list(JUDGE_es_pt_remaining_roundtrip_gate) == converted and len(converted) == 12
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
        assert t["response"] == JUDGE_es_pt_remaining_roundtrip_gate[t["converted"]]
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
    for name, ids in REVERSED_es_pt_remaining_roundtrip_gate.items():
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


# ──── fr_roundtrip_gate ───────────────────────────────────────────

"""fr (ge100m) adopted winners: independent blind AI round-trip (docs/fr_roundtrip_20261109.md)."""


JUDGE_fr_roundtrip_gate = json.loads((FIX / "roundtrip_judge/fr_blind.json").read_text(encoding="utf-8"))


REPORT = {c["src"]: c for c in json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]}


# prends / vins / vis / voulus / sus / avais su / ira (and es_fr arrivé) were reversed here
# first, then re-enabled by the 3bot in-context round-trip (docs/reaudit_a_3bot_roundtrip_20261110.md).
# pris / ont su / que dit / que ont voulu / que ont eu / que ont su were reversed here first, then
# restored by the re-score (docs/roundtrip_rescore_20261110.md).
REVERSED_TM = ["avoir voulu", "avoir eu", "avoir su"]


# es_fr take-past-1s (pris, re-score) and arrive-past-1s (arrivé, 3bot reaudit) are both restored.
RESTORED_ES_FR = {"take-past-1s": "pris", "arrive-past-1s": "arrivé"}


# fr forms re-enabled by a passing context cohort; roundtrip.json still holds their bare 0/9
# (essayé: no fr record), the context cohort lives in roundtrip_judge/reaudit_a_3bot_results.json
REAUDIT = {f for lang, f in reaudit.restored() if lang == "fr"}


# Re-score (docs/roundtrip_rescore_20261110.md): pris / ont su matched another official source of
# the same form; que dit / que ont voulu / que ont eu / que ont su matched with leading que≡that.
RESCUED_TM = ["pris", "ont su", "que dit", "que ont voulu", "que ont eu", "que ont su"]


# parity followers adopted again with their restored base (ont su: re-score; ira: 3bot reaudit)
PARITY_RESTORED = {"these have known": "these ont su", "those have known": "those ont su",
                   "this will go": "this ira"}


def _fr_forms() -> set[str]:
    return {e["to"] for bank in (BANK, ES_FR) for e in bank["entries"] if e["lang"] == "fr"}


def test_fr_is_ge100m():
    assert "fr" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_policy_scope_unchanged():
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    assert {f for lang, f in tm.ROUNDTRIP_REVERSED if lang == "fr"} == set(REVERSED_TM)


def test_every_fr_winner_passed_independent_blind_roundtrip():
    forms = _fr_forms()
    # 93 + 6 rescued + these / those ont su (parity) + 10 reaudit (incl. this ira, essayé)
    assert len(forms) == 111 and REAUDIT <= forms
    for form in forms - REAUDIT:
        assert rt.status(DATA, "fr", form) == "pass", form
        cohort = rt.latest_cohort(DATA["records"][rt.key("fr", form)])
        assert cohort["complete"] and cohort["completed"] >= DATA["min_trials"]
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        for t in cohort["targets"]:
            assert t["converted"] in JUDGE_fr_roundtrip_gate


def test_all_113_fr_forms_recorded():
    recs = [k for k in DATA["records"] if k.startswith("fr:")]
    assert len(recs) == 113
    st = [rt.status(DATA, "fr", DATA["records"][k]["form"]) for k in recs]
    assert st.count("pass") == 102 and st.count("never") == 11


@pytest.mark.parametrize("form", REVERSED_TM)
def test_failed_fr_forms_reversed(form):
    assert rt.status(DATA, "fr", form) == "never"
    assert form not in _fr_forms()


@pytest.mark.parametrize("eid,form", sorted(RESTORED_ES_FR.items()))
def test_es_fr_reversals_restored(eid, form):
    entry = next(e for e in ES_FR["entries"] if e["id"] == eid)
    assert (entry["to"], entry["lang"]) == (form, "fr")
    assert all(e["id"] != eid for e in ES_FR["examples_not_registered"])


@pytest.mark.parametrize("form", RESCUED_TM)
def test_rescued_fr_forms_adopted_again(form):
    assert rt.status(DATA, "fr", form) == "pass"
    assert form in _fr_forms()
    assert ("fr", form) not in tm.ROUNDTRIP_REVERSED


def test_es_fr_pris_restored_after_rescore():
    # judge restored 'I took' for Pris.; the cohort had been scored against 'you took' only
    restored = next(e for e in ES_FR["entries"] if e["id"] == "take-past-1s")
    assert (restored["to"], restored["lang"]) == ("pris", "fr")
    assert all(e["id"] != "take-past-1s" for e in ES_FR["examples_not_registered"])


@pytest.mark.parametrize("src,form", sorted(PARITY_RESTORED.items()))
def test_parity_followers_restored_with_base(src, form):
    assert rt.status(DATA, "fr", form) == "pass"
    assert any(src in e["from"] and e["to"] == form for e in BANK["entries"])


@pytest.mark.parametrize("src", ["I took", "I arrived"])
def test_restored_es_fr_sources_not_duplicated_by_matrix(src):
    # pris / arrivé live in es_fr_tense again; the matrix promotes no other candidate (e.g. de ``nahm``)
    assert all(src not in e["from"] for e in BANK["entries"])
    assert src not in REPORT or REPORT[src]["status"] in ("reject", "existing")
    assert tm.build()[0]["entries"] == BANK["entries"]


def test_reaudit_forms_adopted_on_the_context_cohort_only():
    assert REAUDIT == {"vis", "vins", "sus", "voulus", "prends", "avais su", "ira", "arrivé", "essayé"}
    res = json.loads(reaudit.RESULTS.read_text(encoding="utf-8"))["results"]
    for form in REAUDIT:
        key = "pt:essayé" if form == "essayé" else f"fr:{form}"
        assert res[key]["status"] == "pass" and res[key]["exact"] >= 6
        # gate-visible roundtrip.json is not rewritten by this study (owned by the 2bot audit)
        assert rt.status(DATA, "fr", form) == ("unverified" if form == "essayé" else "never")
    assert rt.status(DATA, "fr", "this ira") == "pass"
    assert any(e["from"] == ["this will go"] and e["to"] == "this ira" for e in BANK["entries"])


# ──── it_roundtrip_gate ───────────────────────────────────────────

"""it (ge100m) adopted winners: independent blind AI round-trip (docs/it_roundtrip_20261108.md)."""


PHRASES_it_roundtrip_gate = json.loads((FIX / "pt_el_latin_phrases.json").read_text(encoding="utf-8"))


JUDGE_it_roundtrip_gate = json.loads((FIX / "roundtrip_judge/it_blind.json").read_text(encoding="utf-8"))


def test_it_is_ge100m():
    assert "it" in DATA["ge100m_langs"] and DATA["thresholds"]["ge100m"] == 0.6


def test_every_it_winner_passed_independent_blind_roundtrip():
    forms = {e["to"] for bank in (BANK, PHRASES_it_roundtrip_gate) for e in bank["entries"] if e["lang"] == "it"}
    # 28 → 30: que sa / que dà passed the leading que≡that re-score (docs/roundtrip_rescore_20261110.md)
    assert {"que sa", "que dà"} <= forms
    assert len(forms) == 30
    for form in forms:
        assert rt.status(DATA, "it", form) == "pass", form
        cohort = rt.latest_cohort(DATA["records"][rt.key("it", form)])
        assert cohort["complete"] and cohort["completed"] >= DATA["min_trials"]
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        for t in cohort["targets"]:
            assert t["converted"] in JUDGE_it_roundtrip_gate


@pytest.mark.parametrize("form", ["ciao"])
def test_failed_it_forms_reversed(form):
    assert rt.status(DATA, "it", form) == "never"
    assert all(not (e["lang"] == "it" and e["to"] == form) for b in (BANK, PHRASES_it_roundtrip_gate) for e in b["entries"])


def test_ciao_recorded_as_not_registered():
    dropped = next(e for e in PHRASES_it_roundtrip_gate["examples_not_registered"] if e["id"] == "see-you-soon-it-pt-el")
    assert dropped["to"] == "ciao" and "0/9" in dropped["why_dropped"]


# ──── nl_roundtrip_gate ───────────────────────────────────────────

"""#29: nl (<100M speakers) tense-matrix forms are adopted only after an AI round-trip pass."""


BANK_nl_roundtrip_gate = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/tense_matrix.json").read_text(encoding="utf-8"))


JUDGE_nl_roundtrip_gate = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge/nl_blind.json").read_text(encoding="utf-8"))


def test_nl_is_enforced_and_lt100m():
    assert "nl" in tm.ROUNDTRIP_ENFORCED_LANGS and "nl" not in DATA["ge100m_langs"]
    assert DATA["thresholds"]["lt100m"] == 0.9


def test_every_nl_bank_winner_passed_roundtrip():
    nl = [e for e in BANK_nl_roundtrip_gate["entries"] if e["lang"] == "nl"]
    assert nl
    for e in nl:
        assert rt.status(DATA, "nl", e["to"]) == "pass", e
        assert rt.rate(DATA["records"][rt.key("nl", e["to"])]) >= 0.9


@pytest.mark.parametrize("form", ["nam", "dacht", "zei", "ging", "wil", "zagen", "namen", "wilden",
                                  "who zei", "these deden"])
def test_failed_forms_not_adopted(form):
    assert rt.status(DATA, "nl", form) in ("fail", "never")
    assert all(not (e["lang"] == "nl" and e["to"] == form) for e in BANK_nl_roundtrip_gate["entries"])


def test_gate_is_per_lang_not_per_form():
    # nl denkt failed, de denkt (same spelling) must survive
    assert rt.status(DATA, "nl", "denkt") != "pass"
    he = next(e for e in BANK_nl_roundtrip_gate["entries"] if e["from"][0] == "he thinks")
    assert (he["to"], he["lang"]) == ("denkt", "de")


def test_nl_records_complete():
    nl_keys = {k for k in DATA["records"] if k.startswith("nl:")}
    assert all(DATA["records"][k]["trials"] >= DATA["min_trials"] for k in nl_keys)


def test_replay_harness_matches_judge_file():
    # reproducible: replay restorer returns the recorded blind judge answer
    conv = "Maybe kom today."
    p = subprocess.run([sys.executable, str(ROOT / "scripts/roundtrip_replay.py"), "nl"],
                       input=rt.PROMPT.format(c=conv), capture_output=True, text=True, check=True)
    assert p.stdout.strip() == JUDGE_nl_roundtrip_gate[conv] == "Maybe I come today."


def test_bank_is_fresh():
    assert tm.main(["--check"]) == 0


@pytest.mark.parametrize("fixture", ["es_fr_tense.json", "zh_de_phrases.json"])
def test_nl_winners_outside_tense_matrix_passed(fixture):
    bank = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures" / fixture).read_text(encoding="utf-8"))
    nl = [entry for entry in bank["entries"] if entry["lang"] == "nl"]
    assert nl
    for entry in nl:
        form = entry["to"]
        assert rt.status(DATA, "nl", form) == "pass", entry
        cohort = rt.latest_cohort(DATA["records"][rt.key("nl", form)])
        assert cohort is not None and cohort["complete"]
        assert cohort["judge_provenance"]["kind"] == "independent_blind_judge"
        assert cohort["completed"] >= DATA["min_trials"]
        assert cohort["config"]["seeds"] == [1, 2, 3]
        assert cohort["config"]["templates"] == DATA["templates"]
        for target in cohort["targets"]:
            assert rt.norm(JUDGE_nl_roundtrip_gate[target["converted"]]) == rt.norm(target["source"])


# ──── pt_roundtrip_gate ───────────────────────────────────────────

"""Frozen independent pt judge, any-source evidence, and narrowly scoped reversals."""


JUDGE_pt_roundtrip_gate = FIX / "roundtrip_judge/pt_blind.json"


SNAPSHOT_pt_roundtrip_gate = json.loads((FIX / "roundtrip_judge/pt_sources.json").read_text(encoding="utf-8"))


SOURCES = SNAPSHOT_pt_roundtrip_gate["forms"]


JUDGE_SHA = "d161afaef0b6f8dea08c5ff5babb69f349a7baea60f697ddaf5e85b36dd369df"


BASE_OTHER_LANG_HASHES = {
    # after #172 (es reversals) + it que sa / que dà restored by the que≡that re-score (2026-11-10)
    "tense_matrix": "d962f1bb29cee5937def2bf27f4b168409ae5274935491ed6d391f1c6672b18b",
    "es_fr_tense": "5c4d9e525a8df17eef85c4128698ccd65c5d4f4a4d10610a0d8fc0ef97c4a045",  # after #164 (el reversals) + #161 (la entries / el υπέρ reversal)
    # after #164 (el reversals) + #161 (la entries / el υπέρ reversal) + la among-others-la restored
    # by the form-level re-score (owner-approved, docs/roundtrip_rescore_20261110.md)
    "pt_el_latin_phrases": "cee068f80af710eb80028c67809339e7e27ac8c59e6bbd4ca6886bd4bb795ddc",
    "pt_el_latin_tense": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
}


# pt forms re-enabled on a passing in-context cohort kept outside roundtrip.json
# (docs/reaudit_a_3bot_roundtrip_20261110.md); their pt record is still the bare 0/9.
REAUDIT_pt_roundtrip_gate = reaudit_a.restored()


def test_judge_is_unchanged_and_covers_official_converted_sentences():
    assert hashlib.sha256(JUDGE_pt_roundtrip_gate.read_bytes()).hexdigest() == JUDGE_SHA
    judge = json.loads(JUDGE_pt_roundtrip_gate.read_text(encoding="utf-8"))
    data = rt.load()
    converted = {cv for f in SOURCES for _, cv in rt.sentences(data, f["entry"]["from"][0], f["entry"]["to"])}
    assert len(SOURCES) == 270 and len(converted) == len(judge) == 810
    assert set(judge) == converted
    assert sum(len(f["source_entries"]) for f in SOURCES) == 404
    assert sum(len(f["accepted_sources"]) > 1 for f in SOURCES) == 65
    assert sum(len(f["source_entries"]) > 1 for f in SOURCES) == 63


def test_each_receipt_recomputes_from_immutable_judge_without_inflated_trials():
    data = rt.load()
    judge = json.loads(JUDGE_pt_roundtrip_gate.read_text(encoding="utf-8"))
    statuses = []
    for f in SOURCES:
        rec = data["records"][f["key"]]
        cohort = rt.latest_cohort(rec)
        assert cohort is not None and cohort["complete"]
        assert cohort["completed"] == cohort["attempted"] == 9
        assert rec["trials"] == sum(c["completed"] for c in rec["cohorts"])
        assert len(cohort["targets"]) == 9
        assert cohort["config"]["source_acceptance"] == "any-official-source-v1"
        assert cohort["judge_provenance"]["judge_sha256"] == JUDGE_SHA
        for target in cohort["targets"]:
            assert target["response"] == judge[target["converted"]]
            expected = []
            for source in f["accepted_sources"]:
                expected += [en for en, cv in rt.sentences(data, source, f["entry"]["to"]) if cv == target["converted"]]
            assert set(target["accepted_sources"]) == set(expected)
            # latest cohort = 2026-11-10 re-score with the owner-approved leading que≡that equivalence
            assert cohort["config"]["marker_equivalence"] == rt.MARKER_EQUIVALENCE
            equivalent = [v for en in target["accepted_sources"] for v in rt.leading_que_that(en, data["templates"])]
            assert target["equivalent_sources"] == equivalent
            restored = any(rt.norm(target["response"]) == rt.norm(en) for en in expected + equivalent)
            assert target["restored"] is restored
        statuses.append(rt.status(data, "pt", f["entry"]["to"]))
    # 210 / 60 → 212 / 58: que acha / que vem pass with leading que≡that
    assert statuses.count("pass") == 212 and statuses.count("never") == 58
    # other language cohorts (it / zh from #168 / #169, ...) share run_history
    latest = [r for r in data["run_history"] if r["config"].get("only_lang") == "pt"][-1]
    assert latest["completed"] == latest["attempted"] == latest["scheduled"] == 2430
    assert latest["duplicate_targets"] == 0


@pytest.mark.parametrize("name", BASE_OTHER_LANG_HASHES)
def test_existing_other_language_winners_and_losing_pt_candidates_unchanged(name):
    # es/fr/de have their own independently verified reversals (#172–174).
    # Preserve every other language and its candidates from main after #168/#169.
    entries = [e for e in read(name)["entries"] if e["lang"] not in {"pt", "es", "fr", "de"}]
    canonical = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode()
    assert hashlib.sha256(canonical).hexdigest() == BASE_OTHER_LANG_HASHES[name]


@pytest.mark.parametrize("name", BASE_OTHER_LANG_HASHES)
def test_only_failed_pt_entries_removed_no_unmeasured_promotions(name):
    data = rt.load()
    expected = {
        e["id"]: f["entry"]["to"] for f in SOURCES for e in f["source_entries"]
        if e["file"] == f"SentenceCalibratedMosaic/fixtures/{name}.json"
        and (rt.status(data, "pt", f["entry"]["to"]) == "pass" or ("pt", f["entry"]["to"]) in REAUDIT_pt_roundtrip_gate)
    }
    got = {e["id"]: e["to"] for e in read(name)["entries"] if e["lang"] == "pt"}
    # #161 (la reversal of ergo / ideo) and #164 (el βρω reversal) promoted pt runner-ups
    # before the pt round-trip (#171) existed; they are NOT in the pt blind judge. Measured
    # separately on 2026-11-10: acharei passed in designed contexts (kept), logo / por isso
    # failed (reversed). Listed explicitly so no other unmeasured pt promotion slips in.
    measured_later = {"es_fr_tense": {"find-fut-1s": "acharei", "find-fut-goingto-1s": "acharei"}}
    for k, v in measured_later.get(name, {}).items():
        assert got.pop(k) == v and rt.status(data, "pt", v) == "pass"
    unmeasured = {
        # mislabelled es until relabelled pt; surface measured 9/9 only under es:vou sair
        "es_fr_tense": {"leave-fut-goingto-1s": "vou sair"},
    }
    # Passing pt forms removed later for a reason other than their own round-trip:
    # do-it-past-1s fiz never restores "it". (this virá was removed by #178 as a follower of
    # reversed virá and is adopted again since #181 re-enabled virá.)
    removed_later = {"pt_el_latin_tense": {"do-it-past-1s"}}
    for k, v in unmeasured.get(name, {}).items():
        assert got.pop(k) == v
    for k in removed_later.get(name, ()):
        assert expected.pop(k) and k not in got
    # Bare 0/9 in roundtrip.json (untouched); reversal undone by the reaudit_b_4bot context
    # round-trip (roundtrip_judge/reaudit_b_4bot_results.json).
    context_undone = {"pt_el_latin_phrases": {"blood-pressure-el-pt": "tensão"}}
    if name in context_undone:
        ctx = json.loads((FIX / "roundtrip_judge/reaudit_b_4bot_results.json").read_text(encoding="utf-8"))["forms"]
        for k, v in context_undone[name].items():
            assert got.pop(k) == v
            assert rt.status(data, "pt", v) == "never"
            assert ctx[f"pt:{v}"]["status"] == "pass" and ctx[f"pt:{v}"]["reversal_undone"]
    assert got == expected


def test_generated_reversals_are_per_form_and_leave_empty_english_cells():
    assert tm.ROUNDTRIP_ENFORCED_LANGS == frozenset({"nl"})
    data = rt.load()
    failed = {
        ("pt", f["entry"]["to"]) for f in SOURCES
        if any(e["file"].endswith("/tense_matrix.json") for e in f["source_entries"])
        and rt.status(data, "pt", f["entry"]["to"]) != "pass"
        and ("pt", f["entry"]["to"]) not in REAUDIT_pt_roundtrip_gate
    }
    # ROUNDTRIP_REVERSED is a union across languages (it from #168, ...); pt part only here.
    assert {r for r in tm.ROUNDTRIP_REVERSED if r[0] == "pt"} == failed
    cells = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))["cells"]
    pt_rev = {f for _, f in failed}
    reversed_cells = [c for c in cells if set(c.get("roundtrip_reversed") or ()) & pt_rev]
    # 63 -> 62: virá (it will come) re-enabled; 62 -> 60: que acha / que vem cells (re-score)
    assert len(reversed_cells) == 60
    assert all(c["status"] == "reject" and c["candidates"] == [] for c in reversed_cells)


# es_fr_tense 3 -> 2: essayé (pt label, French form) re-enabled as fr by the 3bot reaudit
# pt_el_latin_phrases 4 → 6: logo / por isso reversed on 2026-11-10 (0/9 bare and in context);
# 6 → 5: tensão reversal undone by the reaudit_b_4bot context round-trip.
@pytest.mark.parametrize("name,removed", [("es_fr_tense", 2), ("pt_el_latin_phrases", 5), ("pt_el_latin_tense", 1)])
def test_quarantined_failure_evidence_and_sources_reserved(name, removed):
    data = read(name)
    reversed_entries = [e for e in data["examples_not_registered"] if e.get("roundtrip_reversed")]
    assert len(reversed_entries) == removed
    assert all(e["lang"] == "pt" and "0/9" in e["why_dropped"] and "actual restorations" in e["why_dropped"] for e in reversed_entries)
    if name != "pt_el_latin_phrases":
        from tests._helpers import load
        talk = load("pt_source_guard", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
        reserved = tm._existing_sources(talk)
        assert all(s.lower() in reserved for e in reversed_entries for s in e["from"])


def test_alt_only_passes_are_transparently_documented():
    data = rt.load()
    alternate = []
    marker = []
    strict = total = 0
    for f in SOURCES:
        c = data["records"][f["key"]]["cohorts"][-1]
        first = sum(t["first_source_match"] for t in c["targets"])
        strict += first
        total += c["restored"]
        if any(t["matched_via_marker_equivalence"] for t in c["targets"]):
            marker.append(f["entry"]["to"])
        elif c["restored"] >= 6 and first < 6:
            alternate.append(f["entry"]["to"])
    # 1890 → 1908: que acha / que vem (9 + 9) pass only via leading que≡that (2026-11-10 re-score)
    assert sorted(marker) == ["que acha", "que vem"]
    assert len(alternate) == 21 and strict == 1701 and total == 1908
    results = (FIX / "roundtrip_judge/pt_results.md").read_text(encoding="utf-8")
    assert all(f"`{form}`" in results for form in alternate)


def test_live_runner_uses_its_own_checkout_from_another_repo(tmp_path, monkeypatch):
    from http.server import HTTPServer
    from threading import Thread
    import live_roundtrip
    from tests.test_llama_cmd import _Handler

    checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    caller = tmp_path / "other project"
    caller.mkdir()
    monkeypatch.chdir(caller)
    subprocess.run(["git", "init", "-q"], check=True)
    Path("receipt.json").write_text("{}")
    monkeypatch.setattr(sys, "argv", ["live_roundtrip", "--output", "report.json",
                                     "--model-receipt", "receipt.json", "--runtime", "test server"])
    monkeypatch.setattr(rt, "load", lambda: {
        "templates": ["{s}."], "seeds": [1, 2, 3], "min_trials": 3, "records": {},
        "thresholds": {"lt100m": 0.9, "ge100m": 0.6}, "ge100m_langs": []})
    monkeypatch.setattr(tm, "build", lambda: ({"entries": [{"lang": "nl", "to": "x", "from": ["none"]}]},))
    with HTTPServer(("127.0.0.1", 0), _Handler) as server:
        monkeypatch.setenv("LLAMA_URL", f"http://127.0.0.1:{server.server_port}/v1/chat/completions")
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            assert live_roundtrip.main() == 0
        finally:
            server.shutdown()
            worker.join()
    result = json.loads(Path("report.json").read_text())
    assert result["checkout"] == checkout
    assert result["run"]["completed"] == 3
    assert all(t["response"] == "none" for t in result["forms"]["nl:x"]["trials"])


def test_any_source_run_keeps_first_source_identity_and_judge_response(monkeypatch):
    data = {"templates": ["{s}."], "seeds": [1, 2, 3], "min_trials": 3,
            "thresholds": {"lt100m": 0.9, "ge100m": 0.6}, "ge100m_langs": ["pt"], "records": {}}
    entry = {"lang": "pt", "from": ["he had seen"], "to": "vira"}
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="She had seen.\n", returncode=0))
    rt.run(data, "fake", entries=[entry], accepted_sources={"pt:vira": ["he had seen", "she had seen"]})
    c = rt.latest_cohort(data["records"]["pt:vira"])
    assert c["completed"] == c["restored"] == 3
    assert all(t["source"] == "He had seen." and t["response"] == "She had seen." and t["matched_via_alternate"] for t in c["targets"])
    forged = copy.deepcopy(c)
    forged["targets"][0]["response"] = "She saw."
    assert not rt._valid_cohort(forged)
    default = {**data, "records": {}, "run_history": []}
    rt.run(default, "fake", entries=[entry])
    assert default["records"]["pt:vira"]["restored"] == 0


@pytest.mark.parametrize("invalid", [{"pt:x": []}, {"pt:x": "not a list"}, {"pt:x": [None]}])
def test_invalid_alternate_sources_do_not_execute_or_mutate(monkeypatch, invalid):
    data = {"templates": ["{s}."], "seeds": [1], "records": {}}
    before = copy.deepcopy(data)
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **kw: pytest.fail("must not execute"))
    with pytest.raises(ValueError, match="accepted_sources"):
        rt.run(data, "fake", entries=[], accepted_sources=invalid)
    assert data == before


def test_evidence_is_loaded_once_per_build_cache(monkeypatch):
    data = rt.load()
    calls = []
    monkeypatch.setattr(rt, "load", lambda: calls.append(1) or data)
    monkeypatch.setattr(tm, "_RT_DATA", {})
    tm._rt_status("denkt", "nl")
    tm._rt_status("denkt", "nl")
    tm._rt_ok("denkt", "nl")
    assert len(calls) == 1


@pytest.mark.parametrize("remove_hash", [False, True])
@pytest.mark.parametrize("tamper_response", [False, True])
def test_any_source_receipt_cannot_downgrade_to_single_source(remove_hash, tamper_response):
    cohort = copy.deepcopy(rt.load()["records"][SOURCES[0]["key"]]["cohorts"][-1])
    assert rt._valid_cohort(cohort)
    if tamper_response:
        cohort["targets"][0]["response"] = "Unrelated synthetic tampering probe."
    del cohort["config"]["source_acceptance"]
    if remove_hash:
        del cohort["config"]["accepted_sources_sha256"]
    assert not rt._valid_cohort(cohort)


@pytest.mark.parametrize("field", ["accepted_sources", "first_source_match", "matched_source", "matched_via_alternate"])
def test_single_source_receipt_rejects_any_source_fields(monkeypatch, field):
    data = {"templates": ["{s}."], "seeds": [1], "min_trials": 1,
            "thresholds": {"lt100m": 0.9, "ge100m": 0.6}, "ge100m_langs": ["pt"], "records": {}}
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="He had seen.", returncode=0))
    rt.run(data, "fake", entries=[{"lang": "pt", "from": ["he had seen"], "to": "vira"}])
    cohort = rt.latest_cohort(data["records"]["pt:vira"])
    assert rt._valid_cohort(cohort)
    cohort["targets"][0][field] = None
    assert not rt._valid_cohort(cohort)


def test_single_source_receipt_rejects_orphan_hash(monkeypatch):
    data = {"templates": ["{s}."], "seeds": [1], "min_trials": 1,
            "thresholds": {"lt100m": 0.9, "ge100m": 0.6}, "ge100m_langs": ["pt"], "records": {}}
    monkeypatch.setattr(rt.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="He had seen.", returncode=0))
    rt.run(data, "fake", entries=[{"lang": "pt", "from": ["he had seen"], "to": "vira"}])
    cohort = rt.latest_cohort(data["records"]["pt:vira"])
    assert rt._valid_cohort(cohort)
    cohort["config"]["accepted_sources_sha256"] = "0" * 64
    assert not rt._valid_cohort(cohort)


# ──── zh_roundtrip_gate ───────────────────────────────────────────

"""Scoped Chinese (zh) round-trip evidence for the 62 labelled zh_de_phrases winners."""


# (form, entry id, restored, completed, runtime_pair_loaded on main 84e5dca)
RESULTS = [
    ('多谢', 'thanks-zh', 0, 9, True),
    ('早', 'morning-zh', 9, 9, False),
    ('再见', 'later-zh', 0, 9, False),
    ('晚安', 'night-zh', 9, 9, False),
    ('稍等', 'wait-zh', 0, 9, False),
    ('明白', 'understand-zh', 0, 9, False),
    ('几点', 'time-zh', 0, 9, True),
    ('明天见', 'tomorrow-zh', 9, 9, False),
    ('当然', 'course-zh', 9, 9, False),
    ('高速', 'high-speed-zh', 9, 9, True),  # re-score: another official source of the form
    ('短期', 'short-term-zh', 9, 9, False),  # re-score: another official source of the form
    ('绿茶', 'green-tea-zh', 9, 9, False),
    ('红茶', 'black-tea-zh', 9, 9, False),
    ('驾照', 'fuehrerschein', 0, 9, False),
    ('警局', 'polizeiwache', 9, 9, False),
    ('邮局', 'postamt', 9, 9, False),
    ('血压', 'blutdruck', 9, 9, False),
    ('心脏病', 'herzinfarkt', 0, 9, False),
    ('操作系统', 'betriebssystem', 9, 9, False),
    ('餐厅', 'eetkamer', 0, 9, False),
    ('高中', 'high-school-zh', 9, 9, False),
    ('初中', 'middle-school-zh', 9, 9, False),
    ('小学', 'primary-school-zh', 9, 9, False),  # re-score: another official source of the form
    ('地铁站', 'subway-zh', 9, 9, False),
    ('客厅', 'living-room-zh', 9, 9, False),
    ('限速', 'speed-limit-zh', 9, 9, False),
    ('人权', 'human-rights-zh', 9, 9, False),
    ('社媒', 'social-media-zh', 9, 9, False),
    ('开源', 'open-source-zh', 9, 9, True),
    ('酱油', 'soy-sauce-zh', 9, 9, False),
    ('炒饭', 'fried-rice-zh', 9, 9, False),
    ('高铁', 'hsr-zh', 9, 9, True),  # re-score: another official source of the form
    ('便利店', 'convenience-zh', 9, 9, False),
    ('商场', 'mall-zh', 9, 9, False),
    ('百货', 'dept-store-zh', 9, 9, False),
    ('书店', 'bookstore-zh', 0, 9, False),
    ('药店', 'drugstore-zh', 0, 9, False),
    ('超市', 'supermarket-zh', 0, 9, False),
    ('名片', 'biz-card-zh', 9, 9, False),
    ('出差', 'biz-trip-zh', 9, 9, False),
    ('邮箱', 'email-zh', 0, 9, False),
    ('电话', 'phone-zh', 0, 9, True),
    ('U盘', 'flash-drive-zh', 0, 9, False),
    ('源码', 'source-code-zh', 9, 9, False),
    ('界面', 'ui-zh', 0, 9, False),
    ('前端', 'frontend-zh', 0, 9, False),
    ('全栈', 'fullstack-zh', 9, 9, True),
    ('知识库', 'kb-zh', 9, 9, False),
    ('向量库', 'vecdb-zh', 0, 9, False),
    ('大模型', 'llm-zh', 0, 9, True),
    ('思维链', 'cot-zh', 9, 9, True),
    ('微调', 'finetune-zh', 9, 9, True),  # re-score: another official source of the form
    ('限流', 'ratelimit-zh', 0, 9, False),
    ('高可用', 'ha-zh', 9, 9, False),
    ('灾备', 'dr-zh', 9, 9, False),
    ('技术债', 'techdebt-zh', 9, 9, False),
    ('持续集成', 'ci-zh', 9, 9, False),
    ('往返', 'roundtrip-zh', 9, 9, False),
    ('邮编', 'postal-zh', 9, 9, False),
    ('截图', 'screenshot-zh', 0, 9, False),
    ('黑箱', 'blackbox-zh', 9, 9, False),
    ('白皮书', 'whitepaper-zh', 9, 9, False),
]


# Bare 0/9 forms whose reversal the reaudit_b_4bot context round-trip undid (roundtrip.json untouched;
# evidence in roundtrip_judge/reaudit_b_4bot_results.json).
CONTEXT_UNDONE = {"understand-zh", "herzinfarkt", "eetkamer", "phone-zh"}


def test_parent_judge_table_is_unchanged_zh_roundtrip_gate():
    path = ROOT / "SentenceCalibratedMosaic/fixtures/roundtrip_judge/zh_blind.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "bd799e8beb775359b3c85ef109996aa0e4d98c51bf4b671b3aa90722814464a8"
    assert len(json.loads(path.read_text(encoding="utf-8"))) == 186


def test_counts():
    assert len(RESULTS) == len({r[0] for r in RESULTS}) == 62
    assert sum(r[3] for r in RESULTS) == 558
    # 37 → 42 / 3 → 6 after the accepted-sources re-score (docs/roundtrip_rescore_20261110.md)
    assert sum(r[2] == r[3] for r in RESULTS) == 42
    assert sum(r[4] for r in RESULTS) == 10
    assert sum(r[4] and r[2] == r[3] for r in RESULTS) == 6


@pytest.mark.parametrize("form,eid,restored,completed,loaded", RESULTS)
def test_scoped_zh_evidence(form, eid, restored, completed, loaded):
    data = roundtrip.load()
    rec = data["records"]["zh:" + form]
    cohort = roundtrip.latest_cohort(rec)
    assert cohort["complete"]
    assert (cohort["restored"], cohort["completed"]) == (restored, completed)
    assert cohort["timeouts"] == cohort["execution_errors"] == 0
    assert cohort["config"]["templates"] == ["{s}.", "Maybe {s} today.", "She told me that {s}."]
    assert cohort["config"]["seeds"] == [1, 2, 3]
    assert cohort["config"]["normalization"] == "norm-nfc-v1"
    assert cohort["config"]["evaluation_policy"]["min_trials"] == 9
    assert cohort["config"]["evaluation_policy"]["thresholds"]["ge100m"] == 0.6
    assert "zh" in cohort["config"]["evaluation_policy"]["ge100m_langs"]
    assert roundtrip.status(data, "zh", form) == ("pass" if restored / completed >= 0.6 else "never")
    answers = fixture("roundtrip_judge/zh_blind.json")
    for target in cohort["targets"]:
        # the latest cohort is the accepted-sources re-score: any official source of the form counts
        accepted = target.get("accepted_sources", [target["source"]]) + target.get("equivalent_sources", [])
        assert target["restored"] == any(roundtrip.norm(answers[target["converted"]]) == roundtrip.norm(s) for s in accepted)
    assert set(Counter(t["source"] for t in cohort["targets"]).values()) == {3}
    bank = fixture("zh_de_phrases.json")
    live = {e["id"]: e for e in bank["entries"]}
    dropped = {e["id"]: e for e in bank.get("examples_not_registered", [])}
    if restored == completed or eid in CONTEXT_UNDONE:
        assert live[eid]["to"] == form and live[eid]["lang"] == "zh"
        if eid in CONTEXT_UNDONE:
            assert eid not in dropped
            ctx = fixture("roundtrip_judge/reaudit_b_4bot_results.json")["forms"][f"zh:{form}"]
            assert ctx["status"] == "pass" and ctx["reversal_undone"]
    else:
        assert eid not in live
        assert dropped[eid]["to"] == form and "restored as" in dropped[eid]["why_dropped"]


def test_runtime_pairs_after_gate():
    t = load("mosaic_zh_gate", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    zh_entry_forms = {e["to"] for e in fixture("zh_de_phrases.json")["entries"] if e["lang"] == "zh"}
    loaded = {r for _, r, lg in t.zh_de_phrase_pairs() if lg == "zh"} & zh_entry_forms
    # 电话 (phone number) is back via the reaudit_b_4bot context round-trip.
    # + 高速 / 高铁 / 微调 restored by the accepted-sources re-score (短期 / 小学 are not loaded at runtime)
    assert loaded == {"开源", "全栈", "思维链", "电话", "高速", "高铁", "微调"}


def test_non_zh_entries_unchanged():
    """de / en / nl entries (incl. those carrying losing zh candidates) are byte-identical to main 84e5dca,
    minus the three de entries reversed by the de round-trip (#174: Tankstelle, Parkplatz, wenn)."""
    n = [e for e in fixture("zh_de_phrases.json")["entries"] if e["lang"] != "zh"]
    assert len(n) == 22
    blob = json.dumps(n, ensure_ascii=False, sort_keys=True).encode()
    assert hashlib.sha256(blob).hexdigest() == "8b00a966355899c7633af1af5fe4f91be11d5e86a2cb72a7d5acc2ff78b9def9"
