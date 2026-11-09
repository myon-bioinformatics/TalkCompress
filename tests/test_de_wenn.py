"""German ``wenn`` was adopted then reversed after AI round-trip failure (0/9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers import load

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "SentenceCalibratedMosaic/fixtures/zh_de_phrases.json").read_text(encoding="utf-8"))
WENN = next(e for e in BANK["examples_not_registered"] if e["id"] == "wenn")


def _t():
    return load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")


def _o200k():
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    return lambda s: (len(enc.encode(s)), len(s.encode("utf-8")))


def test_entry_moved_to_not_registered():
    assert WENN["to"] == "wenn" and WENN["lang"] == "de"
    assert set(WENN["from"]) == {"if and when", "when and if", "if or when", "when or if"}
    assert "0/9" in WENN["why_dropped"]
    assert all(e.get("id") != "wenn" for e in BANK["entries"])


@pytest.mark.parametrize("src", ["if and when", "when and if", "if or when", "when or if"])
def test_wenn_still_cheaper_on_o200k_but_not_applied(src):
    """Token win remains true; runtime no longer applies the reversed form."""
    m = _o200k()
    for pre in ("", " "):
        assert m(pre + "wenn") < m(pre + src)
        assert m(pre + "wenn")[0] < m(pre + src)[0]
    s = f"Call me {src} you arrive."
    assert _t().apply_zh_de_phrases(s) == s


@pytest.mark.parametrize("src", ["if", "when"])
def test_bare_if_when_not_adopted(src):
    m = _o200k()
    assert not m("wenn") < m(src)
    assert src not in WENN["from"]
    s = f"Call me {src} you arrive."
    assert _t().apply_zh_de_phrases(s) == s


def test_iff_untouched():
    assert "wenn" not in _t().apply_zh_de_phrases("x if and only if y")


def test_wenn_only_in_not_registered_of_zh_de():
    for p in (ROOT / "SentenceCalibratedMosaic/fixtures").glob("*.json"):
        txt = p.read_text(encoding="utf-8")
        if p.name == "zh_de_phrases.json":
            # id + to inside examples_not_registered; not in live entries
            assert txt.count('"wenn"') >= 2
            assert all(e.get("to") != "wenn" for e in BANK["entries"])
        elif p.name == "roundtrip.json":
            continue  # failure evidence retained
        else:
            assert '"wenn"' not in txt, p.name
