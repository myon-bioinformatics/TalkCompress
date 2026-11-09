"""多言語つまみ食い (it / nl / el / la): Tatoeba 実文を final pass に通し、壊さず token を増やさない。

#161 (es/fr/pt/de/zh/ja/en) と重複しない言語のみ。文は Tatoeba (https://tatoeba.org) の実文で、
CC BY 2.0 FR (https://creativecommons.org/licenses/by/2.0/fr/)。各行の author / url が帰属先。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
NIBBLE = ROOT / "tests/fixtures/tatoeba_nibble.jsonl"
ROWS = [json.loads(x) for x in NIBBLE.read_text(encoding="utf-8").splitlines() if x.strip()]


def _t():
    return _load("tessera_talk", "TesseraTalk/tessera_talk.py")


def test_nibble_rows_licensed_and_attributed():
    assert {r["lang"] for r in ROWS} == {"it", "nl", "el", "la"}
    for r in ROWS:
        assert r["source"] == "Tatoeba" and r["license"] == "CC BY 2.0 FR"
        assert r["author"] and r["url"].startswith("https://tatoeba.org/sentences/show/")


@pytest.mark.parametrize("lang", ["it", "nl", "el", "la"])
def test_tatoeba_nibble_final_pass(lang):
    t = _t()
    texts = [r["text"] for r in ROWS if r["lang"] == lang]
    assert len(texts) == 3
    for s in texts:
        out = t.final_token_pass(s)
        assert out == s, (lang, s, out)  # EN-source banks must not touch non-EN text
        assert t.estimate_tokens(out) <= t.estimate_tokens(s), (lang, s, out)
