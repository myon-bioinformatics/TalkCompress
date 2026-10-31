"""shared.ledger: 規約の置換先はリテラル、that is 判定は ASCII のみの大小無視。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared import ledger as G  # noqa: E402


def _book(tmp_path: Path, src: str, to: str) -> Path:
    p = tmp_path / "conv.json"
    p.write_text(
        json.dumps(
            {"version": 1, "conventions": [
                {"id": "t", "kind": "lex", "apply_layer": "C", "from": [src], "to": to}
            ]}
        ),
        encoding="utf-8",
    )
    return p


@pytest.mark.parametrize("to", [r"C:\new\1x", r"\g<0>!", r"a\tb", "\\"])
def test_replace_src_literal(to: str) -> None:
    assert G._replace_src("see my path now", "my path", to) == f"see {to} now"


@pytest.mark.parametrize("to", [r"i\.e\.", r"\g<0>!"])
def test_appositive_that_is_literal(tmp_path: Path, to: str) -> None:
    out = G.apply_ledger_lex("the plan, that is, ours", _book(tmp_path, "that is", to))
    assert out == f"the plan, {to}, ours"


def test_appositive_ascii_only_case(tmp_path: Path) -> None:
    book = _book(tmp_path, "that is", "ie")
    assert G.apply_ledger_lex("the plan, THAT IS, ours", book) == "the plan, ie, ours"
    assert G.apply_ledger_lex("the plan, that ıs, ours", book) == "the plan, that ıs, ours"
    assert G.apply_ledger_lex("the plan, that iſ, ours", book) == "the plan, that iſ, ours"
