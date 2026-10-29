"""Person × tense matrix bank (scripts/tense_matrix.py) — runtime + guards."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
REPORT = json.loads((ROOT / "docs/tense_matrix_report.json").read_text(encoding="utf-8"))
ENTRIES = BANK["entries"]
CELLS = REPORT["cells"]


def _t():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def test_generator_outputs_up_to_date():
    r = subprocess.run(
        [sys.executable, "scripts/tense_matrix.py", "--check"], cwd=ROOT, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_matrix_covers_all_subjects_and_tenses():
    subs = {c["subject"] for c in CELLS}
    tenses = {c["tense"] for c in CELLS}
    for s in ("1s", "2", "3s-he", "3s-she", "3s-it", "1p", "3p", "dem-this", "dem-that",
              "dem-these", "dem-those", "rel-who-sg", "rel-who-pl", "rel-which-sg", "rel-which-pl"):
        assert s in subs
    assert tenses == {"pres", "fut", "past", "perf", "futperf", "pluperf", "presprog", "pastprog", "futprog"}
    assert {c["status"] for c in CELLS} <= {"adopt", "existing", "reject"}
    assert all(c.get("reason") for c in CELLS if c["status"] == "reject")
    assert sum(c["status"] == "adopt" for c in CELLS) == len(ENTRIES)


@pytest.mark.parametrize("e", ENTRIES, ids=[e["id"] for e in ENTRIES])
def test_matrix_to_is_runtime_winner_and_shrinks(e):
    t = _t()
    for src in e["from"][:1]:
        out = t.apply_es_fr_tense(src)
        assert out == e["to"], (src, out)
        assert t.estimate_tokens(out) < t.estimate_tokens(src)
        assert len(out.encode()) < len(src.encode())
        assert t.apply_es_fr_tense(src) == out  # deterministic
        if e["subject"].startswith(("dem-", "rel-")):
            assert out.split(" ", 1)[0].lower() == src.split(" ", 1)[0].lower()


@pytest.mark.parametrize(
    "s",
    [
        "his will to go", "the will to go is strong", "That said, we left.", "this saw cuts",
        "he does not go", "he had eaten", "he will have eaten", "that is going well",
        "he is going to see", "who will go", "that will go", "which will go",
        "the good will he had", "a will to win", "those saw blades",
    ],
)
def test_negative_no_misfire(s):
    assert _t().apply_es_fr_tense(s) == s


@pytest.mark.parametrize(
    ("s", "want"),
    [
        ("This has gone well", "This foi well"),
        ("People who are going home", "People who van home"),
        ("I'm going to buy it", "compraré it"),
    ],
)
def test_subject_kept_and_goingto(s, want):
    assert _t().apply_es_fr_tense(s) == want


def test_second_person_only_true_2nd_forms():
    two = [c for c in CELLS if c["subject"] == "2" and c["status"] == "adopt"]
    assert two and all(c["number"] in ("2sg-tú", "2pl-vosotros/vous") for c in two)
    # usted would win more cells, but collapses into 3sg after subject drop.
    ust = Counter(c["usted_style_best"]["number"] for c in CELLS if "usted_style_best" in c)
    assert ust["2sg-usted"] > ust["2sg-tú"]


def test_no_token_increase_on_sentences():
    t = _t()
    for c in CELLS:
        s = f"{c['src']} today."
        assert t.estimate_tokens(t.apply_es_fr_tense(s)) <= t.estimate_tokens(s)
