"""Scoped Greek round-trip evidence and runtime bank regressions."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import roundtrip
from tests._helpers import load


def fixture(name):
    return json.loads((ROOT / "TesseraTalk/fixtures" / name).read_text(encoding="utf-8"))


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
    path = ROOT / "TesseraTalk/fixtures/roundtrip_judge/el_blind.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == "9457b13a985fde33e5ec438f67a86b95c8c1e06e0d75534f4e8dbcc97fdb163f"


def test_failed_future_candidates_removed_and_labels_match_runtime():
    t = load("tessera_el_gate", "TesseraTalk/tessera_talk.py")
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
    assert entries["more-or-less-la-el"]["to"] == "circa"
    assert entries["in-favor-of-la-el"]["to"] == "pro"
    assert entries["with-respect-to-la-el"]["to"] == "re"
    dropped = next(e for e in bank["examples_not_registered"] if e["id"] == "once-again-el-pt-la")
    assert dropped["to"] == "πάλι" and "restored as again" in dropped["why_dropped"]
