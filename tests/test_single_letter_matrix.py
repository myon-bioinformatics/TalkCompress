"""大文字1文字 A–Z × 例文の型 × 全経路の総当たり（手選びの例なし）。"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("sla", ROOT / "scripts/single_letter_audit.py")
sla = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sla)

CASES = [
    (t, L, p)
    for t, _ in sla.TEMPLATES
    for L in sla.LETTERS
    for p in sla.PIPES
    if (L, t) not in sla.EXEMPT
]
TPL = dict(sla.TEMPLATES)


@pytest.mark.parametrize(("tname", "letter", "pipe"), CASES)
def test_single_capital_survives(tname, letter, pipe):
    ok, got = sla.check(letter, TPL[tname], sla.PIPES[pipe])
    assert ok, got


@pytest.mark.parametrize(("letter", "tname"), sorted(sla.EXEMPT))
def test_exempt_is_dropped_article(letter, tname):
    # 除外一覧は「意図的に落とす」ことの確認（一覧が空洞化しないように）
    got = sla.PIPES["MorphoZip"](TPL[tname].replace("_", letter))
    assert sla.standalone_count(letter, got) == 0, got


def test_exempt_list_is_only_article_a():
    assert {L for L, _ in sla.EXEMPT} == {"A"}
