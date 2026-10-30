"""German ``wenn`` as the neutral if/when conjunction (zh_de_phrases, o200k_base measured)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers import load

ROOT = Path(__file__).resolve().parents[1]
BANK = json.loads((ROOT / "TesseraTalk/fixtures/zh_de_phrases.json").read_text(encoding="utf-8"))
WENN = next(e for e in BANK["entries"] if e["id"] == "wenn")


def _t():
    return load("tessera_talk", "TesseraTalk/tessera_talk.py")


def _o200k():
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    return lambda s: (len(enc.encode(s)), len(s.encode("utf-8")))


def test_entry_shape():
    assert WENN["to"] == "wenn" and WENN["lang"] == "de"
    assert set(WENN["from"]) == {"if and when", "when and if", "if or when", "when or if"}


@pytest.mark.parametrize("src", ["if and when", "when and if", "if or when", "when or if"])
def test_wenn_wins_on_o200k(src):
    m = _o200k()
    for pre in ("", " "):
        assert m(pre + "wenn") < m(pre + src)
        assert m(pre + "wenn")[0] < m(pre + src)[0]  # strictly fewer tokens


@pytest.mark.parametrize("src", ["if", "when"])
def test_bare_if_when_not_adopted(src):
    m = _o200k()
    assert not m("wenn") < m(src)  # if: 1/2 beats 1/4; when: 1/4 ties
    assert src not in WENN["from"]
    s = f"Call me {src} you arrive."
    assert _t().apply_zh_de_phrases(s) == s


@pytest.mark.parametrize("s,want", [
    ("Call me if and when you arrive.", "Call me wenn you arrive."),
    ("Tell me when or if it breaks.", "Tell me wenn it breaks."),
])
def test_runtime_applies_bank_to(s, want):
    out = _t().apply_zh_de_phrases(s)
    assert out == want and WENN["to"] in out.split()


def test_iff_untouched():
    assert "wenn" not in _t().apply_zh_de_phrases("x if and only if y")


def test_wenn_not_registered_elsewhere():
    for p in (ROOT / "TesseraTalk/fixtures").glob("*.json"):
        txt = p.read_text(encoding="utf-8")
        if p.name == "zh_de_phrases.json":
            assert txt.count('"wenn"') == 2  # id + to
        else:
            assert '"wenn"' not in txt, p.name
