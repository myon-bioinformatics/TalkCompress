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


def _ns(**kwargs):
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    defaults = dict(
        key=None,
        key_file=None,
        langs=None,
        state=None,
        stats=False,
        mode="compress",
        aad="",
        lexicon=None,
        export_lexicon=None,
        no_rle=False,
        preserve_newlines=False,
        prefer_ltr=False,
        strip=False,
        no_strip=False,
        no_unique=False,
        no_etymon=False,
        no_counters=False,
        aggressive_fillers=False,
        hex_nums=False,
        hex_bare=False,
        file=None,
        out=None,
        text=None,
        pipeline=None,
        auto_machine=False,
        lex_policy=None,
        trace=False,
        jsonl=False,
        window=None,
        keep_system=False,
        pack=None,
        protect_regex=None,
        min_ratio=None,
        allow_weak=False,
        max_loss_tokens=None,
        strict_loss=False,
        budget=None,
        role_layers=None,
        auto=False,
        layer=None,
        compare=False,
        keep_articles=False,
        spelled_nums=False,
        rule_state=None,
    )
    defaults.update(kwargs)
    return c.argparse.Namespace(**defaults)


def test_ledger_file_exists_and_loads():
    from shared.ledger import convention_ids, default_ledger_path, list_conventions, load_ledger

    path = default_ledger_path()
    assert path.is_file()
    assert "ShorthandEdge" in str(path)
    assert "ConvoHub" not in str(path)
    assert "DispatchHub" not in str(path)
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


def test_classic_matrix_still_holds_with_ledger():
    """Regression: I'll/nums/ledger on C; ℹ️ on E."""
    m = _load("morpho_zip", "MorphoZip/morpho_zip.py")
    s = _load("shorthand_edge", "ShorthandEdge/shorthand_edge.py")
    c = _load("dispatch_hub", "DispatchHub/dispatch_hub.py")
    classic = "um 私は will find out the information about three animals"

    from shared.lex_policy import INFO_GLYPH

    e_out = m.compress(classic)
    assert "um" in e_out.lower()
    assert "ascertain" in e_out.lower()
    assert "ascrt" not in e_out.lower()
    assert INFO_GLYPH in e_out
    assert "I'll" not in e_out
    assert "three" in e_out.lower()
    assert "3匹" not in e_out

    c_out = s.compress(classic)
    assert "um" not in c_out.lower()
    assert "ascrt" in c_out.lower()
    assert "I'll" in c_out
    assert "3" in c_out
    assert INFO_GLYPH not in c_out

    pipe = c.run_pipeline(["C", "E"], classic, _ns())
    assert "um" not in pipe.lower()
    assert "ascrt" in pipe.lower()
    assert "3匹" in pipe
    assert INFO_GLYPH in pipe
    assert "I'll" in pipe
    assert pipe == "I'll ascrt ℹ️ about 3匹" or (
        "I'll" in pipe and "ascrt" in pipe.lower() and INFO_GLYPH in pipe and "3匹" in pipe
    )


def test_d_does_not_own_ledger_path():
    from shared.ledger import default_ledger_path

    path = default_ledger_path()
    assert path == ROOT / "ShorthandEdge" / "ledger" / "conventions.json"
    assert not (ROOT / "DispatchHub" / "ledger").exists()
    assert not (ROOT / "ConvoHub").exists()
