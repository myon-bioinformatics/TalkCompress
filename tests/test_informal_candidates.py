"""口語クリップ採点台帳（MorphoGrammarMinimal/fixtures/informal_candidates.json）の検証。"""

from __future__ import annotations

import json
from pathlib import Path

from tests._helpers import load as _load

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "MorphoGrammarMinimal/fixtures/informal_candidates.json").read_text(encoding="utf-8"))
BECAUSE_FAMILY = {"because", "cuz", "bc", "'cause", "cause", "cos", "coz", "becuz", "b/c", "∵"}


def _entry(meaning):
    return next(e for e in DATA["entries"] if e["meaning"] == meaning)


def test_measurements_match_official_estimator():
    tt = _load("sentence_calibrated_mosaic", "SentenceCalibratedMosaic/sentence_calibrated_mosaic.py")
    tpl = DATA["sentence_template"]
    for e in DATA["entries"]:
        for c in e["candidates"]:
            f = c["form"]
            assert c["tokens"] == tt.estimate_tokens(f), f
            assert c["bytes"] == len(f.encode("utf-8")), f
            assert c["sentence_tokens"] == tt.estimate_tokens(tpl.format(form=f)), f


def test_every_non_winner_has_reject_and_winner_is_cheapest_token():
    for e in DATA["entries"]:
        forms = {c["form"]: c for c in e["candidates"]}
        assert e["winner"] in forms and e["source"] in forms
        assert forms[e["winner"]]["reject"] is None
        for f, c in forms.items():
            if f != e["winner"]:
                assert c["reject"], f"{e['meaning']}: {f} lacks reject reason"
        assert forms[e["winner"]]["tokens"] == min(c["tokens"] for c in forms.values())


def test_because_family_all_scored_and_winner_cuz():
    e = _entry("because")
    assert e["winner"] == "cuz"
    assert BECAUSE_FAMILY <= {c["form"] for c in e["candidates"]}


def test_winner_matches_engine_and_legacy_aliases():
    m = _load("morpho_grammar_minimal", "MorphoGrammarMinimal/morpho_grammar_minimal.py")
    e = _entry("because")
    assert e["winner"] in m.CONJ_CANONICAL
    out = m.compress("We left because it rained.", unique=False, etymon=False)
    assert "cuz" in out.split() and "bc" not in out.split() and "because" not in out
    for src in ("because", "cuz", "bc", "∵"):
        assert m.canonicalize_closed("conjunction", src) == "cuz", src


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
