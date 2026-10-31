import os
import importlib.util
from pathlib import Path
import types

import pytest

from MorphoZip.morpho_zip import _CURLY_MERGE_WORDS, compress, normalize_quotes


def _manual_o200k():
    # Must precede even the import: get_encoding may obtain data over the network.
    if os.environ.get("TALKCOMPRESS_RUN_TOKENIZER_CHECKS") != "1":
        pytest.skip("manual tokenizer check; set TALKCOMPRESS_RUN_TOKENIZER_CHECKS=1 explicitly")
    return pytest.importorskip("tiktoken").get_encoding("o200k_base")


def test_line_start_merge_word_keeps_curly():
    assert normalize_quotes("“Well,” he said.") == "“Well,” he said."
    assert normalize_quotes("x\n“With it,” she said.") == "x\n“With it,” she said."


def test_after_space_or_other_word_goes_straight():
    assert normalize_quotes('He said “Well, ok”.') == 'He said "Well, ok".'
    assert normalize_quotes("“But no,” he said.") == '"But no," he said.'
    assert normalize_quotes("“Wellington” x") == '"Wellington" x'


def test_after_bracket_goes_straight():
    assert normalize_quotes("(“Well,” he said.)") == '("Well," he said.)'
    assert normalize_quotes("[“With it”]") == '["With it"]'


def test_after_bracket_straight_not_more_tokens():
    e = _manual_o200k()
    for src in ("(“Well,” he said.)", "[“With it”]"):
        assert len(e.encode(normalize_quotes(src))) <= len(e.encode(src)), src


def test_merge_word_table_matches_o200k():
    e = _manual_o200k()
    for w in _CURLY_MERGE_WORDS:
        assert len(e.encode("“" + w)) == 1 < len(e.encode('"' + w)), w


@pytest.mark.parametrize("word", [
    "Allāh", "Wellé", "Well\u1dc4", "Well\u0903", "Well\u20dd",
    "Well\U0001e000", "Well2", "Well_", "Well's", "Well’s", "Well猫",
])
def test_unicode_and_other_word_continuations_are_not_merge_words(word):
    assert normalize_quotes(f"“{word}”") == f'"{word}"'


@pytest.mark.parametrize("text,options,expected", [
    ("“Well, I know.”", {"strip": True}, '"I know."'),
    ("“One cat.”", {"spelled_nums": True}, '"1匹."'),
])
def test_final_pipeline_rechecks_changed_openers(text, options, expected):
    assert compress(text, **options) == expected


def test_unchanged_opener_stays_curly_after_pipeline():
    assert compress("“Well, I know.”") == "“Well, I know.”"


@pytest.mark.parametrize("wrapper", ["[[keep:{text}]]", "`keep:{text}`"])
def test_protected_quotes_remain_verbatim(wrapper):
    text = "“Wellé” ‘A’"
    assert compress(wrapper.format(text=text), strip=True) == text


def test_regex_protected_quotes_remain_verbatim():
    text = "“Wellé”"
    assert compress(text, protect_regexes=[r"“[^”]+”"]) == text


def test_quoted_a_and_romance_guards_survive():
    assert compress('Mark it “A” now.') == 'Mark it "A" now.'
    assert compress('“Il a un chat.”') == '"Il a un chat."'


def test_quote_audit_can_still_disable_both_normalization_passes():
    path = Path(__file__).resolve().parents[1] / "scripts/quote_roundtrip.py"
    spec = importlib.util.spec_from_file_location("quote_audit_fake_only", path)
    qr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(qr)
    # len is a fake counter, not a tokenizer/accuracy measurement.
    result = qr.check({"synthetic.txt": "“But no.”"}, qr.load_mz(), len)
    assert result["rows"]["curly"]["bytes"] > result["rows"]['Q""']["bytes"]


@pytest.mark.parametrize("setting", [None, "0", "true"])
def test_manual_check_requires_exact_opt_in_before_import(monkeypatch, setting):
    if setting is None:
        monkeypatch.delenv("TALKCOMPRESS_RUN_TOKENIZER_CHECKS", raising=False)
    else:
        monkeypatch.setenv("TALKCOMPRESS_RUN_TOKENIZER_CHECKS", setting)
    monkeypatch.setattr(pytest, "importorskip", lambda *a, **k: pytest.fail("tokenizer imported before opt-in"))
    with pytest.raises(pytest.skip.Exception):
        _manual_o200k()


def test_explicit_opt_in_wiring_uses_fake_tokenizer_only(monkeypatch):
    marker = object()
    calls = []
    monkeypatch.setenv("TALKCOMPRESS_RUN_TOKENIZER_CHECKS", "1")
    fake = types.SimpleNamespace(get_encoding=lambda name: (calls.append(name) or marker))
    monkeypatch.setattr(pytest, "importorskip", lambda name: fake)
    assert _manual_o200k() is marker
    assert calls == ["o200k_base"]


@pytest.mark.parametrize("probe", [
    test_after_bracket_straight_not_more_tokens, test_merge_word_table_matches_o200k,
])
def test_real_tokenizer_probes_skip_before_import_by_default(monkeypatch, probe):
    monkeypatch.delenv("TALKCOMPRESS_RUN_TOKENIZER_CHECKS", raising=False)
    monkeypatch.setattr(pytest, "importorskip", lambda *a, **k: pytest.fail("unexpected tokenizer import"))
    with pytest.raises(pytest.skip.Exception):
        probe()
