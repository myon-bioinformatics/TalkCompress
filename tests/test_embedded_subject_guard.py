"""Pro-drop only at clause start: embedded-clause subjects are never lost."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "TesseraTalk/fixtures/tense_matrix.json").read_text(encoding="utf-8"))
SUBJ = {"i", "you", "he", "she", "it", "we", "they"}
MAINS = ["I think", "She said", "We know", "They hope"]
CONNECTORS = ["that", "which", "who", "if", "when", "because", "", "and"]


def _t():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def _embedded_sources():
    seen = {}
    for e in BANK["entries"]:
        for src in e["from"]:
            subj = re.split(r"['’ ]", src, maxsplit=1)[0].lower()
            if subj in SUBJ:
                seen.setdefault((subj, e["tense"]), src)
    return sorted(seen.items())


EMB = _embedded_sources()


def test_sweep_covers_all_subjects_and_many_tenses():
    assert {s for (s, _), _src in EMB} == SUBJ
    assert len({t for (_, t), _src in EMB}) >= 8


@pytest.mark.parametrize("main", MAINS)
@pytest.mark.parametrize("conn", CONNECTORS)
def test_embedded_subject_never_lost(main, conn):
    t = _t()
    for (subj, _tense), src in EMB:
        lead = f"{main} {conn} ".replace("  ", " ") if conn else f"{main} "
        out = t.apply_es_fr_tense(lead + src)
        tail = out.split(" ", 2)[-1] if conn else out
        head = src.split(" ", 1)[0]
        # you is kept as its 1-char surface U (apply_you_u), never dropped.
        heads = (head, "U") if head.lower() == "you" else (head,)
        assert any(
            re.search(rf"(?<![A-Za-z']){re.escape(h)}(?![A-Za-z'])", out, re.I) for h in heads
        ), (lead + src, out)
        assert tail


def test_regression_examples():
    t = _t()
    assert t.apply_es_fr_tense("I think that he is going") == "denk that he is going"
    assert t.apply_es_fr_tense("I know he is going") == "sé he is going"
    assert t.apply_es_fr_tense("he is going") == "está indo"
    assert t.apply_es_fr_tense("Yes. He is going") == "Yes. está indo"
    assert t.apply_es_fr_tense("I said, he went").endswith("he went")
