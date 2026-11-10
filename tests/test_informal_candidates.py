"""口語クリップ採点台帳（MorphoGrammarMinimal/fixtures/informal_candidates.json）の検証。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "MorphoGrammarMinimal/fixtures/informal_candidates.json").read_text(encoding="utf-8"))
BECAUSE_FAMILY = {"because", "cuz", "bc", "'cause", "cause", "cos", "coz", "becuz", "b/c", "∵"}
FOR_FAMILY = {"for", "4", "4r", "fo", "fer", "f"}
# meaning → (inventory, source, winner, extended canonicalize?)
WINNERS = {
    "because": ("conjunction", "because", "cuz", False),
    "for": ("preposition", "for", "for", False),
    "with": ("preposition", "with", "with", False),
    "without": ("prep2", "without", "无", False),
    "though": ("adverb", "though", "tho", False),
    "especially": ("adverb", "especially", "especially", False),
    "often": ("adverb", "often", "oft", True),
    "from": ("preposition", "from", "←", False),
    "at": ("preposition", "at", "@", False),
}


def _entry(meaning):
    return next(e for e in DATA["entries"] if e["meaning"] == meaning)


def _template(entry) -> str:
    return entry.get("sentence_template") or DATA["sentence_template"]


def test_measurements_match_official_estimator():
    tt = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    for e in DATA["entries"]:
        tpl = _template(e)
        for c in e["candidates"]:
            f = c["form"]
            sent = tpl.format(form=f)
            assert c["tokens"] == tt.estimate_tokens(f), f
            assert c["bytes"] == len(f.encode("utf-8")), f
            assert c["sentence_tokens"] == tt.estimate_tokens(sent), f


def test_measurements_match_tiktoken_o200k_base():
    """参照実測は tiktoken 0.14.0 の o200k_base。o200k_tokens は文中想定の先頭スペース付き。"""
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    for e in DATA["entries"]:
        tpl = _template(e)
        for c in e["candidates"]:
            f = c["form"]
            sent = tpl.format(form=f)
            assert "o200k_tokens" in c and "o200k_sentence_tokens" in c, f
            assert c["o200k_tokens"] == len(enc.encode(" " + f)), f
            assert c["o200k_sentence_tokens"] == len(enc.encode(sent)), f


def test_every_non_winner_has_reject_and_winner_is_cheapest_o200k():
    for e in DATA["entries"]:
        forms = {c["form"]: c for c in e["candidates"]}
        assert e["winner"] in forms and e["source"] in forms
        assert forms[e["winner"]]["reject"] is None
        for f, c in forms.items():
            if f != e["winner"]:
                assert c["reject"], f"{e['meaning']}: {f} lacks reject reason"
        # 第一指標は o200k 文中トークン（公式推定とずれる場合がある）
        assert forms[e["winner"]]["o200k_tokens"] == min(c["o200k_tokens"] for c in forms.values())


def test_because_family_all_scored_and_winner_cuz():
    e = _entry("because")
    assert e["winner"] == "cuz"
    assert BECAUSE_FAMILY <= {c["form"] for c in e["candidates"]}


def test_for_family_all_scored_and_winner_for():
    e = _entry("for")
    assert e["winner"] == "for"
    assert FOR_FAMILY <= {c["form"] for c in e["candidates"]}
    four = next(c for c in e["candidates"] if c["form"] == "4")
    # 公式推定は見逃すが、o200k 文中では token loser
    assert four["tokens"] == 1 and four["o200k_tokens"] == 2


def test_ai_readability_is_unmeasured():
    assert DATA["ai_readability"] == "未測定"
    for e in DATA["entries"]:
        assert e["ai_readability"] == "未測定", e["meaning"]


def test_winner_matches_engine_and_legacy_aliases():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    e = _entry("because")
    assert e["winner"] in m.CONJ_CANONICAL
    out = m.compress("We left because it rained.", unique=False, etymon=False)
    assert "cuz" in out.split() and "bc" not in out.split() and "because" not in out
    for src in ("because", "cuz", "bc", "∵"):
        assert m.canonicalize_closed("conjunction", src) == "cuz", src


def test_scored_winners_match_current_emit_without_changing_it():
    """採点の勝者は現行 emit と一致すること（この PR は emit を変えない）。"""
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    sentences = {
        "because": "We left because it rained.",
        "for": "This is for lunch.",
        "with": "I went with them.",
        "without": "I left without them.",
        "though": "We left though it rained.",
        "especially": "I like tea, especially green tea.",
        "often": "We often leave early.",
        "from": "We came from home.",
        "at": "Meet me at noon.",
    }
    for meaning, (inv, source, winner, extended) in WINNERS.items():
        e = _entry(meaning)
        assert e["winner"] == winner and e["source"] == source
        out = m.compress(sentences[meaning], unique=False, etymon=False)
        # 語境界: 句読点に隣接しても winner が表層に残ること
        assert winner in out.split() or winner in out, (meaning, out)
        if source != winner:
            # 原形は勝者へ畳まれる（とくに 1 トークン語が残渣になりにくいこと）
            tokens = out.split()
            assert source not in tokens, (meaning, out)
        assert m.canonicalize_closed(inv, source, extended=extended) == winner
        assert m.canonicalize_closed(inv, winner, extended=extended) == winner


def test_ledger_because_row_points_at_winner():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    led = json.loads((ROOT / "ShorthandSessionEdge/ledger/conventions.json").read_text(encoding="utf-8"))
    row = next(c for c in led["conventions"] if c["id"] == "e-conj-because")
    assert row["to"] == _entry("because")["winner"]
    for a in row["input_aliases"]:
        assert m.canonicalize_closed("conjunction", a) == row["to"]
    # ∵ は展開側で whereas に割り当て済み（既存仕様）なので、展開検証は cuz / 旧 bc のみ
    for a in ("cuz", "bc"):
        assert m.expand(a) == "because"
