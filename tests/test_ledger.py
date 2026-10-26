"""ShorthandEdge (C) agreed-convention ledger: load + C-applied lex."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ledger_file_exists_and_loads():
    from shared.ledger import convention_ids, default_ledger_path, list_conventions, load_ledger

    path = default_ledger_path()
    assert path.is_file()
    assert path == ROOT / "ShorthandEdge" / "ledger" / "conventions.json"
    assert "ShorthandEdge" in str(path)
    assert "ConvoHub" not in str(path)
    assert "DispatchHub" not in str(path)
    assert not (ROOT / "DispatchHub" / "ledger").exists()
    assert not (ROOT / "ConvoHub").exists()
    data = load_ledger()
    assert data["version"] == 1
    assert "meta" in data
    assert data["meta"]["base_mix"] == ["en", "zh", "ja"]
    ids = convention_ids()
    assert "spatial-under" in ids
    assert "uneven-凹凸" in ids
    assert "policy-base-mix" in ids
    lex = list_conventions(kind="lex", apply_layer="C")
    assert any(c["id"] == "spatial-under" for c in lex)
    # E-tagged lex rows should be empty (all current lex is C)
    assert list_conventions(kind="lex", apply_layer="E") == []
    policy = list_conventions(kind="policy")
    assert len(policy) >= 1
    assert policy[0]["payload"]["prefer_short_alphabet_cognates"] is True


def test_ledger_lex_under_below_and_凹凸():
    from shared.ledger import apply_ledger_lex

    assert "下" in apply_ledger_lex("under the table")
    assert "under" not in apply_ledger_lex("under the table").lower()
    assert "下" in apply_ledger_lex("below average")
    assert "below" not in apply_ledger_lex("below average").lower()
    assert "上" in apply_ledger_lex("above zero")
    assert "上下" == apply_ledger_lex("up and down")
    assert "上下" == apply_ledger_lex("above and below")
    assert "凹凸" in apply_ledger_lex("デコボコな道")
    assert "凹凸" in apply_ledger_lex("bumpy road")
    assert "凹凸" in apply_ledger_lex("uneven surface")
    # do not mangle understand
    assert "understand" in apply_ledger_lex("I understand now").lower()


def test_shorthand_applies_ledger_under_and_凹凸():
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    out = s.compress("put it under the table")
    assert "下" in out
    assert "under" not in out.lower()

    out2 = s.compress("below average results")
    assert "下" in out2
    assert "below" not in out2.lower()

    out3 = s.compress("この道はデコボコだ")
    assert "凹凸" in out3
    assert "デコボコ" not in out3

    out4 = s.compress("bumpy path")
    assert "凹凸" in out4

    # opt-out
    kept = s.compress("under the table", ledger=False)
    assert "under" in kept.lower()


def test_morpho_does_not_apply_ledger_under():
    """E alone should leave under/凹凸 alone (C owns ledger lex)."""
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    out = m.compress("put it under the table", unique=False, etymon=False, counters=False)
    assert "under" in out.lower()
    assert "下" not in out

    out3 = m.compress("この道はデコボコだ", unique=False, etymon=False, counters=False)
    assert "デコボコ" in out3
    assert "凹凸" not in out3

