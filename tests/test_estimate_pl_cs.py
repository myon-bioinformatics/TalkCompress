import os
from pathlib import Path
import subprocess
import sys
import types

import pytest

from TesseraTalk.tessera_talk import estimate_tokens, _fallback_cost, _wclass

# Historical #108 author-reported o200k_base counts (2026-10-31), not
# independently remeasured by the offline tests below. Raw fitting evidence
# is not committed; these bounds are regression checks, not accuracy proof.
CASES = [
    ("Przepraszam, gdzie jest najbliższy przystanek autobusowy?", 18),
    ("Děkuji za pomoc, přijdu zítra.", 13),
    ("Zażółć gęślą jaźń.", 12),
    ("Příliš žluťoučký kůň úpěl ďábelské ódy.", 22),
]


def test_pl_cs_estimate_within_25_percent():
    for text, ref in CASES:
        est = estimate_tokens(text)
        assert abs(est - ref) <= max(2, ref // 4), (text, est, ref)


# #108's author-reported exceptions: no +1 for ı ğ ş İ đ. The reference
# counts are retained as history, not freshly verified tokenizer evidence.
TR_VI = [
    ("Bugün hava çok sıcak.", 6),
    ("yazılım", 3),
    ("başka", 2),
    ("Tôi muốn đi Hà Nội.", 7),
]


def test_tr_vi_not_overestimated():
    for text, ref in TR_VI:
        assert estimate_tokens(text) <= ref + 1, (text, estimate_tokens(text), ref)


def test_tr_vi_match_o200k():
    if os.environ.get("TALKCOMPRESS_RUN_TOKENIZER_CHECKS") != "1":
        pytest.skip("explicit tokenizer check only; may download encoding data")
    tiktoken = pytest.importorskip("tiktoken")
    e = tiktoken.get_encoding("o200k_base")
    for text, ref in TR_VI:
        assert len(e.encode(text)) == ref, text


@pytest.mark.parametrize("word,cost", [("œuvre", 3), ("āāāā", 5), ("ǐǐǐǐ", 5)])
def test_fallback_range_is_not_limited_to_polish_or_czech(word, cost):
    assert _wclass(word) == "s"
    assert _fallback_cost(word, {}) == cost


@pytest.mark.parametrize("letter", "ıİğĞşŞđĐ")
def test_reported_exception_letters_keep_legacy_fallback(letter):
    assert _wclass(letter) == "s"
    assert _fallback_cost(letter, {}) == 1


def test_length_table_and_existing_suffix_rules_take_precedence():
    word = "žluťoučký"
    table = {f"s{len(word)}": 3}
    assert _fallback_cost(word, table) == 3
    assert _fallback_cost(word, table, suffixes={word[-3:]: 1}) == 4
    assert _fallback_cost(word, table, suffixes={word[-3:]: 1},
                          floor={word[-3:]: 5}) == 5


def test_mixed_additional_range_keeps_existing_class_priority():
    # U+1E00–1EFF wins over class-s; do not silently stack both surcharges.
    assert _wclass("ěệ") == "v"
    assert _fallback_cost("ěệ", {}) == 2
    assert _fallback_cost("ascii", {}) == 2
    assert _fallback_cost("café", {}) == 1


def test_tokenizer_probe_requires_opt_in_before_import(tmp_path):
    code = """
import builtins, runpy, sys, types
import pytest
root, test_path = sys.argv[1:]
sys.path.insert(0, root)
def forbidden_encoding(*args, **kwargs):
    raise AssertionError('encoding requested without explicit opt-in')
# Model an installed dependency, so a missing-package skip cannot hide a lost guard.
sys.modules['tiktoken'] = types.SimpleNamespace(get_encoding=forbidden_encoding)
original_importorskip = pytest.importorskip
def guarded_importorskip(name, *args, **kwargs):
    if name == 'tiktoken':
        raise AssertionError('tokenizer imported without explicit opt-in')
    return original_importorskip(name, *args, **kwargs)
pytest.importorskip = guarded_importorskip
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] == 'tiktoken':
        raise AssertionError('tokenizer imported without explicit opt-in')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
test = runpy.run_path(test_path)['test_tr_vi_match_o200k']
try:
    test()
except pytest.skip.Exception:
    pass
else:
    raise AssertionError('manual tokenizer probe did not skip')
"""
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop("TALKCOMPRESS_RUN_TOKENIZER_CHECKS", None)
    result = subprocess.run([sys.executable, "-c", code, str(root), __file__],
                            cwd=tmp_path, env=env, capture_output=True,
                            text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_explicit_tokenizer_probe_wiring_with_fake_module(monkeypatch):
    calls = []
    class FakeEncoding:
        def encode(self, text):
            return [0] * dict(TR_VI)[text]
    def get_encoding(name):
        calls.append(name)
        return FakeEncoding()
    monkeypatch.setenv("TALKCOMPRESS_RUN_TOKENIZER_CHECKS", "1")
    monkeypatch.setitem(sys.modules, "tiktoken", types.SimpleNamespace(get_encoding=get_encoding))
    test_tr_vi_match_o200k()
    assert calls == ["o200k_base"]
